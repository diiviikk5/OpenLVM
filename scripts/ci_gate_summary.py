"""Render a concise Markdown summary from OpenLVM CI gate artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _build_summary(artifacts_dir: Path) -> str:
    bundle = _load_json(artifacts_dir / "readiness-bundle.json") or {}
    gate = _load_json(artifacts_dir / "ci-gate.json") or bundle.get("ci_gate") or {}
    doctor = _load_json(artifacts_dir / "doctor.json") or bundle.get("doctor") or gate.get("doctor") or {}
    preflight = (
        _load_json(artifacts_dir / "arena-preflight.json")
        or bundle.get("arena_preflight")
        or gate.get("arena_preflight")
        or {}
    )
    readiness = _load_json(artifacts_dir / "arena-readiness.json") or bundle.get("arena_readiness") or {}

    overall_source = bundle if bundle else gate
    overall = "ok" if overall_source.get("ok") else "fail"
    doctor_ok = "ok" if doctor.get("ok") else "missing"
    preflight_ok = "ok" if preflight.get("ok") else "missing"
    readiness_ok = "ok" if readiness.get("can_real_submission") else "missing"
    doctor_missing = doctor.get("missing") or []
    preflight_missing = [c.get("name") for c in (preflight.get("checks") or []) if c.get("status") != "ok"]
    readiness_reasons = readiness.get("reasons") or []

    lines = [
        "## OpenLVM CI Gate Summary",
        "",
        f"- Overall: **{overall}**",
        f"- Doctor: **{doctor_ok}**",
        f"- Arena readiness: **{readiness_ok}**",
        f"- Arena preflight: **{preflight_ok}**",
        f"- Doctor missing checks: `{', '.join(doctor_missing) if doctor_missing else 'none'}`",
        f"- Readiness reasons: `{', '.join(readiness_reasons) if readiness_reasons else 'none'}`",
        f"- Preflight missing checks: `{', '.join(preflight_missing) if preflight_missing else 'none'}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", default="artifacts", help="Directory containing JSON artifacts")
    parser.add_argument("--output", default="", help="Output markdown path (default: stdout)")
    args = parser.parse_args()

    summary = _build_summary(Path(args.artifacts_dir))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary, encoding="utf-8")
    else:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
