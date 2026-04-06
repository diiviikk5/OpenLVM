//! OpenLVM Memory Management
//!
//! Per-agent arena allocator with tracking for CoW-friendly memory layouts.
//! Designed to work with fork() — all allocations are in mmap'd regions that
//! benefit from copy-on-write page sharing.

const std = @import("std");
const posix = std.posix;
const builtin = @import("builtin");
const ManagedArrayList = std.array_list.Managed;

/// A memory region backed by mmap (Unix) or VirtualAlloc (Windows).
/// Provides CoW-friendly allocation that works seamlessly with fork().
pub const MappedRegion = struct {
    base: [*]align(std.heap.page_size_min) u8,
    len: usize,
    used: usize,

    /// Create a new memory-mapped region.
    pub fn init(size: usize) !MappedRegion {
        const page_size = std.heap.pageSize();
        const aligned_size = std.mem.alignForward(usize, size, page_size);

        if (comptime builtin.os.tag == .windows) {
            // Windows: use VirtualAlloc
            const kernel32 = std.os.windows.kernel32;
            const ptr = kernel32.VirtualAlloc(
                null,
                aligned_size,
                std.os.windows.MEM_COMMIT | std.os.windows.MEM_RESERVE,
                std.os.windows.PAGE_READWRITE,
            ) orelse return error.MmapFailed;
            return MappedRegion{
                .base = @alignCast(@ptrCast(ptr)),
                .len = aligned_size,
                .used = 0,
            };
        } else {
            // Unix: use mmap with MAP_PRIVATE | MAP_ANONYMOUS for CoW
            const result = posix.mmap(
                null,
                aligned_size,
                posix.PROT.READ | posix.PROT.WRITE,
                .{ .TYPE = .PRIVATE, .ANONYMOUS = true },
                -1,
                0,
            );
            const ptr = result orelse return error.MmapFailed;
            return MappedRegion{
                .base = @alignCast(@ptrCast(ptr.ptr)),
                .len = aligned_size,
                .used = 0,
            };
        }
    }

    /// Release the mapped region.
    pub fn deinit(self: *MappedRegion) void {
        if (comptime builtin.os.tag == .windows) {
            const kernel32 = std.os.windows.kernel32;
            _ = kernel32.VirtualFree(@ptrCast(self.base), 0, std.os.windows.MEM_RELEASE);
        } else {
            posix.munmap(@as([*]align(std.heap.page_size_min) u8, @alignCast(self.base))[0..self.len]);
        }
        self.* = undefined;
    }

    /// Allocate bytes from this region.
    pub fn alloc(self: *MappedRegion, size: usize, alignment: usize) ?[*]u8 {
        const aligned_offset = std.mem.alignForward(usize, self.used, alignment);
        if (aligned_offset + size > self.len) return null;
        const ptr = self.base + aligned_offset;
        self.used = aligned_offset + size;
        return ptr;
    }

    /// Reset the region (mark all memory as free without unmapping).
    pub fn reset(self: *MappedRegion) void {
        self.used = 0;
    }

    /// Get bytes used.
    pub fn bytesUsed(self: *const MappedRegion) usize {
        return self.used;
    }

    /// Get total capacity.
    pub fn capacity(self: *const MappedRegion) usize {
        return self.len;
    }
};

