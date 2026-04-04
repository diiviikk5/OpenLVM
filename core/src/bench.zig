//! OpenLVM Benchmarks
//!
//! Standalone benchmark suite for measuring fork performance,
//! memory overhead, and throughput.

const std = @import("std");
const fork_engine = @import("fork_engine.zig");
const capabilities = @import("capabilities.zig");
const snapshot_mod = @import("snapshot.zig");
const replay = @import("replay.zig");
const chaos = @import("chaos.zig");

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();
    const stdout = std.io.getStdOut().writer();

    try stdout.writeAll("═══════════════════════════════════════════\n");
    try stdout.writeAll("  OpenLVM Benchmark Suite v0.1.0\n");
    try stdout.writeAll("═══════════════════════════════════════════\n\n");

    try benchForkSingle(allocator, stdout);
    try benchForkMany(allocator, stdout, 100);
    try benchForkMany(allocator, stdout, 1000);
    try benchForkMany(allocator, stdout, 5000);
    try benchForkMany(allocator, stdout, 10000);
    try benchSnapshotCreate(allocator, stdout);
    try benchReplayRecord(allocator, stdout);
    try benchCapabilityChecks(stdout);
    try benchChaosDecisions(allocator, stdout);

    try stdout.writeAll("\n═══════════════════════════════════════════\n");
    try stdout.writeAll("  Done.\n");
    try stdout.writeAll("═══════════════════════════════════════════\n");
}

fn benchForkSingle(allocator: std.mem.Allocator, stdout: anytype) !void {
    const iterations = 10_000;
    var eng = fork_engine.ForkEngine.init(allocator);
    defer eng.deinit();
    eng.max_forks = iterations + 1;

    const parent_id = try eng.registerAgent(capabilities.Profiles.standard);

    const start = std.time.nanoTimestamp();
    for (0..iterations) |_| {
        _ = try eng.forkAgent(parent_id);
    }
    const end = std.time.nanoTimestamp();
    const elapsed_ns: u64 = @intCast(end - start);

    try stdout.print("Fork single x{}: {}us total, {}ns/fork\n", .{
        iterations,
        elapsed_ns / 1000,
        elapsed_ns / iterations,
    });
}

fn benchForkMany(allocator: std.mem.Allocator, stdout: anytype, count: u32) !void {
    var eng = fork_engine.ForkEngine.init(allocator);
    defer eng.deinit();
    eng.max_forks = count + 1;

    const parent_id = try eng.registerAgent(capabilities.Profiles.standard);

    const start = std.time.nanoTimestamp();
    const handles = try eng.forkMany(parent_id, count);
    const end = std.time.nanoTimestamp();
    defer allocator.free(handles);

    const elapsed_ns: u64 = @intCast(end - start);
    const elapsed_us = elapsed_ns / 1000;

    try stdout.print("ForkMany({}): {}us total, {}ns/fork, {} agents active\n", .{
        count,
        elapsed_us,
        elapsed_ns / count,
        eng.activeAgentCount(),
    });
}

fn benchSnapshotCreate(allocator: std.mem.Allocator, stdout: anytype) !void {
    const iterations = 1000;
    var store = snapshot_mod.SnapshotStore.init(allocator);
    defer store.deinit();

    // Simulate 1KB state data per snapshot
    var state_data: [1024]u8 = undefined;
    @memset(&state_data, 0xAB);

    const start = std.time.nanoTimestamp();
    for (0..iterations) |i| {
        _ = try store.createSnapshot(@intCast(i), capabilities.Profiles.standard, &state_data, null);
    }
    const end = std.time.nanoTimestamp();
    const elapsed_ns: u64 = @intCast(end - start);

    try stdout.print("Snapshot create x{}: {}us total, {}ns/snap, {}KB stored\n", .{
        iterations,
        elapsed_ns / 1000,
        elapsed_ns / iterations,
        store.totalBytes() / 1024,
    });
}

fn benchReplayRecord(allocator: std.mem.Allocator, stdout: anytype) !void {
    const events = 10_000;
    var engine = replay.ReplayEngine.init(allocator);
    defer engine.deinit();

    const rec_id = try engine.startRecording(1, null);

    const start = std.time.nanoTimestamp();
    for (0..events) |_| {
        try engine.recordEvent(rec_id, .llm_response, 1, "response data payload", 100_000, null);
    }
    const end = std.time.nanoTimestamp();
    const elapsed_ns: u64 = @intCast(end - start);

    try engine.stopRecording(rec_id);

    try stdout.print("Replay record x{}: {}us total, {}ns/event\n", .{
        events,
        elapsed_ns / 1000,
        elapsed_ns / events,
    });
}

fn benchCapabilityChecks(stdout: anytype) !void {
    const iterations = 1_000_000;
    const caps = capabilities.Profiles.standard;

    const caps_to_check = [_]capabilities.Capability{
        .fs_read, .fs_write, .llm_call, .network_outbound, .tool_use,
        .shared_db_write, .subprocess_spawn, .clock_read,
    };

    const start = std.time.nanoTimestamp();
    var result: u32 = 0;
    for (0..iterations) |i| {
        const cap = caps_to_check[i % caps_to_check.len];
        if (caps.has(cap)) result += 1;
    }
    const end = std.time.nanoTimestamp();
    const elapsed_ns: u64 = @intCast(end - start);

    try stdout.print("Capability check x{}: {}us total, {}ns/check ({} granted)\n", .{
        iterations,
        elapsed_ns / 1000,
        elapsed_ns / iterations,
        result,
    });
}

fn benchChaosDecisions(allocator: std.mem.Allocator, stdout: anytype) !void {
    const iterations = 100_000;
    var engine = chaos.ChaosEngine.init(allocator, 42);
    defer engine.deinit();

    try engine.addConfig(.{
        .mode = .network_delay,
        .target_agent_id = 1,
        .probability = 0.3,
        .params = .{ .delay_ms = 100 },
        .enabled = true,
    });

    const start = std.time.nanoTimestamp();
    var applied: u32 = 0;
    for (0..iterations) |_| {
        if (engine.getNetworkDelay(1) > 0) applied += 1;
    }
    const end = std.time.nanoTimestamp();
    const elapsed_ns: u64 = @intCast(end - start);

    try stdout.print("Chaos decision x{}: {}us total, {}ns/check ({} applied)\n", .{
        iterations,
        elapsed_ns / 1000,
        elapsed_ns / iterations,
        applied,
    });
}
