from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from snappy_putty import active_planner, agent as agent_module
from snappy_putty import cli
from snappy_putty.active_planner import LLMPlanValidationError, PlanningMode, create_llm_assisted_plan, validate_llm_plan
from snappy_putty.project_inspector import inspect_project
from snappy_putty.skills import discover_skills, match_skills
from snappy_putty.task_router import route_task, route_to_skill_matches


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


def _write_skill(
    root: Path,
    name: str,
    description: str,
    *,
    relationships: list[str] | None = None,
    targets: list[str] | None = None,
    indicators: list[str] | None = None,
) -> None:
    skill_dir = root / ".snappy" / "skills" / name
    skill_dir.mkdir(parents=True)
    lines = ["---", f"name: {name}", f"description: {description}"]
    if relationships or targets or indicators:
        lines.append("x-snappy:")
        if relationships:
            lines.append("  project_relationships:")
            lines.extend(f"    - {item}" for item in relationships)
        if targets:
            lines.append("  extension_targets:")
            lines.extend(f"    - {item}" for item in targets)
        if indicators:
            lines.append("  indicators:")
            lines.extend(f"    - {item}" for item in indicators)
    lines.extend(["---", "", "Use as planning guidance only."])
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


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


def test_why_this_plan_is_read_only_but_other_plan_commands_validate(tmp_path: Path) -> None:
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
    assert proc.stdout.count("Plan invalidated: snapshot_changed") == 2
    assert "LLM-backed plan rationale is unavailable." in proc.stdout
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


