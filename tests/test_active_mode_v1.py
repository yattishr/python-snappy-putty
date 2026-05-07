from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from snappy_putty import active_planner, agent as agent_module
from snappy_putty.active_planner import LLMPlanValidationError, PlanningMode, validate_llm_plan
from snappy_putty.project_inspector import inspect_project


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    env["SNAPPY_AGENT_MODE"] = "active"
    env.pop("OPENAI_API_KEY", None)
    return env


def _llm_env() -> dict[str, str]:
    env = _env()
    env["SNAPPY_PUTTY_MOCK_LLM_PLAN"] = "1"
    return env


def _llm_failure_env() -> dict[str, str]:
    env = _env()
    env["SNAPPY_PUTTY_MOCK_LLM_FAILURE"] = "1"
    return env


def _llm_unavailable_env() -> dict[str, str]:
    env = _env()
    env.pop("SNAPPY_PUTTY_MOCK_LLM_PLAN", None)
    env.pop("SNAPPY_PUTTY_MOCK_LLM_FAILURE", None)
    env.pop("OPENAI_API_KEY", None)
    return env


def _off_env() -> dict[str, str]:
    env = _env()
    env["SNAPPY_AGENT_MODE"] = "off"
    return env


def test_grounded_llm_planner_uses_same_session_mode_capability_check(monkeypatch) -> None:
    seen_session_modes: list[str | None] = []

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            pass

    class FakeRunner:
        pass

    monkeypatch.setattr(
        agent_module,
        "is_llm_available",
        lambda session_mode=None: seen_session_modes.append(session_mode) or True,
    )
    monkeypatch.setattr(agent_module, "Agent", FakeAgent)
    monkeypatch.setattr(agent_module, "Runner", FakeRunner)

    client = active_planner.default_llm_planner_client(session_mode="active")

    assert client is not None
    assert seen_session_modes == ["active"]


