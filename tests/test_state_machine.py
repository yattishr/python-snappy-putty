from io import StringIO
from contextlib import contextmanager
from pathlib import Path
import sys

import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.agent_fixtures import load_agent_fixture
from snappy_putty import cli
from snappy_putty.fs_models import FsApplyItem, FsApplyResult, FsPlan, PlannedOp
from snappy_putty.memory import save_project_snapshot
from snappy_putty.project_inspector import inspect_project
from snappy_putty.session import (
    ActiveGoalConflictError,
    ActiveWorkflowSnapshot,
    ClarificationContext,
    ConfirmationContext,
    ExecutionOperation,
    ExecutionResult,
    InvalidLifecycleTransition,
    LifecycleState,
    OutputGenerationContext,
    SessionState,
    clear_workflow_snapshot,
    load_workflow_snapshot,
    save_workflow_snapshot,
)


def _capture_console(monkeypatch):
    buffer = StringIO()
    test_console = Console(file=buffer, force_terminal=False, color_system=None)
    monkeypatch.setattr(cli, "console", test_console)
    return buffer


def _write_config(root: Path, *, name: str = "Home Demo", mode: str = "active", skills: list[str] | None = None) -> None:
    enabled = "\n".join(f"    - {skill}" for skill in skills or [])
    enabled_block = f"\n{enabled}" if enabled else " []"
    config_dir = root / ".snappy"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "snappy.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "",
                "agent:",
                f"  name: {name}",
                f"  mode: {mode}",
                "",
                "skills:",
                f"  enabled:{enabled_block}",
                "  disabled: []",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / ".snappy" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: Use when testing the home screen.
x-snappy:
  risk: low
---

