import asyncio

from openlvm.integrations import DeepEvalAdapter, OpenLLMetryAdapter, PromptfooAdapter


def test_deepeval_adapter_returns_requested_metrics():
    adapter = DeepEvalAdapter()
    result = asyncio.run(adapter.evaluate("tool plan completed", ["TaskCompletionMetric", "PlanAdherenceMetric"]))
    assert set(result) == {"TaskCompletionMetric", "PlanAdherenceMetric"}


def test_promptfoo_adapter_produces_summary():
    adapter = PromptfooAdapter()
    result = asyncio.run(adapter.run_eval("examples/swarm.yaml", ["ok", "error"]))
    assert result["passed"] == 1
    assert result["failed"] == 1


def test_openllmetry_adapter_instruments_trace_shape():
    adapter = OpenLLMetryAdapter()
    trace = adapter.instrument_fork(42)
    assert trace["fork_handle"] == 42
    assert trace["trace_name"] == "openlvm-fork-42"