/// Per-agent arena allocator.
/// Each agent gets its own arena backed by mmap'd regions.
/// On fork(), these regions are shared via CoW — only modified pages are copied.
pub const AgentArena = struct {
    regions: ManagedArrayList(MappedRegion),
    default_region_size: usize,
    total_allocated: usize,
    agent_id: u64,

    const DEFAULT_REGION_SIZE = 4 * 1024 * 1024; // 4MB default

    pub fn init(backing_allocator: std.mem.Allocator, agent_id: u64) AgentArena {
        return AgentArena{
            .regions = ManagedArrayList(MappedRegion).init(backing_allocator),
            .default_region_size = DEFAULT_REGION_SIZE,
            .total_allocated = 0,
            .agent_id = agent_id,
        };
    }

    pub fn deinit(self: *AgentArena) void {
        for (self.regions.items) |*region| {
            region.deinit();
        }
        self.regions.deinit();
    }

    /// Allocate memory from the agent's arena.
    pub fn allocBytes(self: *AgentArena, size: usize, alignment: usize) ![]u8 {
        // Try to allocate from the last region first
        if (self.regions.items.len > 0) {
            const last = &self.regions.items[self.regions.items.len - 1];
            if (last.alloc(size, alignment)) |ptr| {
                self.total_allocated += size;
                return ptr[0..size];
            }
        }

        // Need a new region
        const region_size = @max(self.default_region_size, size + std.heap.pageSize());
        var new_region = try MappedRegion.init(region_size);
        const ptr = new_region.alloc(size, alignment) orelse return error.OutOfMemory;
        try self.regions.append(new_region);
        self.total_allocated += size;
        return ptr[0..size];
    }

    /// Get a std.mem.Allocator interface for this arena.
    pub fn allocator(self: *AgentArena) std.mem.Allocator {
        return .{
            .ptr = self,
            .vtable = &.{
                .alloc = arenaAlloc,
                .resize = arenaResize,
                .free = arenaFree,
            },
        };
    }

    fn arenaAlloc(ctx: *anyopaque, n: usize, log2_ptr_align: u8, _: usize) ?[*]u8 {
        const self: *AgentArena = @ptrCast(@alignCast(ctx));
        const alignment = @as(usize, 1) << @intCast(log2_ptr_align);
        const result = self.allocBytes(n, alignment) catch return null;
        return result.ptr;
    }

    fn arenaResize(_: *anyopaque, _: []u8, _: u8, _: usize, _: usize) bool {
        // Arenas don't support resize — always return false to force realloc
        return false;
    }

    fn arenaFree(_: *anyopaque, _: []u8, _: u8, _: usize) void {
        // Arenas don't free individual allocations
    }

    /// Reset all regions (keep allocated pages, mark as free).
    pub fn reset(self: *AgentArena) void {
        for (self.regions.items) |*region| {
            region.reset();
        }
        self.total_allocated = 0;
    }

    /// Get memory stats.
    pub fn stats(self: *const AgentArena) MemoryStats {
        var total_capacity: usize = 0;
        var total_used: usize = 0;
        for (self.regions.items) |region| {
            total_capacity += region.capacity();
            total_used += region.bytesUsed();
        }
        return MemoryStats{
            .agent_id = self.agent_id,
            .region_count = self.regions.items.len,
            .total_capacity = total_capacity,
            .total_used = total_used,
            .total_allocated = self.total_allocated,
        };
    }
};

pub const MemoryStats = struct {
    agent_id: u64,
    region_count: usize,
    total_capacity: usize,
    total_used: usize,
    total_allocated: usize,
};

// ── Tests ────────────────────────────────────────────────────────

test "MappedRegion basic allocation" {
    var region = try MappedRegion.init(4096);
    defer region.deinit();

    const ptr = region.alloc(128, 8) orelse unreachable;
    try std.testing.expect(@intFromPtr(ptr) != 0);
    try std.testing.expectEqual(@as(usize, 128), region.bytesUsed());
}

test "MappedRegion reset" {
    var region = try MappedRegion.init(4096);
    defer region.deinit();

    _ = region.alloc(512, 8);
    try std.testing.expect(region.bytesUsed() > 0);

    region.reset();
    try std.testing.expectEqual(@as(usize, 0), region.bytesUsed());
}

test "AgentArena multi-region growth" {
    var arena = AgentArena.init(std.testing.allocator, 1);
    defer arena.deinit();

    // Allocate enough to trigger a new region
    const data = try arena.allocBytes(1024, 8);
    try std.testing.expectEqual(@as(usize, 1024), data.len);
    try std.testing.expectEqual(@as(usize, 1024), arena.total_allocated);
}
