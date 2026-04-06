//! OpenLVM Chaos Injection Engine
//!
//! Injects controlled failures into agent execution for resilience testing.
//! Supports: network delays, API errors, hallucination corruption,
//! memory pressure, CPU throttle, clock skew, and tool failures.

const std = @import("std");

/// Types of chaos that can be injected.
pub const ChaosMode = enum(u8) {
    network_delay = 0, // Add latency to outbound calls
    network_drop = 1, // Drop N% of packets
    api_error = 2, // Return 500/429/timeout from tool calls
    hallucination = 3, // Corrupt LLM response tokens
    memory_pressure = 4, // Reduce available memory
    cpu_throttle = 5, // Limit CPU cycles via sched
    clock_skew = 6, // Shift system time reads
    tool_failure = 7, // Random tool call failures
};

/// Configuration for a single chaos injection.
pub const ChaosConfig = struct {
    mode: ChaosMode,
    target_agent_id: u64,
    probability: f64, // 0.0 - 1.0
    params: ChaosParams,
    enabled: bool,

    pub const ChaosParams = union {
        delay_ms: u64,
        error_code: u32,
        corruption_rate: f64,
        memory_limit_bytes: u64,
        cpu_percent: u32,
        skew_seconds: i64,
        generic: u64,
    };
};

/// A single recorded chaos event (for replay/tracing).
pub const ChaosEvent = struct {
    timestamp_ns: i128,
    mode: ChaosMode,
    agent_id: u64,
    applied: bool,
    detail_offset: usize,
    detail_len: usize,
};

/// Result of checking whether chaos should be applied.
pub const ChaosDecision = struct {
    should_apply: bool,
    mode: ChaosMode,
    config: ChaosConfig,
};

const ManagedArrayList = std.array_list.Managed;

