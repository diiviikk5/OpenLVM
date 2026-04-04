//! OpenLVM C-ABI FFI Exports
//!
//! Every function here is exported with C calling convention for consumption
//! by the Python orchestrator via ctypes/cffi.
//!
//! ABI contract:
//!   - Returns: 0 = success, negative = error code
//!   - IDs: positive u64 values
//!   - Strings: null-terminated C strings
//!   - Memory: caller owns output buffers, library owns internal state

const std = @import("std");
const fork_engine = @import("fork_engine.zig");
const capabilities = @import("capabilities.zig");
const snapshot_mod = @import("snapshot.zig");
const replay = @import("replay.zig");
const sandbox = @import("sandbox.zig");
const chaos = @import("chaos.zig");

// ── Global state ─────────────────────────────────────────────────
// The shared library maintains one global engine instance.
// Initialized on first call, lives for the library lifetime.

var global_allocator: std.mem.Allocator = undefined;
var gpa: std.heap.GeneralPurposeAllocator(.{}) = undefined;
var engine: fork_engine.ForkEngine = undefined;
var snap_store: snapshot_mod.SnapshotStore = undefined;
var replay_engine: replay.ReplayEngine = undefined;
var sandbox_mgr: sandbox.SandboxManager = undefined;
var chaos_engine: chaos.ChaosEngine = undefined;
var initialized: bool = false;

// ── Error codes ──────────────────────────────────────────────────
const ERR_NOT_INITIALIZED: i32 = -1;
const ERR_ALREADY_INITIALIZED: i32 = -2;
const ERR_AGENT_NOT_FOUND: i32 = -10;
const ERR_TOO_MANY_FORKS: i32 = -11;
const ERR_OUT_OF_MEMORY: i32 = -12;
const ERR_FORK_FAILED: i32 = -13;
const ERR_SNAPSHOT_NOT_FOUND: i32 = -20;
const ERR_RECORDING_NOT_FOUND: i32 = -30;
const ERR_RECORDING_NOT_ACTIVE: i32 = -31;
const ERR_RECORDING_STILL_ACTIVE: i32 = -32;
const ERR_CAPABILITY_DENIED: i32 = -40;
const ERR_SANDBOX_TERMINATED: i32 = -41;
const ERR_INVALID_PARAM: i32 = -50;
const ERR_UNKNOWN: i32 = -99;

// ── Lifecycle ────────────────────────────────────────────────────

/// Initialize the OpenLVM runtime. Must be called before any other function.
export fn openlvm_init() callconv(.C) i32 {
    if (initialized) return ERR_ALREADY_INITIALIZED;

    gpa = std.heap.GeneralPurposeAllocator(.{}){};
    global_allocator = gpa.allocator();
    engine = fork_engine.ForkEngine.init(global_allocator);
    snap_store = snapshot_mod.SnapshotStore.init(global_allocator);
    replay_engine = replay.ReplayEngine.init(global_allocator);
    sandbox_mgr = sandbox.SandboxManager.init(global_allocator);
    chaos_engine = chaos.ChaosEngine.init(global_allocator, @intCast(@as(u64, @truncate(@as(u128, @bitCast(std.time.nanoTimestamp()))))));
    initialized = true;
    return 0;
}

/// Shutdown the OpenLVM runtime and free all resources.
export fn openlvm_shutdown() callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;

    chaos_engine.deinit();
    sandbox_mgr.deinit();
    replay_engine.deinit();
    snap_store.deinit();
    engine.deinit();
    _ = gpa.deinit();
    initialized = false;
    return 0;
}

// ── Agent Management ─────────────────────────────────────────────

/// Register a new agent with the given capability bitmask.
/// Returns the agent ID (positive) or error code (negative).
export fn openlvm_register_agent(caps_bitmask: u64) callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const caps = capabilities.CapabilitySet.fromU64(caps_bitmask);
    const id = engine.registerAgent(caps) catch return ERR_OUT_OF_MEMORY;
    return @intCast(id);
}

