"""Helpers for Solana Arena run metadata."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_trace_commitment(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_onchain_intent(
    *,
    agent_address: str,
    scenario_id: str,
    score: float,
    status: str,
    payment: dict[str, Any],
    trace_commitment: str,
    cluster: str = "devnet",
    arena_program_hint: str = "openlvm-arena-v1",
) -> dict[str, Any]:
    """Build deterministic transaction intent payload for eventual Solana settlement."""
    tx_intent = {
        "intent_type": "x402_settle_and_commit",
        "amount_usdc": float(payment.get("amount_usdc", 0.0)),
        "payment_ref": str(payment.get("tx_ref", "")),
        "result_status": status,
        "score_bps": max(0, min(10_000, int(round(float(score) * 10_000)))),
    }
    seed_bundle = {
        "namespace": "openlvm",
        "agent_address": agent_address,
        "scenario_id": scenario_id,
        "trace_commitment": trace_commitment,
    }
    intent_commitment = build_trace_commitment(
        {
            "seed_bundle": seed_bundle,
            "tx_intent": tx_intent,
            "cluster": cluster,
            "arena_program_hint": arena_program_hint,
        }
    )
    return {
        "schema": "openlvm.arena.intent.v1",
        "cluster": cluster,
        "arena_program_hint": arena_program_hint,
        "seed_bundle": seed_bundle,
        "tx_intent": tx_intent,
        "intent_commitment": intent_commitment,
    }
