"""Helpers for Solana Arena run metadata."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_trace_commitment(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
