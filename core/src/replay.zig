//! OpenLVM Deterministic Replay Engine
//!
//! Records non-deterministic events during agent execution and replays
//! them verbatim to reproduce exact behavior.

const std = @import("std");
const snapshot_mod = @import("snapshot.zig");
const ManagedArrayList = std.array_list.Managed;

pub const EventType = enum(u8) {
    llm_request = 0,
    llm_response = 1,
    tool_call = 2,
    tool_result = 3,
    network_request = 4,
    network_response = 5,
    time_read = 6,
    random_generate = 7,
    file_read = 8,
    file_write = 9,
    env_read = 10,
    agent_message_send = 11,
    agent_message_recv = 12,
    user_input = 13,
    error_occurred = 14,
    checkpoint = 15,
};

pub const ReplayEvent = struct {
    sequence: u64,
    timestamp_ns: i128,
    event_type: EventType,
    agent_id: u64,
    data_offset: usize,
    data_len: usize,
    duration_ns: u64,
    correlation_id: ?u64,
};

pub const RecordingId = u64;

const RecordingStatus = enum { active, stopped, replaying };

const Recording = struct {
    id: RecordingId,
    agent_id: u64,
    start_snapshot: ?snapshot_mod.SnapshotId,
    events: ManagedArrayList(ReplayEvent),
    data_buffer: ManagedArrayList(u8),
    next_seq: u64,
    start_time_ns: i128,
    status: RecordingStatus,
};

pub const RecordingInfo = struct {
    id: RecordingId,
    agent_id: u64,
    event_count: usize,
    data_bytes: usize,
    start_time_ns: i128,
    status: RecordingStatus,
    start_snapshot: ?snapshot_mod.SnapshotId,
};

pub const ReplayCursor = struct {
    recording_id: RecordingId,
    current_index: usize,
    total_events: usize,
    engine: *ReplayEngine,

    pub fn next(self: *ReplayCursor) ?ReplayEvent {
        if (self.current_index >= self.total_events) return null;
        const events = self.engine.getEvents(self.recording_id) orelse return null;
        const event = events[self.current_index];
        self.current_index += 1;
        return event;
    }

    pub fn currentData(self: *ReplayCursor) ?[]const u8 {
        if (self.current_index == 0) return null;
        return self.engine.getEventData(self.recording_id, self.current_index - 1);
    }

    pub fn isDone(self: *const ReplayCursor) bool {
        return self.current_index >= self.total_events;
    }

    pub fn reset(self: *ReplayCursor) void {
        self.current_index = 0;
    }

    pub fn progress(self: *const ReplayCursor) f32 {
        if (self.total_events == 0) return 1.0;
        return @as(f32, @floatFromInt(self.current_index)) / @as(f32, @floatFromInt(self.total_events));
    }
};

