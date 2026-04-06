from pathlib import Path

import pytest
from typer.testing import CliRunner

from openlvm.cli import app


runner = CliRunner()
zig_dll = Path(__file__).resolve().parents[2] / "core" / "zig-out" / "bin" / "openlvm.dll"


@pytest.mark.skipif(not zig_dll.exists(), reason="Zig runtime library is not built")
def test_cli_test_runs_with_zig_backend(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "zig")
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    result = runner.invoke(app, ["test", str(config_path), "--scenarios", "2", "--chaos", "network_delay"])

    assert result.exit_code == 0
    assert "Run complete:" in result.stdout
    assert "Warnings:" in result.stdout
