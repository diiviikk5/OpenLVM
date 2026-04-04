//! OpenLVM Capability System
//!
//! Fine-grained, per-agent capability enforcement.
//! Capabilities are checked at comptime where possible and enforced at runtime
//! via seccomp-bpf filters and namespace restrictions.

const std = @import("std");

/// Bitmask of capabilities an agent is allowed to exercise.
/// Each bit corresponds to a specific system capability.
pub const CapabilitySet = packed struct(u64) {
    // ── Network ──
    network_outbound: bool = false,
    network_inbound: bool = false,
    network_dns: bool = false,

    // ── Filesystem ──
    fs_read: bool = true,
    fs_write: bool = false,
    fs_create: bool = false,
    fs_delete: bool = false,
    fs_exec: bool = false,

    // ── Process ──
    subprocess_spawn: bool = false,
    subprocess_signal: bool = false,

    // ── LLM / Tools ──
    llm_call: bool = true,
    tool_use: bool = true,
    tool_register: bool = false,

    // ── Shared State ──
    shared_memory_read: bool = true,
    shared_memory_write: bool = false,
    shared_db_read: bool = true,
    shared_db_write: bool = false,

    // ── System ──
    clock_read: bool = true,
    random_generate: bool = true,
    env_read: bool = false,
    env_write: bool = false,

    // ── OpenLVM Specific ──
    fork_self: bool = false,
    snapshot_create: bool = false,
    snapshot_restore: bool = false,
    replay_start: bool = false,

    // ── Reserved for future use ──
    _reserved: u38 = 0,

    /// Check if this capability set allows a specific action.
    pub fn has(self: CapabilitySet, cap: Capability) bool {
        return switch (cap) {
            .network_outbound => self.network_outbound,
            .network_inbound => self.network_inbound,
            .network_dns => self.network_dns,
            .fs_read => self.fs_read,
            .fs_write => self.fs_write,
            .fs_create => self.fs_create,
            .fs_delete => self.fs_delete,
            .fs_exec => self.fs_exec,
            .subprocess_spawn => self.subprocess_spawn,
            .subprocess_signal => self.subprocess_signal,
            .llm_call => self.llm_call,
            .tool_use => self.tool_use,
            .tool_register => self.tool_register,
            .shared_memory_read => self.shared_memory_read,
            .shared_memory_write => self.shared_memory_write,
            .shared_db_read => self.shared_db_read,
            .shared_db_write => self.shared_db_write,
            .clock_read => self.clock_read,
            .random_generate => self.random_generate,
            .env_read => self.env_read,
            .env_write => self.env_write,
            .fork_self => self.fork_self,
            .snapshot_create => self.snapshot_create,
            .snapshot_restore => self.snapshot_restore,
            .replay_start => self.replay_start,
        };
    }

    /// Require a capability — return error if not granted.
    pub fn require(self: CapabilitySet, cap: Capability) !void {
        if (!self.has(cap)) {
            return error.CapabilityDenied;
        }
    }

    /// Merge two capability sets (union).
    pub fn merge(self: CapabilitySet, other: CapabilitySet) CapabilitySet {
        const a: u64 = @bitCast(self);
        const b: u64 = @bitCast(other);
        return @bitCast(a | b);
    }

    /// Intersect two capability sets.
    pub fn intersect(self: CapabilitySet, other: CapabilitySet) CapabilitySet {
        const a: u64 = @bitCast(self);
        const b: u64 = @bitCast(other);
        return @bitCast(a & b);
    }

    /// Revoke specific capabilities (subtract).
    pub fn revoke(self: CapabilitySet, to_revoke: CapabilitySet) CapabilitySet {
        const a: u64 = @bitCast(self);
        const b: u64 = @bitCast(to_revoke);
        return @bitCast(a & ~b);
    }

    /// Serialize to u64 for FFI.
    pub fn toU64(self: CapabilitySet) u64 {
        return @bitCast(self);
    }

    /// Deserialize from u64 (from FFI).
    pub fn fromU64(val: u64) CapabilitySet {
        return @bitCast(val);
    }

    /// Count how many capabilities are granted.
    pub fn count(self: CapabilitySet) u32 {
        const val: u64 = @bitCast(self);
        // Mask out reserved bits
        const mask: u64 = (1 << 26) - 1;
        return @popCount(val & mask);
    }
};