/// Terminate an agent and free its resources.
export fn openlvm_terminate_agent(agent_id: u64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    engine.terminateAgent(agent_id) catch return ERR_AGENT_NOT_FOUND;
    sandbox_mgr.removeSandbox(agent_id);
    return 0;
}

/// Get the number of active agents.
export fn openlvm_active_agent_count() callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    return @intCast(engine.activeAgentCount());
}

// ── Fork Operations ──────────────────────────────────────────────

/// Fork a single agent. Returns the child agent ID or error code.
export fn openlvm_fork_agent(agent_id: u64) callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;

    const result = engine.forkAgent(agent_id) catch |err| {
        return switch (err) {
            fork_engine.ForkError.AgentNotFound => ERR_AGENT_NOT_FOUND,
            fork_engine.ForkError.TooManyForks => ERR_TOO_MANY_FORKS,
            fork_engine.ForkError.OutOfMemory => ERR_OUT_OF_MEMORY,
            fork_engine.ForkError.ForkFailed => ERR_FORK_FAILED,
            else => ERR_UNKNOWN,
        };
    };

    return switch (result) {
        .parent => |handle| @intCast(handle.id),
        .child => |handle| @intCast(handle.id),
        .err => ERR_FORK_FAILED,
    };
}

/// Fork N parallel universes from the same agent.
/// Writes child IDs into the output buffer. Returns count or error.
export fn openlvm_fork_many(agent_id: u64, count: u32, out_ids: [*]i64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    if (count == 0) return 0;

    const handles = engine.forkMany(agent_id, count) catch |err| {
        return switch (err) {
            fork_engine.ForkError.AgentNotFound => ERR_AGENT_NOT_FOUND,
            fork_engine.ForkError.TooManyForks => ERR_TOO_MANY_FORKS,
            fork_engine.ForkError.OutOfMemory => ERR_OUT_OF_MEMORY,
            else => ERR_UNKNOWN,
        };
    };
    defer global_allocator.free(handles);

    for (handles, 0..) |handle, i| {
        out_ids[i] = @intCast(handle.id);
    }
    return @intCast(handles.len);
}

// ── Snapshot Operations ──────────────────────────────────────────

/// Create a snapshot of an agent's state.
/// Returns snapshot ID (positive) or error code (negative).
export fn openlvm_snapshot_create(agent_id: u64) callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;

    const agent = engine.getAgent(agent_id) orelse return ERR_AGENT_NOT_FOUND;
    const id = snap_store.createSnapshot(
        agent_id,
        agent.caps,
        "", // State data will be populated by the Python orchestrator
        null,
    ) catch return ERR_OUT_OF_MEMORY;
    return @intCast(id);
}

/// Get the number of snapshots.
export fn openlvm_snapshot_count() callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    return @intCast(snap_store.count());
}

/// Delete a snapshot.
export fn openlvm_snapshot_delete(snapshot_id: u64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    snap_store.deleteSnapshot(snapshot_id) catch return ERR_SNAPSHOT_NOT_FOUND;
    return 0;
}

// ── Replay Operations ────────────────────────────────────────────

/// Start recording events for an agent.
/// Returns recording ID (positive) or error code (negative).
export fn openlvm_replay_start(agent_id: u64) callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const id = replay_engine.startRecording(agent_id, null) catch return ERR_OUT_OF_MEMORY;
    return @intCast(id);
}

/// Record an event into an active recording.
export fn openlvm_replay_record_event(
    recording_id: u64,
    event_type: u8,
    agent_id: u64,
    data_ptr: [*]const u8,
    data_len: u32,
    duration_ns: u64,
) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const data = data_ptr[0..data_len];
    replay_engine.recordEvent(
        recording_id,
        @enumFromInt(event_type),
        agent_id,
        data,
        duration_ns,
        null,
    ) catch |err| {
        _ = err;
        return ERR_RECORDING_NOT_FOUND;
    };
    return 0;
}

/// Stop recording.
export fn openlvm_replay_stop(recording_id: u64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    replay_engine.stopRecording(recording_id) catch return ERR_RECORDING_NOT_FOUND;
    return 0;
}

