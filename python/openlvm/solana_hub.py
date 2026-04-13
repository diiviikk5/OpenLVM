"""Solana integration hub helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def _registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "solana" / "integrations" / "registry.json"


def load_solana_integrations() -> list[dict[str, Any]]:
    payload = json.loads(_registry_path().read_text(encoding="utf-8"))
    rows = payload.get("integrations", [])
    return [row for row in rows if isinstance(row, dict)]


def integration_readiness(row: dict[str, Any]) -> dict[str, Any]:
    required_tools = [str(token) for token in row.get("required_tools", [])]
    missing = [tool for tool in required_tools if shutil.which(tool) is None]
    ready = len(missing) == 0
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "kind": row.get("kind", ""),
        "status": row.get("status", "unknown"),
        "required_tools": required_tools,
        "ready": ready,
        "missing_tools": missing,
    }
