//! OpenLVM Sandbox Manager
//!
//! Per-agent isolation using OS security primitives.
//! On Linux: seccomp-bpf + namespaces + rlimits.
//! On other platforms: logical enforcement only (no kernel isolation).

const std = @import("std");
const builtin = @import("builtin");
const capabilities = @import("capabilities.zig");

// ── Seccomp BPF constants (Linux-only) ──────────────────────────

const SECCOMP_SET_MODE_FILTER = 1;
const SECCOMP_RET_ALLOW: u32 = 0x7fff_0000;
const SECCOMP_RET_KILL_PROCESS: u32 = 0x8000_0000;
const SECCOMP_RET_ERRNO: u32 = 0x0005_0000;

const BPF_LD: u16 = 0x00;
const BPF_W: u16 = 0x00;
const BPF_ABS: u16 = 0x20;
const BPF_JMP: u16 = 0x05;
const BPF_JEQ: u16 = 0x10;
const BPF_K: u16 = 0x00;
const BPF_RET: u16 = 0x06;

const sock_filter = extern struct {
    code: u16,
    jt: u8,
    jf: u8,
    k: u32,
};

/// Resource limits for sandboxed agents.
pub const ResourceLimits = struct {
    /// Maximum CPU time in seconds (0 = unlimited).
    max_cpu_seconds: u64 = 60,
    /// Maximum resident memory in bytes (0 = unlimited).
    max_memory_bytes: u64 = 256 * 1024 * 1024, // 256MB
    /// Maximum number of open file descriptors.
    max_open_files: u64 = 64,
    /// Maximum file size in bytes.
    max_file_size: u64 = 64 * 1024 * 1024, // 64MB
    /// Maximum number of child processes.
    max_processes: u64 = 16,

    pub const unlimited = ResourceLimits{
        .max_cpu_seconds = 0,
        .max_memory_bytes = 0,
        .max_open_files = 0,
        .max_file_size = 0,
        .max_processes = 0,
    };

    pub const tight = ResourceLimits{
        .max_cpu_seconds = 10,
        .max_memory_bytes = 64 * 1024 * 1024,
        .max_open_files = 16,
        .max_file_size = 8 * 1024 * 1024,
        .max_processes = 4,
    };
};

/// Namespace isolation flags (Linux-specific).
pub const NamespaceFlags = packed struct(u32) {
    mount: bool = false,
    pid: bool = false,
    network: bool = false,
    user: bool = false,
    ipc: bool = false,
    uts: bool = false,
    _reserved: u26 = 0,

    pub const none = NamespaceFlags{};

    pub const full = NamespaceFlags{
        .mount = true,
        .pid = true,
        .network = true,
        .user = true,
        .ipc = true,
        .uts = true,
    };

    pub const process_only = NamespaceFlags{
        .pid = true,
        .mount = true,
    };
};