/// Get event count for a recording.
export fn openlvm_replay_event_count(recording_id: u64) callconv(.C) i64 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const info = replay_engine.getRecordingInfo(recording_id) orelse return ERR_RECORDING_NOT_FOUND;
    return @intCast(info.event_count);
}

// ── Sandbox Operations ───────────────────────────────────────────

/// Create a sandbox for an agent with the given capability bitmask.
export fn openlvm_sandbox_create(agent_id: u64, caps_bitmask: u64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const caps = capabilities.CapabilitySet.fromU64(caps_bitmask);
    _ = sandbox_mgr.createSandbox(agent_id, caps) catch return ERR_OUT_OF_MEMORY;
    return 0;
}

/// Apply sandbox restrictions to the current process.
export fn openlvm_sandbox_apply(agent_id: u64) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const sb = sandbox_mgr.getSandbox(agent_id) orelse return ERR_AGENT_NOT_FOUND;
    sb.apply() catch return ERR_UNKNOWN;
    return 0;
}

/// Check if an agent has a specific capability.
export fn openlvm_sandbox_check_cap(agent_id: u64, cap_index: u8) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    const sb = sandbox_mgr.getSandbox(agent_id) orelse return ERR_AGENT_NOT_FOUND;
    const cap: capabilities.Capability = @enumFromInt(@as(u6, @truncate(cap_index)));
    sb.checkCapability(cap) catch |err| {
        return switch (err) {
            error.CapabilityDenied => ERR_CAPABILITY_DENIED,
            error.SandboxTerminated => ERR_SANDBOX_TERMINATED,
            //else => ERR_UNKNOWN,
        };
    };
    return 0; // allowed
}

// ── Chaos Operations ─────────────────────────────────────────────

/// Add a chaos config. Params is mode-specific.
export fn openlvm_chaos_add(
    mode: u8,
    agent_id: u64,
    probability: f64,
    param_value: u64,
) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    if (probability < 0.0 or probability > 1.0) return ERR_INVALID_PARAM;

    const chaos_mode: chaos.ChaosMode = @enumFromInt(mode);
    const params: chaos.ChaosConfig.ChaosParams = switch (chaos_mode) {
        .network_delay => .{ .delay_ms = param_value },
        .api_error => .{ .error_code = @truncate(param_value) },
        .hallucination => .{ .corruption_rate = @bitCast(param_value) },
        .memory_pressure => .{ .memory_limit_bytes = param_value },
        .cpu_throttle => .{ .cpu_percent = @truncate(param_value) },
        .clock_skew => .{ .skew_seconds = @bitCast(param_value) },
        else => .{ .generic = param_value },
    };

    chaos_engine.addConfig(.{
        .mode = chaos_mode,
        .target_agent_id = agent_id,
        .probability = probability,
        .params = params,
        .enabled = true,
    }) catch return ERR_OUT_OF_MEMORY;
    return 0;
}

/// Get network delay for an agent (0 = no delay).
export fn openlvm_chaos_get_delay(agent_id: u64) callconv(.C) u64 {
    if (!initialized) return 0;
    return chaos_engine.getNetworkDelay(agent_id);
}

/// Check if API should error (returns error code, or 0 = no error).
export fn openlvm_chaos_get_api_error(agent_id: u64) callconv(.C) u32 {
    if (!initialized) return 0;
    return chaos_engine.getApiError(agent_id) orelse 0;
}

/// Enable/disable chaos globally.
export fn openlvm_chaos_set_enabled(enabled: u8) callconv(.C) i32 {
    if (!initialized) return ERR_NOT_INITIALIZED;
    chaos_engine.setEnabled(enabled != 0);
    return 0;
}

/// Get total chaos events recorded.
export fn openlvm_chaos_event_count() callconv(.C) i64 {
    if (!initialized) return 0;
    return @intCast(chaos_engine.eventCount());
}

// ── Version ──────────────────────────────────────────────────────

export fn openlvm_version_major() callconv(.C) u32 {
    return 0;
}

export fn openlvm_version_minor() callconv(.C) u32 {
    return 1;
}

export fn openlvm_version_patch() callconv(.C) u32 {
    return 0;
}
