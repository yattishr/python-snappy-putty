from io import StringIO
from pathlib import Path
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty import cli
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


def test_confirmation_without_pending_plan_records_failed_goal() -> None:
    state = SessionState(active_goal="copy a b", current_state=LifecycleState.CONFIRMATION)

    cli._consume_confirmation_response("YES", state, Path.cwd())

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.last_failed_goal == "copy a b"
    assert state.error_message == "Confirmation received, but no actionable pending state remained."
    assert state.last_result == "Confirmation received, but no actionable pending state remained."

