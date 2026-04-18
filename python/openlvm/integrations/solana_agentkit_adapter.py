"""Solana AgentKit integration adapter with Node bridge fallback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SolanaAgentIdentity:
    """Connected Solana agent identity."""

    address: str
    wallet_provider: str
    metadata: dict[str, Any]


class SolanaAgentKitAdapter:
    """Bridge for Solana agent operations through a Node worker, with safe local fallback."""

    def __init__(self):
        self.node = shutil.which("node") or shutil.which("node.exe")
        repo_root = Path(__file__).resolve().parents[3]
        self.bridge_script = Path(
            os.getenv("OPENLVM_SOLANA_BRIDGE_SCRIPT", str(repo_root / "solana" / "agentkit_bridge.mjs"))
        )
        self.bridge_mode_env = os.getenv("OPENLVM_SOLANA_BRIDGE_MODE", "").strip().lower()
        self.agentkit_api_key = os.getenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "").strip()
        self.agentkit_endpoint = os.getenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "").strip()
        timeout_env = os.getenv("OPENLVM_SOLANA_AGENTKIT_TIMEOUT_MS", "").strip()
        self.agentkit_timeout_ms = int(timeout_env) if timeout_env.isdigit() else 15000
        self.force_stub = self.bridge_mode_env == "stub"
        self._session_id: str | None = None

    @property
    def bridge_mode(self) -> str:
        if self.force_stub:
            return "mvp-local-stub"
        if (
            self.bridge_mode_env == "agentkit"
            and self.agentkit_api_key
            and self.agentkit_endpoint
        ):
            return "agentkit-session"
        if self.node and self.bridge_script.exists():
            return "node-bridge"
        return "mvp-local-stub"

    @staticmethod
    def is_real_submission_mode(mode: str) -> bool:
        return str(mode or "").strip().lower() == "agentkit-session"

    def readiness(self) -> dict[str, Any]:
        mode = self.bridge_mode
        can_real_submit = self.is_real_submission_mode(mode)
        issues: list[dict[str, str]] = []
        if self.bridge_mode_env != "agentkit":
            issues.append(
                {
                    "id": "bridge-mode-not-agentkit",
                    "severity": "critical",
                    "message": "OPENLVM_SOLANA_BRIDGE_MODE is not set to agentkit",
                    "fix": "Set OPENLVM_SOLANA_BRIDGE_MODE=agentkit for strict real submission mode",
                    "command": "export OPENLVM_SOLANA_BRIDGE_MODE=agentkit",
                }
            )
        if mode != "agentkit-session" and self.bridge_mode_env == "agentkit":
            if not self.agentkit_api_key:
                issues.append(
                    {
                        "id": "agentkit-api-key-missing",
                        "severity": "critical",
                        "message": "OPENLVM_SOLANA_AGENTKIT_API_KEY is missing",
                        "fix": "Configure your AgentKit API key in environment variables",
                        "command": "export OPENLVM_SOLANA_AGENTKIT_API_KEY=...",
                    }
                )
            if not self.agentkit_endpoint:
                issues.append(
                    {
                        "id": "agentkit-endpoint-missing",
                        "severity": "critical",
                        "message": "OPENLVM_SOLANA_AGENTKIT_ENDPOINT is missing",
                        "fix": "Configure your AgentKit endpoint in environment variables",
                        "command": "export OPENLVM_SOLANA_AGENTKIT_ENDPOINT=https://...",
                    }
                )
        if not self.bridge_script.exists():
            issues.append(
                {
                    "id": "bridge-script-missing",
                    "severity": "warning",
                    "message": f"bridge script not found: {self.bridge_script}",
                    "fix": "Restore solana/agentkit_bridge.mjs or set OPENLVM_SOLANA_BRIDGE_SCRIPT",
                    "command": "export OPENLVM_SOLANA_BRIDGE_SCRIPT=/absolute/path/to/agentkit_bridge.mjs",
                }
            )
        if not self.node and mode != "agentkit-session":
            issues.append(
                {
                    "id": "node-not-available",
                    "severity": "warning",
                    "message": "node is not available on PATH",
                    "fix": "Install Node.js if you want node-bridge mode fallback",
                    "command": "node --version",
                }
            )
        if not can_real_submit and not any(issue["id"] == "bridge-mode-not-agentkit" for issue in issues):
            issues.append(
                {
                    "id": "agentkit-session-inactive",
                    "severity": "warning",
                    "message": "AgentKit session mode is not active",
                    "fix": "Run arena-readiness and arena-preflight to identify blocking configuration",
                    "command": "python -m openlvm.cli arena-preflight --json",
                }
            )
        reasons = [issue["message"] for issue in issues]
        readiness_score = 100
        for issue in issues:
            if issue["severity"] == "critical":
                readiness_score -= 40
            elif issue["severity"] == "warning":
                readiness_score -= 15
            else:
                readiness_score -= 5
        readiness_score = max(0, readiness_score)
        next_actions: list[str] = []
        for issue in issues:
            command = issue.get("command", "").strip()
            if command and command not in next_actions:
                next_actions.append(command)
        return {
            "adapter_mode": mode,
            "can_real_submission": can_real_submit,
            "bridge_script": str(self.bridge_script),
            "reasons": reasons,
            "issues": issues,
            "next_actions": next_actions,
            "readiness_score": readiness_score,
        }

    def connect_agent(
        self,
        *,
        agent_address: str,
        wallet_provider: str = "embedded",
        private_key: str | None = None,
    ) -> SolanaAgentIdentity:
        if not agent_address.strip():
            raise ValueError("agent_address is required")
        payload = self._invoke(
            "connect_agent",
            {
                "agent_address": agent_address.strip(),
                "wallet_provider": wallet_provider.strip() or "embedded",
                "private_key": private_key or "",
            },
        )
        metadata = payload.get("metadata", {})
        session_id = metadata.get("session_id")
        self._session_id = str(session_id).strip() if session_id else None
        return SolanaAgentIdentity(
            address=payload["agent_address"],
            wallet_provider=payload["wallet_provider"],
            metadata=metadata,
        )

    def simulate_x402_transfer(
        self,
        *,
        from_agent: str,
        to_agent: str,
        amount_usdc: float,
    ) -> dict[str, Any]:
        payload = self._invoke(
            "simulate_x402_transfer",
            {
                "from_agent": from_agent,
                "to_agent": to_agent,
                "amount_usdc": float(amount_usdc),
                "session_id": self._session_id or "",
            },
        )
        return payload

    def submit_onchain_intent(
        self,
        *,
        intent_commitment: str,
        cluster: str = "devnet",
    ) -> dict[str, Any]:
        payload = self._invoke(
            "submit_onchain_intent",
            {
                "intent_commitment": intent_commitment,
                "cluster": cluster,
                "session_id": self._session_id or "",
            },
        )
        return payload

    def _invoke(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.force_stub and self.bridge_mode_env == "agentkit" and self.agentkit_api_key and self.agentkit_endpoint:
            try:
                return self._invoke_agentkit_http(command, payload)
            except (ValueError, OSError, urllib.error.URLError):
                pass
        if not self.force_stub and self.node and self.bridge_script.exists():
            try:
                proc = subprocess.run(
                    [self.node, str(self.bridge_script), command, json.dumps(payload)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    result = json.loads(proc.stdout)
                    if "error" not in result:
                        return result
            except OSError:
                pass
        return self._stub(command, payload)

    def _invoke_agentkit_http(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        request_body = json.dumps({"command": command, "payload": payload}).encode("utf-8")
        request = urllib.request.Request(
            self.agentkit_endpoint,
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agentkit_api_key}",
            },
            method="POST",
        )
        timeout_s = max(self.agentkit_timeout_ms, 1) / 1000.0
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            raw_payload: dict[str, Any] = {}
            if body:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    raw_payload = parsed
            result = raw_payload.get("result") if isinstance(raw_payload.get("result"), dict) else raw_payload
            if not isinstance(result, dict):
                raise ValueError("agentkit response payload must be an object")
            return self._normalize_agentkit_response(command, payload, result)

    def _normalize_agentkit_response(
        self,
        command: str,
        request_payload: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = result.get("metadata")
        metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
        if command == "connect_agent":
            session_id = str(result.get("session_id") or metadata_dict.get("session_id") or "").strip()
            if not session_id:
                raise ValueError("agentkit connect response missing session_id")
            return {
                "agent_address": str(result.get("agent_address") or request_payload.get("agent_address") or ""),
                "wallet_provider": str(result.get("wallet_provider") or request_payload.get("wallet_provider") or "embedded"),
                "metadata": {
                    **metadata_dict,
                    "private_key_supplied": bool(request_payload.get("private_key")),
                    "adapter_mode": "agentkit-session",
                    "session_id": session_id,
                    "session_state": str(result.get("session_state") or metadata_dict.get("session_state") or "connected"),
                    "agentkit_endpoint": self.agentkit_endpoint,
                },
            }
        if command == "simulate_x402_transfer":
            session_id = str(request_payload.get("session_id") or result.get("session_id") or metadata_dict.get("session_id") or "")
            return {
                "x402_status": str(result.get("x402_status") or "settled"),
                "amount_usdc": float(result.get("amount_usdc", request_payload.get("amount_usdc", 0.0))),
                "tx_ref": str(result.get("tx_ref") or ""),
                "metadata": {
                    **metadata_dict,
                    "adapter_mode": "agentkit-session",
                    "session_id": session_id,
                    "from_agent": request_payload.get("from_agent", ""),
                    "to_agent": request_payload.get("to_agent", ""),
                    "agentkit_endpoint": self.agentkit_endpoint,
                },
            }
        if command == "submit_onchain_intent":
            signature = str(result.get("signature") or "").strip()
            if not signature:
                raise ValueError("agentkit submit response missing signature")
            cluster = str(result.get("cluster") or request_payload.get("cluster") or "devnet")
            session_id = str(request_payload.get("session_id") or result.get("session_id") or metadata_dict.get("session_id") or "")
            return {
                "submission_status": str(result.get("submission_status") or "confirmed"),
                "signature": signature,
                "cluster": cluster,
                "explorer_url": str(
                    result.get("explorer_url") or f"https://explorer.solana.com/tx/{signature}?cluster={cluster}"
                ),
                "metadata": {
                    **metadata_dict,
                    "adapter_mode": "agentkit-session",
                    "session_id": session_id,
                    "agentkit_endpoint": self.agentkit_endpoint,
                },
            }
        raise ValueError(f"unknown bridge command: {command}")

    @staticmethod
    def _stub(command: str, payload: dict[str, Any]) -> dict[str, Any]:
        if command == "connect_agent":
            return {
                "agent_address": payload["agent_address"],
                "wallet_provider": payload.get("wallet_provider", "embedded"),
                "metadata": {
                    "private_key_supplied": bool(payload.get("private_key")),
                    "adapter_mode": "mvp-local-stub",
                },
            }
        if command == "simulate_x402_transfer":
            amount = float(payload.get("amount_usdc", 0.0))
            return {
                "x402_status": "simulated_settled",
                "amount_usdc": amount,
                "tx_ref": f"sim-x402-{payload.get('from_agent', 'from')[:6]}-{payload.get('to_agent', 'to')[:6]}",
                "metadata": {
                    "adapter_mode": "mvp-local-stub",
                    "from_agent": payload.get("from_agent", ""),
                    "to_agent": payload.get("to_agent", ""),
                },
            }
        if command == "submit_onchain_intent":
            commitment = str(payload.get("intent_commitment", "")).strip()
            if not commitment:
                raise ValueError("intent_commitment is required")
            cluster = str(payload.get("cluster", "devnet") or "devnet")
            signature = f"simsig-{commitment.replace(':', '')[:24]}"
            return {
                "submission_status": "simulated_confirmed",
                "signature": signature,
                "cluster": cluster,
                "explorer_url": f"https://explorer.solana.com/tx/{signature}?cluster={cluster}",
                "metadata": {
                    "adapter_mode": "mvp-local-stub",
                },
            }
        raise ValueError(f"unknown bridge command: {command}")
