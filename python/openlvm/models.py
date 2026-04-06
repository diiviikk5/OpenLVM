"""Pydantic data models for configuration and results."""

from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field

class CapabilityConfig(BaseModel):
    network_outbound: bool = False
    fs_read: bool = True
    fs_write: bool = False
    llm_call: bool = True
    tool_use: bool = True
    shared_memory_read: bool = True
    shared_memory_write: bool = False

class AgentConfig(BaseModel):
    entry: str
    capabilities: List[str] = Field(default_factory=lambda: ["llm_call", "tool_use", "fs_read"])
    depends_on: List[str] = Field(default_factory=list)

class ScenarioConfig(BaseModel):
    input: str
    expected_tools: List[str] = Field(default_factory=list)
    expected_behavior: Optional[str] = None

class ChaosParams(BaseModel):
    delay_ms: Optional[int] = None
    probability: Optional[float] = None
    error_code: Optional[int] = None
    corruption_rate: Optional[float] = None

class ChaosConfig(BaseModel):
    type: str
    target: str
    params: ChaosParams

class MetricsConfig(BaseModel):
    deepeval: List[str] = Field(default_factory=list)
    promptfoo: Dict[str, Any] = Field(default_factory=dict)
    custom: List[Dict[str, str]] = Field(default_factory=list)

class EvalStoreConfig(BaseModel):
    compare_with: str = "last_5_runs"
    alert_on_regression: bool = True


class TestSuiteConfig(BaseModel):
    name: str
    version: str = "1.0"
    agents: Dict[str, AgentConfig]
    scenarios: Dict[str, ScenarioConfig]
    chaos: List[ChaosConfig] = Field(default_factory=list)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    eval_store: EvalStoreConfig = Field(default_factory=EvalStoreConfig)

    def to_capability_mask(self, caps_list: List[str]) -> int:
        """Convert a list of string capabilities into a u64 bitmask for Zig core."""
        mask = 0
        cap_map = {
            "network_outbound": 1 << 0,
            "network_inbound": 1 << 1,
            "network_dns": 1 << 2,
            "fs_read": 1 << 3,
            "fs_write": 1 << 4,
            "subprocess_spawn": 1 << 8,
            "llm_call": 1 << 10,
            "tool_use": 1 << 11,
            "shared_memory_write": 1 << 14,
        }
        for cap in caps_list:
            if cap in cap_map:
                mask |= cap_map[cap]
        return mask


class ScenarioRunResult(BaseModel):
    name: str
    fork_id: int
    input: str
    status: str
    score: float
    network_delay_ms: int = 0
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    chaos_effects: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class AgentRunSummary(BaseModel):
    name: str
    agent_id: int
    capabilities: List[str] = Field(default_factory=list)


class EvalRun(BaseModel):
    run_id: str
    suite_name: str
    suite_version: str
    config_path: str
    started_at: str
    completed_at: str
    scenarios_requested: int
    scenarios_executed: int
    chaos_mode: Optional[str] = None
    agent_count: int = 0
    status: str = "completed"
    summary: Dict[str, int] = Field(default_factory=dict)
    agents: List[AgentRunSummary] = Field(default_factory=list)
    results: List[ScenarioRunResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunDiff(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    summary_delta: Dict[str, int] = Field(default_factory=dict)
    score_delta: float = 0.0


class WorkspaceRecord(BaseModel):
    workspace_id: str
    name: str
    description: str = ""
    created_at: str


class CollectionRecord(BaseModel):
    collection_id: str
    workspace_id: str
    name: str
    description: str = ""
    created_at: str


class SavedScenarioRecord(BaseModel):
    scenario_id: str
    collection_id: str
    name: str
    config_path: str
    input_text: str
    created_at: str


class BaselineRecord(BaseModel):
    baseline_id: str
    collection_id: str
    run_id: str
    label: str
    created_at: str
