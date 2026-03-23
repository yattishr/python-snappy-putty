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


def test_new_command_in_clarification_resets_before_pending_question_can_consume_it() -> None:
    state = SessionState(
        current_state=LifecycleState.CLARIFICATION,
        active_goal="git push",
        pending_question="Which remote do you mean?",
        pending_plan=["step"],
        pending_context={"type": "ask_followup", "base_intent": "git push"},
    )
    text = "give me a file listing for the current directory"
    decision = cli.classify_input(text)

    if state.current_state == LifecycleState.CLARIFICATION and not cli.is_valid_clarification_response(text, state):
        state.reset()

    assert state.current_state == LifecycleState.IDLE
    assert state.active_goal is None
    assert state.pending_question is None
    assert state.pending_plan is None
    assert cli._should_consume_pending_question(text=text, route=decision.route, state=state) is False


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
