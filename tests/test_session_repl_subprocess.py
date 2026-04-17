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
    assert proc.stdout.index("Goal") < proc.stdout.index("Planned Changes")
    assert proc.stdout.index("Planned Changes") < proc.stdout.index("Plan Warnings")
    assert proc.stdout.index("Plan Warnings") < proc.stdout.index("Type YES to apply, or NO to cancel.")
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert (tmp_path / "README-copy.md").exists()


def test_repl_overwrite_confirmation_flow_applies_on_yes(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    destination = tmp_path / "README-copy.md"
    source.write_text("demo", encoding="utf-8")
    destination.write_text("existing", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nYES\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Destination exists. Type YES to overwrite, or NO to cancel." in proc.stdout
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert destination.read_text(encoding="utf-8") == "demo"


def test_repl_overwrite_confirmation_flow_accepts_lowercase_yes(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    destination = tmp_path / "README-copy.md"
    source.write_text("demo", encoding="utf-8")
    destination.write_text("existing", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nyes\nyes\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Destination exists. Type YES to overwrite, or NO to cancel." in proc.stdout
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert destination.read_text(encoding="utf-8") == "demo"


def test_repl_invalid_confirmation_input_reprompts_cleanly(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nmaybe\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Please answer YES or NO." in proc.stdout
    assert proc.stdout.count("Type YES to apply, or NO to cancel.") == 2
    assert (tmp_path / "README-copy.md").exists()


def test_repl_invalid_confirmation_input_keeps_control_state_pending(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nmaybe\nstatus\nNO\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Please answer YES or NO." in proc.stdout
    assert "Awaiting confirmation: yes" in proc.stdout
    assert "Current control state: awaiting_confirm" in proc.stdout
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert not (tmp_path / "README-copy.md").exists()


def test_repl_confirmation_flow_cancels_on_no(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nNO\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert "Cancelled. No pending action was applied." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Last cancelled goal: copy README.md README-copy.md" in proc.stdout
    assert not (tmp_path / "README-copy.md").exists()


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
    assert "Awaiting confirmation: Type YES to apply, or NO to cancel." in proc.stdout
    assert "Cleared pending question/plan state." in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Active goal: (none)" in proc.stdout
    assert "Last cancelled goal: copy README.md README-copy.md" in proc.stdout
    assert "No pending next step." in proc.stdout
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


def test_repl_clarification_blocks_new_safe_inspect_goal(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\ngive me a file listing for the current directory\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "You have a pending question." in proc.stdout
    assert "destination path>" in proc.stdout
    assert "Answer it, or type 'cancel' to abandon the current goal." in proc.stdout
    assert "Directory Listing" not in proc.stdout
    assert "Current state: CLARIFICATION" in proc.stdout
    assert "Active goal: copy README.md" in proc.stdout
    assert "Pending question: destination path>" in proc.stdout
    assert "Last route: fs_mutation" in proc.stdout
    assert "Last completed goal: (none)" in proc.stdout
    assert "Last failed goal: (none)" in proc.stdout
    assert "Last cancelled goal: (none)" in proc.stdout
    assert proc.stdout.count("destination path>") <= 5


def test_repl_clarification_blocks_new_ask_goal(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nhelp me debug this\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "You have a pending question." in proc.stdout
    assert "destination path>" in proc.stdout
    assert "Answer it, or type 'cancel' to abandon the current goal." in proc.stdout
    assert "Current state: CLARIFICATION" in proc.stdout
    assert "Active goal: copy README.md" in proc.stdout
    assert "Pending question: destination path>" in proc.stdout
    assert "Last route: fs_mutation" in proc.stdout
    assert "Last completed goal: (none)" in proc.stdout
    assert "Last failed goal: (none)" in proc.stdout
    assert "Last cancelled goal: (none)" in proc.stdout
    assert proc.stdout.count("destination path>") <= 5


def test_repl_help_during_clarification_preserves_prompt_continuity(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nhelp\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Welcome" in proc.stdout
    assert "Your pending question is still active." in proc.stdout
    assert "Answer it, or type 'cancel' to abandon the current goal." in proc.stdout
    assert proc.stdout.count("destination path>") <= 4


def test_repl_status_during_clarification_preserves_prompt_continuity(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Session Status" in proc.stdout
    assert "Current state: CLARIFICATION" in proc.stdout
    assert "Pending question: destination path>" in proc.stdout
    assert "Your pending question is still active." not in proc.stdout
    assert proc.stdout.count("destination path>") <= 4


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
    assert "Confirm Destructive Actions [confirm_destructive_actions] (informational)" in proc.stdout


def test_repl_protect_project_root_blocks_workspace_escape_with_rule_message(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to /\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert proc.stdout.index("Goal") < proc.stdout.index("Policy Block")
    assert proc.stdout.index("Policy Block") < proc.stdout.index("Next Step")
    assert "Operation blocked by rule: protect_project_root" in proc.stdout
    assert "The requested filesystem mutation targets a protected path." in proc.stdout
    assert "Adjust the target path or request, then try again." in proc.stdout
    assert "No filesystem changes planned." not in proc.stdout
    assert "Path escapes workspace root" not in proc.stdout
    assert "Current state: IDLE" in proc.stdout
    assert "Pending plan: (none)" in proc.stdout
    assert "Last failed goal: copy README.md to /" in proc.stdout


def test_repl_block_rule_outranks_confirm_rule_when_both_are_loaded(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to /\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Policy Block" in proc.stdout
    assert "Operation blocked by rule: protect_project_root" in proc.stdout
    assert "Additional policy context: confirmation rule(s) also matched:" in proc.stdout
    assert "require_confirm" in proc.stdout
    assert "Type YES to apply, or NO to cancel." not in proc.stdout
    assert "Pending plan: (none)" in proc.stdout


def test_repl_confirm_rule_and_info_rule_require_confirmation_without_block(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )
    (rules_dir / "custom_note.md").write_text(
        "# Rule: custom_note\nHuman-readable guidance only.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to tests/\nNO\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Policy" in proc.stdout
    assert "Loaded rules require confirmation before filesystem changes are applied." in proc.stdout
    assert "Policy Block" not in proc.stdout
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert "Current state: IDLE" in proc.stdout


def test_repl_info_rule_only_does_not_change_safe_copy_behavior(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "custom_note.md").write_text(
        "# Rule: custom_note\nHuman-readable guidance only.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Planned Changes" in proc.stdout
    assert "Policy Block" not in proc.stdout
    assert "Loaded rules require confirmation before filesystem changes are applied." not in proc.stdout
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert "Current state: CONFIRMATION" in proc.stdout


def test_repl_workspace_escape_without_rule_is_reported_as_blocked_request(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to /\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    output = " ".join(proc.stdout.split())
    assert "Blocked Request" in output
    assert "No executable filesystem changes were planned" in output
    assert "outside the workspace root." in output
    assert "Path escapes workspace root:" in output
    assert "Choose a destination inside the workspace and try again." in output
    assert "Type YES to apply, or NO to cancel." not in output
    assert "Current state: IDLE" in output
    assert "Pending plan: (none)" in output
    assert "Last failed goal: copy README.md to /" in output


def test_repl_zero_op_invalid_request_does_not_leave_pending_plan(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy missing.txt to beta.txt\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    output = " ".join(proc.stdout.split())
    assert "Invalid Request" in output
    assert "No executable filesystem changes were planned" in output
    assert "could not be normalized into a valid filesystem change." in output
    assert "Source does not exist: missing.txt" in output
    assert "Adjust the request and try again." in output
    assert "Type YES to apply, or NO to cancel." not in output
    assert "Current state: IDLE" in output
    assert "Pending plan: (none)" in output
    assert "Last failed goal: copy missing.txt to beta.txt" in output


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


def test_repl_agent_mode_shows_default_non_interactively(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode\nexit\n",
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
    assert "Select mode:" not in proc.stdout
    assert "Enter choice >" not in proc.stdout
    assert "Agent mode set to:" not in proc.stdout


def test_repl_agent_mode_respects_environment(tmp_path: Path) -> None:
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Current: passive" in proc.stdout
    assert "Source: environment" in proc.stdout
    assert "Select mode:" not in proc.stdout
    assert "Agent mode set to:" not in proc.stdout


def test_repl_agent_mode_select_opens_menu(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode select\n1\nexit\n",
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


def test_repl_agent_mode_active_is_blocked_by_loaded_rule(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "no_active_mode.md").write_text(
        "# Rule: no_active_mode\nActive mode is disabled in this repo.\n",
        encoding="utf-8",
    )
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode active\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Active mode is disabled by the loaded agent rules." in proc.stdout
    assert "Agent feature mode: passive" in proc.stdout


def test_repl_agent_mode_block_does_not_fall_through_to_selector(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "no_active_mode.md").write_text(
        "# Rule: no_active_mode\nActive mode is disabled in this repo.\n",
        encoding="utf-8",
    )
    env = _repl_env()
    env["SNAPPY_AGENT_MODE"] = "passive"
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="agent mode active\nagent mode\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Active mode is disabled by the loaded agent rules." in proc.stdout
    assert "Current: passive" in proc.stdout
    assert "Source: environment" in proc.stdout
    assert "Select mode:" not in proc.stdout
    assert "Enter choice >" not in proc.stdout
    assert "Invalid mode. Choose: off, passive, active" not in proc.stdout


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
    assert "Policy tiers: block=0, confirm=0, warn=0, info=1" in proc.stdout
    assert "Agent memory session keys: last_goal, notes" in proc.stdout


def test_repl_after_during_clarification_is_actionable(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nafter\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Pending question: destination path>" in proc.stdout
    assert "Session Status" not in proc.stdout


def test_repl_after_in_idle_is_clean(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="after\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "No pending next step." in proc.stdout
    assert "Session Status" not in proc.stdout


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
