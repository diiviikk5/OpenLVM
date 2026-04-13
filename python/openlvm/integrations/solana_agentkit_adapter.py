"""Solana AgentKit integration adapter (MVP stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SolanaAgentIdentity:
    """Connected Solana agent identity."""

    address: str
    wallet_provider: str
    metadata: dict[str, Any]


class SolanaAgentKitAdapter:
    """Bridge for Solana agent connections until full AgentKit runtime is wired."""

    def connect_agent(
        self,
        *,
        agent_address: str,
        wallet_provider: str = "embedded",
        private_key: str | None = None,
    ) -> SolanaAgentIdentity:
        if not agent_address.strip():
            raise ValueError("agent_address is required")
        return SolanaAgentIdentity(
            address=agent_address.strip(),
            wallet_provider=wallet_provider.strip() or "embedded",
            metadata={
                "private_key_supplied": bool(private_key),
                "adapter_mode": "mvp-local",
            },
        )
