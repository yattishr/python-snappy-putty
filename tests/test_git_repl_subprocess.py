import os
from pathlib import Path
import subprocess
import sys


def _repl_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    return env


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Snappy Test"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "snappy@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)


def test_repl_git_status_and_status_bookkeeping(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="git status\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Git Status" in proc.stdout
    assert "README.md" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Last route: git_read" in proc.stdout
    assert "Last completed goal: git status" in proc.stdout


def test_repl_git_status_outside_repo_fails_and_returns_to_idle(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="git status\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Git Read Failed" in proc.stdout
    assert "Git repository" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Last route: git_read" in proc.stdout
    assert "Last failed goal: git status" in proc.stdout