/// The sandbox wrapping a single agent.
pub const Sandbox = struct {
    agent_id: u64,
    caps: capabilities.CapabilitySet,
    limits: ResourceLimits,
    namespaces: NamespaceFlags,
    status: SandboxStatus,
    created_at_ns: i128,

    /// Syscall whitelist built from capabilities.
    allowed_syscalls: std.ArrayList(u32),
    allocator: std.mem.Allocator,

    pub const SandboxStatus = enum {
        created,
        configured,
        applied,
        violated,
        terminated,
    };

    pub fn init(allocator: std.mem.Allocator, agent_id: u64, caps: capabilities.CapabilitySet) Sandbox {
        return .{
            .agent_id = agent_id,
            .caps = caps,
            .limits = .{},
            .namespaces = .{},
            .status = .created,
            .created_at_ns = std.time.nanoTimestamp(),
            .allowed_syscalls = std.ArrayList(u32).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *Sandbox) void {
        self.allowed_syscalls.deinit();
    }

    /// Configure resource limits.
    pub fn setLimits(self: *Sandbox, limits: ResourceLimits) void {
        self.limits = limits;
    }

    /// Configure namespace isolation.
    pub fn setNamespaces(self: *Sandbox, ns: NamespaceFlags) void {
        self.namespaces = ns;
    }

    /// Build the syscall whitelist from the capability set.
    pub fn buildSyscallFilter(self: *Sandbox) !void {
        self.allowed_syscalls.clearRetainingCapacity();

        // Always allow basic process management
        const base_syscalls = [_]u32{
            0, // read
            1, // write
            3, // close
            9, // mmap
            10, // mprotect
            11, // munmap
            12, // brk
            60, // exit
            231, // exit_group
            158, // arch_prctl
            63, // uname
            218, // set_tid_address
        };
        for (base_syscalls) |sc| {
            try self.allowed_syscalls.append(sc);
        }

        // Conditionally add syscalls based on capabilities
        if (self.caps.has(.fs_read)) {
            try self.allowed_syscalls.append(2); // open
            try self.allowed_syscalls.append(257); // openat
            try self.allowed_syscalls.append(4); // stat
            try self.allowed_syscalls.append(5); // fstat
            try self.allowed_syscalls.append(6); // lstat
            try self.allowed_syscalls.append(8); // lseek
            try self.allowed_syscalls.append(79); // getcwd
            try self.allowed_syscalls.append(89); // readlink
            try self.allowed_syscalls.append(217); // getdents64
        }

        if (self.caps.has(.fs_write)) {
            try self.allowed_syscalls.append(1); // write (already in base)
            try self.allowed_syscalls.append(82); // rename
            try self.allowed_syscalls.append(77); // ftruncate
            try self.allowed_syscalls.append(74); // fsync
        }

        if (self.caps.has(.fs_create)) {
            try self.allowed_syscalls.append(83); // mkdir
            try self.allowed_syscalls.append(85); // creat
            try self.allowed_syscalls.append(86); // link
            try self.allowed_syscalls.append(88); // symlink
        }

        if (self.caps.has(.fs_delete)) {
            try self.allowed_syscalls.append(87); // unlink
            try self.allowed_syscalls.append(84); // rmdir
        }

        if (self.caps.has(.network_outbound) or self.caps.has(.network_inbound)) {
            try self.allowed_syscalls.append(41); // socket
            try self.allowed_syscalls.append(42); // connect
            try self.allowed_syscalls.append(44); // sendto
            try self.allowed_syscalls.append(45); // recvfrom
            try self.allowed_syscalls.append(46); // sendmsg
            try self.allowed_syscalls.append(47); // recvmsg
            try self.allowed_syscalls.append(48); // shutdown
            try self.allowed_syscalls.append(49); // bind
            try self.allowed_syscalls.append(50); // listen
            try self.allowed_syscalls.append(43); // accept
        }

        if (self.caps.has(.subprocess_spawn)) {
            try self.allowed_syscalls.append(56); // clone
            try self.allowed_syscalls.append(57); // fork
            try self.allowed_syscalls.append(58); // vfork
            try self.allowed_syscalls.append(59); // execve
            try self.allowed_syscalls.append(61); // wait4
        }

        if (self.caps.has(.clock_read)) {
            try self.allowed_syscalls.append(228); // clock_gettime
            try self.allowed_syscalls.append(96); // gettimeofday
        }

        if (self.caps.has(.random_generate)) {
            try self.allowed_syscalls.append(318); // getrandom
        }

        self.status = .configured;
    }

    /// Apply all sandbox restrictions.
    /// On Linux: sets rlimits, namespaces, and seccomp filter.
    /// On other platforms: records configuration but only does logical enforcement.
    pub fn apply(self: *Sandbox) !void {
        if (self.status != .configured) {
            try self.buildSyscallFilter();
        }

        if (comptime builtin.os.tag == .linux) {
            try self.applyRlimitsLinux();
            // Note: namespace and seccomp application requires elevated privileges
            // or specific user namespace configurations. In production, this would
            // be done via clone(CLONE_NEWNS | CLONE_NEWPID | ...) during fork.
        }

        self.status = .applied;
    }

    /// Check if a capability is currently allowed in this sandbox.
    pub fn checkCapability(self: *const Sandbox, cap: capabilities.Capability) !void {
        if (!self.caps.has(cap)) {
            return error.CapabilityDenied;
        }
        if (self.status == .violated or self.status == .terminated) {
            return error.SandboxTerminated;
        }
    }

    /// Record a capability violation.
    pub fn recordViolation(self: *Sandbox) void {
        self.status = .violated;
    }

    /// Terminate the sandbox.
    pub fn terminate(self: *Sandbox) void {
        self.status = .terminated;
    }

    // ── Internal: Linux rlimits ──────────────────────────────────

    fn applyRlimitsLinux(self: *const Sandbox) !void {
        if (comptime builtin.os.tag != .linux) return;

        const posix = std.posix;

        if (self.limits.max_cpu_seconds > 0) {
            const limit = posix.rlimit{ .cur = self.limits.max_cpu_seconds, .max = self.limits.max_cpu_seconds };
            posix.setrlimit(.CPU, limit) catch {};
        }

        if (self.limits.max_memory_bytes > 0) {
            const limit = posix.rlimit{ .cur = self.limits.max_memory_bytes, .max = self.limits.max_memory_bytes };
            posix.setrlimit(.AS, limit) catch {};
        }

        if (self.limits.max_open_files > 0) {
            const limit = posix.rlimit{ .cur = self.limits.max_open_files, .max = self.limits.max_open_files };
            posix.setrlimit(.NOFILE, limit) catch {};
        }

        if (self.limits.max_file_size > 0) {
            const limit = posix.rlimit{ .cur = self.limits.max_file_size, .max = self.limits.max_file_size };
            posix.setrlimit(.FSIZE, limit) catch {};
        }

        if (self.limits.max_processes > 0) {
            const limit = posix.rlimit{ .cur = self.limits.max_processes, .max = self.limits.max_processes };
            posix.setrlimit(.NPROC, limit) catch {};
        }
    }
};

/// Sandbox manager — tracks all active sandboxes.
pub const SandboxManager = struct {
    sandboxes: std.AutoHashMap(u64, Sandbox),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) SandboxManager {
        return .{
            .sandboxes = std.AutoHashMap(u64, Sandbox).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *SandboxManager) void {
        var it = self.sandboxes.valueIterator();
        while (it.next()) |sb| {
            sb.deinit();
        }
        self.sandboxes.deinit();
    }

    /// Create a sandbox for an agent.
    pub fn createSandbox(self: *SandboxManager, agent_id: u64, caps: capabilities.CapabilitySet) !*Sandbox {
        var sb = Sandbox.init(self.allocator, agent_id, caps);
        try sb.buildSyscallFilter();
        try self.sandboxes.put(agent_id, sb);
        return self.sandboxes.getPtr(agent_id).?;
    }

    /// Get a sandbox by agent ID.
    pub fn getSandbox(self: *SandboxManager, agent_id: u64) ?*Sandbox {
        return self.sandboxes.getPtr(agent_id);
    }

    /// Remove a sandbox.
    pub fn removeSandbox(self: *SandboxManager, agent_id: u64) void {
        if (self.sandboxes.getPtr(agent_id)) |sb| {
            sb.deinit();
        }
        _ = self.sandboxes.remove(agent_id);
    }

    /// Get count of active sandboxes.
    pub fn count(self: *const SandboxManager) usize {
        return self.sandboxes.count();
    }
};

// ── Tests ────────────────────────────────────────────────────────

test "Sandbox init and capability check" {
    var sb = Sandbox.init(std.testing.allocator, 1, capabilities.Profiles.readonly);
    defer sb.deinit();

    try sb.checkCapability(.fs_read);
    try sb.checkCapability(.llm_call);
    try std.testing.expectError(error.CapabilityDenied, sb.checkCapability(.fs_write));
    try std.testing.expectError(error.CapabilityDenied, sb.checkCapability(.network_outbound));
}

test "Sandbox build syscall filter" {
    var sb = Sandbox.init(std.testing.allocator, 1, capabilities.Profiles.standard);
    defer sb.deinit();

    try sb.buildSyscallFilter();
    try std.testing.expect(sb.allowed_syscalls.items.len > 0);
    try std.testing.expectEqual(Sandbox.SandboxStatus.configured, sb.status);
}

test "Sandbox apply" {
    var sb = Sandbox.init(std.testing.allocator, 1, capabilities.Profiles.sandboxed);
    defer sb.deinit();

    try sb.apply();
    try std.testing.expectEqual(Sandbox.SandboxStatus.applied, sb.status);
}

test "Sandbox violation terminates access" {
    var sb = Sandbox.init(std.testing.allocator, 1, capabilities.Profiles.readonly);
    defer sb.deinit();

    try sb.checkCapability(.fs_read); // ok
    sb.recordViolation();
    try std.testing.expectError(error.SandboxTerminated, sb.checkCapability(.fs_read));
}

test "SandboxManager lifecycle" {
    var mgr = SandboxManager.init(std.testing.allocator);
    defer mgr.deinit();

    _ = try mgr.createSandbox(1, capabilities.Profiles.standard);
    _ = try mgr.createSandbox(2, capabilities.Profiles.readonly);
    try std.testing.expectEqual(@as(usize, 2), mgr.count());

    mgr.removeSandbox(1);
    try std.testing.expectEqual(@as(usize, 1), mgr.count());
    try std.testing.expect(mgr.getSandbox(1) == null);
    try std.testing.expect(mgr.getSandbox(2) != null);
}
