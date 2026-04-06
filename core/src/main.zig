//! OpenLVM Core - Standalone Binary

const std = @import("std");
const builtin = @import("builtin");
const capabilities = @import("capabilities.zig");
const chaos = @import("chaos.zig");
const fork_engine = @import("fork_engine.zig");
const replay = @import("replay.zig");
const sandbox = @import("sandbox.zig");
const snapshot_mod = @import("snapshot.zig");

const version = "0.1.0";

fn print(comptime fmt: []const u8, args: anytype) !void {
    var buf: [4096]u8 = undefined;
    var writer = std.fs.File.stdout().writer(&buf);
    try writer.interface.print(fmt, args);
    try writer.interface.flush();
}

fn printErr(comptime fmt: []const u8, args: anytype) !void {
    var buf: [2048]u8 = undefined;
    var writer = std.fs.File.stderr().writer(&buf);
    try writer.interface.print(fmt, args);
    try writer.interface.flush();
}

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
    } else if (std.mem.eql(u8, command, "info")) {
        try printInfo();
    } else if (std.mem.eql(u8, command, "selftest")) {
        try runSelfTest(allocator);
    } else if (std.mem.eql(u8, command, "bench")) {
        const count = if (args.len > 2) try std.fmt.parseInt(u32, args[2], 10) else 1000;
        try runBenchmark(allocator, count);
    } else if (std.mem.eql(u8, command, "help")) {
        try printUsage();
    } else {
        try printErr("Unknown command: {s}\n\n", .{command});
        try printUsage();
    }
}

fn printVersion() !void {
    try print("openlvm-core {s}\n", .{version});
}

fn printUsage() !void {
    try print(
        \\openlvm-core - OpenLVM Zig Runtime
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
    , .{});
}

fn printInfo() !void {
    const caps = capabilities.Profiles.privileged;
    try print(
        "openlvm-core {s}\n  platform: {s}-{s}\n  zig version: {s}\n  page size: {} bytes\n  native fork: {}\n  capability bits: {}\n  capability profiles: readonly, standard, privileged, sandboxed\n",
        .{
            version,
            @tagName(builtin.os.tag),
            @tagName(builtin.cpu.arch),
            builtin.zig_version_string,
            std.heap.pageSize(),
            builtin.os.tag == .linux or builtin.os.tag == .macos,
            caps.count(),
        },
    );
}

