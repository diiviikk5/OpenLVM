//! OpenLVM Snapshot Manager
//!
//! Serializes and restores full agent state for deterministic replay
//! and checkpoint/restore workflows.

const std = @import("std");
const capabilities = @import("capabilities.zig");
const ManagedArrayList = std.array_list.Managed;

/// Unique identifier for a snapshot.
pub const SnapshotId = u64;

/// Serialized agent state.
pub const Snapshot = struct {
    id: SnapshotId,
    agent_id: u64,
    capabilities: capabilities.CapabilitySet,
    created_at_ns: i128,
    parent_snapshot_id: ?SnapshotId,

    // Metadata
    label: ?[]const u8,
    memory_used: usize,
    fork_count: u32,

    // Serialized data references
    data_offset: usize,
    data_len: usize,
};

/// Snapshot storage backend.
pub const SnapshotStore = struct {
    snapshots: std.AutoHashMap(SnapshotId, Snapshot),
    data_buffer: ManagedArrayList(u8),
    next_id: SnapshotId,
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) SnapshotStore {
        return SnapshotStore{
            .snapshots = std.AutoHashMap(SnapshotId, Snapshot).init(allocator),
            .data_buffer = ManagedArrayList(u8).init(allocator),
            .next_id = 1,
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *SnapshotStore) void {
        var it = self.snapshots.valueIterator();
        while (it.next()) |snap| {
            if (snap.label) |label| {
                self.allocator.free(label);
            }
        }
        self.snapshots.deinit();
        self.data_buffer.deinit();
    }

    /// Create a snapshot of current agent state.
    pub fn createSnapshot(
        self: *SnapshotStore,
        agent_id: u64,
        caps: capabilities.CapabilitySet,
        state_data: []const u8,
        label: ?[]const u8,
    ) !SnapshotId {
        const id = self.next_id;
        self.next_id += 1;

        const data_offset = self.data_buffer.items.len;
        try self.data_buffer.appendSlice(state_data);

        // Duplicate label if provided
        const owned_label = if (label) |l| blk: {
            const dup = try self.allocator.alloc(u8, l.len);
            @memcpy(dup, l);
            break :blk dup;
        } else null;

        const snap = Snapshot{
            .id = id,
            .agent_id = agent_id,
            .capabilities = caps,
            .created_at_ns = std.time.nanoTimestamp(),
            .parent_snapshot_id = null,
            .label = owned_label,
            .memory_used = state_data.len,
            .fork_count = 0,
            .data_offset = data_offset,
            .data_len = state_data.len,
        };

        try self.snapshots.put(id, snap);
        return id;
    }

    /// Get a snapshot by ID.
    pub fn getSnapshot(self: *SnapshotStore, id: SnapshotId) ?Snapshot {
        return self.snapshots.get(id);
    }

    /// Get the raw state data for a snapshot.
    pub fn getSnapshotData(self: *SnapshotStore, id: SnapshotId) ?[]const u8 {
        const snap = self.snapshots.get(id) orelse return null;
        if (snap.data_offset + snap.data_len > self.data_buffer.items.len) return null;
        return self.data_buffer.items[snap.data_offset..][0..snap.data_len];
    }

    /// Delete a snapshot.
    pub fn deleteSnapshot(self: *SnapshotStore, id: SnapshotId) !void {
        const snap = self.snapshots.get(id) orelse return error.SnapshotNotFound;
        if (snap.label) |label| {
            self.allocator.free(label);
        }
        _ = self.snapshots.remove(id);
    }

    /// List all snapshot IDs.
    pub fn listSnapshots(self: *SnapshotStore) ![]SnapshotId {
        var ids = try self.allocator.alloc(SnapshotId, self.snapshots.count());
        var i: usize = 0;
        var it = self.snapshots.keyIterator();
        while (it.next()) |key| {
            ids[i] = key.*;
            i += 1;
        }
        return ids[0..i];
    }

    /// Get total number of snapshots.
    pub fn count(self: *const SnapshotStore) usize {
        return self.snapshots.count();
    }

    /// Get total bytes stored.
    pub fn totalBytes(self: *const SnapshotStore) usize {
        return self.data_buffer.items.len;
    }
};

// ── Tests ────────────────────────────────────────────────────────

test "SnapshotStore create and retrieve" {
    var store = SnapshotStore.init(std.testing.allocator);
    defer store.deinit();

    const state_data = "test agent state data";
    const id = try store.createSnapshot(
        1, // agent_id
        capabilities.Profiles.standard,
        state_data,
        "test-snapshot",
    );

    try std.testing.expectEqual(@as(SnapshotId, 1), id);
    try std.testing.expectEqual(@as(usize, 1), store.count());

    const snap = store.getSnapshot(id).?;
    try std.testing.expectEqual(@as(u64, 1), snap.agent_id);

    const data = store.getSnapshotData(id).?;
    try std.testing.expectEqualStrings(state_data, data);
}

test "SnapshotStore multiple snapshots" {
    var store = SnapshotStore.init(std.testing.allocator);
    defer store.deinit();

    _ = try store.createSnapshot(1, capabilities.Profiles.readonly, "state1", null);
    _ = try store.createSnapshot(2, capabilities.Profiles.standard, "state2", null);
    _ = try store.createSnapshot(3, capabilities.Profiles.privileged, "state3", null);

    try std.testing.expectEqual(@as(usize, 3), store.count());

    const ids = try store.listSnapshots();
    defer std.testing.allocator.free(ids);
    try std.testing.expectEqual(@as(usize, 3), ids.len);
}

test "SnapshotStore delete" {
    var store = SnapshotStore.init(std.testing.allocator);
    defer store.deinit();

    const id = try store.createSnapshot(1, capabilities.Profiles.standard, "data", "to-delete");
    try std.testing.expectEqual(@as(usize, 1), store.count());

    try store.deleteSnapshot(id);
    try std.testing.expectEqual(@as(usize, 0), store.count());
    try std.testing.expectEqual(@as(?Snapshot, null), store.getSnapshot(id));
}
