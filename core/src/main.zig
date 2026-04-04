//! OpenLVM Core — Standalone Binary
//!
//! CLI entry point for direct invocation of the Zig core runtime.
//! Primarily used for:
//!   - Running benchmarks
//!   - Health checks
//!   - Standalone fork/replay without Python
//!   - Integration testing

const std = @import("std");
const fork_engine = @import("fork_engine.zig");
const capabilities = @import("capabilities.zig");
const snapshot_mod = @import("snapshot.zig");
const replay = @import("replay.zig");
const sandbox = @import("sandbox.zig");
const chaos = @import("chaos.zig");
const memory = @import("memory.zig");

const version = "0.1.0";

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        try printUsage();
        return;
    }

    const command = args[1];

    if (std.mem.eql(u8, command, "version")) {
        try printVersion();
    } else if (std.mem.eql(u8, command, "selftest")) {
        try runSelfTest(allocator);
    } else if (std.mem.eql(u8, command, "bench")) {
        const count = if (args.len > 2) try std.fmt.parseInt(u32, args[2], 10) else 1000;
        try runBenchmark(allocator, count);
    } else if (std.mem.eql(u8, command, "info")) {
        try printInfo(allocator);
    } else if (std.mem.eql(u8, command, "help")) {
        try printUsage();
    } else {
        const stderr = std.io.getStdErr().writer();
        try stderr.print("Unknown command: {s}\n\n", .{command});
        try printUsage();
    }
}

fn printVersion() !void {
    const stdout = std.io.getStdOut().writer();
    try stdout.print("openlvm-core {s}\n", .{version});
}

fn printUsage() !void {
    const stdout = std.io.getStdOut().writer();
    try stdout.writeAll(
        \\openlvm-core — OpenLVM Zig Runtime
        \\
        \\USAGE:
        \\  openlvm-core <command> [args...]
        \\
        \\COMMANDS:
        \\  version     Print version
        \\  selftest    Run internal self-test suite
        \\  bench [N]   Run fork benchmark with N agents (default: 1000)
        \\  info        Print runtime info (platform, capabilities)
        \\  help        Show this help
        \\
    );
}

fn printInfo(allocator: std.mem.Allocator) !void {
    _ = allocator;
    const stdout = std.io.getStdOut().writer();
    const builtin = @import("builtin");

    try stdout.print("openlvm-core {s}\n", .{version});
    try stdout.print("  platform: {s}-{s}\n", .{ @tagName(builtin.os.tag), @tagName(builtin.cpu.arch) });
    try stdout.print("  zig version: {s}\n", .{builtin.zig_version_string});
    try stdout.print("  page size: {} bytes\n", .{std.mem.page_size});
    try stdout.print("  native fork: {}\n", .{builtin.os.tag == .linux or builtin.os.tag == .macos});

    // Capability system info
    const caps = capabilities.Profiles.privileged;
    try stdout.print("  capability bits: {}\n", .{caps.count()});
    try stdout.print("  capability profiles: readonly, standard, privileged, sandboxed\n", .{});
}

