"""Solana AgentKit integration adapter with Node bridge fallback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        self.force_stub = os.getenv("OPENLVM_SOLANA_BRIDGE_MODE", "").strip().lower() == "stub"

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
        return SolanaAgentIdentity(
            address=payload["agent_address"],
            wallet_provider=payload["wallet_provider"],
            metadata=payload.get("metadata", {}),
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
            },
        )
        return payload

    def _invoke(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
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
        raise ValueError(f"unknown bridge command: {command}")
