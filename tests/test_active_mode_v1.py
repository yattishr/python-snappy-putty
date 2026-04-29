from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from snappy_putty.active_planner import LLMPlanValidationError, PlanningMode, validate_llm_plan
from snappy_putty.project_inspector import inspect_project


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    env["SNAPPY_AGENT_MODE"] = "active"
    return env


def test_inspect_project_creates_project_snapshot_and_history(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "inspect", "project"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    snapshot_path = tmp_path / ".snappy" / "memory" / "project_snapshot.json"
    history_path = tmp_path / ".snappy" / "memory" / "history.md"
    assert snapshot_path.is_file()
    assert history_path.is_file()

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["root_path"] == str(tmp_path.resolve())
    assert "README.md" in snapshot["docs"]
    assert "pyproject.toml" in snapshot["config_files"]
    assert "src/app.py" in snapshot["source_files"]
    assert "project inspection completed" in history_path.read_text(encoding="utf-8")


def test_active_mode_plan_is_invalidated_when_snapshot_changes(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    cli_path = src_dir / "cli.py"
    cli_path.write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    first = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me add logging to the CLI"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert first.returncode == 0
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["current_plan"]["based_on_snapshot_id"]
    assert session["current_plan"]["status"] == "awaiting_confirmation"

    cli_path.write_text("print('changed')\n", encoding="utf-8")

    second = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "show", "plan"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert second.returncode == 0
    assert "Stored plan was based on an outdated project snapshot and was invalidated." in second.stdout
    updated_session = json.loads(session_path.read_text(encoding="utf-8"))
    assert updated_session["current_plan"]["status"] == "invalidated"


def test_validate_llm_plan_accepts_grounded_response(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (src_dir / "session.py").write_text("STATE = 'ok'\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    raw_plan = {
        "goal": "Add logging to the CLI",
        "summary": "Introduce lightweight logging around command handling.",
        "based_on_snapshot_id": snapshot.snapshot_id,
        "files_inspected": ["src/snappy_putty/cli.py", "src/snappy_putty/session.py"],
        "steps": [
            {
                "description": "Identify CLI entry points and workflow transitions where logging is useful.",
                "files": ["src/snappy_putty/cli.py", "src/snappy_putty/session.py"],
                "proposed_new_files": [],
                "risk": "LOW",
                "requires_confirmation": True,
            }
        ],
        "risks": ["Logging could alter visible CLI output if not kept separate from terminal rendering."],
        "assumptions": ["The project prefers minimal dependencies."],
    }

    plan = validate_llm_plan(raw_plan, snapshot, tmp_path)

    assert plan.mode == PlanningMode.LLM_ASSISTED.value
    assert plan.status == "awaiting_confirmation"
    assert plan.based_on_snapshot_id == snapshot.snapshot_id
    assert plan.files_inspected == ["src/snappy_putty/cli.py", "src/snappy_putty/session.py"]


def test_validate_llm_plan_rejects_hallucinated_files(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    raw_plan = {
        "goal": "Add logging to the CLI",
        "summary": "Introduce lightweight logging around command handling.",
        "files_inspected": ["src/fake.py"],
        "steps": [
            {
                "description": "Inspect the fake module.",
                "files": ["src/fake.py"],
                "proposed_new_files": [],
                "risk": "LOW",
                "requires_confirmation": True,
            }
        ],
        "risks": [],
        "assumptions": [],
    }

    try:
        validate_llm_plan(raw_plan, snapshot, tmp_path)
    except LLMPlanValidationError as exc:
        assert "Referenced file does not exist" in str(exc)
    else:
        raise AssertionError("Expected hallucinated file rejection")


def test_validate_llm_plan_rejects_stale_snapshot(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    (tmp_path / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    raw_plan = {
        "goal": "Add logging to the CLI",
        "summary": "Introduce lightweight logging around command handling.",
        "files_inspected": ["src/app.py"],
        "steps": [
            {
                "description": "Inspect the application entry point.",
                "files": ["src/app.py"],
                "proposed_new_files": [],
                "risk": "LOW",
                "requires_confirmation": True,
            }
        ],
        "risks": [],
        "assumptions": [],
    }

    try:
        validate_llm_plan(raw_plan, snapshot, tmp_path)
    except LLMPlanValidationError as exc:
        assert "Project snapshot is stale" in str(exc)
    else:
        raise AssertionError("Expected stale snapshot rejection")


def test_validate_llm_plan_rejects_unsafe_instruction(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    raw_plan = {
        "goal": "Add logging to the CLI",
        "summary": "Introduce lightweight logging around command handling.",
        "files_inspected": ["src/app.py"],
        "steps": [
            {
                "description": "Run rm -rf on the repository root.",
                "files": ["src/app.py"],
                "proposed_new_files": [],
                "risk": "HIGH",
                "requires_confirmation": True,
            }
        ],
        "risks": [],
        "assumptions": [],
    }

    try:
        validate_llm_plan(raw_plan, snapshot, tmp_path)
    except LLMPlanValidationError as exc:
        assert "unsafe instruction" in str(exc).lower()
    else:
        raise AssertionError("Expected unsafe instruction rejection")


def test_status_reports_plan_provenance(tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me add logging to the CLI"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )

    from snappy_putty.cli import _handle_status
    from snappy_putty.session import SessionState

    state = SessionState(agent_mode="active")
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        _handle_status(state)
    finally:
        os.chdir(cwd)

    captured = capsys.readouterr()
    assert "Snapshot valid: yes" in captured.out
    assert "Last plan: present" in captured.out
    assert "Last plan mode: deterministic" in captured.out
    assert "Last plan status: awaiting_confirmation" in captured.out
