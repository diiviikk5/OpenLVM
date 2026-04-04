const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // ── Shared library (for Python FFI) ──────────────────────────
    const lib = b.addSharedLibrary(.{
        .name = "openlvm",
        .root_source_file = b.path("src/ffi.zig"),
        .target = target,
        .optimize = optimize,
    });
    lib.linkLibC();
    b.installArtifact(lib);

    // ── Standalone binary ────────────────────────────────────────
    const exe = b.addExecutable(.{
        .name = "openlvm-core",
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
    });
    exe.linkLibC();
    b.installArtifact(exe);

    // ── Unit tests ───────────────────────────────────────────────
    const test_targets = [_][]const u8{
        "src/fork_engine.zig",
        "src/memory.zig",
        "src/capabilities.zig",
        "src/snapshot.zig",
        "src/replay.zig",
        "src/chaos.zig",
        "src/sandbox.zig",
    };

    const test_step = b.step("test", "Run unit tests");
    for (test_targets) |test_file| {
        const t = b.addTest(.{
            .root_source_file = b.path(test_file),
            .target = target,
            .optimize = optimize,
        });
        t.linkLibC();
        const run_test = b.addRunArtifact(t);
        test_step.dependOn(&run_test.step);
    }

    // ── Benchmarks ───────────────────────────────────────────────
    const bench = b.addExecutable(.{
        .name = "openlvm-bench",
        .root_source_file = b.path("src/bench.zig"),
        .target = target,
        .optimize = .ReleaseFast,
    });
    bench.linkLibC();

    const bench_step = b.step("bench", "Run benchmarks");
    const run_bench = b.addRunArtifact(bench);
    bench_step.dependOn(&run_bench.step);

    // ── Run step ─────────────────────────────────────────────────
    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| {
        run_cmd.addArgs(args);
    }
    const run_step = b.step("run", "Run the openlvm-core binary");
    run_step.dependOn(&run_cmd.step);
}