/// Core chaos injection engine.
pub const ChaosEngine = struct {
    configs: ManagedArrayList(ChaosConfig),
    events: ManagedArrayList(ChaosEvent),
    detail_buffer: ManagedArrayList(u8),
    rng: std.Random.DefaultPrng,
    enabled: bool,
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, seed: u64) ChaosEngine {
        return .{
            .configs = ManagedArrayList(ChaosConfig).init(allocator),
            .events = ManagedArrayList(ChaosEvent).init(allocator),
            .detail_buffer = ManagedArrayList(u8).init(allocator),
            .rng = std.Random.DefaultPrng.init(seed),
            .enabled = true,
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *ChaosEngine) void {
        self.configs.deinit();
        self.events.deinit();
        self.detail_buffer.deinit();
    }

    /// Add a chaos configuration.
    pub fn addConfig(self: *ChaosEngine, config: ChaosConfig) !void {
        try self.configs.append(config);
    }

    /// Remove all configs for a specific agent.
    pub fn removeConfigsForAgent(self: *ChaosEngine, agent_id: u64) void {
        var i: usize = 0;
        while (i < self.configs.items.len) {
            if (self.configs.items[i].target_agent_id == agent_id) {
                _ = self.configs.orderedRemove(i);
            } else {
                i += 1;
            }
        }
    }

    /// Clone all configs from a parent agent to a child agent.
    pub fn cloneConfigs(self: *ChaosEngine, from_agent_id: u64, to_agent_id: u64) !void {
        var clones = ManagedArrayList(ChaosConfig).init(self.allocator);
        defer clones.deinit();

        for (self.configs.items) |config| {
            if (config.target_agent_id == from_agent_id) {
                var cloned = config;
                cloned.target_agent_id = to_agent_id;
                try clones.append(cloned);
            }
        }

        for (clones.items) |config| {
            try self.configs.append(config);
        }
    }

    /// Check if chaos should be applied for a given agent and mode.
    /// Uses the PRNG to decide based on probability.
    pub fn shouldApply(self: *ChaosEngine, agent_id: u64, mode: ChaosMode) ?ChaosDecision {
        if (!self.enabled) return null;

        for (self.configs.items) |config| {
            if (config.target_agent_id == agent_id and
                config.mode == mode and
                config.enabled)
            {
                const roll = self.rng.random().float(f64);
                return .{
                    .should_apply = roll < config.probability,
                    .mode = mode,
                    .config = config,
                };
            }
        }
        return null;
    }

    /// Apply network delay chaos — returns how many ms to sleep.
    pub fn getNetworkDelay(self: *ChaosEngine, agent_id: u64) u64 {
        if (self.shouldApply(agent_id, .network_delay)) |decision| {
            if (decision.should_apply) {
                const base = decision.config.params.delay_ms;
                // Add ±20% jitter
                const jitter_max: u64 = base / 5;
                if (jitter_max > 0) {
                    const jitter = self.rng.random().intRangeAtMost(u64, 0, jitter_max * 2);
                    const result = base -| jitter_max + jitter;
                    self.recordEvent(agent_id, .network_delay, true) catch {};
                    return result;
                }
                self.recordEvent(agent_id, .network_delay, true) catch {};
                return base;
            }
        }
        return 0;
    }

    /// Check if an API call should fail, and with what error code.
    pub fn getApiError(self: *ChaosEngine, agent_id: u64) ?u32 {
        if (self.shouldApply(agent_id, .api_error)) |decision| {
            if (decision.should_apply) {
                self.recordEvent(agent_id, .api_error, true) catch {};
                return decision.config.params.error_code;
            }
        }
        return null;
    }

    /// Corrupt a response string to simulate hallucination.
    /// Randomly replaces characters based on corruption rate.
    pub fn corruptResponse(self: *ChaosEngine, agent_id: u64, response: []u8) bool {
        if (self.shouldApply(agent_id, .hallucination)) |decision| {
            if (decision.should_apply) {
                const rate = decision.config.params.corruption_rate;
                var random = self.rng.random();
                for (response) |*byte| {
                    if (random.float(f64) < rate) {
                        // Replace with a random printable ASCII character
                        byte.* = random.intRangeAtMost(u8, 32, 126);
                    }
                }
                self.recordEvent(agent_id, .hallucination, true) catch {};
                return true;
            }
        }
        return false;
    }

    /// Get clock skew for time reads.
    pub fn getClockSkew(self: *ChaosEngine, agent_id: u64) i64 {
        if (self.shouldApply(agent_id, .clock_skew)) |decision| {
            if (decision.should_apply) {
                self.recordEvent(agent_id, .clock_skew, true) catch {};
                return decision.config.params.skew_seconds;
            }
        }
        return 0;
    }

    /// Check if a tool call should fail.
    pub fn shouldToolFail(self: *ChaosEngine, agent_id: u64) bool {
        if (self.shouldApply(agent_id, .tool_failure)) |decision| {
            if (decision.should_apply) {
                self.recordEvent(agent_id, .tool_failure, true) catch {};
                return true;
            }
        }
        return false;
    }

    /// Record a chaos event for tracing/replay.
    fn recordEvent(self: *ChaosEngine, agent_id: u64, mode: ChaosMode, applied: bool) !void {
        try self.events.append(.{
            .timestamp_ns = std.time.nanoTimestamp(),
            .mode = mode,
            .agent_id = agent_id,
            .applied = applied,
            .detail_offset = 0,
            .detail_len = 0,
        });
    }

    /// Get the number of chaos events recorded.
    pub fn eventCount(self: *const ChaosEngine) usize {
        return self.events.items.len;
    }

    /// Get all configs.
    pub fn getConfigs(self: *const ChaosEngine) []const ChaosConfig {
        return self.configs.items;
    }

    /// Enable/disable chaos globally.
    pub fn setEnabled(self: *ChaosEngine, enabled: bool) void {
        self.enabled = enabled;
    }

    /// Clear all recorded events.
    pub fn clearEvents(self: *ChaosEngine) void {
        self.events.clearRetainingCapacity();
        self.detail_buffer.clearRetainingCapacity();
    }
};