fn runSelfTest(allocator: std.mem.Allocator) !void {
    const stdout = std.io.getStdOut().writer();
    try stdout.writeAll("Running OpenLVM self-test...\n\n");

    var passed: u32 = 0;
    var failed: u32 = 0;

    // Test 1: ForkEngine
    {
        try stdout.writeAll("  [1] ForkEngine register + fork... ");
        var eng = fork_engine.ForkEngine.init(allocator);
        defer eng.deinit();
        const id = eng.registerAgent(capabilities.Profiles.standard) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        _ = eng.forkAgent(id) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        if (eng.activeAgentCount() == 2) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 2: ForkMany
    {
        try stdout.writeAll("  [2] ForkEngine forkMany(100)... ");
        var eng = fork_engine.ForkEngine.init(allocator);
        defer eng.deinit();
        const id = eng.registerAgent(capabilities.Profiles.readonly) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        const handles = eng.forkMany(id, 100) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        defer allocator.free(handles);
        if (handles.len == 100 and eng.activeAgentCount() == 101) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 3: Capabilities
    {
        try stdout.writeAll("  [3] Capability enforcement... ");
        const caps = capabilities.Profiles.readonly;
        if (caps.has(.fs_read) and !caps.has(.fs_write) and caps.has(.llm_call)) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 4: Capability serialization roundtrip
    {
        try stdout.writeAll("  [4] Capability U64 roundtrip... ");
        const original = capabilities.Profiles.standard;
        const serialized = original.toU64();
        const deserialized = capabilities.CapabilitySet.fromU64(serialized);
        if (std.meta.eql(original, deserialized)) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 5: Snapshot store
    {
        try stdout.writeAll("  [5] SnapshotStore create/retrieve... ");
        var store = snapshot_mod.SnapshotStore.init(allocator);
        defer store.deinit();
        const snap_id = store.createSnapshot(1, capabilities.Profiles.standard, "test-state", "selftest") catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        const data = store.getSnapshotData(snap_id);
        if (data != null and std.mem.eql(u8, data.?, "test-state")) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 6: Replay engine
    {
        try stdout.writeAll("  [6] ReplayEngine record/cursor... ");
        var re = replay.ReplayEngine.init(allocator);
        defer re.deinit();
        const rec_id = re.startRecording(1, null) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        re.recordEvent(rec_id, .llm_request, 1, "hello", 0, null) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        re.recordEvent(rec_id, .llm_response, 1, "world", 100, null) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        re.stopRecording(rec_id) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        var cursor = re.createReplayCursor(rec_id) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        const e1 = cursor.next();
        const e2 = cursor.next();
        if (e1 != null and e2 != null and cursor.isDone()) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 7: Sandbox
    {
        try stdout.writeAll("  [7] Sandbox cap enforcement... ");
        var sb = sandbox.Sandbox.init(allocator, 1, capabilities.Profiles.readonly);
        defer sb.deinit();
        const read_ok = if (sb.checkCapability(.fs_read)) |_| true else |_| false;
        const write_denied = if (sb.checkCapability(.fs_write)) |_| false else |_| true;
        if (read_ok and write_denied) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    // Test 8: Chaos engine
    {
        try stdout.writeAll("  [8] ChaosEngine delay injection... ");
        var ce = chaos.ChaosEngine.init(allocator, 42);
        defer ce.deinit();
        ce.addConfig(.{
            .mode = .network_delay,
            .target_agent_id = 1,
            .probability = 1.0,
            .params = .{ .delay_ms = 100 },
            .enabled = true,
        }) catch {
            try stdout.writeAll("FAIL\n");
            failed += 1;
            return;
        };
        const delay = ce.getNetworkDelay(1);
        if (delay > 0 and delay <= 120) {
            try stdout.writeAll("PASS\n");
            passed += 1;
        } else {
            try stdout.writeAll("FAIL\n");
            failed += 1;
        }
    }

    try stdout.print("\n  Results: {} passed, {} failed\n", .{ passed, failed });
    if (failed > 0) {
        std.process.exit(1);
    }
}

fn runBenchmark(allocator: std.mem.Allocator, count: u32) !void {
    const stdout = std.io.getStdOut().writer();
    try stdout.print("OpenLVM Fork Benchmark — {} agents\n\n", .{count});

    // Benchmark: register + fork N agents
    var eng = fork_engine.ForkEngine.init(allocator);
    defer eng.deinit();

    const parent_id = try eng.registerAgent(capabilities.Profiles.standard);

    const start = std.time.nanoTimestamp();
    const handles = try eng.forkMany(parent_id, count);
    defer allocator.free(handles);
    const end = std.time.nanoTimestamp();

    const elapsed_ns: u64 = @intCast(end - start);
    const elapsed_us = elapsed_ns / 1000;
    const elapsed_ms = elapsed_us / 1000;
    const per_fork_ns = elapsed_ns / count;
    const per_fork_us = per_fork_ns / 1000;

    try stdout.print("  Total time: {}ms ({}us)\n", .{ elapsed_ms, elapsed_us });
    try stdout.print("  Per fork:   {}us ({}ns)\n", .{ per_fork_us, per_fork_ns });
    try stdout.print("  Agents:     {} active\n", .{eng.activeAgentCount()});
    try stdout.print("  Rate:       {d:.0} forks/sec\n", .{
        @as(f64, @floatFromInt(count)) / (@as(f64, @floatFromInt(elapsed_ns)) / 1_000_000_000.0),
    });

    // Memory stats for parent agent
    if (eng.getMemoryStats(parent_id)) |stats| {
        try stdout.print("\n  Parent memory:\n", .{});
        try stdout.print("    Regions:    {}\n", .{stats.region_count});
        try stdout.print("    Capacity:   {} bytes\n", .{stats.total_capacity});
        try stdout.print("    Used:       {} bytes\n", .{stats.total_used});
    }
}