pub const ReplayEngine = struct {
    recordings: std.AutoHashMap(RecordingId, Recording),
    next_id: RecordingId,
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) ReplayEngine {
        return .{
            .recordings = std.AutoHashMap(RecordingId, Recording).init(allocator),
            .next_id = 1,
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *ReplayEngine) void {
        var it = self.recordings.valueIterator();
        while (it.next()) |rec| {
            rec.events.deinit();
            rec.data_buffer.deinit();
        }
        self.recordings.deinit();
    }

    pub fn startRecording(self: *ReplayEngine, agent_id: u64, start_snapshot: ?snapshot_mod.SnapshotId) !RecordingId {
        const id = self.next_id;
        self.next_id += 1;
        try self.recordings.put(id, .{
            .id = id,
            .agent_id = agent_id,
            .start_snapshot = start_snapshot,
            .events = ManagedArrayList(ReplayEvent).init(self.allocator),
            .data_buffer = ManagedArrayList(u8).init(self.allocator),
            .next_seq = 0,
            .start_time_ns = std.time.nanoTimestamp(),
            .status = .active,
        });
        return id;
    }

    pub fn recordEvent(self: *ReplayEngine, recording_id: RecordingId, event_type: EventType, agent_id: u64, data: []const u8, duration_ns: u64, correlation_id: ?u64) !void {
        const rec = self.recordings.getPtr(recording_id) orelse return error.RecordingNotFound;
        if (rec.status != .active) return error.RecordingNotActive;
        const data_offset = rec.data_buffer.items.len;
        try rec.data_buffer.appendSlice(data);
        try rec.events.append(.{
            .sequence = rec.next_seq,
            .timestamp_ns = std.time.nanoTimestamp(),
            .event_type = event_type,
            .agent_id = agent_id,
            .data_offset = data_offset,
            .data_len = data.len,
            .duration_ns = duration_ns,
            .correlation_id = correlation_id,
        });
        rec.next_seq += 1;
    }

    pub fn stopRecording(self: *ReplayEngine, recording_id: RecordingId) !void {
        const rec = self.recordings.getPtr(recording_id) orelse return error.RecordingNotFound;
        rec.status = .stopped;
    }

    pub fn getEvents(self: *ReplayEngine, recording_id: RecordingId) ?[]const ReplayEvent {
        const rec = self.recordings.get(recording_id) orelse return null;
        return rec.events.items;
    }

    pub fn getEventData(self: *ReplayEngine, recording_id: RecordingId, event_idx: usize) ?[]const u8 {
        const rec = self.recordings.get(recording_id) orelse return null;
        if (event_idx >= rec.events.items.len) return null;
        const event = rec.events.items[event_idx];
        if (event.data_offset + event.data_len > rec.data_buffer.items.len) return null;
        return rec.data_buffer.items[event.data_offset..][0..event.data_len];
    }

    pub fn getRecordingInfo(self: *ReplayEngine, recording_id: RecordingId) ?RecordingInfo {
        const rec = self.recordings.get(recording_id) orelse return null;
        return .{ .id = rec.id, .agent_id = rec.agent_id, .event_count = rec.events.items.len, .data_bytes = rec.data_buffer.items.len, .start_time_ns = rec.start_time_ns, .status = rec.status, .start_snapshot = rec.start_snapshot };
    }

    pub fn count(self: *const ReplayEngine) usize {
        return self.recordings.count();
    }

    pub fn createReplayCursor(self: *ReplayEngine, recording_id: RecordingId) !ReplayCursor {
        const rec = self.recordings.getPtr(recording_id) orelse return error.RecordingNotFound;
        if (rec.status == .active) return error.RecordingStillActive;
        rec.status = .replaying;
        return .{ .recording_id = recording_id, .current_index = 0, .total_events = rec.events.items.len, .engine = self };
    }
};

test "ReplayEngine basic recording" {
    var engine = ReplayEngine.init(std.testing.allocator);
    defer engine.deinit();
    const rec_id = try engine.startRecording(42, null);
    try engine.recordEvent(rec_id, .llm_request, 42, "prompt: hello", 0, null);
    try engine.recordEvent(rec_id, .llm_response, 42, "response: world", 150_000_000, 0);
    try engine.stopRecording(rec_id);
    const info = engine.getRecordingInfo(rec_id).?;
    try std.testing.expectEqual(@as(usize, 2), info.event_count);
}

test "ReplayEngine replay cursor" {
    var engine = ReplayEngine.init(std.testing.allocator);
    defer engine.deinit();
    const rec_id = try engine.startRecording(1, null);
    try engine.recordEvent(rec_id, .llm_request, 1, "req1", 0, null);
    try engine.recordEvent(rec_id, .llm_response, 1, "res1", 100, null);
    try engine.stopRecording(rec_id);
    var cursor = try engine.createReplayCursor(rec_id);
    const e1 = cursor.next().?;
    try std.testing.expectEqual(EventType.llm_request, e1.event_type);
    const e2 = cursor.next().?;
    try std.testing.expectEqual(EventType.llm_response, e2.event_type);
    try std.testing.expect(cursor.isDone());
}

test "ReplayEngine event data retrieval" {
    var engine = ReplayEngine.init(std.testing.allocator);
    defer engine.deinit();
    const rec_id = try engine.startRecording(1, null);
    try engine.recordEvent(rec_id, .llm_response, 1, "Hello, world!", 100, null);
    try engine.stopRecording(rec_id);
    const data = engine.getEventData(rec_id, 0).?;
    try std.testing.expectEqualStrings("Hello, world!", data);
}