Test skill.
""",
        encoding="utf-8",
    )


def test_session_state_defaults_to_idle_and_preserves_history_on_clear_pending() -> None:
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        pending_question="destination path>",
        pending_plan=["step"],
        awaiting_confirmation=True,
        last_completed_goal="done",
        last_cancelled_goal="stopped",
        last_failed_goal="broken",
        last_blocked_goal="denied",
        error_message="boom",
        pending_context=ConfirmationContext(operation_count=1),
    )

    state.clear_pending()

    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.pending_context is None
    assert state.last_completed_goal == "done"
    assert state.last_cancelled_goal == "stopped"
    assert state.last_failed_goal == "broken"
    assert state.last_blocked_goal == "denied"
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
        pending_context=ClarificationContext(base_intent="git push", prompt_kind="ask_followup"),
        last_completed_goal="done",
        last_blocked_goal="denied",
    )

    state.reset()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.error_message is None
    assert state.pending_context is None
    assert state.last_completed_goal == "done"
    assert state.last_blocked_goal == "denied"


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
        pending_context=ClarificationContext(base_intent="git push", prompt_kind="ask_followup"),
    )

    state.reset_to_idle_preserving_history()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.pending_question is None
    assert state.pending_plan is None
    assert state.awaiting_confirmation is False
    assert state.pending_context is None
    assert state.last_route == "unknown"
    assert state.last_failed_goal == "git push"
    assert state.error_message == "Unrecognized command"


def test_session_state_m3_transitions_allow_required_path_and_terminal_reset() -> None:
    state = SessionState()

    state.transition_to(LifecycleState.INTENT_RECEIVED)
    state.transition_to(LifecycleState.PLANNING)
    state.transition_to(LifecycleState.CONFIRMATION)
    state.transition_to(LifecycleState.EXECUTING)
    state.transition_to(LifecycleState.REFLECTING)
    state.transition_to(LifecycleState.COMPLETED)
    state.transition_to(LifecycleState.IDLE)

    assert state.current_state == LifecycleState.IDLE


def test_session_state_invalid_transition_is_rejected() -> None:
    state = SessionState(current_state=LifecycleState.CONFIRMATION)

    with pytest.raises(InvalidLifecycleTransition):
        state.transition_to(LifecycleState.PLANNING)


def test_active_workflow_snapshot_can_be_created_for_clarification_state() -> None:
    state = SessionState()

    state.start_goal(goal="copy README.md", route="fs_mutation")
    state.pending_question = "destination path>"
    state.update_workflow_context(
        ClarificationContext(source_path="README.md", expected_input="path", action="copy", prompt_kind="fs_destination")
    )
    state.transition_to(LifecycleState.PLANNING)
    state.transition_to(LifecycleState.CLARIFICATION)

    assert state.active_workflow is not None
    assert state.active_workflow.goal == "copy README.md"
    assert state.active_workflow.state == "CLARIFICATION"
    assert state.active_workflow.pending_question == "destination path>"
    assert isinstance(state.active_workflow.context, ClarificationContext)


def test_save_workflow_snapshot_persists_json_safe_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot = ActiveWorkflowSnapshot(
        workflow_id="wf-clarify",
        state="CLARIFICATION",
        goal="copy README.md",
        route="fs_mutation",
        pending_question="destination path>",
        pending_plan_summary=None,
        awaiting_confirmation=False,
        control_state="allowed",
        context=ClarificationContext(
            source_path="README.md",
            expected_input="path",
            action="copy",
            workspace_root=str(tmp_path),
            prompt_kind="fs_destination",
        ),
        pending_question_data={"type": "path", "prompt": "destination path>"},
        pending_plan_data=None,
    )

    save_workflow_snapshot(snapshot)

    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    assert session_path.is_file()
    payload = session_path.read_text(encoding="utf-8")
    assert '"workflow"' in payload
    assert '"state": "CLARIFICATION"' in payload
    assert '"pending_question_data"' in payload


def test_load_workflow_snapshot_restores_valid_confirmation_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    state = SessionState()
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")

    cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)

    restored = load_workflow_snapshot(tmp_path)

    assert restored is not None
    assert restored.state == "CONFIRMATION"
    assert restored.goal == "copy README.md to README-copy.md"
    assert restored.awaiting_confirmation is True
    assert isinstance(restored.context, ConfirmationContext)
    assert isinstance(restored.pending_plan_data, dict)


def test_load_workflow_snapshot_restores_advisory_confirmation_without_prompt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        '{"workflow": {"workflow_id": "wf-plan", "state": "CONFIRMATION", "goal": "help me improve this CLI", "route": "ask", "pending_question": null, "pending_plan_summary": "llm_assisted plan with 1 step(s)", "pending_plan_mode": "llm_assisted", "awaiting_confirmation": false, "control_state": "allowed", "context": null, "pending_question_data": null, "pending_plan_data": [{"step": 1, "action": "Inspect CLI", "why": "Grounded active plan"}]}}\n',
        encoding="utf-8",
    )

    restored = load_workflow_snapshot(tmp_path)

    assert restored is not None
    assert restored.state == "CONFIRMATION"
    assert restored.awaiting_confirmation is False
    assert restored.context is None
    assert isinstance(restored.pending_plan_data, list)


def test_load_workflow_snapshot_ignores_invalid_snapshot_and_clears_it(tmp_path: Path, monkeypatch, caplog) -> None:
    monkeypatch.chdir(tmp_path)
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        '{"workflow": {"workflow_id": "wf-bad", "state": "CLARIFICATION", "goal": "copy README.md", "route": "fs_mutation", "pending_question": null, "awaiting_confirmation": false, "control_state": "allowed", "context": null}}\n',
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        restored = load_workflow_snapshot(tmp_path)

    assert restored is None
    assert "Invalid workflow snapshot:" in caplog.text
    assert not session_path.exists()


def test_clear_workflow_snapshot_preserves_unrelated_agent_memory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        '{"last_goal": "inspect logs", "workflow": {"workflow_id": "wf-1", "state": "PLANNING", "goal": "inspect logs", "route": "ask", "pending_question": null, "pending_plan_summary": "agent plan with 1 step(s)", "awaiting_confirmation": false, "control_state": "allowed", "context": null, "pending_question_data": null, "pending_plan_data": [{"step": 1, "action": "Inspect logs", "why": "Need current data"}]}}\n',
        encoding="utf-8",
    )

    clear_workflow_snapshot(tmp_path)

    assert session_path.is_file()
    assert session_path.read_text(encoding="utf-8").strip() == '{\n  "last_goal": "inspect logs"\n}'


def test_active_workflow_snapshot_clears_on_terminal_cleanup() -> None:
    state = SessionState()

    state.start_goal(goal="git status", route="git_read")
    assert state.active_workflow is not None

    state.transition_to(LifecycleState.REFLECTING)
    state.transition_to(LifecycleState.COMPLETED)
    state.finish_cycle()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_workflow is None


def test_session_state_uses_single_active_workflow_snapshot() -> None:
    state = SessionState()

    state.start_goal(goal="first goal", route="ask")
    first_id = state.active_workflow.workflow_id if state.active_workflow else None
    state.sync_active_workflow()

    assert state.active_workflow is not None
    assert state.active_workflow.workflow_id == first_id

    with pytest.raises(ActiveGoalConflictError):
        state.start_goal(goal="second goal", route="git_read")


def test_restoration_friendly_snapshot_can_drive_status_reads(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        active_goal="copy README.md to backup/README.md",
        last_route="fs_mutation",
        active_workflow=ActiveWorkflowSnapshot(
            workflow_id="wf-123",
            state="CONFIRMATION",
            goal="copy README.md to backup/README.md",
            route="fs_mutation",
            pending_question="destination path>",
            pending_plan_summary="filesystem plan with 1 op(s)",
            awaiting_confirmation=True,
            control_state="awaiting_confirm",
            context=ConfirmationContext(operation_count=1, overwrite_detected=True, stage="overwrite"),
        ),
        workflow_restored_from_memory=True,
        restore_source=".snappy/memory/session.json",
    )

    cli._handle_status(state)

    output = buffer.getvalue()
    assert "Active goal: copy README.md to backup/README.md" in output
    assert "Pending question: destination path>" in output
    assert "Pending plan: filesystem plan with 1 op(s)" in output
    assert "Awaiting confirmation: yes" in output
    assert "Current control state: awaiting_confirm" in output
    assert "Workflow restored from memory: yes" in output
    assert "Restore source: .snappy/memory/session.json" in output


def test_restore_session_from_disk_recovers_clarification_without_execution(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    save_workflow_snapshot(
        ActiveWorkflowSnapshot(
            workflow_id="wf-clarify",
            state="CLARIFICATION",
            goal="copy README.md",
            route="fs_mutation",
            pending_question="destination path>",
            pending_plan_summary=None,
            awaiting_confirmation=False,
            control_state="allowed",
            context=ClarificationContext(
                source_path="README.md",
                expected_input="path",
                action="copy",
                workspace_root=str(tmp_path),
                prompt_kind="fs_destination",
            ),
            pending_question_data={"type": "path", "prompt": "destination path>"},
            pending_plan_data=None,
        ),
        tmp_path,
    )
    state = SessionState()

    message, warning = cli._restore_session_from_disk(state, tmp_path)

    assert warning is None
    assert message == "\n".join(
        [
            "Restored pending workflow: copy README.md",
            "State: clarification",
            "Awaiting: destination path>",
        ]
    )
    assert state.current_state == LifecycleState.CLARIFICATION
    assert state.active_goal == "copy README.md"
    assert state.awaiting_confirmation is False
    assert state.last_execution_result is None
    assert state.workflow_restored_from_memory is True
    assert buffer.getvalue() == ""


def test_restore_session_from_disk_marks_interrupted_execution_failed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    save_workflow_snapshot(
        ActiveWorkflowSnapshot(
            workflow_id="wf-exec",
            state="EXECUTING",
            goal="copy README.md README-copy.md",
            route="fs_mutation",
            pending_question=None,
            pending_plan_summary="filesystem plan with 1 op(s)",
            awaiting_confirmation=False,
            control_state="allowed",
            context=None,
            pending_question_data=None,
            pending_plan_data={
                "goal": "copy README.md README-copy.md",
                "cwd": str(tmp_path),
                "ops": [{"op_id": "op1", "action": "copy", "src": "README.md", "dst": "README-copy.md", "notes": [], "risk": "low"}],
                "warnings": [],
                "requires_confirmation": True,
            },
        ),
        tmp_path,
    )
    state = SessionState()

    message, warning = cli._restore_session_from_disk(state, tmp_path)

    assert warning is None
    assert message == "Previous workflow was interrupted during executing. It has been marked failed."
    assert state.current_state == LifecycleState.IDLE
    assert state.last_failed_goal == "copy README.md README-copy.md"
    assert state.active_goal is None
    assert load_workflow_snapshot(tmp_path) is None


def test_restore_session_from_disk_surfaces_invalid_snapshot_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    session_path = tmp_path / ".snappy" / "memory" / "session.json"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        '{"workflow": {"workflow_id": "wf-bad", "state": "CLARIFICATION", "goal": "copy README.md", "route": "fs_mutation", "pending_question": null, "awaiting_confirmation": false, "control_state": "allowed", "context": null}}\n',
        encoding="utf-8",
    )
    state = SessionState()

    message, warning = cli._restore_session_from_disk(state, tmp_path)

    assert message is None
    assert warning is not None
    assert "Snappy couldn't resume the previous workflow because its saved state was inconsistent" in warning
    assert "clarification workflow is missing pending_question" in warning
    assert "I cleared that stale workflow state and started a fresh session." in warning
    assert "Your project files and saved plans were not changed." in warning
    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.workflow_restored_from_memory is False
    assert not session_path.exists()


def test_render_prompt_uses_confirmation_context_when_confirmation_is_pending() -> None:
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        awaiting_confirmation=True,
        pending_context=ConfirmationContext(operation_count=1, stage="apply"),
    )

    assert cli.render_prompt(state) == "confirm [YES/NO]> "


def test_output_generation_confirmation_uses_choice_question() -> None:
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        awaiting_confirmation=True,
        pending_context=OutputGenerationContext(plan_id="plan-1", task_intent="code_review", selected_skills=("codeguardian-review",)),
    )

    question = cli._build_output_generation_confirmation_question(state)

    assert cli._should_prompt_output_generation_confirmation(state) is True
    assert question["type"] == "choice"
    assert "Ready to generate a CodeGuardian review report" in str(question["message"])
    assert "No files will be changed" in str(question["message"])
    assert question["options"] == [
        {"label": "YES", "value": "YES"},
        {"label": "NO", "value": "NO"},
    ]
    assert question["escape_value"] == "NO"


def test_output_generation_confirmation_choice_fallback_accepts_number(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        awaiting_confirmation=True,
        pending_context=OutputGenerationContext(plan_id="plan-1", task_intent="code_review", selected_skills=("codeguardian-review",)),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")

    selected = cli._prompt_choice_fallback(cli._build_output_generation_confirmation_question(state))

    assert selected == "NO"
    output = buffer.getvalue()
    assert "YES" in output
    assert "NO" in output


def test_session_state_start_goal_rejects_nested_active_goal() -> None:
    state = SessionState(
        current_state=LifecycleState.CONFIRMATION,
        active_goal="copy README.md README-copy.md",
    )

    with pytest.raises(ActiveGoalConflictError):
        state.start_goal(goal="git status", route="git_read")


def test_complete_active_goal_produces_execution_result_completed() -> None:
    state = SessionState(active_goal="git status", current_state=LifecycleState.EXECUTING)

    cli._complete_active_goal(state, message="Git status retrieved.")

    assert state.current_state == LifecycleState.IDLE
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "completed"
    assert state.last_execution_result.goal == "git status"
    assert state.last_result == "Git status retrieved."


def test_fail_active_goal_produces_execution_result_failed() -> None:
    state = SessionState(active_goal="copy a b", current_state=LifecycleState.EXECUTING)

    cli._fail_active_goal(state, message="Copy failed.")

    assert state.current_state == LifecycleState.IDLE
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "failed"
    assert state.last_execution_result.error == "Copy failed."
    assert state.last_failed_goal == "copy a b"


def test_cancel_active_goal_produces_execution_result_cancelled() -> None:
    state = SessionState(active_goal="copy a b", current_state=LifecycleState.CONFIRMATION)

    cli._cancel_active_goal(state, message="Cancelled pending action.")

    assert state.current_state == LifecycleState.IDLE
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "cancelled"
    assert state.last_cancelled_goal == "copy a b"
    assert state.last_blocked_goal is None


@pytest.mark.parametrize(
    ("status", "expected_terminal"),
    [
        ("completed", LifecycleState.COMPLETED),
        ("failed", LifecycleState.FAILED),
        ("cancelled", LifecycleState.CANCELLED),
        ("blocked", LifecycleState.BLOCKED),
    ],
)
def test_reflection_maps_execution_result_status_to_terminal_state(monkeypatch, status: str, expected_terminal: LifecycleState) -> None:
    terminal_states: list[LifecycleState] = []
    state = SessionState(active_goal="demo", current_state=LifecycleState.EXECUTING)

    def _capture_finish(session_state: SessionState) -> None:
        terminal_states.append(session_state.current_state)

    monkeypatch.setattr(cli, "_finish_terminal_state", _capture_finish)

    cli._reflect_execution_result(
        state,
        ExecutionResult(
            goal="demo",
            status=status,
            summary=f"{status} summary",
            operations=(ExecutionOperation(action="demo", status="applied", message="done"),),
            error="boom" if status in {"failed", "blocked"} else None,
        ),
    )

    assert terminal_states == [expected_terminal]


def test_single_goal_loop_successful_execution_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "README.md"
    src.write_text("demo\n", encoding="utf-8")
    state = SessionState()

    handled = cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)

    assert handled is True
    assert state.current_state == LifecycleState.CONFIRMATION
    assert state.active_goal == "copy README.md to README-copy.md"
    assert state.pending_plan is not None
    assert state.awaiting_confirmation is True

    cli._consume_confirmation_response("YES", state, tmp_path)

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "completed"
    assert (tmp_path / "README-copy.md").read_text(encoding="utf-8") == "demo\n"


def test_single_goal_loop_cancel_flow_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState()

    cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)
    cli._consume_confirmation_response("NO", state, tmp_path)

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "cancelled"
    assert not (tmp_path / "README-copy.md").exists()


def test_single_goal_loop_blocked_flow_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState(agent_mode="active")

    handled = cli._handle_fs_intent_repl("copy README.md to /", tmp_path, state)

    assert handled is True
    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "blocked"
    assert state.last_blocked_goal == "copy README.md to /"


def test_single_goal_loop_execution_failure_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState()

    cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)

    def _failed_apply(*args, **kwargs):
        return FsApplyResult(
            goal="copy README.md to README-copy.md",
            results=[FsApplyItem(op_id="op1", action="copy", status="failed", message="write failed")],
            warnings=[],
        )

    monkeypatch.setattr(cli, "apply_fs_plan", _failed_apply)

    cli._consume_confirmation_response("YES", state, tmp_path)

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "failed"
    assert state.last_failed_goal == "copy README.md to README-copy.md"


def test_invalid_confirmation_input_preserves_pending_confirmation_state(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState()

    cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)
    pending_plan = state.pending_plan
    active_goal = state.active_goal

    consumed = cli._handle_confirmation_input(
        text="maybe",
        route="ask",
        state=state,
        workspace_root=tmp_path,
    )

    assert consumed is True
    assert state.current_state == LifecycleState.CONFIRMATION
    assert state.active_goal == active_goal
    assert state.pending_plan == pending_plan
    assert state.awaiting_confirmation is True
    assert state.last_execution_result is None
    assert not (tmp_path / "README-copy.md").exists()
    assert "Please answer YES or NO." in buffer.getvalue()


def test_no_second_goal_begins_while_confirmation_is_pending(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState()

    cli._handle_fs_intent_repl("copy README.md to README-copy.md", tmp_path, state)
    active_goal = state.active_goal

    consumed = cli._handle_confirmation_input(
        text="git status",
        route="git_read",
        state=state,
        workspace_root=tmp_path,
    )

    assert consumed is True
    assert state.current_state == LifecycleState.CONFIRMATION
    assert state.active_goal == active_goal
    assert state.last_execution_result is None


def test_sequential_loop_integrity_across_multiple_runs(monkeypatch, tmp_path: Path) -> None:
    _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    state = SessionState()

    cli._handle_fs_intent_repl("copy README.md to first-copy.md", tmp_path, state)
    cli._consume_confirmation_response("YES", state, tmp_path)

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.goal == "copy README.md to first-copy.md"

    cli._handle_fs_intent_repl("copy README.md to second-copy.md", tmp_path, state)
    cli._consume_confirmation_response("YES", state, tmp_path)

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_execution_result is not None
    assert state.last_execution_result.goal == "copy README.md to second-copy.md"
    assert (tmp_path / "first-copy.md").exists()
    assert (tmp_path / "second-copy.md").exists()


def test_repl_help_includes_agent_commands_with_readable_formatting(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)

    cli.print_repl_cheatsheet()

    output = buffer.getvalue()
    assert "Quick commands" in output
    assert "Ask follow-up questions when a request needs clarification." in output
    assert "agent" in output
    assert "Agent summary." in output
    assert "agent mode" in output
    assert "Edit runtime mode." in output
    assert "after" in output
    assert "Next input or step." in output
    assert "status" in output
    assert "Session status." in output
    assert "cancel" in output
    assert "Clear workflow." in output
    assert "skills" in output
    assert "Skills list." in output
    assert "rules" in output
    assert "Rules list." in output
    assert "init" in output
    assert "Scaffold .snappy/." in output
    assert "exit / quit" in output
    assert "Leave shell." in output
    assert "Workflow tips" in output
    assert "Use 'after' to see the next expected input." in output
    assert '"copy README.md"' in output
    assert '"destination path> tests/"' in output


def test_repl_home_shows_compact_project_status_without_skill_names(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    (tmp_path / "package.json").write_text('{"dependencies":{"express":"latest"}}\n', encoding="utf-8")
    _write_skill(tmp_path, "code-review")
    _write_config(tmp_path, name="Home Screen Project", mode="active", skills=["code-review"])
    save_project_snapshot(tmp_path, inspect_project(tmp_path))

    cli.print_repl_home(SessionState(), root=tmp_path)

    output = buffer.getvalue()
    assert "Snappy PuTTy" in output
    assert "Project-Aware AI Co-Pilot" in output
    assert "Project" in output
    assert "Home Screen Project" in output
    assert "Active" in output
    assert "Snapshot ready" in output
    assert "1 skill enabled" in output
    assert "code-review" not in output
    assert "Build a frontend for this API" in output
    assert "help • skills • inspect • status • exit" in output
    assert "Quick commands" not in output
    assert "Workflow tips" not in output


def test_repl_home_shows_last_activity_when_available(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(last_completed_goal="Review my latest changes and give me MR-style feedback")

    cli.print_repl_home(state, root=tmp_path)

    output = buffer.getvalue()
    assert "Last Activity" in output
    assert "Review my latest changes and give me MR-style feedback" in output


def test_repl_home_shows_last_activity_fallback(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)

    cli.print_repl_home(SessionState(), root=tmp_path)

    output = buffer.getvalue()
    assert "No recent command yet" in output


def test_repl_home_handles_missing_config_and_no_snapshot(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)

    cli.print_repl_home(SessionState(), root=tmp_path)

    output = buffer.getvalue()
    assert tmp_path.name in output
    assert "Config not initialized" in output
    assert "Off" in output
    assert "No snapshot yet" in output
    assert "0 skills enabled" in output
    assert "Inspect this project" in output
    assert "Explain this codebase" in output
    assert "Show available skills" in output


def test_repl_home_handles_malformed_config_without_crashing(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    config_dir = tmp_path / ".snappy"
    config_dir.mkdir()
    (config_dir / "snappy.yaml").write_text("version: [broken\n", encoding="utf-8")

    cli.print_repl_home(SessionState(), root=tmp_path)

    output = buffer.getvalue()
    assert "Config warning: run `snappy config validate`" in output
    assert tmp_path.name in output


def test_agent_mode_choice_question_defaults_to_current_selection() -> None:
    question = cli._build_agent_mode_choice_question(current_mode="active", source="session")

    assert question["selected_index"] == 1
    assert "Current: active" in str(question["message"])
    assert question["footer"] == "(Use ↑/↓ to navigate, ENTER to select)"


def test_choice_prompt_text_numbers_arrow_menu_options() -> None:
    question = cli._build_active_goal_conflict_question(
        active_goal="help me improve this api",
        incoming_goal="help me build a front end with an admin interface",
    )

    output = cli._render_choice_prompt_text(question)

    assert "› 1. Keep current goal active" in output
    assert "  2. Cancel current goal and start this request" in output
    assert "  3. Park this new request for later" in output


def test_active_goal_conflict_choice_maps_numeric_and_text_input() -> None:
    question = cli._build_active_goal_conflict_question(
        active_goal="help me improve this api",
        incoming_goal="help me build a front end with an admin interface",
    )

    assert cli._resolve_active_goal_conflict_choice("1", question) == cli.CONFLICT_KEEP_CURRENT
    assert cli._resolve_active_goal_conflict_choice("2", question) == cli.CONFLICT_CANCEL_AND_START
    assert cli._resolve_active_goal_conflict_choice("3", question) == cli.CONFLICT_PARK_INCOMING
    assert cli._resolve_active_goal_conflict_choice("park this", question) == cli.CONFLICT_PARK_INCOMING
    assert cli._resolve_active_goal_conflict_choice("", question) == cli.CONFLICT_KEEP_CURRENT


def test_agent_mode_without_argument_is_display_only(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(agent_mode="active")

    handled = cli._handle_agent_mode_command("agent mode", state)

    assert handled is True
    assert state.agent_mode == "active"
    output = buffer.getvalue()
    assert "Agent Mode" in output
    assert "Current: active" in output
    assert "Source: session" in output
    assert "Select mode:" not in output


def test_agent_mode_select_opens_menu_and_applies_choice(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState()
    monkeypatch.setattr(cli, "_prompt_for_agent_mode", lambda session, current_mode, source: "active")

    handled = cli._handle_agent_mode_command("agent mode select", state)

    assert handled is True
    assert state.agent_mode == "active"
    output = buffer.getvalue()
    assert "Agent mode set to: active (session)" in output
    assert "Beast mode ON" in output


def test_why_current_plan_uses_spinner_for_llm_rationale(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    entered: list[str] = []

    plan = cli.GroundedPlan(
        plan_id="plan_demo",
        goal="help me improve this CLI",
        mode="llm_assisted",
        created_at="2026-05-18T00:00:00+00:00",
        based_on_snapshot_id="snap_demo",
        files_inspected=["src/snappy_putty/cli.py"],
        steps=[
            cli.GroundedPlanStep(
                step_id="step_1",
                description="Review CLI behavior.",
                files=["src/snappy_putty/cli.py"],
                proposed_new_files=[],
                risk="LOW",
                requires_confirmation=True,
            )
        ],
        risks=[],
        assumptions=[],
        status="awaiting_confirmation",
        summary="Demo plan",
        refinements=[],
        invalidation_reason=None,
        context_selection={},
    )

    class FakeRationaleClient:
        def explain_plan(self, prompt: str) -> str:
            return "Because the selected files contain the active CLI workflow."

    @contextmanager
    def fake_busy(message: str | None = None, *, console=None):
        entered.append(message or "")
        yield

    monkeypatch.setattr(cli, "load_grounded_plan", lambda root: plan)
    monkeypatch.setattr(cli, "default_llm_rationale_client", lambda session_mode=None: FakeRationaleClient())
    monkeypatch.setattr(cli, "load_project_snapshot", lambda root: None)
    monkeypatch.setattr(cli, "get_status_message", lambda mode=None: f"status:{mode}")
    monkeypatch.setattr(cli, "busy", fake_busy)

    result = cli._why_current_plan(tmp_path, session_mode="active")

    assert result == plan
    assert entered == ["status:rationale"]
    assert "Because the selected files contain the active CLI workflow." in buffer.getvalue()


def test_status_includes_current_state_and_failure_fields(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.IDLE,
        last_failed_goal="copy missing.txt out.txt",
        last_blocked_goal="copy README.md to /",
        error_message="Applied 0 filesystem operation(s).",
    )

    cli._handle_status(state)

    output = buffer.getvalue()
    assert "Current state: IDLE" in output
    assert "Last failed goal: copy missing.txt out.txt" in output
    assert "Last blocked goal: copy README.md to /" in output
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent name: Snappy Dev Agent" in output
    assert "Agent version: 2" in output
    assert "Agent mode: supervised" in output


def test_status_displays_agent_warning_when_manifest_is_invalid(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("malformed_manifest", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent warning: Invalid agent manifest:" in output


def test_status_displays_agent_section_with_no_agent(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: active" in output
    assert "Agent mode source: environment" in output
    assert "Agent: (none loaded)" in output


def test_status_reflects_runtime_session_agent_mode(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    state = SessionState(agent_mode="active")

    cli._handle_status(state)

    output = buffer.getvalue()
    assert "Agent feature mode: active" in output
    assert "Agent mode source: session" in output


def test_status_displays_agent_section_with_valid_agent_details(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: active" in output
    assert "Agent name: Fixture Agent" in output
    assert "Agent version: 1" in output
    assert "Agent mode: active" in output
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent memory: present" in output
    assert "Agent memory session keys: last_goal" in output


def test_status_displays_agent_memory_warning(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    load_agent_fixture("malformed_memory", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

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


def test_status_displays_agent_feature_mode_active(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Passive Agent\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Agent feature mode: active" in output
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    cli._handle_status(SessionState())

    output = buffer.getvalue()
    assert "Loaded rules: 1" in output
    assert "Control layer: centralized pre-execution policy gate" in output
    assert "Policy hierarchy: BLOCK > CONFIRM > WARN > INFO" in output
    assert "Policy tiers: block=0, confirm=1, warn=0, info=0" in output
    assert "Confirmation-capable rules: 1" in output


def test_agent_summary_displays_no_agent_loaded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    lines = cli._build_agent_summary_lines()

    assert "Agent feature mode: active" in lines
    assert "Agent loaded: no" in lines
    assert "No .snappy agent is currently loaded." in lines


def test_agent_summary_displays_valid_loaded_agent(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    lines = cli._build_agent_summary_lines()

    assert "Agent feature mode: active" in lines
    assert "Agent loaded: yes" in lines
    assert "Manifest present: yes" in lines
    assert "Control layer: centralized pre-execution policy gate" in lines
    assert "Policy hierarchy: BLOCK > CONFIRM > WARN > INFO" in lines
    assert "Agent name: Fixture Agent" in lines
    assert "Version: 1" in lines
    assert "Agent mode: active" in lines
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    lines = cli._build_agent_doctor_lines()

    assert "Agent feature mode: active" in lines
    assert ".snappy directory: absent" in lines
    assert "Manifest file: absent" in lines
    assert "Skills directory: absent" in lines
    assert "Rules directory: absent" in lines
    assert "Memory directory: absent" in lines
    assert "Session file: absent" in lines


def test_agent_doctor_reports_valid_full_agent_setup(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("valid_agent", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    state = SessionState(agent_mode="active")

    handled = cli._handle_agent_mode_command("agent mode active", state)

    assert handled is True
    assert state.agent_mode == "active"
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    state = SessionState(agent_mode="active")

    handled = cli._handle_agent_mode_command("agent mode active", state)

    assert handled is True
    assert state.agent_mode == "active"
    assert "Active mode is disabled by the loaded agent rules." in buffer.getvalue()


def test_confirmation_blocked_by_protect_project_root_rule_marks_goal_blocked(monkeypatch, tmp_path: Path) -> None:
    buffer = _capture_console(monkeypatch)
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    state = SessionState(
        agent_mode="active",
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
        pending_context=ConfirmationContext(
            operation_count=1,
            stage="apply",
            workspace_root=str(tmp_path),
            allow_overwrite=False,
            allow_excess_ops=False,
            excess_ops=False,
        ),
    )

    cli._consume_confirmation_response("YES", state, tmp_path)

    output = buffer.getvalue()
    assert "Operation blocked by rule: protect_project_root" in output
    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_failed_goal is None
    assert state.last_completed_goal is None
    assert state.last_blocked_goal == "make a folder called ."
    assert state.last_execution_result is not None
    assert state.last_execution_result.status == "blocked"
    assert state.error_message is not None
    assert "Operation blocked by rule: protect_project_root" in state.error_message


def test_agent_doctor_reports_malformed_manifest(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("malformed_manifest", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    lines = cli._build_agent_doctor_lines()

    assert "Manifest file: present" in lines
    assert "Manifest parse: failed" in lines
    assert any(line.startswith("Manifest warning: Invalid agent manifest:") for line in lines)


def test_agent_doctor_reports_malformed_memory_file(monkeypatch, tmp_path: Path) -> None:
    load_agent_fixture("malformed_memory", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

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
    blocked = SessionState(current_state=LifecycleState.BLOCKED, error_message="Operation blocked by rule: protect_project_root")
    allowed = SessionState()

    assert cli._current_control_state(awaiting) == "awaiting_confirm"
    assert cli._current_control_state(blocked) == "blocked"
    assert cli._current_control_state(allowed) == "allowed"


def test_confirmation_prompt_message_varies_by_stage() -> None:
    apply_state = SessionState(pending_context=ConfirmationContext(operation_count=1, stage="apply"))
    overwrite_state = SessionState(pending_context=ConfirmationContext(operation_count=1, stage="overwrite", overwrite_detected=True))
    limit_state = SessionState(pending_context=ConfirmationContext(operation_count=6, stage="limit"))

    assert cli._confirmation_prompt_message(apply_state) == "Ready to apply filesystem changes.\n\nFiles may be modified.\n\nContinue?"
    assert cli._confirmation_prompt_message(overwrite_state) == "Destination exists.\n\nFiles may be modified.\n\nContinue?"
    assert cli._confirmation_prompt_message(limit_state) == f"Plan exceeds {cli.MAX_OPS} operations.\n\nFiles may be modified.\n\nContinue?"


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
        pending_context=ConfirmationContext(operation_count=1, stage="overwrite", overwrite_detected=True),
    )

    cli._handle_after(state)

    output = " ".join(buffer.getvalue().split())
    assert "Awaiting confirmation: Destination exists." in output
    assert "Files may be modified." in output
    assert "Continue?" in output


def test_after_in_idle_reports_no_pending_next_step(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)

    cli._handle_after(SessionState())

    assert "No pending next step." in buffer.getvalue()


def test_clarification_response_validation_distinguishes_answers_from_new_commands() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="copy a.txt",
        pending_question="destination path>",
        pending_context=ClarificationContext(source_path="a.txt", expected_input="path", action="copy", prompt_kind="fs_destination"),
    )

    assert cli.is_valid_clarification_response("b.txt", state) is True
    assert cli.is_valid_clarification_response("yes", state) is True
    assert cli.is_valid_clarification_response("give me a file listing for the current directory", state) is False


def test_path_clarification_accepts_path_like_input_and_rejects_command_like_input() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="copy README.md",
        pending_question={"type": "path", "prompt": "destination path>"},
        pending_context=ClarificationContext(source_path="README.md", expected_input="path", action="copy", prompt_kind="fs_destination"),
    )

    assert cli.is_valid_clarification_response("tests/", state) is True
    assert cli.is_valid_clarification_response("./backup", state) is True
    assert cli.is_valid_clarification_response("../dir", state) is True
    assert cli.is_valid_clarification_response("git status", state) is False
    assert cli.is_valid_clarification_response("copy README.md README_manual_12.md", state) is False


def test_resolve_choice_menu_input_maps_numeric_selection_to_value() -> None:
    question = cli._build_listing_choice_question()

    assert cli._resolve_choice_menu_input("1", question) == "."
    assert cli._resolve_choice_menu_input("2", question) == "/"
    assert cli._resolve_choice_menu_input("3", question) == "custom"
    assert cli._resolve_choice_menu_input("git status", question) == "git status"


def test_should_consume_path_clarification_response_even_when_route_is_unknown() -> None:
    state = SessionState(
        pending_question={"type": "path", "prompt": "destination path>"},
        pending_context=ClarificationContext(source_path="README.md", expected_input="path", action="copy", prompt_kind="fs_destination"),
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
        last_blocked_goal="blocked",
        pending_context=ClarificationContext(base_intent="git push", expected_input="answer", prompt_kind="ask_followup"),
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
    assert state.last_blocked_goal == "blocked"
    assert cli._should_consume_pending_question(text=text, route=decision.route, state=state) is False
    assert "You have a pending question." in buffer.getvalue()
    assert "Answer it, or type 'cancel' to abandon the current goal." in buffer.getvalue()


def test_fs_destination_clarification_rejects_command_shaped_input_without_mutating_state(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="copy README.md",
        pending_question={"type": "path", "prompt": "destination path>"},
        pending_plan=None,
        last_route="fs_mutation",
        pending_context=ClarificationContext(
            source_path="README.md",
            expected_input="path",
            action="copy",
            workspace_root="/tmp/workspace",
            prompt_kind="fs_destination",
        ),
    )
    text = "git status"
    decision = cli.classify_input(text)

    assert cli._clarification_input_is_locked(text=text, route=decision.route, state=state) is True

    cli._render_clarification_lock_message(state)

    assert state.current_state == LifecycleState.CLARIFICATION
    assert state.active_goal == "copy README.md"
    assert state.pending_question == {"type": "path", "prompt": "destination path>"}
    assert state.pending_plan is None
    assert state.last_route == "fs_mutation"
    assert state.last_execution_result is None
    assert state.active_workflow is None
    assert cli._should_consume_pending_question(text=text, route=decision.route, state=state) is False
    assert "You have a pending question." in buffer.getvalue()
    assert "Answer it, or type 'cancel' to abandon the current goal." in buffer.getvalue()


def test_guided_listing_custom_selection_switches_to_custom_path_prompt(monkeypatch) -> None:
    buffer = _capture_console(monkeypatch)
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="give me a file listing",
        pending_question=cli._build_listing_choice_question(),
        pending_context=ClarificationContext(base_intent="give me a file listing", expected_input="choice", prompt_kind="guided_listing_choice"),
    )

    cli._consume_pending_question_answer("custom", state)

    assert state.current_state == LifecycleState.CLARIFICATION
    assert state.pending_question == {"type": "path", "prompt": "Enter custom path:"}
    assert state.pending_context == ClarificationContext(
        base_intent="give me a file listing",
        expected_input="path",
        prompt_kind="guided_listing_custom_path",
    )
    assert buffer.getvalue() == ""


def test_render_prompt_uses_inline_clarification_prompt() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        pending_question={"type": "path", "prompt": "destination path>"},
    )

    assert cli.render_prompt(state) == "destination path>"
    state.current_state = LifecycleState.IDLE
    assert cli.render_prompt(state) == "snappy> "
