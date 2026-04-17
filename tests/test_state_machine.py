from io import StringIO
from pathlib import Path
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.agent_fixtures import load_agent_fixture
from snappy_putty import cli
from snappy_putty.fs_models import FsPlan, PlannedOp
from snappy_putty.session import LifecycleState, SessionState


def _capture_console(monkeypatch):
    buffer = StringIO()
    test_console = Console(file=buffer, force_terminal=False, color_system=None)
    monkeypatch.setattr(cli, "console", test_console)
    return buffer


def test_session_state_defaults_to_idle_and_preserves_history_on_clear_pending() -> None:
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        pending_question="destination path>",
        pending_plan=["step"],
        awaiting_confirmation=True,
        last_completed_goal="done",
        last_cancelled_goal="stopped",
        last_failed_goal="broken",
        error_message="boom",
        pending_context={"type": "fs_confirmation"},
    )

    state.clear_pending()

    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.pending_context == {}
    assert state.last_completed_goal == "done"
    assert state.last_cancelled_goal == "stopped"
    assert state.last_failed_goal == "broken"
    assert state.error_message == "boom"
    assert SessionState().current_state == LifecycleState.IDLE


def test_session_reset_clears_active_and_pending_state() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="git push",
        last_route="ask",
        last_result="Awaiting clarification.",
        pending_question="Which remote?",
        pending_plan=["step"],
        awaiting_confirmation=True,
        error_message="boom",
        pending_context={"type": "ask_followup", "base_intent": "git push"},
        last_completed_goal="done",
    )

    state.reset()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.error_message is None
    assert state.pending_context == {}
    assert state.last_completed_goal == "done"


def test_reset_to_idle_preserving_history_keeps_failure_metadata() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="git push",
        last_route="unknown",
        pending_question="Which remote?",
        pending_plan=["step"],
        awaiting_confirmation=True,
        last_failed_goal="git push",
        error_message="Unrecognized command",
        pending_context={"type": "ask_followup", "base_intent": "git push"},
    )

    state.reset_to_idle_preserving_history()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.pending_context == {}
    assert state.last_route == "unknown"
    assert state.last_failed_goal == "git push"
    assert state.error_message == "Unrecognized command"


def test_repl_help_includes_agent_commands_with_readable_formatting(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)

    cli.print_repl_cheatsheet()

    output = buffer.getvalue()
    assert "Quick commands" in output
    assert "Ask follow-up questions when a request needs clarification." in output
    assert "agent             Show the loaded agent summary." in output
    assert "agent mode        Inspect or change agent runtime mode." in output
    assert "after             Show the next expected input or step." in output
    assert "status            Show diagnostic session and agent status." in output
    assert "cancel            Clear pending workflow state." in output
    assert "skills            List loaded .snappy skills." in output
    assert "rules             List loaded .snappy rules." in output
    assert "init              Scaffold a .snappy/ agent directory." in output
    assert "exit / quit       Leave the interactive shell." in output
    assert "Workflow tips" in output
    assert "Use 'after' to see the next expected input." in output
    assert '"copy README.md"' in output
    assert '"destination path> tests/"' in output


def test_agent_mode_choice_question_defaults_to_current_selection() -> None:
    question = cli._build_agent_mode_choice_question(current_mode="passive", source="session")

    assert question["selected_index"] == 1
    assert "Current: passive" in str(question["message"])
    assert question["footer"] == "(Use ↑/↓ to navigate, ENTER to select)"