def test_node_frontend_request_is_project_extension_with_skill(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    (tmp_path / "controllers").mkdir()
    (tmp_path / "controllers" / "productControllers.js").write_text("exports.listProducts = () => []\n", encoding="utf-8")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "productModel.js").write_text("class Product {}\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "products.json").write_text("[]\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "frontend-design",
        "Create production-grade frontend interfaces. Use this skill for web UI, dashboards, React components, and HTML/CSS layouts.",
        indicators=["frontend", "web ui", "dashboard"],
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me build a frontend interface for this application"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Classified request as project_extension" in proc.stdout
    assert "Matched skill: frontend-design" in proc.stdout
    assert "Grounded Plan" in proc.stdout
    assert not (tmp_path / "frontend").exists()
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    plan = session["current_plan"]
    relationship = plan["context_selection"]["project_relationship"]
    assert relationship["relationship"] == "project_extension"
    assert relationship["matched_skills"] == ["frontend-design"]
    assert "controllers/productControllers.js" in plan["files_inspected"]
    assert "models/productModel.js" in plan["files_inspected"]


def test_skill_guided_frontend_extension_reaches_llm_when_no_frontend_exists(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    (tmp_path / "controllers").mkdir()
    (tmp_path / "controllers" / "productControllers.js").write_text("exports.listProducts = () => []\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "frontend-design",
        "Create production-grade frontend interfaces. Use this skill for web UI, dashboards, React components, and HTML/CSS layouts.",
        relationships=["project_extension"],
        targets=["javascript"],
        indicators=["frontend", "front end", "admin interface"],
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me build a front end with an admin interface"],
        cwd=tmp_path,
        env=_llm_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Matched skill: frontend-design" in proc.stdout
    assert "LLM-assisted plan was rejected by validation." not in proc.stdout
    assert "Generating deterministic grounded plan from inspected project context" not in proc.stdout
    assert "Mode: llm_assisted" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    plan = session["current_plan"]
    assert plan["mode"] == PlanningMode.LLM_ASSISTED.value
    assert plan["context_selection"]["project_relationship"]["relationship"] == "project_extension"
    assert plan["context_selection"]["skill_selection"]["matched"][0]["name"] == "frontend-design"


def test_skill_guided_extension_bypasses_negative_sufficiency_gate(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "frontend-design",
        "Create production-grade frontend interfaces. Use this skill for web UI, dashboards, React components, and HTML/CSS layouts.",
        relationships=["project_extension"],
        targets=["javascript"],
        indicators=["frontend", "front end", "admin interface"],
    )
    goal = "help me build a front end with an admin interface"
    snapshot = inspect_project(tmp_path)
    skills = discover_skills(tmp_path)
    skill_matches = match_skills(goal, skills.skills)
    project_relationship = active_planner.assess_project_relationship(goal, snapshot, skill_matches=skill_matches)

    class InsufficientButPlannableClient:
        def __init__(self) -> None:
            self.create_plan_called = False

        def check_context_sufficiency(self, prompt: str) -> dict[str, object]:
            return {
                "sufficient": False,
                "reason": "No frontend files exist yet.",
                "missing_context_queries": [],
                "files_to_read_next": [],
            }

        def create_plan(self, prompt: str) -> dict[str, object]:
            self.create_plan_called = True
            assert "Skill: frontend-design" in prompt
            return {
                "goal": goal,
                "summary": "Add a frontend admin interface grounded in the existing API files.",
                "based_on_snapshot_id": snapshot.snapshot_id,
                "files_inspected": ["package.json", "server.js"],
                "steps": [
                    {
                        "description": "Create a small admin frontend that consumes the existing product API.",
                        "files": ["package.json", "server.js"],
                        "proposed_new_files": ["admin/index.html", "admin/app.js", "admin/styles.css"],
                        "risk": "MEDIUM",
                        "requires_confirmation": True,
                    }
                ],
                "risks": ["Frontend asset serving may change server routing."],
                "assumptions": ["The new admin interface can be added as static assets."],
            }

    client = InsufficientButPlannableClient()

    plan = create_llm_assisted_plan(
        goal,
        snapshot,
        client=client,
        skill_matches=skill_matches,
        project_relationship=project_relationship,
    )

    assert client.create_plan_called is True
    assert plan.mode == PlanningMode.LLM_ASSISTED.value
    assert plan.steps[0].proposed_new_files == ["admin/index.html", "admin/app.js", "admin/styles.css"]


def test_active_planning_records_skill_routing_metadata_and_prompt_context(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"vite"}}\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.tsx").write_text("export function App() { return null }\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "codeguardian-review",
        "Use this skill when reviewing code changes, inspecting diffs, and producing PR or MR review feedback.",
        relationships=["direct_project_work"],
        indicators=["code review", "MR feedback", "PR feedback"],
    )
    _write_skill(
        tmp_path,
        "frontend-design",
        "Use this skill when building frontend interfaces, dashboards, React components, and UI polish.",
        relationships=["project_extension"],
        targets=["typescript"],
        indicators=["frontend", "dashboard", "interface"],
    )
    goal = "Build a frontend interface for this application."
    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)
    route = route_task(goal, registry.skills, snapshot=snapshot)
    skill_matches = route_to_skill_matches(route, registry.skills)
    relationship = active_planner.assess_project_relationship(goal, snapshot, skill_matches=skill_matches)

    class CapturingClient(active_planner._MockLLMPlannerClient):
        def __init__(self) -> None:
            self.prompt = ""

        def create_plan(self, prompt: str) -> dict[str, object]:
            self.prompt = prompt
            return super().create_plan(prompt)

    client = CapturingClient()
    plan = create_llm_assisted_plan(
        goal,
        snapshot,
        client=client,
        skill_matches=skill_matches,
        skill_route=route,
        project_relationship=relationship,
    )

    assert route.task_intent.label == "frontend_build"
    assert route.selected_skills == ["frontend-design"]
    assert "Skill: frontend-design" in client.prompt
    assert "Skill: codeguardian-review" not in client.prompt
    assert plan.context_selection["skill_routing"]["task_intent"]["label"] == "frontend_build"
    assert plan.context_selection["skill_routing"]["selected_skills"] == ["frontend-design"]


