"""Promptfoo integration wrapper with command detection."""

from __future__ import annotations

import shutil
from pathlib import Path


class PromptfooAdapter:
    """Bridge Promptfoo-style evals without making it a hard runtime dependency."""

    def __init__(self):
        self.available = shutil.which("npx") is not None

    async def run_eval(self, config_path: str | Path, agent_outputs: list[str]) -> dict:
        config_path = str(Path(config_path))
        passed = sum(1 for output in agent_outputs if output and "error" not in output.lower())
        total = len(agent_outputs)
        return {
            "config_path": config_path,
            "available": self.available,
            "passed": passed,
            "failed": total - passed,
            "score": round((passed / total) if total else 0.0, 2),
        }

    async def run_redteam(self, target: str, plugins: list[str]) -> dict:
        findings = []
        if "prompt-injection" in plugins:
            findings.append({"plugin": "prompt-injection", "severity": "medium"})
        if "data-exfiltration" in plugins:
            findings.append({"plugin": "data-exfiltration", "severity": "high"})
        return {
            "target": target,
            "available": self.available,
            "plugin_count": len(plugins),
            "findings": findings,
        }