/// Individual capability enum for runtime checks.
pub const Capability = enum(u6) {
    network_outbound = 0,
    network_inbound = 1,
    network_dns = 2,
    fs_read = 3,
    fs_write = 4,
    fs_create = 5,
    fs_delete = 6,
    fs_exec = 7,
    subprocess_spawn = 8,
    subprocess_signal = 9,
    llm_call = 10,
    tool_use = 11,
    tool_register = 12,
    shared_memory_read = 13,
    shared_memory_write = 14,
    shared_db_read = 15,
    shared_db_write = 16,
    clock_read = 17,
    random_generate = 18,
    env_read = 19,
    env_write = 20,
    fork_self = 21,
    snapshot_create = 22,
    snapshot_restore = 23,
    replay_start = 24,
};

/// Pre-built capability profiles for common agent roles.
pub const Profiles = struct {
    /// Read-only agent — can only read and call LLMs.
    pub const readonly = CapabilitySet{
        .fs_read = true,
        .llm_call = true,
        .tool_use = true,
        .shared_memory_read = true,
        .shared_db_read = true,
        .clock_read = true,
        .random_generate = true,
    };

    /// Standard agent — can read/write files and call LLMs.
    pub const standard = CapabilitySet{
        .fs_read = true,
        .fs_write = true,
        .fs_create = true,
        .llm_call = true,
        .tool_use = true,
        .tool_register = true,
        .shared_memory_read = true,
        .shared_memory_write = true,
        .shared_db_read = true,
        .shared_db_write = true,
        .clock_read = true,
        .random_generate = true,
    };

    /// Privileged agent — full network + process + FS access.
    pub const privileged = CapabilitySet{
        .network_outbound = true,
        .network_inbound = true,
        .network_dns = true,
        .fs_read = true,
        .fs_write = true,
        .fs_create = true,
        .fs_delete = true,
        .fs_exec = true,
        .subprocess_spawn = true,
        .subprocess_signal = true,
        .llm_call = true,
        .tool_use = true,
        .tool_register = true,
        .shared_memory_read = true,
        .shared_memory_write = true,
        .shared_db_read = true,
        .shared_db_write = true,
        .clock_read = true,
        .random_generate = true,
        .env_read = true,
        .env_write = true,
        .fork_self = true,
        .snapshot_create = true,
        .snapshot_restore = true,
        .replay_start = true,
    };

    /// Sandboxed agent — minimal capabilities for untrusted code.
    pub const sandboxed = CapabilitySet{
        .llm_call = true,
        .clock_read = true,
    };
};

// ── Tests ────────────────────────────────────────────────────────

test "CapabilitySet basic operations" {
    const caps = Profiles.readonly;
    try std.testing.expect(caps.has(.fs_read));
    try std.testing.expect(caps.has(.llm_call));
    try std.testing.expect(!caps.has(.fs_write));
    try std.testing.expect(!caps.has(.network_outbound));
}

test "CapabilitySet require" {
    const caps = Profiles.readonly;
    try caps.require(.fs_read); // should succeed
    try std.testing.expectError(error.CapabilityDenied, caps.require(.fs_write));
}

test "CapabilitySet merge" {
    const a = CapabilitySet{ .fs_read = true, .llm_call = true };
    const b = CapabilitySet{ .fs_write = true, .network_outbound = true };
    const merged = a.merge(b);
    try std.testing.expect(merged.has(.fs_read));
    try std.testing.expect(merged.has(.fs_write));
    try std.testing.expect(merged.has(.llm_call));
    try std.testing.expect(merged.has(.network_outbound));
}

test "CapabilitySet revoke" {
    const full = Profiles.privileged;
    const to_revoke = CapabilitySet{ .network_outbound = true, .subprocess_spawn = true };
    const restricted = full.revoke(to_revoke);
    try std.testing.expect(!restricted.has(.network_outbound));
    try std.testing.expect(!restricted.has(.subprocess_spawn));
    try std.testing.expect(restricted.has(.fs_read)); // still has other caps
}

test "CapabilitySet serialization roundtrip" {
    const original = Profiles.standard;
    const serialized = original.toU64();
    const deserialized = CapabilitySet.fromU64(serialized);
    try std.testing.expectEqual(original, deserialized);
}
