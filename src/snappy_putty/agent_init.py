from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InitAgentResult:
    created: bool
    agent_root: Path
    manifest_path: Path
    message: str


def init_agent_project(cwd: Path | None = None, *, force: bool = False) -> InitAgentResult:
    root = (cwd or Path.cwd()).resolve()
    agent_root = root / ".snappy"
    manifest_path = agent_root / "snappy.yaml"

    if agent_root.exists() and not force:
        return InitAgentResult(
            created=False,
            agent_root=agent_root,
            manifest_path=manifest_path,
            message="Refusing to overwrite existing .snappy/. Re-run with --force to replace scaffold files.",
        )

    agent_root.mkdir(parents=True, exist_ok=True)
    for name in ("skills", "rules", "memory"):
        (agent_root / name).mkdir(exist_ok=True)

    manifest_path.write_text(_default_manifest(root), encoding="utf-8")
    return InitAgentResult(
        created=True,
        agent_root=agent_root,
        manifest_path=manifest_path,
        message=f"Initialized agent scaffold at {agent_root}",
    )


def _default_manifest(root: Path) -> str:
    project_name = root.name or "snappy-project"
    return (
        f"name: {project_name}\n"
        "version: 1\n"
        "mode: supervised\n"
        "confirmations: true\n"
        "dry_run: false\n"
        "skills: []\n"
        "rules: []\n"
        "memory: true\n"
    )
