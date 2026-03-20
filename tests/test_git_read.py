from io import StringIO
from pathlib import Path
import subprocess
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty import cli
from snappy_putty.git_read import execute_git_read, parse_git_read_intent
from snappy_putty.session import LifecycleState, SessionState


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Snappy Test"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "snappy@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("first\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)


def _capture_console(monkeypatch) -> StringIO:
    buffer = StringIO()
    test_console = Console(file=buffer, force_terminal=False, color_system=None)
    monkeypatch.setattr(cli, "console", test_console)
    return buffer


def test_parse_git_read_intent_keeps_vague_status_outside_git_route() -> None:
    assert parse_git_read_intent("status") is None
    assert parse_git_read_intent("show me status") is None


def test_execute_git_read_status_and_log(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")

    status_result = execute_git_read(parse_git_read_intent("git status"), tmp_path)
    commits_result = execute_git_read(parse_git_read_intent("show last 5 commits"), tmp_path)

    assert status_result.ok is True
    assert "##" in status_result.body
    assert "README.md" in status_result.body
    assert commits_result.ok is True
    assert "initial" in commits_result.body


def test_execute_git_read_non_repo_fails_cleanly(tmp_path: Path) -> None:
    result = execute_git_read(parse_git_read_intent("git status"), tmp_path)

    assert result.ok is False
    assert "not a Git repository" in result.body
    assert result.error_message == result.body


def test_git_read_repl_updates_state_on_success(tmp_path: Path, monkeypatch) -> None:
    _init_repo(tmp_path)
    buffer = _capture_console(monkeypatch)
    state = SessionState()

    handled = cli._handle_git_read_repl("git status", tmp_path, state)

    assert handled is True
    assert state.current_state == LifecycleState.IDLE
    assert state.last_route == "git_read"
    assert state.last_completed_goal == "git status"
    assert state.last_result == "Git status retrieved."
    assert state.active_goal is None
    assert "Git Status" in buffer.getvalue()


def test_git_read_repl_updates_failure_bookkeeping(tmp_path: Path, monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState()

    handled = cli._handle_git_read_repl("git status", tmp_path, state)

    assert handled is True
    assert state.current_state == LifecycleState.IDLE
    assert state.last_route == "git_read"
    assert state.last_failed_goal == "git status"
    assert state.error_message == f"{tmp_path} is not a Git repository."
    assert state.last_result == f"{tmp_path} is not a Git repository."
    assert "Git Read Failed" in buffer.getvalue()
