"""
YAML configuration parser for test suites.
"""

import yaml
from pathlib import Path
from .models import TestSuiteConfig

def load_config(path: str | Path) -> TestSuiteConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return TestSuiteConfig(**data)