def test_api_auth_extension_bypasses_negative_sufficiency_gate_with_existing_context(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    (tmp_path / "controllers").mkdir()
    (tmp_path / "controllers" / "productControllers.js").write_text("exports.listProducts = () => []\n", encoding="utf-8")
    goal = "help me add API authentication grounded in the existing API files"
    snapshot = inspect_project(tmp_path)
    project_relationship = active_planner.assess_project_relationship(goal, snapshot, skill_matches=[])

    class InsufficientButPlannableClient:
        def __init__(self) -> None:
            self.create_plan_called = False

        def check_context_sufficiency(self, prompt: str) -> dict[str, object]:
            return {
                "sufficient": False,
                "reason": "No auth layer exists yet.",
                "missing_context_queries": [],
                "files_to_read_next": [],
            }

        def create_plan(self, prompt: str) -> dict[str, object]:
            self.create_plan_called = True
            return {
                "goal": goal,
                "summary": "Add API authentication grounded in the current server and controller files.",
                "based_on_snapshot_id": snapshot.snapshot_id,
                "files_inspected": ["package.json", "server.js", "controllers/productControllers.js"],
                "steps": [
                    {
                        "description": "Add authentication checks around the existing product API routing.",
                        "files": ["package.json", "server.js", "controllers/productControllers.js"],
                        "proposed_new_files": ["auth.js"],
                        "risk": "MEDIUM",
                        "requires_confirmation": True,
                    }
                ],
                "risks": ["Authentication changes may alter response status codes for existing clients."],
                "assumptions": ["The API can use a new local auth helper."],
            }

    client = InsufficientButPlannableClient()

    plan = create_llm_assisted_plan(
        goal,
        snapshot,
        client=client,
        skill_matches=[],
        project_relationship=project_relationship,
    )

    assert client.create_plan_called is True
    assert plan.mode == PlanningMode.LLM_ASSISTED.value
    assert plan.steps[0].proposed_new_files == ["auth.js"]


def test_python_streamlit_and_gradio_requests_are_project_extensions(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("def predict(value):\n    return value\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "streamlit-dashboard",
        "Use this skill when the user asks to build a Streamlit dashboard, analytics interface, data app, or Python-based frontend.",
        relationships=["project_extension"],
        targets=["python"],
        indicators=["streamlit", "dashboard", "data app"],
    )
    _write_skill(
        tmp_path,
        "gradio-interface",
        "Use this skill when the user asks to add a Gradio UI or machine learning interface for the current Python project.",
        relationships=["project_extension"],
        targets=["python"],
        indicators=["gradio", "ui"],
    )

    streamlit = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me build a Streamlit dashboard for this project"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    gradio = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me add a Gradio UI for this app"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert streamlit.returncode == 0
    assert "Classified request as project_extension" in streamlit.stdout
    assert "Matched skill: streamlit-dashboard" in streamlit.stdout
    assert gradio.returncode == 0
    assert "Classified request as project_extension" in gradio.stdout
    assert "Matched skill: gradio-interface" in gradio.stdout
    assert not (tmp_path / "streamlit_app.py").exists()
    assert not (tmp_path / "app.py").exists()


def test_python_flask_request_is_project_adaptation_with_skill(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "flask-web-interface",
        "Use this skill when the user asks to build a Flask web interface, lightweight Python web app, admin UI, or browser-based frontend.",
        relationships=["project_extension", "project_adaptation"],
        targets=["python"],
        indicators=["flask", "web interface"],
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me turn this script into a Flask app"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Classified request as project_adaptation" in proc.stdout
    assert "Matched skill: flask-web-interface" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["context_selection"]["project_relationship"]["relationship"] == "project_adaptation"
    assert not (tmp_path / "app.py").exists()


def test_generic_docker_extension_creates_grounded_plan(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me add Docker support for this project"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Classified request as project_extension" in proc.stdout
    assert "Grounded Plan" in proc.stdout
    assert not (tmp_path / "Dockerfile").exists()


def test_active_planning_uses_latest_saved_snapshot(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    first = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "inspect", "project"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    second = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "inspect", "project"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    saved_snapshot = json.loads((tmp_path / ".snappy" / "memory" / "project_snapshot.json").read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "summarize README.md"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert proc.returncode == 0
    assert f"Using snapshot: {saved_snapshot['snapshot_id']}" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["based_on_snapshot_id"] == saved_snapshot["snapshot_id"]


def test_skill_match_without_project_context_still_rejects_unrelated_request(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("console.log('server')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "frontend-design",
        "Create distinctive posters and frontend designs. Use this skill for web UI, dashboards, and birthday party posters.",
        indicators=["poster", "frontend"],
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me design a poster for a birthday party"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "does not appear to be related to the current project" in proc.stdout
    assert "No project plan was created." in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "current_plan" not in session


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


def test_broad_api_goal_creates_deterministic_plan_for_node_api(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text(
        "const express = require('express')\nconst productRoutes = require('./routes/products')\n",
        encoding="utf-8",
    )
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    (routes_dir / "products.js").write_text("module.exports = router\n", encoding="utf-8")
    controllers_dir = tmp_path / "controllers"
    controllers_dir.mkdir()
    (controllers_dir / "products.js").write_text("exports.listProducts = (req, res) => res.json([])\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help me improve this api\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "This request does not appear to be related to the current project." not in proc.stdout
    assert "Classified request as direct_project_work" in proc.stdout
    assert "Generating deterministic grounded plan from inspected project context" in proc.stdout
    assert "Pending plan: deterministic plan with" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    plan = session["current_plan"]
    assert plan["goal"] == "help me improve this api"
    assert plan["context_selection"]["project_relationship"]["relationship"] == "direct_project_work"
    assert "server.js" in plan["files_inspected"]
    assert "routes/products.js" in plan["files_inspected"]
    assert "controllers/products.js" in plan["files_inspected"]


def test_create_spec_goal_matches_doc_coauthoring_skill_for_node_api(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "doc-coauthoring",
        "Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.",
    )

    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)
    matches = match_skills("help me create a spec for this nodejs api", registry.skills)
    relationship = active_planner.assess_project_relationship(
        "help me create a spec for this nodejs api",
        snapshot,
        skill_matches=matches,
    )

    assert matches
    assert matches[0].skill.metadata.name == "doc-coauthoring"
    assert relationship.is_project_related
    assert relationship.matched_skills == ["doc-coauthoring"]


def test_negated_repo_context_is_not_project_related_even_with_matching_skill(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text("const http = require('http')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "doc-coauthoring",
        "Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.",
    )
    goal = "help me create a spec for a random API not in this repo"
    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)
    skill_matches = match_skills(goal, registry.skills)

    relationship = active_planner.assess_project_relationship(goal, snapshot, skill_matches=skill_matches)

    assert skill_matches
    assert not relationship.is_project_related
    assert relationship.reason == "goal_explicitly_not_project_related"


def test_doc_skill_direct_project_work_can_plan_without_existing_docs_convention(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text(
        "const http = require('http')\nconst controllers = require('./controllers/productControllers')\n",
        encoding="utf-8",
    )
    controllers_dir = tmp_path / "controllers"
    controllers_dir.mkdir()
    (controllers_dir / "productControllers.js").write_text(
        "exports.listProducts = (req, res) => res.end(JSON.stringify([]))\n",
        encoding="utf-8",
    )
    _write_skill(
        tmp_path,
        "doc-coauthoring",
        "Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.",
    )
    goal = "help me draft documentation for the routes"
    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)
    skill_matches = match_skills(goal, registry.skills)
    project_relationship = active_planner.assess_project_relationship(goal, snapshot, skill_matches=skill_matches)

    class InsufficientDocsConventionClient:
        def check_context_sufficiency(self, prompt: str) -> dict[str, object]:
            return {
                "sufficient": False,
                "reason": "No existing docs convention exists.",
                "missing_context_queries": [],
                "files_to_read_next": [],
            }

        def create_plan(self, prompt: str) -> dict[str, object]:
            return {
                "goal": goal,
                "summary": "Draft route documentation from the inspected API source.",
                "based_on_snapshot_id": snapshot.snapshot_id,
                "files_inspected": ["server.js", "controllers/productControllers.js"],
                "steps": [
                    {
                        "description": "Draft route documentation from the inspected server and controller behavior.",
                        "files": ["server.js", "controllers/productControllers.js"],
                        "proposed_new_files": ["docs/api.md"],
                        "risk": "LOW",
                        "requires_confirmation": True,
                    }
                ],
                "risks": ["The documentation may omit behavior not visible in inspected files."],
                "assumptions": ["The server and controller files define the route behavior."],
            }

    assert project_relationship.relationship.value == "direct_project_work"

    plan = create_llm_assisted_plan(
        goal,
        snapshot,
        client=InsufficientDocsConventionClient(),
        skill_matches=skill_matches,
        project_relationship=project_relationship,
    )

    assert plan.mode == PlanningMode.LLM_ASSISTED.value
    assert plan.steps[0].proposed_new_files == ["docs/api.md"]


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


def test_latest_changes_code_review_is_project_goal_not_current_info(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("const http = require('http')\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "codeguardian-review",
        "Use this skill when reviewing code changes, inspecting diffs, and producing PR or MR review feedback.",
        relationships=["direct_project_work"],
        indicators=["code review", "review changes", "MR feedback", "PR feedback"],
    )

    assert (
        active_planner.classify_planning_intent("Review my latest changes and give me MR-style feedback.")
        == active_planner.PlanningIntent.STRUCTURED_PROJECT_INTENT
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="Review my latest changes and give me MR-style feedback.\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Matched task intent: code_review" in proc.stdout
    assert "Selected skill: codeguardian-review" in proc.stdout
    assert "current information request" not in proc.stdout
    assert "Produce structured review feedback" in proc.stdout
    assert "Apply the smallest project change" not in proc.stdout
    assert "Last skip reason: (none)" in proc.stdout


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


def test_skill_routed_plan_confirmation_generates_non_mutating_output(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "codeguardian-review",
        "Use when the user asks to review latest changes and give PR or MR feedback.",
        indicators=["review latest changes", "MR feedback"],
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="Review my latest changes and give me MR feedback.\nYES\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Type YES to generate the non-mutating skill output" in proc.stdout
    assert "Generating skill output..." in proc.stdout
    assert "Using skill: codeguardian-review" in proc.stdout
    assert "Output kind: code_review_report" in proc.stdout
    assert "# Code Review Report" in proc.stdout
    assert "_No files were changed._" in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["last_plan"]["status"] == "output_generated"
    assert session["last_skill_output"]["mutations_applied"] is False
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Skill output generated" in history
    assert "Mutations applied: False" in history


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
    assert "Why these files" in proc.stdout
    assert "Trade-offs" in proc.stdout
    assert "Remaining uncertainty" in proc.stdout
    assert "What it does:" in proc.stdout
    assert "Files touched:" in proc.stdout
    assert "Risk level:" in proc.stdout
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan displayed" in history
    assert "Event: Plan rationale requested" in history
    assert "Mode: llm_assisted" in history
    assert "Event: Step explained" in history


def test_why_this_plan_falls_back_without_llm_and_is_read_only(tmp_path: Path) -> None:
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
    before = json.loads(session_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="why this plan\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_unavailable_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "LLM-backed plan rationale is unavailable." in proc.stdout
    assert "I can show the stored plan metadata" in proc.stdout
    assert "Why these files:" in proc.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))
    assert after["current_plan"] == before["current_plan"]
    assert after["last_plan"] == before["last_plan"]
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan rationale requested" in history
    assert "Mode: metadata_fallback" in history


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


def test_disabled_best_match_prompts_before_generic_fallback_yes(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"test":"npm test"}}\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.js").write_text("module.exports = {}\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "codeguardian-review",
        "Use this skill when the user asks for code review, PR feedback, MR feedback, or diff inspection.",
        relationships=["direct_project_work"],
        indicators=["PR feedback", "code review"],
    )
    (tmp_path / ".snappy" / "snappy.yaml").write_text(
        "version: 1\nskills:\n  enabled: []\n  disabled:\n    - codeguardian-review\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "Review my latest changes and give me PR feedback."],
        input="YES\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Matched task intent: code_review" in proc.stdout
    assert "Best matching skill is disabled by config: codeguardian-review" in proc.stdout
    assert "No specialized skill selected." in proc.stdout
    assert "Continue with generic grounded planning? [YES/NO]>" in proc.stdout
    assert "Continuing without disabled skill: codeguardian-review" in proc.stdout
    assert "Generating generic grounded plan" in proc.stdout
    assert "Selected skill: codeguardian-review" not in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    routing = session["last_plan"]["context_selection"]["skill_routing"]
    assert routing["selected_skills"] == []
    assert routing["disabled_best_match"] == "codeguardian-review"
    assert routing["generic_fallback_confirmed"] is True


def test_disabled_best_match_prompt_no_cancels_without_plan(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"test":"npm test"}}\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.js").write_text("module.exports = {}\n", encoding="utf-8")
    _write_skill(
        tmp_path,
        "codeguardian-review",
        "Use this skill when the user asks for code review, PR feedback, MR feedback, or diff inspection.",
        relationships=["direct_project_work"],
        indicators=["PR feedback", "code review"],
    )
    (tmp_path / ".snappy" / "snappy.yaml").write_text(
        "version: 1\nskills:\n  enabled: []\n  disabled:\n    - codeguardian-review\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "Review my latest changes and give me PR feedback."],
        input="NO\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Best matching skill is disabled by config: codeguardian-review" in proc.stdout
    assert "No project plan was created." in proc.stdout
    assert "Generating generic grounded plan" not in proc.stdout
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        assert "last_plan" not in session
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Generic skill fallback cancelled" in history
    assert "'generic_fallback_confirmed': False" in history
    assert "'status': 'cancelled'" in history


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


def test_llm_validation_rejection_falls_back_to_deterministic_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("console.log('server')\n", encoding="utf-8")
    controllers_dir = tmp_path / "controllers"
    controllers_dir.mkdir()
    (controllers_dir / "productControllers.js").write_text("exports.listProducts = () => []\n", encoding="utf-8")

    def reject_llm_plan(*args, **kwargs):
        raise LLMPlanValidationError("not enough grounded context")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "create_llm_assisted_plan", reject_llm_plan)

    result = cli.handle_ask("help me improve this api", session_mode="active")

    captured = capsys.readouterr()
    assert "LLM-assisted plan was rejected by validation." in captured.out
    assert "Generating deterministic grounded plan from inspected project context" in captured.out
    assert result.plan_mode == PlanningMode.DETERMINISTIC.value
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert session["current_plan"]["goal"] == "help me improve this api"
    assert session["current_plan"]["mode"] == PlanningMode.DETERMINISTIC.value
    assert "last_skipped_goal" not in session
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: LLM-assisted plan rejected" in history
    assert "Event: Grounded plan created" in history


def test_llm_plan_validation_relocates_new_doc_paths_to_proposed_files(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{"express":"latest"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
    controllers_dir = tmp_path / "controllers"
    controllers_dir.mkdir()
    (controllers_dir / "productControllers.js").write_text("exports.listProducts = () => []\n", encoding="utf-8")
    snapshot = inspect_project(tmp_path)

    plan = validate_llm_plan(
        {
            "goal": "help me create a spec for this nodejs api",
            "summary": "Create a grounded API spec plan.",
            "based_on_snapshot_id": snapshot.snapshot_id,
            "files_inspected": ["server.js", "controllers/productControllers.js", "spec/README.md"],
            "steps": [
                {
                    "description": "Draft the API spec from the inspected server and controller behavior.",
                    "files": ["server.js", "controllers/productControllers.js", "spec/README.md"],
                    "proposed_new_files": [],
                    "risk": "LOW",
                    "requires_confirmation": True,
                }
            ],
            "risks": ["The spec may omit behavior not visible in inspected files."],
            "assumptions": ["The server and controller files are the authoritative API surface."],
        },
        snapshot,
        tmp_path,
    )

    assert plan.files_inspected == ["server.js", "controllers/productControllers.js"]
    assert plan.steps[0].files == ["server.js", "controllers/productControllers.js"]
    assert plan.steps[0].proposed_new_files == ["spec/README.md"]


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
    assert "Refining step 2." in proc.stdout
    assert "Describe how you want this step adjusted." in proc.stdout
    assert "The refinement should stay related to the current goal." in proc.stdout
    assert "refinement>" in proc.stdout
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


def test_direct_safe_inspection_does_not_overwrite_existing_plan(tmp_path: Path) -> None:
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
    before = json.loads(session_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="show file listing\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Directory Listing" in proc.stdout
    assert "Grounded Plan" not in proc.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))
    assert after["last_plan"] == before["last_plan"]
    assert after["current_plan"] == before["current_plan"]


def test_refine_step_inline_refinement_does_not_show_prompt(tmp_path: Path) -> None:
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
        input="help me improve this CLI\nrefine step 2 focus more on validation\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Refining step 2." not in proc.stdout
    assert "Describe how you want this step adjusted." not in proc.stdout
    assert "Plan refined: step 2 refined." in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "focus more on validation" in session["last_plan"]["steps"][1]["description"]


def test_refine_step_out_of_range_leaves_state_unchanged(tmp_path: Path) -> None:
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
    before = json.loads(session_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="refine step 99\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Step 99 does not exist. Plan unchanged." in proc.stdout
    assert "Current state:" in proc.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))
    assert after["last_plan"] == before["last_plan"]
    assert after["current_plan"] == before["current_plan"]


def test_refine_step_rejects_new_goal_prompt_input_and_leaves_plan_unchanged(tmp_path: Path) -> None:
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
    before = json.loads(session_path.read_text(encoding="utf-8"))

    reject = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="refine step 2\nhelp me build a starship\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert reject.returncode == 0
    assert "That looks like a new request, not a refinement instruction." in reject.stdout
    assert "The current plan was not changed." in reject.stdout
    after = json.loads(session_path.read_text(encoding="utf-8"))
    assert after["last_plan"] == before["last_plan"]
    assert after["current_plan"] == before["current_plan"]
    history = (tmp_path / ".snappy" / "memory" / "history.md").read_text(encoding="utf-8")
    assert "Event: Plan refinement rejected" in history
    assert "Reason: new_goal_attempt" in history
    assert "Validation: failed" in history


def test_refine_step_rejected_prompt_stays_open_and_accepts_next_refinement(tmp_path: Path) -> None:
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
    before = json.loads(session_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="refine step 2\nhelp me build a starship\nfocus only on task validation and bad input handling\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert proc.stdout.count("refinement>") >= 2
    assert "That looks like a new request, not a refinement instruction." in proc.stdout
    assert "Plan refined: step 2 refined." in proc.stdout
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session.get("last_failed_goal") is None
    assert session["last_plan"]["steps"][0] == before["last_plan"]["steps"][0]
    assert "help me build a starship" not in json.dumps(session["last_plan"])
    assert "focus only on task validation and bad input handling" in session["last_plan"]["steps"][1]["description"]


def test_refine_step_back_exits_refinement_without_cancelling_workflow(tmp_path: Path) -> None:
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
        input="help me improve this CLI\nrefine step 2\nback\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_llm_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Exited refinement mode. Plan unchanged." in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    after = json.loads(session_path.read_text(encoding="utf-8"))
    assert after["current_plan"]["status"] == "awaiting_confirmation"
    assert after["last_plan"]["refinements"] == []


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


def test_destructive_preflight_clears_active_goal_instead_of_parking_conflict(tmp_path: Path) -> None:
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
    assert "A goal is already active:" not in proc.stdout
    assert "That request is destructive and unsafe." in proc.stdout
    assert "No action was taken." in proc.stdout
    assert "No pending goal." in proc.stdout
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    assert "workflow" not in session
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
