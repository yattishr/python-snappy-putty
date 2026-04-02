from __future__ import annotations

import shutil
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "agent_runtime"


def load_agent_fixture(name: str, destination: Path) -> Path:
    source = FIXTURE_ROOT / name
    if not source.is_dir():
        raise FileNotFoundError(f"Unknown agent fixture: {name}")

    target = destination / ".snappy"
    shutil.copytree(source, target)
    return target