def test_cli_goal_context_selection_prioritizes_actual_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'taskcli'\n[project.scripts]\ntaskcli = 'taskcli.main:main'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "taskcli"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text(
        "import typer\nfrom .tasks import list_tasks\n\napp = typer.Typer()\n\n"
        "def main():\n    app()\n\nif __name__ == \"__main__\":\n    main()\n",
        encoding="utf-8",
    )
    (src_dir / "tasks.py").write_text("def list_tasks():\n    return []\n", encoding="utf-8")
    (src_dir / "storage.py").write_text("def load_tasks():\n    return []\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_tasks.py").write_text("def test_tasks():\n    assert True\n", encoding="utf-8")
    (tests_dir / "test_storage.py").write_text("def test_storage():\n    assert True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Task CLI\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    selected = active_planner._select_deterministic_files("help me improve this CLI", snapshot)

    assert selected[0] == "src/taskcli/main.py"
    assert "src/taskcli/tasks.py" in selected
    assert "src/taskcli/storage.py" in selected
    assert "tests/test_tasks.py" in selected
    assert "tests/test_storage.py" in selected
    assert "README.md" in selected
    assert "pyproject.toml" not in selected


def test_cli_goal_context_selection_supports_node_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"bin": {"taskcli": "./src/cli.js"}}\n', encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "cli.js").write_text(
        "#!/usr/bin/env node\nconst commands = require('./commands')\ncommands.run(process.argv.slice(2))\n",
        encoding="utf-8",
    )
    (src_dir / "commands.js").write_text("exports.run = function run(args) { return args }\n", encoding="utf-8")
    (src_dir / "store.js").write_text("exports.load = function load() { return [] }\n", encoding="utf-8")
    (tmp_path / "commands.test.js").write_text("test('commands', () => {})\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Task CLI\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    selected = active_planner._select_deterministic_files("help me improve this CLI", snapshot)

    assert selected[0] == "src/cli.js"
    assert "src/commands.js" in selected
    assert "package.json" not in selected[:2]


def test_cli_goal_context_selection_supports_go_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/taskcli\n", encoding="utf-8")
    cmd_dir = tmp_path / "cmd" / "taskcli"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text(
        'package main\n\nimport "flag"\n\nfunc main() {\n    flag.Parse()\n}\n',
        encoding="utf-8",
    )
    (cmd_dir / "commands.go").write_text("package main\n\nfunc runCommand() {}\n", encoding="utf-8")
    (tmp_path / "commands_test.go").write_text("package main\n\nfunc TestCommands(t *testing.T) {}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Task CLI\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    selected = active_planner._select_deterministic_files("help me improve this terminal command", snapshot)

    assert selected[0] == "cmd/taskcli/main.go"
    assert "cmd/taskcli/commands.go" in selected
    assert "go.mod" not in selected[:2]


def test_llm_plan_for_cli_goal_references_actual_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'taskcli'\n[project.scripts]\ntaskcli = 'taskcli.main:main'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "taskcli"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text(
        "import typer\nfrom .tasks import list_tasks\n\napp = typer.Typer()\n\n"
        "def main():\n    app()\n\nif __name__ == \"__main__\":\n    main()\n",
        encoding="utf-8",
    )
    (src_dir / "tasks.py").write_text("def list_tasks():\n    return []\n", encoding="utf-8")
    (src_dir / "storage.py").write_text("def load_tasks():\n    return []\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_tasks.py").write_text("def test_tasks():\n    assert True\n", encoding="utf-8")
    (tests_dir / "test_storage.py").write_text("def test_storage():\n    assert True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Task CLI\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nshow plan\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Pending plan: llm_assisted plan with" in proc.stdout
    assert "Last plan status: awaiting_confirmation" in proc.stdout
    assert "src/taskcli/main.py" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "src/taskcli/main.py" in session["current_plan"]["files_inspected"]
    assert "src/taskcli/main.py" in session["current_plan"]["steps"][0]["files"]


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
        env=_llm_env(),
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
    assert "Plan invalidated: snapshot_changed" in second.stdout
    updated_session = json.loads(session_path.read_text(encoding="utf-8"))
    assert updated_session["current_plan"]["status"] == "invalidated"
    assert updated_session["current_plan"]["invalidation_reason"] == "snapshot_changed"


def test_history_logging_does_not_invalidate_active_plan_in_git_repo(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, text=True, capture_output=True, timeout=20, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, text=True, capture_output=True, timeout=20, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )

    create = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me improve this CLI"],
        cwd=tmp_path,
        env=_llm_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert create.returncode == 0

    show = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "show", "plan"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert show.returncode == 0
    assert "Plan invalidated:" not in show.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["status"] == "awaiting_confirmation"


def test_plan_validation_reports_missing_snapshot_reason(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "summarize README.md"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    (tmp_path / ".snappy" / "memory" / "project_snapshot.json").unlink()

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "show", "plan"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Plan invalidated: missing_snapshot" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["invalidation_reason"] == "missing_snapshot"


def test_plan_validation_reports_snapshot_mismatch_reason(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "summarize README.md"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["current_plan"]["based_on_snapshot_id"] = "snap_mismatch"
    session["last_plan"] = session["current_plan"]
    session_path.write_text(json.dumps(session), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "show", "plan"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Plan invalidated: plan_snapshot_mismatch" in proc.stdout
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["current_plan"]["invalidation_reason"] == "plan_snapshot_mismatch"


def test_plan_interaction_commands_share_invalidation_check(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    cli_path = src_dir / "cli.py"
    cli_path.write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me improve this CLI"],
        cwd=tmp_path,
        env=_llm_env(),
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    cli_path.write_text("print('changed')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="why this plan\nexplain step 1\nrefine plan keep scope tight\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert proc.stdout.count("Plan invalidated: snapshot_changed") == 3
    assert "Cannot refine an invalidated plan." in proc.stdout


def test_active_mode_rejects_irrelevant_goal_without_creating_plan(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me build a rocketship"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "does not appear to be related to the current project" in proc.stdout
    assert "No project plan was created." in proc.stdout
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert "current_plan" not in session
    assert session["last_skipped_goal"] == "help me build a rocketship"
    assert session["last_skip_reason"] == "goal_not_project_related"
    history_path = tmp_path / ".snappy" / "memory" / "history.md"
    assert "Planning skipped" in history_path.read_text(encoding="utf-8")


def test_broad_developer_goal_with_llm_unavailable_creates_deterministic_plan(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Generating deterministic grounded plan from inspected project context" in proc.stdout
    assert "LLM-assisted planning is unavailable" not in proc.stdout
    assert "Apply the smallest project change" in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Active goal: help me improve this CLI" in proc.stdout
    assert "Pending plan: deterministic plan with" in proc.stdout
    assert "Awaiting confirmation: no" in proc.stdout
    assert "Last skipped goal: (none)" in proc.stdout
    assert "Last skip reason: (none)" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["goal"] == "help me improve this CLI"
    assert session["current_plan"]["mode"] == PlanningMode.DETERMINISTIC.value
    assert session["last_plan"]["mode"] == PlanningMode.DETERMINISTIC.value
    assert "last_skipped_goal" not in session
    assert "last_skip_reason" not in session


def test_active_mode_without_llm_capability_creates_deterministic_plan(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_unavailable_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "LLM-assisted planning is unavailable" not in proc.stdout
    assert "Apply the smallest project change" in proc.stdout
    assert "Pending plan: deterministic plan with" in proc.stdout
    assert "Last skip reason: (none)" in proc.stdout


def test_agent_mode_off_broad_developer_goal_does_not_trigger_planning(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_off_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Active planning is off." in proc.stdout
    assert "Broad developer goals require active LLM-assisted planning." in proc.stdout
    assert "No project plan was created." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout


def test_non_project_general_question_exits_cleanly(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="what is the movie Interstellar about?\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "This looks like a general question, not a project task." in proc.stdout
    assert "No project plan was created." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Last skip reason: non_project_question" in proc.stdout


def test_current_info_question_exits_cleanly(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="what is the price of bitcoin?\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "This looks like a current information request, not a project task." in proc.stdout
    assert "current-info tools are enabled" in proc.stdout
    assert "No project plan was created." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Last skip reason: unsupported_current_info_question" in proc.stdout


def test_rejected_grounded_planning_resets_workflow_state(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me build a rocketship\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "This request does not appear to be related to the current project." in proc.stdout
    assert "I did not create a grounded project plan because there is no clear connection" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Awaiting confirmation: no" in proc.stdout
    assert "Last blocked goal: (none)" in proc.stdout
    assert "Last skipped goal: help me build a rocketship" in proc.stdout
    assert "Last skip reason: goal_not_project_related" in proc.stdout
    assert "Error message: (none)" in proc.stdout


def test_second_rejected_request_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me build a rocketship\nhelp me create a fitness routine\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "ActiveGoalConflictError" not in proc.stdout
    assert "fitness routine" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout


def test_valid_project_request_still_works_after_rejection(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me build a rocketship\nhelp me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "This request does not appear to be related to the current project." in proc.stdout
    assert "Grounded Plan" in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Last skipped goal: (none)" in proc.stdout
    assert "Last skip reason: (none)" in proc.stdout
    assert "Last plan status: awaiting_confirmation" in proc.stdout


def test_active_mode_creates_plan_for_readme_reference(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "summarize README.md"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["current_plan"]["based_on_snapshot_id"]
    assert session["current_plan"]["status"] == "awaiting_confirmation"
    assert "README.md" in session["current_plan"]["files_inspected"]


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
        env=_llm_env(),
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
    assert "Last plan mode: llm_assisted" in captured.out
    assert "Last plan status: awaiting_confirmation" in captured.out


def test_active_shell_status_uses_grounded_plan_label(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Pending plan: llm_assisted plan with" in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Last plan status: awaiting_confirmation" in proc.stdout
    assert "agent plan" not in proc.stdout.lower()


def test_plan_interaction_show_why_and_explain_step(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nshow plan\nwhy this plan\nexplain step 1\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Goal: help me improve this CLI" in proc.stdout
    assert "Mode:" in proc.stdout
    assert "Snapshot ID:" in proc.stdout
    assert "Why files were selected:" in proc.stdout
    assert "Why steps exist:" in proc.stdout
    assert "What it does:" in proc.stdout
    assert "Files touched:" in proc.stdout
    assert "Risk level:" in proc.stdout
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan displayed" in history
    assert "Event: Plan explained" in history
    assert "Event: Step explained" in history


def test_llm_available_creates_llm_assisted_plan(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me improve this CLI"],
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Generating LLM-assisted grounded plan" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["last_plan"]["mode"] == PlanningMode.LLM_ASSISTED.value
    assert session["last_plan"]["status"] == "awaiting_confirmation"
    assert "src/snappy_putty/cli.py" in session["last_plan"]["files_inspected"]
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: LLM-assisted plan created" in history


def test_llm_failure_falls_back_to_deterministic_plan(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_failure_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "LLM-assisted planning is unavailable" not in proc.stdout
    assert "Generating deterministic grounded plan from inspected project context" in proc.stdout
    assert "Apply the smallest project change" in proc.stdout
    assert "Pending plan: deterministic plan with" in proc.stdout
    assert "Last skip reason: (none)" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["goal"] == "help me improve this CLI"
    assert session["current_plan"]["mode"] == PlanningMode.DETERMINISTIC.value
    assert session["last_plan"]["mode"] == PlanningMode.DETERMINISTIC.value
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Grounded plan created" in history


def test_previous_valid_plan_not_confused_with_skipped_request(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nwhat is the weather in San Francisco today?\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Last skipped goal: what is the weather in San Francisco today?" in proc.stdout
    assert "Last skip reason: unsupported_current_info_question" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["last_plan"]["goal"] == "help me improve this CLI"
    assert "current_plan" not in session
    assert session["last_skipped_goal"] == "what is the weather in San Francisco today?"


def test_plan_interaction_no_plan_and_invalid_step(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    no_plan = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="show plan\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert no_plan.returncode == 0
    assert "No active plan to display." in no_plan.stdout

    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    invalid_step = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="summarize README.md\nexplain step 99\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert invalid_step.returncode == 0
    assert "Step 99 does not exist." in invalid_step.stdout


def test_refine_step_updates_session_and_history_without_execution(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nrefine step 2\nfocus only on CLI logging\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Plan refined: step 2 refined." in proc.stdout
    assert "No changes have been applied." in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "focus only on CLI logging" in session["last_plan"]["steps"][1]["description"]
    assert session["last_plan"]["status"] == "awaiting_confirmation"
    assert session["last_plan"]["refinements"][-1]["change"] == "step 2 refined"
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan refined" in history
    assert "Change: step 2 refined: focus only on CLI logging" in history


def test_refine_plan_updates_session_without_adding_files(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="summarize README.md\nrefine plan limit changes to README\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "User refinement: limit changes to README" in session["last_plan"]["assumptions"]
    assert "limit changes to README" in session["last_plan"]["summary"]
    assert session["last_plan"]["files_inspected"] == session["current_plan"]["files_inspected"]


def test_refine_step_rejects_new_file_and_leaves_plan_unchanged(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    create = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me improve this CLI"],
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
        check=True,
    )
    assert create.returncode == 0
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    before = json.loads(session_path.read_text(encoding="utf-8"))["last_plan"]

    reject = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="refine step 2\nadd utils/logger.py\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert reject.returncode == 0
    assert "Refinement rejected." in reject.stdout
    assert "introduces files not present in project snapshot" in reject.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))["last_plan"]
    assert after == before
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan refinement rejected" in history
    assert "Validation: failed" in history


def test_refine_step_allows_narrowing_scope(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nrefine step 2\nlimit to CLI only\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Plan refined: step 2 refined." in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "limit to CLI only" in session["last_plan"]["steps"][1]["description"]
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Validation: passed" in history


def test_refine_plan_rejects_expansion_to_existing_out_of_scope_file(tmp_path: Path) -> None:
    for index in range(12):
        (tmp_path / f"DOC{index}.md").write_text(f"# Doc {index}\n", encoding="utf-8")
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('cli')\n", encoding="utf-8")
    (src_dir / "other.py").write_text("print('other')\n", encoding="utf-8")

    create = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me improve this CLI"],
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
        check=True,
    )
    assert create.returncode == 0
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    before = json.loads(session_path.read_text(encoding="utf-8"))["last_plan"]
    assert "src/snappy_putty/other.py" not in before["files_inspected"]

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="refine plan also update src/snappy_putty/other.py\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Refinement rejected." in proc.stdout
    assert "expands beyond original plan scope" in proc.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))["last_plan"]
    assert after == before


def test_multiple_refinements_emit_coherence_warning(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input=(
            "help me improve this CLI\n"
            "refine step 2 limit to CLI only\n"
            "refine step 2 focus on output text\n"
            "refine step 2 keep behavior unchanged\n"
            "exit\n"
        ),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Warning:" in proc.stdout
    assert "plan may no longer be coherent after multiple refinements" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert len(session["last_plan"]["refinements"]) == 3


def test_new_goal_during_confirmation_does_not_crash_and_can_be_parked(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input=(
            "help me improve this CLI\n"
            "help me add logging\n"
            "show pending\n"
            "park this\n"
            "show pending\n"
            "resume pending\n"
            "cancel\n"
            "resume pending\n"
            "status\n"
            "exit\n"
        ),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "ActiveGoalConflictError" not in proc.stdout
    assert "A goal is already active:" in proc.stdout
    assert "I can't start a second goal yet." in proc.stdout
    assert "Use: park this" in proc.stdout
    assert "No pending goal." in proc.stdout
    assert "Active goal:\nhelp me improve this CLI" in proc.stdout
    assert "Unparked request:\nhelp me add logging" in proc.stdout
    assert "Goal parked." in proc.stdout
    assert "Pending goal:\nhelp me add logging" in proc.stdout
    assert "Cannot resume pending goal while another goal is active." in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Active goal: help me add logging" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "pending_goal" not in session
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Goal conflict detected" in history
    assert "Event: Goal parked" in history
    assert "Event: Pending goal resumed" in history


def test_show_pending_reports_active_goal_and_unparked_conflict(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input=(
            "help me add a menu screen\n"
            "help me delete all files on the filesystem\n"
            "show pending\n"
            "exit\n"
        ),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "A goal is already active:" in proc.stdout
    assert "No pending goal." in proc.stdout
    assert "Active goal:\nhelp me add a menu screen" in proc.stdout
    assert "State: CONFIRMATION" in proc.stdout
    assert "Unparked request:\nhelp me delete all files on the filesystem" in proc.stdout
    assert "Use: park this" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "pending_goal" not in session


def test_new_goal_during_restored_planning_does_not_crash_or_change_state(tmp_path: Path) -> None:
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        json.dumps(
            {
                "workflow": {
                    "workflow_id": "wf-planning",
                    "state": "PLANNING",
                    "goal": "help me improve this CLI",
                    "route": "ask",
                    "pending_question": None,
                    "pending_plan_summary": "llm_assisted plan with 2 step(s)",
                    "pending_plan_mode": "llm_assisted",
                    "awaiting_confirmation": False,
                    "control_state": "allowed",
                    "context": None,
                    "pending_question_data": None,
                    "pending_plan_data": [{"step": 1, "action": "Review CLI", "why": "Existing active plan"}],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me add logging\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "ActiveGoalConflictError" not in proc.stdout
    assert "A goal is already active:" in proc.stdout
    assert "Current state: PLANNING" in proc.stdout
    assert "Active goal: help me improve this CLI" in proc.stdout
    assert "Pending plan: llm_assisted plan with 2 step(s)" in proc.stdout


def test_existing_pending_goal_is_not_silently_overwritten(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input=(
            "help me improve this CLI\n"
            "help me add logging\n"
            "park this\n"
            "help me add tests\n"
            "park this\n"
            "no\n"
            "show pending\n"
            "exit\n"
        ),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "A pending goal already exists:" in proc.stdout
    assert "Replace it? [yes/no]" in proc.stdout
    assert "Pending goal unchanged." in proc.stdout
    assert "Pending goal:\nhelp me add logging" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["pending_goal"]["text"] == "help me add logging"


def test_clear_pending_removes_parked_goal(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n[project.scripts]\nsnappy = 'snappy_putty.cli:app'\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "snappy_putty"
    src_dir.mkdir(parents=True)
    (src_dir / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this CLI\nhelp me add logging\npark this\nclear pending\nshow pending\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Pending goal cleared." in proc.stdout
    assert "No pending goal." in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "pending_goal" not in session
