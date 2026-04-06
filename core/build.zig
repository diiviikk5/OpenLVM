const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const lib_module = b.createModule(.{
        .root_source_file = b.path("src/ffi.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
    });
    const lib = b.addLibrary(.{
        .name = "openlvm",
        .root_module = lib_module,
        .linkage = .dynamic,
    });
    b.installArtifact(lib);

    const exe_module = b.createModule(.{
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
    });
    const exe = b.addExecutable(.{
        .name = "openlvm-core",
        .root_module = exe_module,
    });
    b.installArtifact(exe);

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
        const test_module = b.createModule(.{
            .root_source_file = b.path(test_file),
            .target = target,
            .optimize = optimize,
            .link_libc = true,
        });
        const t = b.addTest(.{
            .root_module = test_module,
        });
        const run_test = b.addRunArtifact(t);
        test_step.dependOn(&run_test.step);
    }

    const bench_module = b.createModule(.{
        .root_source_file = b.path("src/bench.zig"),
        .target = target,
        .optimize = .ReleaseFast,
        .link_libc = true,
    });
    const bench = b.addExecutable(.{
        .name = "openlvm-bench",
        .root_module = bench_module,
    });

    const bench_step = b.step("bench", "Run benchmarks");
    const run_bench = b.addRunArtifact(bench);
    if (b.args) |args| {
        run_bench.addArgs(args);
    }
    bench_step.dependOn(&run_bench.step);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| {
        run_cmd.addArgs(args);
    }
    const run_step = b.step("run", "Run the openlvm-core binary");
    run_step.dependOn(&run_cmd.step);
}