def test_agent_mode_without_argument_is_display_only(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(agent_mode="passive")

    handled = cli._handle_agent_mode_command("agent mode", state)

    assert handled is True
    assert state.agent_mode == "passive"
    output = buffer.getvalue()
    assert "Agent Mode" in output
    assert "Current: passive" in output
    assert "Source: session" in output
    assert "Select mode:" not in output


def test_agent_mode_select_opens_menu_and_applies_choice(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState()
    monkeypatch.setattr(cli, "_prompt_for_agent_mode", lambda session, current_mode, source: "passive")

    handled = cli._handle_agent_mode_command("agent mode select", state)

    assert handled is True
    assert state.agent_mode == "passive"
    output = buffer.getvalue()
    assert "Agent mode set to: passive (session)" in output


def test_status_includes_current_state_and_failure_fields(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.IDLE,
        last_failed_goal="copy missing.txt out.txt",
        error_message="Applied 0 filesystem operation(s).",
    )

    cli._handle_status(state)

    output = buffer.getvalue()
    assert "Current state: IDLE" in output
    assert "Last failed goal: copy missing.txt out.txt" in output
    assert "Error message: Applied 0 filesystem operation(s)." in output


def test_status_displays_agent_metadata_when_manifest_is_valid(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text(
        "name: Snappy Dev Agent\nversion: 2\nmode: supervised\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent name: Snappy Dev Agent" in output
    assert "Agent version: 2" in output
    assert "Agent mode: supervised" in output


def test_status_displays_agent_warning_when_manifest_is_invalid(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("malformed_manifest", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent warning: Invalid agent manifest:" in output


def test_status_displays_agent_section_with_no_agent(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: passive" in output
    assert "Agent mode source: environment" in output
    assert "Agent: (none loaded)" in output


def test_status_reflects_runtime_session_agent_mode(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    state = SessionState(agent_mode="passive")

    cli._handle_status(state)

    output = buffer.getvalue()
    assert "Agent feature mode: passive" in output
    assert "Agent mode source: session" in output


def test_status_displays_agent_section_with_valid_agent_details(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: passive" in output
    assert "Agent name: Fixture Agent" in output
    assert "Agent version: 1" in output
    assert "Agent mode: passive" in output
    assert "Loaded skills: 1" in output
    assert "Loaded rules: 1" in output
    assert "Enforceable rules: 0" in output
    assert "Informational rules: 1" in output
    assert "Agent memory: present" in output
    assert "Agent memory session keys: last_goal, notes" in output


def test_status_displays_agent_section_with_partial_metadata(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Partial Agent\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent name: Partial Agent" in output
    assert "Agent version: (unknown)" in output
    assert "Agent mode: (unknown)" in output
    assert "Loaded skills: 0" in output
    assert "Loaded rules: 0" in output
    assert "Agent memory: absent" in output


def test_status_displays_agent_memory_metadata(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    memory_dir = tmp_path / ".snappy" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "session.json").write_text('{"last_goal": "inspect logs"}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent memory: present" in output
    assert "Agent memory session keys: last_goal" in output


def test_status_displays_agent_memory_warning(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("malformed_memory", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent memory: present" in output
    assert "Agent memory warning: Invalid agent memory session:" in output


def test_status_displays_agent_feature_mode_off(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Hidden Agent\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "off")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: off" in output
    assert "Agent: (none loaded)" in output
    assert "Agent name: Hidden Agent" not in output
    assert "Agent memory:" not in output


def test_status_displays_agent_feature_mode_passive(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Passive Agent\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: passive" in output
    assert "Agent name: Passive Agent" in output


def test_status_displays_policy_tier_summary(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Loaded rules: 1" in output
    assert "Control layer: centralized pre-execution policy gate" in output
    assert "Policy hierarchy: BLOCK > CONFIRM > WARN > INFO" in output
    assert "Policy tiers: block=0, confirm=1, warn=0, info=0" in output
    assert "Confirmation-capable rules: 1" in output


def test_agent_summary_displays_no_agent_loaded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_summary_lines()

    assert "Agent feature mode: passive" in lines
    assert "Agent loaded: no" in lines
    assert "No .snappy agent is currently loaded." in lines


def test_agent_summary_displays_valid_loaded_agent(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_summary_lines()

    assert "Agent feature mode: passive" in lines
    assert "Agent loaded: yes" in lines
    assert "Manifest present: yes" in lines
    assert "Control layer: centralized pre-execution policy gate" in lines
    assert "Policy hierarchy: BLOCK > CONFIRM > WARN > INFO" in lines
    assert "Agent name: Fixture Agent" in lines
    assert "Version: 1" in lines
    assert "Agent mode: passive" in lines
    assert "Loaded skills: 1" in lines
    assert "Loaded rules: 1" in lines
    assert "Enforceable rules: 0" in lines
    assert "Informational rules: 1" in lines
    assert "Block rules: (none)" in lines
    assert "Confirm rules: (none)" in lines
    assert "Warn rules: (none)" in lines
    assert "Info rules: confirm_destructive_actions" in lines
    assert "Memory present: yes" in lines
    assert "Session memory keys: last_goal, notes" in lines


def test_agent_doctor_reports_no_agent_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_doctor_lines()

    assert "Agent feature mode: passive" in lines
    assert ".snappy directory: absent" in lines
    assert "Manifest file: absent" in lines
    assert "Skills directory: absent" in lines
    assert "Rules directory: absent" in lines
    assert "Memory directory: absent" in lines
    assert "Session file: absent" in lines


def test_agent_doctor_reports_valid_full_agent_setup(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_doctor_lines()

    assert ".snappy directory: present" in lines
    assert "Manifest file: present" in lines
    assert "Manifest parse: ok" in lines
    assert "Control layer ready: yes" in lines
    assert "Policy hierarchy: BLOCK > CONFIRM > WARN > INFO" in lines
    assert "Skills directory: present" in lines
    assert "Loaded skills: 1" in lines
    assert "Rules directory: present" in lines
    assert "Loaded rules: 1" in lines
    assert "Enforceable rules: 0" in lines
    assert "Informational rules: 1" in lines
    assert "Policy tiers: block=0, confirm=0, warn=0, info=1" in lines
    assert "Confirmation-capable rules: 0" in lines
    assert "Memory directory: present" in lines
    assert "Session file: present" in lines
    assert "Session parse: ok" in lines


def test_agent_mode_change_is_blocked_by_no_active_mode_rule(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "no_active_mode.md").write_text(
        "# Rule: no_active_mode\nActive mode is disabled in this repo.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
    state = SessionState(agent_mode="passive")

    handled = cli._handle_agent_mode_command("agent mode active", state)

    assert handled is True
    assert state.agent_mode == "passive"
    assert "Active mode is disabled by the loaded agent rules." in buffer.getvalue()


def test_agent_mode_change_is_blocked_when_no_active_mode_and_info_rule_are_loaded(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "no_active_mode.md").write_text(
        "# Rule: no_active_mode\nActive mode is disabled in this repo.\n",
        encoding="utf-8",
    )
    (rules_dir / "custom_note.md").write_text(
        "# Rule: custom_note\nHuman-readable guidance only.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
    state = SessionState(agent_mode="passive")

    handled = cli._handle_agent_mode_command("agent mode active", state)

    assert handled is True
    assert state.agent_mode == "passive"
    assert "Active mode is disabled by the loaded agent rules." in buffer.getvalue()


def test_confirmation_blocked_by_protect_project_root_rule_marks_goal_failed(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
    state = SessionState(
        agent_mode="passive",
        current_state=LifecycleState.CONFIRMATION,
        active_goal="make a folder called .",
        pending_plan=FsPlan(
            goal="make a folder called .",
            cwd=str(tmp_path),
            ops=[PlannedOp(op_id="op1", action="mkdir", src=None, dst=".", notes=[], risk="low")],
            warnings=[],
            requires_confirmation=True,
        ),
        awaiting_confirmation=True,
        pending_context={
            "type": "fs_confirmation",
            "stage": "apply",
            "workspace_root": str(tmp_path),
            "allow_overwrite": False,
            "allow_excess_ops": False,
            "excess_ops": False,
        },
    )

    cli._consume_confirmation_response("YES", state, tmp_path)

    output = buffer.getvalue()
    assert "Operation blocked by rule: protect_project_root" in output
    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_failed_goal == "make a folder called ."
    assert state.last_completed_goal is None


def test_agent_doctor_reports_malformed_manifest(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("malformed_manifest", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_doctor_lines()

    assert "Manifest file: present" in lines
    assert "Manifest parse: failed" in lines
    assert any(line.startswith("Manifest warning: Invalid agent manifest:") for line in lines)


def test_agent_doctor_reports_malformed_memory_file(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("malformed_memory", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_doctor_lines()

    assert "Memory directory: present" in lines
    assert "Session file: present" in lines
    assert "Session parse: failed" in lines
    assert any(line.startswith("Session warning: Invalid agent memory session:") for line in lines)


def test_agent_doctor_reports_malformed_skill_and_rule_files(monkeypatch, tmp_path: Path) -> None:
    agent_root = load_agent_fixture("malformed_skill", tmp_path)
    rules_dir = agent_root / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "broken.md").write_text("Rule without heading\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")

    lines = cli._build_agent_doctor_lines()

    assert "Loaded skills: 0" in lines
    assert "Loaded rules: 0" in lines
    assert any("Warning: skipped .snappy/skills/broken.md" in line for line in lines)
    assert any("Skipped invalid rule file broken.md" in line for line in lines)


def test_confirmation_without_pending_plan_records_failed_goal() -> None:
    state = SessionState(active_goal="copy a b", current_state=LifecycleState.CONFIRMATION)

    cli._consume_confirmation_response("YES", state, Path.cwd())

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_failed_goal == "copy a b"
    assert state.error_message == "Confirmation received, but no actionable pending state remained."
    assert state.last_result == "Confirmation received, but no actionable pending state remained."


def test_current_control_state_reports_confirmation_block_and_allow() -> None:
    awaiting = SessionState(awaiting_confirmation=True)
    blocked = SessionState(current_state=LifecycleState.FAILED, error_message="Operation blocked by rule: protect_project_root")
    allowed = SessionState()

    assert cli._current_control_state(awaiting) == "awaiting_confirm"
    assert cli._current_control_state(blocked) == "blocked"
    assert cli._current_control_state(allowed) == "allowed"


def test_confirmation_prompt_message_varies_by_stage() -> None:
    apply_state = SessionState(pending_context={"type": "fs_confirmation", "stage": "apply"})
    overwrite_state = SessionState(pending_context={"type": "fs_confirmation", "stage": "overwrite"})
    limit_state = SessionState(pending_context={"type": "fs_confirmation", "stage": "limit"})

    assert cli._confirmation_prompt_message(apply_state) == "Type YES to apply, or NO to cancel."
    assert cli._confirmation_prompt_message(overwrite_state) == "Destination exists. Type YES to overwrite, or NO to cancel."
    assert cli._confirmation_prompt_message(limit_state) == f"Plan exceeds {cli.MAX_OPS} operations. Type YES to continue, or NO to cancel."


def test_empty_fs_plan_feedback_distinguishes_workspace_block_from_invalid_request() -> None:
    workspace_block = FsPlan(
        goal="copy README.md to /",
        cwd="/tmp/demo",
        ops=[],
        warnings=["Path escapes workspace root: /tmp/demo"],
        requires_confirmation=False,
    )
    invalid_request = FsPlan(
        goal="copy missing.txt to beta.txt",
        cwd="/tmp/demo",
        ops=[],
        warnings=["Source does not exist: missing.txt"],
        requires_confirmation=False,
    )
    same_file = FsPlan(
        goal="copy README.md README.md",
        cwd="/tmp/demo",
        ops=[],
        warnings=["Source and destination resolve to the same file."],
        requires_confirmation=False,
    )

    assert cli._empty_fs_plan_feedback(workspace_block)[0:2] == (
        "Blocked Request",
        "No executable filesystem changes were planned because the target path is outside the workspace root.",
    )
    assert cli._empty_fs_plan_feedback(invalid_request)[0:2] == (
        "Invalid Request",
        "No executable filesystem changes were planned because the request could not be normalized into a valid filesystem change.",
    )
    assert cli._empty_fs_plan_feedback(same_file)[0:2] == (
        "No-Op Request",
        "No executable filesystem changes were planned because the request resolves to the same source and destination.",
    )


def test_after_uses_stage_specific_confirmation_prompt(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        awaiting_confirmation=True,
        pending_context={"type": "fs_confirmation", "stage": "overwrite"},
    )

    cli._handle_after(state)

    output = " ".join(buffer.getvalue().split())
    assert "Awaiting confirmation: Destination exists." in output
    assert "Type YES to overwrite, or NO to cancel." in output


def test_after_in_idle_reports_no_pending_next_step(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)

    cli._handle_after(SessionState())

    assert "No pending next step." in buffer.getvalue()


def test_clarification_response_validation_distinguishes_answers_from_new_commands() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="copy a.txt",
        pending_question="destination path>",
        pending_context={"type": "fs_destination", "action": "copy", "src": "a.txt"},
    )

    assert cli.is_valid_clarification_response("b.txt", state) is True
    assert cli.is_valid_clarification_response("yes", state) is True
    assert cli.is_valid_clarification_response("give me a file listing for the current directory", state) is False


def test_path_clarification_accepts_path_like_input_and_rejects_command_like_input() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="copy README.md",
        pending_question={"type": "path", "prompt": "destination path>"},
        pending_context={"type": "fs_destination", "action": "copy", "src": "README.md"},
    )

    assert cli.is_valid_clarification_response("tests/", state) is True
    assert cli.is_valid_clarification_response("./backup", state) is True
    assert cli.is_valid_clarification_response("../dir", state) is True
    assert cli.is_valid_clarification_response("git status", state) is False


def test_resolve_choice_menu_input_maps_numeric_selection_to_value() -> None:
    question = cli._build_listing_choice_question()

    assert cli._resolve_choice_menu_input("1", question) == "."
    assert cli._resolve_choice_menu_input("2", question) == "/"
    assert cli._resolve_choice_menu_input("3", question) == "custom"
    assert cli._resolve_choice_menu_input("git status", question) == "git status"


def test_should_consume_path_clarification_response_even_when_route_is_unknown() -> None:
    state = SessionState(
        pending_question={"type": "path", "prompt": "destination path>"},
        pending_context={"type": "fs_destination", "action": "copy", "src": "README.md"},
    )

    assert cli._should_consume_pending_question(text="tests/", route="unknown", state=state) is True


def test_clarification_lock_rejects_new_command_without_mutating_state(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="git push",
        pending_question="Which remote do you mean?",
        pending_plan=["step"],
        last_route="ask",
        last_completed_goal="completed",
        last_failed_goal="failed",
        last_cancelled_goal="cancelled",
        pending_context={"type": "ask_followup", "base_intent": "git push"},
    )
    text = "give me a file listing for the current directory"
    decision = cli.classify_input(text)

    assert cli._clarification_input_is_locked(text=text, route=decision.route, state=state) is True

    cli._render_clarification_lock_message(state)

    assert state.current_state == LifecycleState.CLARIFICATION
    assert state.active_goal == "git push"
    assert state.pending_question == "Which remote do you mean?"
    assert state.pending_plan == ["step"]
    assert state.last_route == "ask"
    assert state.last_completed_goal == "completed"
    assert state.last_failed_goal == "failed"
    assert state.last_cancelled_goal == "cancelled"
    assert cli._should_consume_pending_question(text=text, route=decision.route, state=state) is False
    assert "You have a pending question." in buffer.getvalue()
    assert "Answer it, or type 'cancel' to abandon the current goal." in buffer.getvalue()


def test_guided_listing_custom_selection_switches_to_custom_path_prompt(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="give me a file listing",
        pending_question=cli._build_listing_choice_question(),
        pending_context={"type": "guided_listing_choice", "base_intent": "give me a file listing"},
    )

    cli._consume_pending_question_answer("custom", state)

    assert state.current_state == LifecycleState.CLARIFICATION
    assert state.pending_question == {"type": "path", "prompt": "Enter custom path:"}
    assert state.pending_context == {"type": "guided_listing_custom_path", "base_intent": "give me a file listing"}
    assert buffer.getvalue() == ""


def test_render_prompt_uses_inline_clarification_prompt() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        pending_question={"type": "path", "prompt": "destination path>"},
    )

    assert cli.render_prompt(state) == "destination path>"
    state.current_state = LifecycleState.IDLE
    assert cli.render_prompt(state) == "snappy> "
