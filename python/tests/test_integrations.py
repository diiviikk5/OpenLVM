import asyncio
import json
import pytest
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


def test_solana_adapter_submit_intent_stub_shape(monkeypatch):
    from openlvm.integrations import SolanaAgentKitAdapter

    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "stub")
    adapter = SolanaAgentKitAdapter()
    result = adapter.submit_onchain_intent(
        intent_commitment="sha256:abc123",
        cluster="devnet",
    )
    assert result["submission_status"] == "simulated_confirmed"
    assert result["signature"]
    assert "explorer.solana.com/tx/" in result["explorer_url"]


def test_solana_adapter_bridge_mode_agentkit_session(monkeypatch):
    from openlvm.integrations import SolanaAgentKitAdapter

    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    adapter = SolanaAgentKitAdapter()
    assert adapter.bridge_mode == "agentkit-session"


def test_solana_adapter_agentkit_mode_requires_endpoint(monkeypatch):
    from openlvm.integrations import SolanaAgentKitAdapter

    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-api-key")
    monkeypatch.delenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", raising=False)
    adapter = SolanaAgentKitAdapter()
    assert adapter.bridge_mode != "agentkit-session"


def test_solana_adapter_real_submission_mode_helper():
    from openlvm.integrations import SolanaAgentKitAdapter

    assert SolanaAgentKitAdapter.is_real_submission_mode("agentkit-session") is True
    assert SolanaAgentKitAdapter.is_real_submission_mode("node-bridge") is False
    assert SolanaAgentKitAdapter.is_real_submission_mode("mvp-local-stub") is False


def test_solana_adapter_session_id_is_forwarded(monkeypatch):
    from openlvm.integrations import SolanaAgentKitAdapter

    calls: list[tuple[str, dict]] = []

    def fake_invoke(self, command, payload):
        calls.append((command, payload))
        if command == "connect_agent":
            return {
                "agent_address": payload["agent_address"],
                "wallet_provider": payload.get("wallet_provider", "embedded"),
                "metadata": {"adapter_mode": "agentkit-session", "session_id": "ak_test_123"},
            }
        if command == "simulate_x402_transfer":
            return {"x402_status": "simulated_settled", "metadata": {"session_id": payload.get("session_id", "")}}
        if command == "submit_onchain_intent":
            return {
                "submission_status": "simulated_confirmed",
                "signature": "sig-test",
                "cluster": payload.get("cluster", "devnet"),
                "explorer_url": "https://explorer.solana.com/tx/sig-test?cluster=devnet",
                "metadata": {"session_id": payload.get("session_id", "")},
            }
        raise AssertionError(f"unexpected command {command}")

    monkeypatch.setattr(SolanaAgentKitAdapter, "_invoke", fake_invoke, raising=True)
    adapter = SolanaAgentKitAdapter()
    adapter.connect_agent(agent_address="AgentPubKey111")
    adapter.simulate_x402_transfer(from_agent="AgentPubKey111", to_agent="arena-pool", amount_usdc=0.05)
    adapter.submit_onchain_intent(intent_commitment="sha256:intent", cluster="devnet")

    transfer_payload = next(payload for command, payload in calls if command == "simulate_x402_transfer")
    submit_payload = next(payload for command, payload in calls if command == "submit_onchain_intent")
    assert transfer_payload["session_id"] == "ak_test_123"
    assert submit_payload["session_id"] == "ak_test_123"


def test_solana_adapter_agentkit_session_via_http_bridge(monkeypatch):
    from openlvm.integrations import SolanaAgentKitAdapter

    calls: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            auth = self.headers.get("Authorization", "")
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            calls.append({"auth": auth, "payload": payload})
            command = payload.get("command", "")
            command_payload = payload.get("payload", {})
            if command == "connect_agent":
                body = {
                    "result": {
                        "agent_address": command_payload.get("agent_address", ""),
                        "wallet_provider": command_payload.get("wallet_provider", "embedded"),
                        "session_id": "ak_http_123",
                        "session_state": "connected",
                    }
                }
            elif command == "simulate_x402_transfer":
                body = {
                    "x402_status": "settled",
                    "amount_usdc": command_payload.get("amount_usdc", 0.0),
                    "tx_ref": "x402-http-tx",
                }
            elif command == "submit_onchain_intent":
                body = {
                    "submission_status": "confirmed",
                    "signature": "httpsig-1",
                    "cluster": command_payload.get("cluster", "devnet"),
                }
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"unknown command"}')
                return

            response = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, _format, *_args):  # noqa: D401
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    deadline = time.time() + 1.5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.02)
    try:
        endpoint = f"http://127.0.0.1:{port}"
        monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
        monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
        monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", endpoint)
        adapter = SolanaAgentKitAdapter()
        identity = adapter.connect_agent(agent_address="AgentPubKeyHTTP111")
        payment = adapter.simulate_x402_transfer(
            from_agent=identity.address,
            to_agent="arena-pool",
            amount_usdc=0.05,
        )
        submission = adapter.submit_onchain_intent(
            intent_commitment="sha256:intent-http",
            cluster="testnet",
        )

        assert adapter.bridge_mode == "agentkit-session"
        assert identity.metadata.get("session_id") == "ak_http_123"
        assert payment["x402_status"] == "settled"
        assert submission["submission_status"] == "confirmed"
        assert submission["signature"] == "httpsig-1"
        assert submission["metadata"]["adapter_mode"] == "agentkit-session"
        assert submission["metadata"]["session_id"] == "ak_http_123"

        assert [call["payload"].get("command") for call in calls] == [
            "connect_agent",
            "simulate_x402_transfer",
            "submit_onchain_intent",
        ]
        assert calls[0]["auth"] == "Bearer test-key"
        assert calls[1]["payload"]["payload"].get("session_id") == "ak_http_123"
        assert calls[2]["payload"]["payload"].get("session_id") == "ak_http_123"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