// ── Tests ────────────────────────────────────────────────────────

test "ChaosEngine basic init" {
    var engine = ChaosEngine.init(std.testing.allocator, 42);
    defer engine.deinit();
    try std.testing.expect(engine.enabled);
    try std.testing.expectEqual(@as(usize, 0), engine.eventCount());
}

test "ChaosEngine add config and check" {
    var engine = ChaosEngine.init(std.testing.allocator, 12345);
    defer engine.deinit();

    try engine.addConfig(.{
        .mode = .network_delay,
        .target_agent_id = 1,
        .probability = 1.0, // always trigger
        .params = .{ .delay_ms = 500 },
        .enabled = true,
    });

    const delay = engine.getNetworkDelay(1);
    try std.testing.expect(delay > 0);
    try std.testing.expect(delay <= 600); // base ± 20% jitter
}

test "ChaosEngine zero probability never fires" {
    var engine = ChaosEngine.init(std.testing.allocator, 99);
    defer engine.deinit();

    try engine.addConfig(.{
        .mode = .api_error,
        .target_agent_id = 1,
        .probability = 0.0,
        .params = .{ .error_code = 500 },
        .enabled = true,
    });

    // Check many times — should never fire
    var fired: u32 = 0;
    for (0..100) |_| {
        if (engine.getApiError(1) != null) fired += 1;
    }
    try std.testing.expectEqual(@as(u32, 0), fired);
}

test "ChaosEngine disabled does nothing" {
    var engine = ChaosEngine.init(std.testing.allocator, 42);
    defer engine.deinit();

    try engine.addConfig(.{
        .mode = .network_delay,
        .target_agent_id = 1,
        .probability = 1.0,
        .params = .{ .delay_ms = 1000 },
        .enabled = true,
    });

    engine.setEnabled(false);
    const delay = engine.getNetworkDelay(1);
    try std.testing.expectEqual(@as(u64, 0), delay);
}

test "ChaosEngine corrupt response" {
    var engine = ChaosEngine.init(std.testing.allocator, 42);
    defer engine.deinit();

    try engine.addConfig(.{
        .mode = .hallucination,
        .target_agent_id = 1,
        .probability = 1.0,
        .params = .{ .corruption_rate = 0.5 },
        .enabled = true,
    });

    var response = [_]u8{ 'H', 'e', 'l', 'l', 'o', ',', ' ', 'w', 'o', 'r', 'l', 'd' };
    const original = [_]u8{ 'H', 'e', 'l', 'l', 'o', ',', ' ', 'w', 'o', 'r', 'l', 'd' };
    const corrupted = engine.corruptResponse(1, &response);
    try std.testing.expect(corrupted);
    // With 50% corruption rate, at least some chars should differ
    var diffs: u32 = 0;
    for (response, 0..) |c, i| {
        if (c != original[i]) diffs += 1;
    }
    // Statistically, ~6 of 12 should be different, but allow for randomness
    try std.testing.expect(diffs > 0);
}

test "ChaosEngine remove configs for agent" {
    var engine = ChaosEngine.init(std.testing.allocator, 42);
    defer engine.deinit();

    try engine.addConfig(.{ .mode = .network_delay, .target_agent_id = 1, .probability = 1.0, .params = .{ .delay_ms = 100 }, .enabled = true });
    try engine.addConfig(.{ .mode = .api_error, .target_agent_id = 1, .probability = 1.0, .params = .{ .error_code = 500 }, .enabled = true });
    try engine.addConfig(.{ .mode = .network_delay, .target_agent_id = 2, .probability = 1.0, .params = .{ .delay_ms = 200 }, .enabled = true });

    try std.testing.expectEqual(@as(usize, 3), engine.getConfigs().len);
    engine.removeConfigsForAgent(1);
    try std.testing.expectEqual(@as(usize, 1), engine.getConfigs().len);
    try std.testing.expectEqual(@as(u64, 2), engine.getConfigs()[0].target_agent_id);
}
