from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import shutil
import subprocess


DEFAULT_TOOLS = ("git", "docker", "gcloud", "kubectl", "terraform")


@dataclass(frozen=True)
class ContextSnapshot:
    os_name: str
    platform_info: str
    cwd: str
    in_git_repo: bool
    git_branch: str | None
    git_state: str | None
    tools: dict[str, bool]
    project_types: list[str]


def detect_tools(tools: tuple[str, ...] = DEFAULT_TOOLS) -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in tools}


def detect_project_types(cwd: Path) -> list[str]:
    markers = ("Dockerfile", "package.json", "pyproject.toml")
    return [marker for marker in markers if (cwd / marker).exists()]


def git_status(cwd: Path) -> tuple[bool, str | None, str | None]:
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False, None, None

    if inside.returncode != 0 or inside.stdout.strip().lower() != "true":
        return False, None, None

    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    branch_name = branch.stdout.strip() if branch.returncode == 0 and branch.stdout.strip() else "unknown"

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return True, branch_name, "unknown"

    result = status.stdout.strip()
    return True, branch_name, "dirty" if result else "clean"


def collect_context(cwd: Path | None = None) -> ContextSnapshot:
    active_cwd = cwd or Path.cwd()
    in_repo, branch, state = git_status(active_cwd)
    system_name = platform.system()
    release = platform.release()
    return ContextSnapshot(
        os_name=f"{system_name} {release}",
        platform_info=platform.platform(),
        cwd=str(active_cwd),
        in_git_repo=in_repo,
        git_branch=branch,
        git_state=state,
        tools=detect_tools(),
        project_types=detect_project_types(active_cwd),
    )
