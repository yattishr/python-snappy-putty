import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.agent_fixtures import load_agent_fixture
from snappy_putty.session import SessionState


def _repl_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    return env


def test_repl_pending_question_consumes_next_input_as_answer(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing for\nsrc\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Which directory path should I list?" in proc.stdout
    assert "Directory not found" in proc.stdout
    assert "Directory Listing" in proc.stdout


def test_repl_confirmation_flow_applies_on_yes(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert (tmp_path / "README-copy.md").exists()


def test_repl_after_status_cancel(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nstatus\nafter\ncancel\nstatus\nafter\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Session Status" in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout
    assert "Awaiting confirmation: yes" in proc.stdout
    assert "Pending confirmation: type YES to continue or NO to cancel." in proc.stdout
    assert "Cleared pending question/plan state." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Last cancelled goal: copy README.md README-copy.md" in proc.stdout
    assert "No active task." in proc.stdout
    assert not (tmp_path / "README-copy.md").exists()


def test_reserved_commands_not_consumed_as_pending_question_answers(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nstatus\nafter\ncancel\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Session Status" in proc.stdout
    assert "Current state: CLARIFICATION" in proc.stdout
    assert "Active goal: copy README.md" in proc.stdout
    assert "Pending question: destination path>" in proc.stdout
    assert "Cleared pending question/plan state." in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending question: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Awaiting confirmation: no" in proc.stdout
    assert "Last cancelled goal: copy README.md" in proc.stdout
    assert "copy README.md -> status" not in proc.stdout


def test_repl_successful_fs_apply_moves_goal_to_last_completed(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nYES\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert (tmp_path / "README-copy.md").exists()
    assert "Session Status" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending question: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Awaiting confirmation: no" in proc.stdout
    assert "Last completed goal: copy README.md README-copy.md" in proc.stdout


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ("ask", True),
        ("safe_inspect", False),
        ("git_read", False),
        ("fs_mutation", False),
    ],
)
def test_ask_followup_only_consumes_plain_ask_responses(route: str, expected: bool) -> None:
    from snappy_putty import cli

    state = SessionState(
        pending_question="Which target do you mean?",
        pending_context={"type": "ask_followup", "base_intent": "git push"},
    )

    assert cli._should_consume_pending_question(
        text="give me a file listing for the current directory",
        route=route,
        state=state,
    ) is expected


def test_current_directory_listing_request_resolves_to_cwd() -> None:
    from snappy_putty.agent import _extract_requested_path

    assert _extract_requested_path("give me a file listing for the current directory") == "."


def test_safe_inspect_success_returns_lifecycle_to_idle(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing for the current directory\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Directory Listing" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending question: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Awaiting confirmation: no" in proc.stdout
    assert "Last route: safe_inspect" in proc.stdout
    assert "Last completed goal: give me a file listing for the current directory" in proc.stdout


def test_unknown_command_resets_session_to_idle(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="do something random and undefined\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "I don't recognize that command. Try 'help' to see what I can do." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Pending question: (none)" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Last route: unknown" in proc.stdout
    assert "Last failed goal: do something random and undefined" in proc.stdout
    assert "Error message: Unrecognized command" in proc.stdout


def test_guided_listing_fallback_selection_executes_current_directory_listing(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing\n1\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Where would you like the file listing from?" in proc.stdout
    assert "Current directory (.)" in proc.stdout
    assert "Directory Listing" in proc.stdout
    assert "alpha.txt" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Last route: safe_inspect" in proc.stdout


def test_guided_listing_fallback_custom_path_executes_selected_directory(tmp_path: Path) -> None:
    custom_dir = tmp_path / "logs"
    custom_dir.mkdir()
    (custom_dir / "app.log").write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing\n3\nlogs\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Specify a custom path" in proc.stdout
    assert "Enter custom path:" in proc.stdout
    assert "Directory Listing" in proc.stdout
    assert "app.log" in proc.stdout


def test_repl_skills_command_shows_skill_registry(tmp_path: Path) -> None:
    skills_dir = tmp_path / ".snappy" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "docker.md").write_text(
        "\n".join(
            [
                "# Skill: Docker Logs",
                "Description:",
                "Inspect running container logs safely.",
                "Intent examples:",
                "- show docker logs for api",
                "Risk: low",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="skills\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Loaded skills:" in proc.stdout
    assert "Docker Logs [low]" in proc.stdout


def test_repl_rules_command_shows_rule_registry(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "safety.md").write_text(
        "# Rule: Confirm Destructive Actions\nAlways ask for confirmation before destructive commands.\n",
        encoding="utf-8",
    )
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="rules\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Loaded rules:" in proc.stdout
    assert "Confirm Destructive Actions" in proc.stdout


def test_repl_help_includes_agent_related_commands(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="help\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "- agent             Show the loaded agent summary." in proc.stdout
    assert "- agent mode        Inspect or change agent runtime mode." in proc.stdout
    assert "- init" in proc.stdout
    assert "- skills" in proc.stdout
    assert "- rules" in proc.stdout


def test_repl_init_creates_snappy_directory(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="init\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Initialized agent scaffold" in proc.stdout
    assert (tmp_path / ".snappy").is_dir()
    assert (tmp_path / ".snappy" / "snappy.yaml").is_file()


def test_repl_init_twice_does_not_crash(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="init\ninit\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Initialized agent scaffold" in proc.stdout
    assert "Refusing to overwrite existing .snappy/" in proc.stdout


def test_repl_agent_mode_shows_default_and_menu(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode\n1\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Agent Mode" in proc.stdout
    assert "Current: off" in proc.stdout
    assert "Source: default" in proc.stdout
    assert "Select mode:" in proc.stdout
    assert "Agent mode set to: off (session)" in proc.stdout


def test_repl_agent_mode_respects_environment(tmp_path: Path) -> None:
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode\n1\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Current: passive" in proc.stdout
    assert "Source: environment" in proc.stdout
    assert "Agent mode set to: off (session)" in proc.stdout


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("agent mode off\nstatus\nexit\n", "Agent mode set to: off (session)"),
        ("agent mode passive\nstatus\nexit\n", "Agent mode set to: passive (session)"),
        ("agent mode active\nstatus\nexit\n", "Agent mode set to: active (session)"),
        ("agent mode PASSIVE\nstatus\nexit\n", "Agent mode set to: passive (session)"),
    ],
)
def test_repl_agent_mode_direct_setters(command: str, expected: str, tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input=command,
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert expected in proc.stdout


def test_repl_agent_mode_invalid_value_is_handled(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode chaos\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Invalid mode. Choose: off, passive, active" in proc.stdout


def test_repl_agent_mode_status_reflects_session_override(tmp_path: Path) -> None:
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "active"
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode passive\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Agent mode set to: passive (session)" in proc.stdout
    assert "Agent feature mode: passive" in proc.stdout
    assert "Agent mode source: session" in proc.stdout


def test_repl_status_shows_agent_metadata_when_present(tmp_path: Path) -> None:
    load_agent_fixture("valid_agent", tmp_path)
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="status\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Session Status" in proc.stdout
    assert "Agent feature mode: passive" in proc.stdout
    assert "Agent name: Fixture Agent" in proc.stdout
    assert "Agent version: 1" in proc.stdout
    assert "Loaded skills: 1" in proc.stdout
    assert "Loaded rules: 1" in proc.stdout
    assert "Agent memory session keys: last_goal, notes" in proc.stdout


def test_guided_listing_override_runs_new_command_without_state_contamination(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing\ngit status\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Where would you like the file listing from?" in proc.stdout
    assert "Git Read Failed" in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Last route: git_read" in proc.stdout
    assert "Last failed goal: git status" in proc.stdout


def test_fs_path_clarification_accepts_relative_directory_input(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    destination_dir = tmp_path / "tests"
    destination_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\ntests/\nYES\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert (destination_dir / "README.md").exists()
    assert "Current state: IDLE" in proc.stdout
    assert "Last completed goal: copy README.md to tests/" in proc.stdout
    assert "snappy [ask]>" not in proc.stdout
    assert "snappy> " in proc.stdout


def test_fs_path_clarification_still_allows_command_override(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\ngit status\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "destination path>" in proc.stdout
    assert "Git Read Failed" in proc.stdout
    assert not (tmp_path / "README-copy.md").exists()
    assert "Current state: IDLE" in proc.stdout
    assert "Last route: git_read" in proc.stdout