fn runSelfTest(allocator: std.mem.Allocator) !void {
    try print("Running OpenLVM self-test...\n\n", .{});

    var passed: u32 = 0;
    var failed: u32 = 0;

    {
        var eng = fork_engine.ForkEngine.init(allocator);
        defer eng.deinit();
        const id = eng.registerAgent(capabilities.Profiles.standard) catch {
            failed += 1;
            try print("  [1] ForkEngine register + fork... FAIL\n", .{});
            return;
        };
        _ = eng.forkAgent(id) catch {
            failed += 1;
            try print("  [1] ForkEngine register + fork... FAIL\n", .{});
            return;
        };
        if (eng.activeAgentCount() == 2) {
            passed += 1;
            try print("  [1] ForkEngine register + fork... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [1] ForkEngine register + fork... FAIL\n", .{});
        }
    }

    {
        var eng = fork_engine.ForkEngine.init(allocator);
        defer eng.deinit();
        const id = eng.registerAgent(capabilities.Profiles.readonly) catch {
            failed += 1;
            try print("  [2] ForkEngine forkMany(100)... FAIL\n", .{});
            return;
        };
        const handles = eng.forkMany(id, 100) catch {
            failed += 1;
            try print("  [2] ForkEngine forkMany(100)... FAIL\n", .{});
            return;
        };
        defer allocator.free(handles);
        if (handles.len == 100 and eng.activeAgentCount() == 101) {
            passed += 1;
            try print("  [2] ForkEngine forkMany(100)... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [2] ForkEngine forkMany(100)... FAIL\n", .{});
        }
    }

    {
        const caps = capabilities.Profiles.readonly;
        if (caps.has(.fs_read) and !caps.has(.fs_write) and caps.has(.llm_call)) {
            passed += 1;
            try print("  [3] Capability enforcement... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [3] Capability enforcement... FAIL\n", .{});
        }
    }

    {
        const original = capabilities.Profiles.standard;
        const serialized = original.toU64();
        const deserialized = capabilities.CapabilitySet.fromU64(serialized);
        if (std.meta.eql(original, deserialized)) {
            passed += 1;
            try print("  [4] Capability U64 roundtrip... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [4] Capability U64 roundtrip... FAIL\n", .{});
        }
    }

    {
        var store = snapshot_mod.SnapshotStore.init(allocator);
        defer store.deinit();
        const snap_id = store.createSnapshot(1, capabilities.Profiles.standard, "test-state", "selftest") catch {
            failed += 1;
            try print("  [5] SnapshotStore create/retrieve... FAIL\n", .{});
            return;
        };
        const data = store.getSnapshotData(snap_id);
        if (data != null and std.mem.eql(u8, data.?, "test-state")) {
            passed += 1;
            try print("  [5] SnapshotStore create/retrieve... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [5] SnapshotStore create/retrieve... FAIL\n", .{});
        }
    }

    {
        var re = replay.ReplayEngine.init(allocator);
        defer re.deinit();
        const rec_id = re.startRecording(1, null) catch {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
            return;
        };
        re.recordEvent(rec_id, .llm_request, 1, "hello", 0, null) catch {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
            return;
        };
        re.recordEvent(rec_id, .llm_response, 1, "world", 100, null) catch {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
            return;
        };
        re.stopRecording(rec_id) catch {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
            return;
        };
        var cursor = re.createReplayCursor(rec_id) catch {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
            return;
        };
        const e1 = cursor.next();
        const e2 = cursor.next();
        if (e1 != null and e2 != null and cursor.isDone()) {
            passed += 1;
            try print("  [6] ReplayEngine record/cursor... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [6] ReplayEngine record/cursor... FAIL\n", .{});
        }
    }

    {
        var sb = sandbox.Sandbox.init(allocator, 1, capabilities.Profiles.readonly);
        defer sb.deinit();
        const read_ok = if (sb.checkCapability(.fs_read)) |_| true else |_| false;
        const write_denied = if (sb.checkCapability(.fs_write)) |_| false else |_| true;
        if (read_ok and write_denied) {
            passed += 1;
            try print("  [7] Sandbox cap enforcement... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [7] Sandbox cap enforcement... FAIL\n", .{});
        }
    }

    {
        var ce = chaos.ChaosEngine.init(allocator, 42);
        defer ce.deinit();
        ce.addConfig(.{
            .mode = .network_delay,
            .target_agent_id = 1,
            .probability = 1.0,
            .params = .{ .delay_ms = 100 },
            .enabled = true,
        }) catch {
            failed += 1;
            try print("  [8] ChaosEngine delay injection... FAIL\n", .{});
            return;
        };
        const delay = ce.getNetworkDelay(1);
        if (delay > 0 and delay <= 120) {
            passed += 1;
            try print("  [8] ChaosEngine delay injection... PASS\n", .{});
        } else {
            failed += 1;
            try print("  [8] ChaosEngine delay injection... FAIL\n", .{});
        }
    }

    try print("\n  Results: {} passed, {} failed\n", .{ passed, failed });
    if (failed > 0) std.process.exit(1);
}

fn runBenchmark(allocator: std.mem.Allocator, count: u32) !void {
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
    const per_fork_ns = if (count == 0) 0 else elapsed_ns / count;
    const per_fork_us = per_fork_ns / 1000;

    try print(
        "OpenLVM Fork Benchmark - {} agents\n\n  Total time: {}ms ({}us)\n  Per fork:   {}us ({}ns)\n  Agents:     {} active\n  Rate:       {d:.0} forks/sec\n",
        .{
            count,
            elapsed_ms,
            elapsed_us,
            per_fork_us,
            per_fork_ns,
            eng.activeAgentCount(),
            @as(f64, @floatFromInt(count)) / (@as(f64, @floatFromInt(@max(elapsed_ns, 1))) / 1_000_000_000.0),
        },
    );

    if (eng.getMemoryStats(parent_id)) |stats| {
        try print(
            "\n  Parent memory:\n    Regions:    {}\n    Capacity:   {} bytes\n    Used:       {} bytes\n",
            .{ stats.region_count, stats.total_capacity, stats.total_used },
        );
    }
}
