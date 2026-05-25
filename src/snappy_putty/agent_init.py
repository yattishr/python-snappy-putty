from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from snappy_putty.config import init_project_config


@dataclass(frozen=True)
class InitAgentResult:
    created: bool
    agent_root: Path
    manifest_path: Path
    message: str


def init_agent_project(cwd: Path | None = None, *, force: bool = False) -> InitAgentResult:
    _ = force
    root = (cwd or Path.cwd()).resolve()
    agent_root = root / ".snappy"
    manifest_path = agent_root / "snappy.yaml"

    agent_root.mkdir(parents=True, exist_ok=True)
    for name in ("skills", "memory", "logs"):
        (agent_root / name).mkdir(exist_ok=True)

    result = init_project_config(root)
    return InitAgentResult(
        created=result.changed,
        agent_root=agent_root,
        manifest_path=manifest_path,
        message=result.message,
    )
