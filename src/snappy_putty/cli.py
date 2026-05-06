from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
from typing import Callable, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from snappy_putty.agent import AgentRunResult, _extract_requested_path, _is_listing_request, _listing_request_is_ambiguous, plan_with_agent
from snappy_putty.agent_discovery import (
    get_agent_mode,
    get_agent_mode_source,
    load_agent_memory,
    load_agent_project_config,
    load_agent_rule_registry,
    load_agent_skill_registry,
    normalize_agent_mode,
)
from snappy_putty.active_planner import (
    GroundedPlan,
    LLMPlannerUnavailableError,
    LLMPlanValidationError,
    PlanStep as GroundedPlanStep,
    PlanningIntent,
    PlanningMode,
    assess_project_relevance,
    build_grounded_plan,
    build_llm_prompt,
    classify_planning_intent,
    classify_planning_mode,
    create_llm_assisted_plan,
    grounded_plan_to_lines,
    validate_plan_integrity,
)
from snappy_putty.agent_init import init_agent_project
from snappy_putty.context import collect_context
from snappy_putty.fs_ops import MAX_OPS, apply_fs_plan, looks_like_fs_mutation_intent, parse_incomplete_fs_intent, plan_fs_intent
from snappy_putty.fs_models import FsPlan
from snappy_putty.git_read import execute_git_read, parse_git_read_intent
from snappy_putty.history import append_history_event
from snappy_putty.memory import (
    ensure_project_snapshot,
    history_path,
    invalidate_grounded_plan,
    load_grounded_plan,
    load_project_snapshot,
    load_current_snapshot_metadata,
    load_or_refresh_snapshot,
    load_session_payload,
    project_snapshot_path,
    save_grounded_plan,
    save_planning_skipped,
    save_session_payload,
    snapshot_is_stale,
)
from snappy_putty.render import (
    block_message_from_decision,
    policy_notes_from_decision,
    render_agent_output,
    render_agent_parse_error,
    render_agent_doctor_report,
    render_directory_listing,
    render_fs_cannot_proceed,
    render_doctor_report,
    render_fs_apply_result,
    render_fs_plan,
    render_fs_rule_block,
    render_git_read,
)
from snappy_putty.project_inspector import ProjectSnapshot, snapshot_from_payload, snapshot_to_payload
from snappy_putty.rule_hooks import before_agent_mode_change, before_filesystem_mutation_plan_or_execute
from snappy_putty.rule_hooks import POLICY_HIERARCHY
from snappy_putty.router import (
    ROUTE_ASK,
    ROUTE_BUILTIN_AFTER,
    ROUTE_BUILTIN_CANCEL,
    ROUTE_BUILTIN_DOCTOR,
    ROUTE_BUILTIN_EXIT,
    ROUTE_BUILTIN_HELP,
    ROUTE_BUILTIN_STATUS,
    ROUTE_EXPLAIN,
    ROUTE_FS_MUTATION,
    ROUTE_GIT_READ,
    ROUTE_INSPECT_FILE,
    ROUTE_INSPECT_FILES,
    ROUTE_INSPECT_PROJECT,
    ROUTE_INSPECT_STRUCTURE,
    ROUTE_OUT_OF_SCOPE,
    ROUTE_REFRESH_SNAPSHOT,
    ROUTE_SAFE_INSPECT,
    ROUTE_SHOW_PLAN,
    ROUTE_SHOW_SNAPSHOT,
    ROUTE_WHY_PLAN,
    ROUTE_EXPLAIN_STEP,
    ROUTE_REFINE_PLAN,
    ROUTE_UNKNOWN,
    classify_input,
)
from snappy_putty.session import (
    ActiveGoalConflictError,
    ActiveWorkflowSnapshot,
    ClarificationContext,
    ConfirmationContext,
    ExecutionOperation,
    ExecutionResult,
    InvalidLifecycleTransition,
    LifecycleState,
    load_workflow_snapshot,
    restore_workflow_snapshot,
    SessionState,
)
from snappy_putty.status import busy, get_status_message
from snappy_putty.models import AgentOutput, PlanStep as AgentPlanStep

app = typer.Typer(help="Snappy PuTTy CLI", invoke_without_command=True)
inspect_app = typer.Typer(help="Read-only project inspection commands.", invoke_without_command=False)
show_app = typer.Typer(help="Display cached inspection and planning state.", invoke_without_command=False)
refresh_app = typer.Typer(help="Refresh cached project inspection state.", invoke_without_command=False)
app.add_typer(inspect_app, name="inspect")
app.add_typer(show_app, name="show")
app.add_typer(refresh_app, name="refresh")
console = Console()
UNKNOWN_COMMAND_MESSAGE = "I don't recognize that command. Try 'help' to see what I can do."
OUT_OF_SCOPE_MESSAGE = "I can only help with software, hardware, and technology topics."
OUT_OF_SCOPE_HINT_MESSAGE = "Try asking about code, debugging, CLIs, repos, APIs, or hardware."
RESERVED_CONTROL_ROUTES = {
    ROUTE_BUILTIN_HELP,
    ROUTE_BUILTIN_DOCTOR,
    ROUTE_BUILTIN_STATUS,
    ROUTE_BUILTIN_AFTER,
    ROUTE_BUILTIN_CANCEL,
    ROUTE_BUILTIN_EXIT,
    ROUTE_INSPECT_PROJECT,
    ROUTE_INSPECT_FILES,
    ROUTE_INSPECT_STRUCTURE,
    ROUTE_INSPECT_FILE,
    ROUTE_SHOW_SNAPSHOT,
    ROUTE_SHOW_PLAN,
    ROUTE_WHY_PLAN,
    ROUTE_EXPLAIN_STEP,
    ROUTE_REFINE_PLAN,
    ROUTE_REFRESH_SNAPSHOT,
}
_AGENT_MODE_PATTERN = re.compile(r"^\s*agent\s+mode(?:\s+(?P<mode>\S+))?\s*$", flags=re.IGNORECASE)
_COMMAND_SHAPED_PREFIXES = (
    "git",
    "copy",
    "move",
    "delete",
    "remove",
    "list",
    "show",
    "status",
    "give me",
    "create",
    "make",
)


def _non_project_skip_reason(intent: str) -> str:
    planning_intent = classify_planning_intent(intent)
    if planning_intent == PlanningIntent.CURRENT_INFO_QUESTION:
        return "unsupported_current_info_question"
    if planning_intent == PlanningIntent.UNRELATED_NON_PROJECT_REQUEST:
        return "goal_not_project_related"
    return "non_project_question"


def _record_planning_skipped_memory(
    root: Path,
    *,
    goal: str,
    reason: str,
    snapshot: ProjectSnapshot | None = None,
) -> None:
    save_planning_skipped(root, goal=goal, reason=reason, snapshot=snapshot)
    details: dict[str, object] = {
        "Goal": goal,
        "Reason": reason,
        "Result": "no_plan_created",
        "Workflow state": "reset_to_idle",
    }
    if snapshot is not None:
        details["Snapshot ID"] = snapshot.snapshot_id
    append_history_event(root, "Planning skipped", details)


def _render_non_project_skip(intent: str, *, root: Path | None = None, state: SessionState | None = None) -> AgentRunResult:
    workspace_root = root or Path.cwd().resolve()
    reason = _non_project_skip_reason(intent)
    if reason == "unsupported_current_info_question":
        console.print("This looks like a current information request, not a project task.")
        console.print("Snappy cannot answer live market data or other current information unless current-info tools are enabled.")
    else:
        console.print("This looks like a general question, not a project task.")
    console.print(OUT_OF_SCOPE_MESSAGE)
    console.print(OUT_OF_SCOPE_HINT_MESSAGE)
    console.print("No project plan was created.")
    _record_planning_skipped_memory(workspace_root, goal=intent, reason=reason)
    if state is not None:
        state.skip_planning(goal=intent, reason=reason, route=ROUTE_OUT_OF_SCOPE)
    return AgentRunResult(
        output=AgentOutput(
            goal=intent,
            assumptions=[],
            question=None,
            plan=[],
            commands=[],
            warnings=["No project plan was created."],
            snippets=[],
        ),
        skip_reason=reason,
    )


def looks_like_new_command(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(prefix) for prefix in _COMMAND_SHAPED_PREFIXES)


def _is_path_clarification_response(user_input: str) -> bool:
    raw_text = user_input.strip()
    if not raw_text:
        return False
    if not looks_like_path(raw_text):
        return False

    # Path clarifications are data-only. Reject anything routable as a new goal
    # so command-shaped follow-ups cannot escape into planning.
    route = classify_input(raw_text).route
    return route == ROUTE_UNKNOWN


def is_valid_clarification_response(user_input: str, state: SessionState) -> bool:
    raw_text = user_input.strip()
    text = raw_text.lower()
    if text in {"yes", "no"}:
        return True
    if isinstance(state.pending_question, dict):
        question_type = state.pending_question.get("type")
        if question_type == "path":
            return _is_path_clarification_response(raw_text)
        if question_type == "choice":
            return _is_choice_input(raw_text, state.pending_question)
    if state.pending_question and not looks_like_new_command(text):
        return True
    return False


def looks_like_path(text: str) -> bool:
    value = text.strip()
    return bool(
        value
        and (
            "/" in value
            or "." in value
            or value.startswith(".")
            or value.endswith("/")
            or value.isalnum()
        )
    )


def _is_choice_question(question: object) -> bool:
    return isinstance(question, dict) and question.get("type") == "choice"


def _pending_question_message(question: object) -> str:
    if isinstance(question, dict):
        return str(question.get("message") or question.get("prompt") or "(none)")
    return str(question or "(none)")


def _workflow_snapshot(state: SessionState) -> ActiveWorkflowSnapshot | None:
    return state.active_workflow


def _workflow_pending_question(state: SessionState) -> str:
    snapshot = _workflow_snapshot(state)
    if snapshot and snapshot.pending_question:
        return snapshot.pending_question
    return _pending_question_message(state.pending_question)


def _workflow_pending_plan_summary(state: SessionState) -> str:
    snapshot = _workflow_snapshot(state)
    if snapshot and snapshot.pending_plan_summary:
        if snapshot.pending_plan_mode in {"deterministic", "llm_assisted"} and snapshot.pending_plan_summary.startswith("plan with "):
            return f"{snapshot.pending_plan_mode} {snapshot.pending_plan_summary}"
        return snapshot.pending_plan_summary
    if isinstance(state.pending_plan, FsPlan):
        return f"filesystem plan with {len(state.pending_plan.ops)} op(s)"
    if isinstance(state.pending_plan, list):
        if state.pending_plan_mode in {"deterministic", "llm_assisted"}:
            return f"{state.pending_plan_mode} plan with {len(state.pending_plan)} step(s)"
        return f"plan with {len(state.pending_plan)} step(s)"
    return "(none)"


def _workflow_awaiting_confirmation(state: SessionState) -> bool:
    snapshot = _workflow_snapshot(state)
    if snapshot is not None:
        return snapshot.awaiting_confirmation
    return state.awaiting_confirmation


def _workflow_control_state(state: SessionState) -> str:
    snapshot = _workflow_snapshot(state)
    if snapshot and snapshot.control_state:
        return snapshot.control_state
    return _current_control_state(state)


def _clarification_input_is_locked(*, text: str, route: str, state: SessionState) -> bool:
    if state.current_state != LifecycleState.CLARIFICATION:
        return False
    if not state.pending_question:
        return False
    # Trust boundary: clarification is a data-only channel. Only explicit control
    # commands may escape it; command-shaped input must not start a new goal.
    if route in RESERVED_CONTROL_ROUTES or route == ROUTE_BUILTIN_EXIT:
        return False
    context = state.pending_context
    if isinstance(context, ClarificationContext) and context.prompt_kind in {"fs_destination", "guided_listing_custom_path"}:
        if is_valid_clarification_response(text, state):
            return False
        return True
    if _is_choice_question(state.pending_question):
        return False
    return not is_valid_clarification_response(text, state)


def _render_clarification_lock_message(state: SessionState) -> None:
    _render_clarification_followup(state, blocked=True)


def _render_clarification_followup(state: SessionState, *, blocked: bool) -> None:
    lines: list[str] = []
    if blocked:
        lines.extend(
            [
                "You have a pending question.",
                "Answer it, or type 'cancel' to abandon the current goal.",
            ]
        )
    else:
        lines.extend(
            [
                "Your pending question is still active.",
                "Answer it, or type 'cancel' to abandon the current goal.",
            ]
        )
    console.print(
        "\n".join(lines)
    )


def _confirmation_prompt_label(state: SessionState) -> str:
    context = state.pending_context
    stage = context.stage if isinstance(context, ConfirmationContext) else "apply"
    if stage == "overwrite":
        return "overwrite [YES/NO]> "
    if stage == "limit":
        return "continue [YES/NO]> "
    return "confirm [YES/NO]> "


def _confirmation_prompt_message(state: SessionState) -> str:
    context = state.pending_context
    stage = context.stage if isinstance(context, ConfirmationContext) else "apply"
    if stage == "overwrite":
        return "Destination exists. Type YES to overwrite, or NO to cancel."
    if stage == "limit":
        return f"Plan exceeds {MAX_OPS} operations. Type YES to continue, or NO to cancel."
    return "Type YES to apply, or NO to cancel."


def _render_confirmation_prompt(state: SessionState, *, invalid: bool = False) -> None:
    if invalid:
        console.print("Please answer YES or NO.")
    console.print(_confirmation_prompt_message(state))


def _normalized_confirmation_token(value: str) -> str:
    return value.strip().upper()


def _handle_confirmation_input(*, text: str, route: str, state: SessionState, workspace_root: Path) -> bool:
    if not state.awaiting_confirmation:
        return False
    if text.upper() in {"YES", "NO"}:
        _consume_confirmation_response(response=text, state=state, workspace_root=workspace_root)
        return True
    if route in RESERVED_CONTROL_ROUTES or route == ROUTE_BUILTIN_EXIT:
        return False
    state.last_result = "Awaiting explicit YES/NO confirmation; invalid input was ignored."
    _render_confirmation_prompt(state, invalid=True)
    return True


def _empty_fs_plan_feedback(plan: FsPlan) -> tuple[str, str, list[str], str]:
    warnings = list(plan.warnings)
    lowered = [item.lower() for item in warnings]
    if any("workspace root" in item or "escapes workspace root" in item for item in lowered):
        return (
            "Blocked Request",
            "No executable filesystem changes were planned because the target path is outside the workspace root.",
            warnings,
            "Choose a destination inside the workspace and try again.",
        )
    if any("same file" in item or "same path" in item or "same source" in item for item in lowered):
        return (
            "No-Op Request",
            "No executable filesystem changes were planned because the request resolves to the same source and destination.",
            warnings,
            "Choose a different destination and try again.",
        )
    if warnings:
        return (
            "Invalid Request",
            "No executable filesystem changes were planned because the request could not be normalized into a valid filesystem change.",
            warnings,
            "Adjust the request and try again.",
        )
    return (
        "No-Op Request",
        "No executable filesystem changes were planned.",
        [],
        "Adjust the request and try again.",
    )


def render_prompt(state: SessionState) -> str:
    if state.current_state == LifecycleState.CLARIFICATION and state.pending_question and not _is_choice_question(state.pending_question):
        return _pending_question_message(state.pending_question)
    if state.current_state == LifecycleState.CONFIRMATION and state.awaiting_confirmation:
        return _confirmation_prompt_label(state)
    return "snappy> "


def _build_listing_choice_question() -> dict[str, object]:
    return {
        "type": "choice",
        "message": "Where would you like the file listing from?",
        "options": [
            {"label": "Current directory (.)", "value": "."},
            {"label": "Root directory (/)", "value": "/"},
            {"label": "Specify a custom path", "value": "custom"},
        ],
        "selected_index": 0,
    }


def _build_agent_mode_choice_question(*, current_mode: str, source: str) -> dict[str, object]:
    options = [
        {"label": "off", "value": "off"},
        {"label": "active", "value": "active"},
    ]
    selected_index = next((index for index, option in enumerate(options) if option["value"] == current_mode), 0)
    return {
        "type": "choice",
        "message": f"Current: {current_mode}\nSource: {source}\n\nSelect mode:",
        "options": options,
        "selected_index": selected_index,
        "footer": "(Use ↑/↓ to navigate, ENTER to select)",
        "fallback_prompt": "Enter choice > ",
    }


def _resolve_choice_menu_input(raw_value: str, question: dict[str, object]) -> str:
    value = raw_value.strip()
    options = question.get("options", [])
    if value.isdigit() and isinstance(options, list):
        selected_index = int(value) - 1
        if 0 <= selected_index < len(options):
            option = options[selected_index]
            if isinstance(option, dict):
                return str(option.get("value", value))
    return value


def _is_choice_input(raw_value: str, question: dict[str, object]) -> bool:
    value = raw_value.strip()
    if not value:
        return False
    resolved = _resolve_choice_menu_input(value, question)
    options = question.get("options", [])
    if not isinstance(options, list):
        return False
    option_values = {
        str(option.get("value"))
        for option in options
        if isinstance(option, dict) and option.get("value") is not None
    }
    return resolved in option_values


def _render_choice_prompt_text(question: dict[str, object]) -> str:
    options = question.get("options", [])
    selected_index = int(question.get("selected_index", 0))
    lines = [str(question.get("message", "")), ""]
    if isinstance(options, list):
        for index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            prefix = ">" if index == selected_index else " "
            lines.append(f"{prefix} {option.get('label', option.get('value', ''))}")
    footer = str(question.get("footer") or "(Use ↑/↓ to navigate, ENTER to select, or type a command/path)")
    lines.extend(["", footer, "> "])
    return "\n".join(lines)


def _prompt_choice_question(session, question: dict[str, object]) -> str:
    options = question.get("options", [])
    if not isinstance(options, list) or not options:
        return ""

    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("up")
    def _handle_up(event) -> None:
        question["selected_index"] = (int(question.get("selected_index", 0)) - 1) % len(options)
        event.app.invalidate()

    @kb.add("down")
    def _handle_down(event) -> None:
        question["selected_index"] = (int(question.get("selected_index", 0)) + 1) % len(options)
        event.app.invalidate()

    @kb.add("enter")
    def _handle_enter(event) -> None:
        typed = event.app.current_buffer.text.strip()
        if typed:
            event.app.exit(result=typed)
            return
        selected = options[int(question.get("selected_index", 0))]
        selected_value = selected.get("value", "") if isinstance(selected, dict) else ""
        event.app.exit(result=str(selected_value))

    return str(
        session.prompt(
            message=lambda: _render_choice_prompt_text(question),
            key_bindings=kb,
            default="",
        )
    ).strip()


def _prompt_choice_fallback(question: dict[str, object]) -> str:
    console.print(_pending_question_message(question))
    options = question.get("options", [])
    if isinstance(options, list):
        for index, option in enumerate(options, start=1):
            if not isinstance(option, dict):
                continue
            console.print(f"{index}. {option.get('label', option.get('value', ''))}")
    prompt_text = str(question.get("fallback_prompt") or "Enter 1, 2, 3, or a path/command: ")
    return _resolve_choice_menu_input(input(prompt_text), question)


def _should_consume_pending_question(*, text: str, route: str, state: SessionState) -> bool:
    if not state.pending_question:
        return False
    if route in RESERVED_CONTROL_ROUTES:
        return False

    question_context = state.pending_context
    if isinstance(question_context, ClarificationContext):
        context_type = question_context.prompt_kind
    elif isinstance(question_context, dict):
        context_type = str(question_context.get("type") or "")
    else:
        context_type = None

    if context_type == "fs_destination":
        if isinstance(state.pending_question, dict) and state.pending_question.get("type") == "path":
            return _is_path_clarification_response(text)
        return route == ROUTE_ASK

    if context_type == "ask_followup":
        return route == ROUTE_ASK or is_valid_clarification_response(text, state)

    if context_type == "guided_listing_choice":
        if isinstance(state.pending_question, dict):
            return _is_choice_input(text, state.pending_question)
        return True

    if context_type == "guided_listing_custom_path":
        if isinstance(state.pending_question, dict) and state.pending_question.get("type") == "path":
            return _is_path_clarification_response(text)
        return True

    return True


def _should_override_guided_listing_question(*, route: str, state: SessionState) -> bool:
    if state.current_state != LifecycleState.CLARIFICATION:
        return False
    if route in RESERVED_CONTROL_ROUTES or route == ROUTE_BUILTIN_EXIT:
        return False
    context = state.pending_context
    return isinstance(context, ClarificationContext) and context.prompt_kind == "guided_listing_choice"


def _set_state(state: SessionState, lifecycle: LifecycleState) -> None:
    state.transition_to(lifecycle)


def _begin_goal(state: SessionState, *, goal: str, route: str) -> None:
    state.start_goal(goal=goal, route=route)


def _enter_planning(state: SessionState) -> None:
    _set_state(state, LifecycleState.PLANNING)


def _record_clarification(state: SessionState, *, question: object, pending_context: dict[str, object]) -> None:
    state.pending_question = question
    state.pending_plan = None
    state.awaiting_confirmation = False
    context = ClarificationContext(
        source_path=str(pending_context.get("src")) if pending_context.get("src") is not None else None,
        expected_input="choice" if isinstance(question, dict) and question.get("type") == "choice" else ("path" if isinstance(question, dict) and question.get("type") == "path" else "answer"),
        action=str(pending_context.get("action")) if pending_context.get("action") is not None else None,
        base_intent=str(pending_context.get("base_intent")) if pending_context.get("base_intent") is not None else None,
        workspace_root=str(pending_context.get("workspace_root")) if pending_context.get("workspace_root") is not None else None,
        prompt_kind=str(pending_context.get("type") or "clarification"),
    )
    state.update_workflow_context(context)
    _set_state(state, LifecycleState.CLARIFICATION)


def _record_agent_planning_result(
    state: SessionState,
    *,
    route: str,
    goal: str,
    result: AgentRunResult,
    pending_context: dict[str, object] | None = None,
) -> None:
    if not result.output.plan and result.output.question is None and result.plan_mode is None:
        state.last_result = result.output.goal
        if result.skip_reason:
            state.skip_planning(goal=goal, reason=result.skip_reason, route=route)
            return
        state.reset_to_idle_preserving_history()
        if result.blocked_reason:
            state.last_blocked_goal = goal
            state.error_message = result.blocked_reason
            state.last_route = route
        return
    _begin_goal(state, goal=goal, route=route)
    _enter_planning(state)
    state.last_result = result.output.goal
    state.pending_plan = result.output.plan
    state.pending_plan_mode = result.plan_mode
    state.pending_question = result.output.question
    state.awaiting_confirmation = False
    if result.output.plan:
        state.clear_skip_metadata()
    if pending_context:
        state.update_workflow_context(
            ClarificationContext(
                source_path=None,
                expected_input="answer",
                action=None,
                base_intent=str(pending_context.get("base_intent")) if pending_context.get("base_intent") is not None else None,
                workspace_root=None,
                prompt_kind=str(pending_context.get("type") or "ask_followup"),
            )
        )
    else:
        state.update_workflow_context(None)
    if result.output.question is not None:
        _set_state(state, LifecycleState.CLARIFICATION)
    elif result.plan_mode in {PlanningMode.DETERMINISTIC.value, PlanningMode.LLM_ASSISTED.value}:
        _set_state(state, LifecycleState.CONFIRMATION)
    else:
        state.sync_active_workflow()


def _handle_safe_inspect_repl(intent: str, state: SessionState, *, start_new_goal: bool = True) -> bool:
    if _is_listing_request(intent) and _extract_requested_path(intent) is None and not _listing_request_is_ambiguous(intent):
        if start_new_goal:
            _begin_goal(state, goal=intent, route=ROUTE_SAFE_INSPECT)
            _enter_planning(state)
        _record_clarification(
            state,
            question=_build_listing_choice_question(),
            pending_context={"type": "guided_listing_choice", "base_intent": intent},
        )
        state.last_result = "Awaiting guided listing selection."
        return True

    if start_new_goal:
        _begin_goal(state, goal=intent, route=ROUTE_SAFE_INSPECT)
        _enter_planning(state)
    else:
        state.active_goal = intent
        state.last_route = ROUTE_SAFE_INSPECT
        state.error_message = None
        state.sync_active_workflow()
    result = handle_ask(intent=intent, session_mode=state.agent_mode)
    if result.output.question:
        state.last_result = result.output.goal
        state.pending_plan = result.output.plan
        state.pending_question = result.output.question
        state.awaiting_confirmation = False
        state.update_workflow_context(
            ClarificationContext(
                source_path=None,
                expected_input="answer",
                action=None,
                base_intent=intent,
                workspace_root=None,
                prompt_kind="ask_followup",
            )
        )
        _set_state(state, LifecycleState.CLARIFICATION)
        return True

    _set_state(state, LifecycleState.EXECUTING)
    _complete_active_goal(state, message=f"Completed safe inspection for: {intent}")
    return True


def _finish_terminal_state(state: SessionState) -> None:
    state.finish_cycle()


def _reflect_execution_result(state: SessionState, result: ExecutionResult) -> None:
    state.last_execution_result = result
    if state.current_state != LifecycleState.REFLECTING:
        _set_state(state, LifecycleState.REFLECTING)

    terminal_state = {
        "completed": LifecycleState.COMPLETED,
        "failed": LifecycleState.FAILED,
        "cancelled": LifecycleState.CANCELLED,
        "blocked": LifecycleState.BLOCKED,
    }[result.status]
    _set_state(state, terminal_state)

    if result.status == "completed":
        state.last_completed_goal = result.goal
        state.error_message = None
    elif result.status == "cancelled":
        state.last_cancelled_goal = result.goal
        state.error_message = None
    elif result.status == "failed":
        state.last_failed_goal = result.goal
        state.error_message = result.error
    else:
        state.last_blocked_goal = result.goal
        state.error_message = result.error

    state.last_result = result.summary
    _finish_terminal_state(state)


def _execution_result(
    *,
    state: SessionState,
    status: str,
    message: str,
    operations: list[ExecutionOperation] | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
) -> ExecutionResult:
    goal = state.active_goal or ""
    return ExecutionResult(
        goal=goal,
        status=status,
        summary=message,
        operations=tuple(operations or ()),
        error=error,
        warnings=tuple(warnings or ()),
    )


def _cancel_active_goal(state: SessionState, *, message: str) -> None:
    result = _execution_result(state=state, status="cancelled", message=message)
    _reflect_execution_result(state, result)


def _has_cancellable_workflow(state: SessionState) -> bool:
    return (
        state.has_active_goal
        or state.pending_question is not None
        or state.pending_plan is not None
        or state.awaiting_confirmation
    )


def _fail_active_goal(state: SessionState, *, message: str) -> None:
    result = _execution_result(state=state, status="failed", message=message, error=message)
    _reflect_execution_result(state, result)


def _complete_active_goal(state: SessionState, *, message: str) -> None:
    result = _execution_result(state=state, status="completed", message=message)
    _reflect_execution_result(state, result)


def _debug_enabled() -> bool:
    return os.getenv("SNAPPY_PUTTY_DEBUG") == "1"


def _debug(message: str) -> None:
    if _debug_enabled():
        print(f"[snappy_putty:debug] {message}")


def print_repl_cheatsheet() -> None:
    snapshot = collect_context()
    tools = " ".join(f"{name} {'✓' if found else '✗'}" for name, found in snapshot.tools.items())
    quick_commands = [
        ("doctor", "Planning diagnostics."),
        ("agent", "Agent summary."),
        ("agent mode", "Edit runtime mode."),
        ("init", "Scaffold .snappy/."),
        ("skills", "Skills list."),
        ("rules", "Rules list."),
        ("inspect project", "Snapshot cache."),
        ("inspect files", "Snapshot files."),
        ("inspect structure", "Project structure."),
        ("inspect file <p>", "File excerpt."),
        ("show snapshot", "Cached snapshot."),
        ("show plan", "Cached plan."),
        ("refresh snapshot", "Refresh snapshot."),
        ("explain <command>", "Explain command."),
        ("after", "Next input or step."),
        ("status", "Session status."),
        ("cancel", "Clear workflow."),
        ("help", "Help panel."),
        ("exit / quit", "Leave shell."),
    ]
    quick_commands_block = _render_compact_command_block(quick_commands, columns=2)
    content = "\n".join(
        [
            "[bold]Snappy PuTTy[/bold]",
            "Your terminal's clever little co-pilot.",
            "I never execute destructive commands.",
            "",
            "[bold]What I do[/bold]",
            "- Plan and explain terminal workflows.",
            "- Perform safe read-only inspection when needed.",
            "- Ask follow-up questions when a request needs clarification.",
            "",
            "[bold]Quick commands[/bold]",
            quick_commands_block,
            "",
            "[bold]Workflow tips[/bold]",
            "- If Snappy asks a question, answer it directly or type 'cancel'.",
            "- Use 'after' to see the next expected input.",
            "- Use 'status' when you want full diagnostic state.",
            "",
            "[bold]Try[/bold]",
            '- "give me a file listing"',
            '- "give me a file listing for src"',
            '- "copy README.md"',
            '- "destination path> tests/"',
            '- "deploy this to google cloud"',
            "",
            f"[bold]CWD[/bold]: {snapshot.cwd}",
            f"[bold]Tools[/bold]: {tools}",
        ]
    )
    console.print(Panel(content, title="Welcome", border_style="bright_blue"))


def _build_agent_mode_lines(
    session_mode: str | None = None,
    source: str | None = None,
) -> list[str]:
    current_mode = get_agent_mode(session_mode)
    resolved_source = source if source is not None else get_agent_mode_source(session_mode)
    return [
        f"Current: {current_mode}",
        f"Source: {resolved_source}",
    ]


def _render_compact_command_block(commands: list[tuple[str, str]], *, columns: int) -> str:
    command_width = max(len(name) for name, _ in commands)
    description_width = max(len(description) for _, description in commands)
    cell_width = max(command_width, description_width) + 2
    rows: list[str] = []
    for index in range(0, len(commands), columns):
        group = commands[index : index + columns]
        top_line: list[str] = []
        bottom_line: list[str] = []
        for name, description in group:
            top_line.append(f"- {name:<{cell_width - 2}}")
            bottom_line.append(f"  {description:<{cell_width - 2}}")
        while len(top_line) < columns:
            top_line.append(" " * cell_width)
            bottom_line.append(" " * cell_width)
        rows.append("   ".join(top_line))
        rows.append("   ".join(bottom_line))
    return "\n".join(rows)


def _build_agent_summary_lines(cwd: Path | None = None, session_mode: str | None = None) -> list[str]:
    active_cwd = (cwd or Path.cwd()).resolve()
    feature_mode = get_agent_mode(session_mode)
    agent_config = load_agent_project_config(active_cwd, session_mode=session_mode)
    skill_registry = load_agent_skill_registry(active_cwd, session_mode=session_mode)
    rule_registry = load_agent_rule_registry(active_cwd, session_mode=session_mode)
    memory = load_agent_memory(active_cwd, session_mode=session_mode)

    if not agent_config.discovery.agent_found:
        return [
            f"Agent feature mode: {feature_mode}",
            "Agent loaded: no",
            "No .snappy agent is currently loaded.",
        ]

    manifest = agent_config.manifest
    session_keys = "(none)"
    if memory.session_data is not None:
        session_keys = ", ".join(sorted(memory.session_data.keys())) or "(empty)"

    block_rule_names = ", ".join(rule.identifier for rule in rule_registry.block_rules) or "(none)"
    confirm_rule_names = ", ".join(rule.identifier for rule in rule_registry.confirm_rules) or "(none)"
    warn_rule_names = ", ".join(rule.identifier for rule in rule_registry.warn_rules) or "(none)"
    info_rule_names = ", ".join(rule.identifier for rule in rule_registry.info_rules) or "(none)"

    lines = [
        f"Agent feature mode: {feature_mode}",
        "Agent loaded: yes",
        f"Manifest present: {'yes' if agent_config.discovery.manifest_path is not None else 'no'}",
        "Control layer: centralized pre-execution policy gate",
        f"Policy hierarchy: {' > '.join(POLICY_HIERARCHY).upper()}",
        f"Agent name: {manifest.name if manifest and manifest.name else '(unknown)'}",
        f"Version: {manifest.version if manifest and manifest.version is not None else '(unknown)'}",
        f"Agent mode: {manifest.mode if manifest and manifest.mode else '(unknown)'}",
        f"Loaded skills: {len(skill_registry.skills)}",
        f"Loaded rules: {len(rule_registry.rules)}",
        f"Enforceable rules: {len(rule_registry.enforceable_rules)}",
        f"Informational rules: {len(rule_registry.informational_rules)}",
        f"Block rules: {block_rule_names}",
        f"Confirm rules: {confirm_rule_names}",
        f"Warn rules: {warn_rule_names}",
        f"Info rules: {info_rule_names}",
        f"Memory present: {'yes' if memory.memory_found else 'no'}",
    ]
    if memory.memory_found:
        lines.append(f"Session memory keys: {session_keys}")
    if agent_config.warning:
        lines.append(f"Agent warning: {agent_config.warning}")
    if skill_registry.warnings:
        lines.append(f"Skill warnings: {len(skill_registry.warnings)}")
    if rule_registry.warnings:
        lines.append(f"Rule warnings: {len(rule_registry.warnings)}")
    if memory.warning:
        lines.append(f"Memory warning: {memory.warning}")
    return lines


def _handle_agent_summary(session_mode: str | None = None) -> None:
    console.print(
        Panel.fit("\n".join(_build_agent_summary_lines(session_mode=session_mode)), title="Agent Summary", border_style="bright_blue")
    )


def _build_agent_doctor_lines(cwd: Path | None = None, session_mode: str | None = None) -> list[str]:
    active_cwd = (cwd or Path.cwd()).resolve()
    feature_mode = get_agent_mode(session_mode)
    agent_root = active_cwd / ".snappy"
    manifest_path = agent_root / "snappy.yaml"
    skills_dir = agent_root / "skills"
    rules_dir = agent_root / "rules"
    memory_dir = agent_root / "memory"
    session_path = memory_dir / "session.json"

    agent_config = load_agent_project_config(active_cwd, session_mode=session_mode)
    skill_registry = load_agent_skill_registry(active_cwd, session_mode=session_mode)
    rule_registry = load_agent_rule_registry(active_cwd, session_mode=session_mode)
    memory = load_agent_memory(active_cwd, session_mode=session_mode)

    lines = [
        f"Agent feature mode: {feature_mode}",
        f".snappy directory: {'present' if agent_root.is_dir() else 'absent'}",
        f"Manifest file: {'present' if manifest_path.is_file() else 'absent'}",
    ]

    if manifest_path.is_file():
        lines.append(f"Manifest parse: {'ok' if agent_config.manifest is not None else 'failed'}")

    lines.extend(
        [
            "Control layer ready: yes",
            f"Policy hierarchy: {' > '.join(POLICY_HIERARCHY).upper()}",
            f"Skills directory: {'present' if skills_dir.is_dir() else 'absent'}",
            f"Loaded skills: {len(skill_registry.skills)}",
            f"Rules directory: {'present' if rules_dir.is_dir() else 'absent'}",
            f"Loaded rules: {len(rule_registry.rules)}",
            f"Enforceable rules: {len(rule_registry.enforceable_rules)}",
            f"Informational rules: {len(rule_registry.informational_rules)}",
            f"Policy tiers: block={len(rule_registry.block_rules)}, confirm={len(rule_registry.confirm_rules)}, warn={len(rule_registry.warn_rules)}, info={len(rule_registry.info_rules)}",
            f"Confirmation-capable rules: {len(rule_registry.confirm_rules)}",
            f"Memory directory: {'present' if memory_dir.is_dir() else 'absent'}",
            f"Session file: {'present' if session_path.is_file() else 'absent'}",
        ]
    )

    if session_path.is_file():
        lines.append(f"Session parse: {'ok' if memory.session_data is not None and memory.warning is None else 'failed'}")

    for warning in skill_registry.warnings:
        lines.append(warning)
    for warning in rule_registry.warnings:
        lines.append(warning)
    if agent_config.warning:
        lines.append(f"Manifest warning: {agent_config.warning}")
    if memory.warning:
        lines.append(f"Session warning: {memory.warning}")
    return lines


def _handle_agent_doctor(session_mode: str | None = None) -> None:
    render_agent_doctor_report(console=console, lines=_build_agent_doctor_lines(session_mode=session_mode))


def _set_agent_mode(state: SessionState, mode: str) -> None:
    state.agent_mode = mode
    console.print(f"Agent mode set to: {mode} (session)")
    if mode == "active":
        console.print("Beast mode ON")


def _show_agent_mode(current_mode: str, source: str) -> None:
    console.print(Panel.fit("\n".join(_build_agent_mode_lines(current_mode, source)), title="Agent Mode", border_style="bright_blue"))


def _prompt_for_agent_mode(session, current_mode: str, source: str) -> str:
    question = _build_agent_mode_choice_question(current_mode=current_mode, source=source)
    if session is None:
        _show_agent_mode(current_mode, source)
        return _prompt_choice_fallback(question)
    _show_agent_mode(current_mode, source)
    return _prompt_choice_question(session, question)


def _handle_agent_mode_command(raw_text: str, state: SessionState, session=None) -> bool:
    match = _AGENT_MODE_PATTERN.match(raw_text)
    if not match:
        return False

    mode_arg = match.group("mode")
    if mode_arg is None:
        current_mode = get_agent_mode(state.agent_mode)
        source = get_agent_mode_source(state.agent_mode)
        _show_agent_mode(current_mode, source)
        return True

    if mode_arg.lower() == "select":
        current_mode = get_agent_mode(state.agent_mode)
        source = get_agent_mode_source(state.agent_mode)
        choice = _prompt_for_agent_mode(session, current_mode=current_mode, source=source)
        selected = {"1": "off", "2": "active"}.get(choice, normalize_agent_mode(choice))
        if selected is None:
            console.print("Invalid mode. Choose: off, active")
            return True
        registry = load_agent_rule_registry(Path.cwd(), session_mode=state.agent_mode)
        blocked_message = before_agent_mode_change(target_mode=selected, rule_registry=registry)
        if blocked_message:
            console.print(blocked_message)
            return True
        _set_agent_mode(state, selected)
        return True

    normalized = normalize_agent_mode(mode_arg)
    if normalized is None:
        console.print("Invalid mode. Choose: off, active")
        return True

    registry = load_agent_rule_registry(Path.cwd(), session_mode=state.agent_mode)
    blocked_message = before_agent_mode_change(target_mode=normalized, rule_registry=registry)
    if blocked_message:
        console.print(blocked_message)
        return True

    _set_agent_mode(state, normalized)
    return True


def _build_status_agent_lines(cwd: Path | None = None, session_mode: str | None = None) -> list[str]:
    active_cwd = (cwd or Path.cwd()).resolve()
    feature_mode = get_agent_mode(session_mode)
    mode_source = get_agent_mode_source(session_mode)
    agent_config = load_agent_project_config(active_cwd, session_mode=session_mode)
    skill_registry = load_agent_skill_registry(active_cwd, session_mode=session_mode)
    rule_registry = load_agent_rule_registry(active_cwd, session_mode=session_mode)
    memory = load_agent_memory(active_cwd, session_mode=session_mode)

    lines = [
        f"Agent feature mode: {feature_mode}",
        f"Agent mode source: {mode_source}",
    ]
    if not agent_config.discovery.agent_found:
        lines.append("Agent: (none loaded)")
        return lines

    manifest = agent_config.manifest
    lines.extend(
        [
            "Control layer: centralized pre-execution policy gate",
            f"Policy hierarchy: {' > '.join(POLICY_HIERARCHY).upper()}",
            f"Agent name: {manifest.name if manifest and manifest.name else '(unknown)'}",
            f"Agent version: {manifest.version if manifest and manifest.version is not None else '(unknown)'}",
            f"Agent mode: {manifest.mode if manifest and manifest.mode else '(unknown)'}",
            f"Loaded skills: {len(skill_registry.skills)}",
            f"Loaded rules: {len(rule_registry.rules)}",
            f"Enforceable rules: {len(rule_registry.enforceable_rules)}",
            f"Informational rules: {len(rule_registry.informational_rules)}",
            f"Policy tiers: block={len(rule_registry.block_rules)}, confirm={len(rule_registry.confirm_rules)}, warn={len(rule_registry.warn_rules)}, info={len(rule_registry.info_rules)}",
            f"Confirmation-capable rules: {len(rule_registry.confirm_rules)}",
            f"Agent memory: {'present' if memory.memory_found else 'absent'}",
        ]
    )
    if memory.session_data is not None:
        session_keys = ", ".join(sorted(memory.session_data.keys())) or "(empty)"
        lines.append(f"Agent memory session keys: {session_keys}")
    if agent_config.warning:
        lines.append(f"Agent warning: {agent_config.warning}")
    if memory.warning:
        lines.append(f"Agent memory warning: {memory.warning}")
    return lines


def _project_root(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()).resolve()


def _snapshot_summary_lines(snapshot: ProjectSnapshot) -> list[str]:
    return [
        f"Snapshot ID: {snapshot.snapshot_id}",
        f"Root: {snapshot.root_path}",
        f"Created at: {snapshot.created_at}",
        f"Root hash: {snapshot.root_hash or '(none)'}",
        f"Git branch: {snapshot.git_branch or '(none)'}",
        f"Git status: {snapshot.git_status_summary or '(none)'}",
        f"Languages: {', '.join(snapshot.languages) if snapshot.languages else '(none)'}",
        f"Package managers: {', '.join(snapshot.package_managers) if snapshot.package_managers else '(none)'}",
        f"Frameworks/tools: {', '.join(snapshot.frameworks) if snapshot.frameworks else '(none)'}",
        f"Config files: {', '.join(snapshot.config_files) if snapshot.config_files else '(none)'}",
        f"Docs: {', '.join(snapshot.docs[:6]) if snapshot.docs else '(none)'}",
        f"Tests: {', '.join(snapshot.test_files[:6]) if snapshot.test_files else '(none)'}",
        f"Source files: {', '.join(snapshot.source_files[:6]) if snapshot.source_files else '(none)'}",
        f"Entry points: {', '.join(snapshot.entry_points) if snapshot.entry_points else '(none)'}",
        f"File count: {snapshot.file_count}",
        f"Sampled files: {', '.join(snapshot.sampled_files) if snapshot.sampled_files else '(none)'}",
    ]


def _render_snapshot_report(snapshot: ProjectSnapshot, *, title: str = "Project Inspection") -> None:
    lines = _snapshot_summary_lines(snapshot)
    lines.append("")
    lines.append(f"Snapshot saved: {project_snapshot_path(Path(snapshot.root_path)).as_posix()}")
    console.print(Panel.fit("\n".join(lines), title=title, border_style="bright_blue"))


def _render_grounded_plan_report(plan: GroundedPlan, *, title: str = "Grounded Plan") -> None:
    console.print(Panel.fit("\n".join(grounded_plan_to_lines(plan)), title=title, border_style="bright_blue"))


def _plan_interaction_lines(plan: GroundedPlan) -> list[str]:
    lines = [
        f"Goal: {plan.goal}",
        f"Mode: {plan.mode}",
        f"Snapshot ID: {plan.based_on_snapshot_id}",
        "",
        "Steps:",
    ]
    if plan.steps:
        for index, step in enumerate(plan.steps, start=1):
            lines.append(f"{index}. {step.description}")
            lines.append(f"   Files: {', '.join(step.files) if step.files else '(none)'}")
            if step.proposed_new_files:
                lines.append(f"   Proposed new files: {', '.join(step.proposed_new_files)}")
            lines.append(f"   Risk: {step.risk}")
    else:
        lines.append("1. (none)")
    lines.extend(
        [
            "",
            "Files:",
            *(f"- {item}" for item in plan.files_inspected or ["(none)"]),
            "",
            "Risks:",
            *(f"- {item}" for item in plan.risks or ["(none)"]),
            "",
            "Assumptions:",
            *(f"- {item}" for item in plan.assumptions or ["(none)"]),
        ]
    )
    if plan.refinements:
        lines.extend(["", "Refinements:"])
        lines.extend(f"- {item.get('timestamp', '(unknown)')}: {item.get('change', '(unspecified)')}" for item in plan.refinements)
    lines.extend(["", f"Status: {plan.status}", "No changes have been applied."])
    return lines


def _render_plan_interaction_report(plan: GroundedPlan, *, title: str = "Plan") -> None:
    console.print(Panel.fit("\n".join(_plan_interaction_lines(plan)), title=title, border_style="bright_blue"))


def _grounded_plan_to_agent_steps(plan: GroundedPlan) -> list[AgentPlanStep]:
    return [
        AgentPlanStep(
            step=index + 1,
            action=step.description,
            why=f"Risk={step.risk}; files={', '.join(step.files) if step.files else '(none)'}",
        )
        for index, step in enumerate(plan.steps)
    ]


def _render_project_files_report(snapshot: ProjectSnapshot, *, title: str = "Project Files") -> None:
    body = [
        "Important files",
        "",
        "Config files:",
        *(f"- {item}" for item in snapshot.config_files or ["(none)"]),
        "",
        "Docs:",
        *(f"- {item}" for item in snapshot.docs or ["(none)"]),
        "",
        "Tests:",
        *(f"- {item}" for item in snapshot.test_files or ["(none)"]),
        "",
        "Source files:",
        *(f"- {item}" for item in snapshot.source_files or ["(none)"]),
    ]
    console.print(Panel("\n".join(body), title=title, border_style="bright_blue"))


def _render_project_structure_report(snapshot: ProjectSnapshot, *, title: str = "Structure") -> None:
    body = [
        "Project Structure",
        "",
        f"Root: {snapshot.root_path}",
        f"File count: {snapshot.file_count}",
        f"Languages: {', '.join(snapshot.languages) if snapshot.languages else '(none)'}",
        f"Package managers: {', '.join(snapshot.package_managers) if snapshot.package_managers else '(none)'}",
        f"Frameworks/tools: {', '.join(snapshot.frameworks) if snapshot.frameworks else '(none)'}",
        f"Entry points: {', '.join(snapshot.entry_points) if snapshot.entry_points else '(none)'}",
    ]
    console.print(Panel("\n".join(body), title=title, border_style="bright_blue"))


def _print_file_excerpt(path: Path, *, title: str) -> None:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        console.print(Panel.fit(str(exc), title=title, border_style="red"))
        return
    excerpt = content if len(content) <= 12000 else content[:12000] + "\n...\n[truncated]"
    console.print(Panel(excerpt, title=title, border_style="bright_blue"))


def _inspect_project_command(cwd: Path | None = None, *, force_refresh: bool = False) -> ProjectSnapshot:
    root = _project_root(cwd)
    return ensure_project_snapshot(root, force_refresh=force_refresh)


def _load_snapshot_for_display(root: Path) -> ProjectSnapshot:
    snapshot = load_project_snapshot(root)
    if snapshot is not None:
        append_history_event(root, "project snapshot reused", {"Snapshot ID": snapshot.snapshot_id})
        return snapshot
    return ensure_project_snapshot(root, force_refresh=True)


def _show_current_snapshot(root: Path) -> ProjectSnapshot:
    snapshot = load_project_snapshot(root)
    if snapshot is None:
        if project_snapshot_path(root).is_file():
            console.print("Stored project snapshot was invalid and was ignored.")
        snapshot = ensure_project_snapshot(root, force_refresh=True)
    append_history_event(root, "project snapshot reused", {"Snapshot ID": snapshot.snapshot_id})
    _render_snapshot_report(snapshot, title="Project Snapshot")
    return snapshot


def _show_current_plan(root: Path) -> GroundedPlan | None:
    plan = load_grounded_plan(root)
    if plan is None:
        console.print("No active plan to display.")
        return None
    snapshot = load_current_snapshot_metadata(root)
    if snapshot is None:
        if project_snapshot_path(root).is_file():
            plan = invalidate_grounded_plan(root, plan, "Project snapshot changed")
            console.print("Stored plan was based on an outdated project snapshot and was invalidated.")
        append_history_event(root, "Plan displayed", {"Plan ID": plan.plan_id, "Status": plan.status, "Snapshot status": "missing"})
        _render_plan_interaction_report(plan, title="Plan")
        return plan
    if snapshot_is_stale(root, snapshot) or plan.based_on_snapshot_id != snapshot.snapshot_id:
        reason = "Project snapshot changed"
        plan = invalidate_grounded_plan(root, plan, reason)
        console.print("Stored plan was based on an outdated project snapshot and was invalidated.")
        _render_plan_interaction_report(plan, title="Plan")
        return plan
    append_history_event(root, "Plan displayed", {"Plan ID": plan.plan_id, "Status": plan.status})
    _render_plan_interaction_report(plan, title="Plan")
    return plan


def _why_current_plan(root: Path) -> GroundedPlan | None:
    plan = load_grounded_plan(root)
    if plan is None:
        console.print("No active plan to display.")
        return None
    lines = [
        f"Goal: {plan.goal}",
        f"Planning mode: {plan.mode}",
        f"Snapshot ID: {plan.based_on_snapshot_id}",
        "",
        "Why files were selected:",
    ]
    if plan.files_inspected:
        lines.extend(f"- {item}: referenced by the stored plan as project context for this goal." for item in plan.files_inspected)
    else:
        lines.append("- (none)")
    lines.extend(["", "Why steps exist:"])
    if plan.steps:
        for index, step in enumerate(plan.steps, start=1):
            touched = ", ".join(step.files) if step.files else "(none)"
            lines.append(f"{index}. {step.description}")
            lines.append(f"   Reason: stored step for progressing toward the goal; files={touched}; risk={step.risk}.")
    else:
        lines.append("1. (none)")
    lines.extend(["", "Assumptions:", *(f"- {item}" for item in plan.assumptions or ["(none)"])])
    append_history_event(root, "Plan explained", {"Plan ID": plan.plan_id, "Mode": plan.mode})
    console.print(Panel.fit("\n".join(lines), title="Why This Plan", border_style="bright_blue"))
    return plan


def _explain_plan_step(root: Path, raw_step: str) -> GroundedPlan | None:
    plan = load_grounded_plan(root)
    if plan is None:
        console.print("No active plan to display.")
        return None
    try:
        step_index = int(raw_step)
    except ValueError:
        console.print("Usage: explain step <n>")
        return plan
    if step_index < 1 or step_index > len(plan.steps):
        console.print(f"Step {step_index} does not exist.")
        return plan
    step = plan.steps[step_index - 1]
    lines = [
        f"Step: {step_index}",
        f"What it does: {step.description}",
        f"Why it exists: It is part of the stored plan for goal: {plan.goal}",
        f"Files touched: {', '.join(step.files) if step.files else '(none)'}",
    ]
    if step.proposed_new_files:
        lines.append(f"Proposed new files: {', '.join(step.proposed_new_files)}")
    lines.append(f"Risk level: {step.risk}")
    append_history_event(root, "Step explained", {"Plan ID": plan.plan_id, "Step": step_index})
    console.print(Panel.fit("\n".join(lines), title="Step Explanation", border_style="bright_blue"))
    return plan


def _prompt_for_refinement(session: object | None) -> str:
    prompt = "refinement> "
    if session is not None and hasattr(session, "prompt"):
        return str(session.prompt(prompt)).strip()
    return input(prompt).strip()


def _refine_current_plan(root: Path, *, scope: str, step_text: str | None, change: str | None, session: object | None) -> GroundedPlan | None:
    plan = load_grounded_plan(root)
    if plan is None:
        console.print("No active plan to display.")
        return None
    if plan.status == "invalidated":
        console.print("Cannot refine an invalidated plan.")
        return plan
    refinement = (change or "").strip()
    if not refinement:
        refinement = _prompt_for_refinement(session)
    if not refinement:
        console.print("Refinement was empty; plan unchanged.")
        return plan
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    description = "plan refined"
    updated_steps = list(plan.steps)
    updated_summary = plan.summary
    updated_assumptions = list(plan.assumptions)
    if scope == "step":
        if step_text is None:
            console.print("Usage: refine step <n>")
            return plan
        try:
            step_index = int(step_text)
        except ValueError:
            console.print("Usage: refine step <n>")
            return plan
        if step_index < 1 or step_index > len(updated_steps):
            console.print(f"Step {step_index} does not exist.")
            return plan
        original = updated_steps[step_index - 1]
        updated_steps[step_index - 1] = replace(original, description=f"{original.description} Refinement: {refinement}")
        description = f"step {step_index} refined"
    else:
        updated_summary = f"{plan.summary or plan.goal} Refinement: {refinement}"
        updated_assumptions.append(f"User refinement: {refinement}")
    updated_refinements = [*plan.refinements, {"timestamp": timestamp, "change": description}]
    updated_plan = replace(
        plan,
        steps=updated_steps,
        assumptions=updated_assumptions,
        summary=updated_summary,
        status="awaiting_confirmation",
        refinements=updated_refinements,
    )
    snapshot = load_current_snapshot_metadata(root)
    if snapshot is None:
        append_history_event(
            root,
            "Plan refinement rejected",
            {"Plan ID": plan.plan_id, "Reason": "missing_or_invalid_snapshot", "Validation": "failed"},
        )
        console.print("Refinement rejected.")
        console.print("")
        console.print("Reason:")
        console.print("- missing or invalid project snapshot")
        console.print("")
        console.print("No changes were applied to the plan.")
        return plan
    validation = validate_plan_integrity(updated_plan, snapshot, original_plan=plan, refinement_text=refinement)
    if not validation.valid:
        reason = validation.errors[0] if validation.errors else "plan integrity validation failed"
        append_history_event(
            root,
            "Plan refinement rejected",
            {"Plan ID": plan.plan_id, "Reason": reason, "Validation": "failed"},
        )
        console.print("Refinement rejected.")
        console.print("")
        console.print("Reason:")
        for error in validation.errors:
            console.print(f"- {error}")
        console.print("")
        console.print("No changes were applied to the plan.")
        return plan
    save_grounded_plan(root, updated_plan)
    append_history_event(root, "Plan refined", {"Plan ID": plan.plan_id, "Change": f"{description}: {refinement}", "Validation": "passed"})
    console.print(f"Plan refined: {description}.")
    if validation.warnings:
        console.print("Warning:")
        for warning in validation.warnings:
            console.print(f"- {warning}")
        console.print("You can continue refining or revert.")
    console.print("No changes have been applied.")
    return updated_plan


def _restore_session_from_disk(state: SessionState, workspace_root: Path) -> tuple[str | None, str | None]:
    restore_result = restore_workflow_snapshot(workspace_root)
    if restore_result.snapshot is None:
        return None, restore_result.warning

    snapshot = restore_result.snapshot
    state.restore_workflow(snapshot, source_path=restore_result.source_path)
    if snapshot.state in {"EXECUTING", "REFLECTING"}:
        message = f"Previous workflow was interrupted during {snapshot.state.lower()}. It has been marked failed."
        _fail_active_goal(state, message=message)
        return message, None

    if snapshot.state == "CLARIFICATION":
        awaiting = _workflow_pending_question(state)
    elif snapshot.state == "CONFIRMATION":
        awaiting = "YES/NO"
    else:
        awaiting = "(none)"
    message = "\n".join(
        [
            f"Restored pending workflow: {snapshot.goal}",
            f"State: {snapshot.state.lower()}",
            f"Awaiting: {awaiting}",
        ]
    )
    return message, None


def run_shell() -> None:
    workspace_root = Path.cwd().resolve()
    state = SessionState()
    restore_message, restore_warning = _restore_session_from_disk(state, workspace_root)
    session = None
    if sys.stdin.isatty():
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory

            history_file = Path.home() / ".snappy_putty_history"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.touch(exist_ok=True)
            session = PromptSession(history=FileHistory(str(history_file)))
        except Exception:
            session = None

    print_repl_cheatsheet()
    if restore_warning:
        console.print(restore_warning)
    if restore_message:
        console.print(restore_message)
        if state.current_state == LifecycleState.CONFIRMATION:
            _render_confirmation_prompt(state)

    while True:
        try:
            if _is_choice_question(state.pending_question):
                if session is None:
                    line = _prompt_choice_fallback(state.pending_question)
                else:
                    line = _prompt_choice_question(session, state.pending_question)
            else:
                prompt = render_prompt(state)
                if session is None:
                    line = input(prompt)
                else:
                    line = session.prompt(prompt)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        text = line.strip()
        if not text:
            continue
        if _handle_agent_mode_command(text, state, session=session):
            continue
        if text == "init":
            init(force=False)
            continue
        if text == "agent doctor":
            _handle_agent_doctor(session_mode=state.agent_mode)
            continue
        if text == "agent":
            _handle_agent_summary(session_mode=state.agent_mode)
            continue

        decision = classify_input(text)
        route = decision.route
        _debug(f"raw user input={text!r}")
        _debug(f"classified route={route}")

        if _clarification_input_is_locked(text=text, route=route, state=state):
            _render_clarification_lock_message(state)
            continue

        if _handle_confirmation_input(text=text, route=route, state=state, workspace_root=workspace_root):
            continue

        if _should_consume_pending_question(text=text, route=route, state=state):
            _consume_pending_question_answer(answer=text, state=state)
            continue
        if _should_override_guided_listing_question(route=route, state=state):
            state.reset_to_idle_preserving_history()

        if route == ROUTE_BUILTIN_EXIT:
            break
        if route == ROUTE_BUILTIN_AFTER:
            _handle_after(state)
            continue
        if route == ROUTE_BUILTIN_STATUS:
            _handle_status(state)
            continue
        if route == ROUTE_BUILTIN_CANCEL:
            state.last_route = route
            if not _has_cancellable_workflow(state):
                state.reset_to_idle_preserving_history()
                console.print("Nothing to cancel.")
                continue
            _cancel_active_goal(state, message="Cancelled active task state.")
            console.print("Cleared pending question/plan state.")
            continue
        if route == ROUTE_BUILTIN_HELP:
            print_repl_cheatsheet()
            if state.current_state == LifecycleState.CLARIFICATION and state.pending_question and not _is_choice_question(state.pending_question):
                _render_clarification_followup(state, blocked=False)
            continue
        if route == ROUTE_INSPECT_PROJECT:
            _render_snapshot_report(ensure_project_snapshot(workspace_root, force_refresh=True))
            continue
        if route == ROUTE_INSPECT_FILES:
            _render_project_files_report(_load_snapshot_for_display(workspace_root))
            continue
        if route == ROUTE_INSPECT_STRUCTURE:
            _render_project_structure_report(_load_snapshot_for_display(workspace_root))
            continue
        if route == ROUTE_INSPECT_FILE:
            inspect_path = decision.payload.get("path", "").strip()
            if not inspect_path:
                console.print("Usage: inspect file <path>")
            else:
                candidate = (workspace_root / inspect_path).resolve() if not Path(inspect_path).is_absolute() else Path(inspect_path).resolve()
                try:
                    candidate.relative_to(workspace_root)
                except ValueError:
                    console.print("Refusing to inspect a file outside the current project root.")
                else:
                    if candidate.is_file():
                        _print_file_excerpt(candidate, title=f"File: {inspect_path}")
                    else:
                        console.print(f"File not found: {inspect_path}")
            continue
        if route == ROUTE_SHOW_SNAPSHOT:
            _show_current_snapshot(workspace_root)
            continue
        if route == ROUTE_SHOW_PLAN:
            _show_current_plan(workspace_root)
            continue
        if route == ROUTE_WHY_PLAN:
            _why_current_plan(workspace_root)
            continue
        if route == ROUTE_EXPLAIN_STEP:
            _explain_plan_step(workspace_root, decision.payload.get("step", ""))
            continue
        if route == ROUTE_REFINE_PLAN:
            _refine_current_plan(
                workspace_root,
                scope=decision.payload.get("scope", "plan"),
                step_text=decision.payload.get("step"),
                change=decision.payload.get("change"),
                session=session,
            )
            continue
        if route == ROUTE_REFRESH_SNAPSHOT:
            _render_snapshot_report(ensure_project_snapshot(workspace_root, force_refresh=True), title="Refreshed Snapshot")
            continue
        if route == ROUTE_BUILTIN_DOCTOR:
            doctor(verbose=False)
            continue
        if text == "skills":
            skills(agent_mode_override=state.agent_mode)
            continue
        if text == "rules":
            rules(agent_mode_override=state.agent_mode)
            continue
        if route == ROUTE_UNKNOWN:
            state.last_route = ROUTE_UNKNOWN
            state.last_failed_goal = text
            state.error_message = "Unrecognized command"
            console.print(UNKNOWN_COMMAND_MESSAGE)
            state.reset_to_idle_preserving_history()
            continue
        if route == ROUTE_OUT_OF_SCOPE:
            _render_non_project_skip(decision.payload.get("intent", text), root=workspace_root, state=state)
            continue
        if route == ROUTE_EXPLAIN:
            command = decision.payload.get("command", "").strip()
            if not command:
                console.print("Usage: explain <command>")
                continue
            result = handle_explain(command=command, session_mode=state.agent_mode)
            pending_context = {"type": "ask_followup", "base_intent": command} if result.output.question else {}
            _record_agent_planning_result(state, route=route, goal=command, result=result, pending_context=pending_context)
            continue

        if route == ROUTE_FS_MUTATION:
            _handle_fs_intent_repl(
                intent=decision.payload.get("intent", text),
                workspace_root=workspace_root,
                state=state,
            )
            continue

        if route == ROUTE_GIT_READ:
            _handle_git_read_repl(
                intent=decision.payload.get("intent", text),
                workspace_root=workspace_root,
                state=state,
            )
            continue

        if route == ROUTE_SAFE_INSPECT:
            _handle_safe_inspect_repl(intent=decision.payload.get("intent", text), state=state)
            continue

        if route != ROUTE_ASK:
            continue

        current_intent = decision.payload.get("intent", text)
        result = handle_ask(intent=current_intent, session_mode=state.agent_mode)
        pending_context = {"type": "ask_followup", "base_intent": current_intent} if result.output.question else {}
        _record_agent_planning_result(state, route=route, goal=current_intent, result=result, pending_context=pending_context)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Start shell when no subcommand is provided."""
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        run_shell()


@inspect_app.command("project")
def inspect_project() -> None:
    """Inspect the current repository and cache a project snapshot."""
    snapshot = ensure_project_snapshot(Path.cwd().resolve(), force_refresh=True)
    _render_snapshot_report(snapshot)


@inspect_app.command("files")
def inspect_files() -> None:
    """Inspect the project file inventory."""
    snapshot = _load_snapshot_for_display(Path.cwd().resolve())
    _render_project_files_report(snapshot)


@inspect_app.command("structure")
def inspect_structure() -> None:
    """Inspect the overall project structure."""
    snapshot = _load_snapshot_for_display(Path.cwd().resolve())
    _render_project_structure_report(snapshot)


@inspect_app.command("file")
def inspect_file(path: str) -> None:
    """Inspect a single file in read-only mode."""
    root = Path.cwd().resolve()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        console.print("Refusing to inspect a file outside the current project root.")
        return
    if not candidate.is_file():
        console.print(f"File not found: {path}")
        return
    _print_file_excerpt(candidate, title=f"File: {path}")


@show_app.command("snapshot")
def show_snapshot() -> None:
    """Show the current cached project snapshot."""
    _show_current_snapshot(Path.cwd().resolve())


@show_app.command("plan")
def show_plan() -> None:
    """Show the current grounded plan."""
    _show_current_plan(Path.cwd().resolve())


@refresh_app.command("snapshot")
def refresh_snapshot() -> None:
    """Force a fresh project snapshot."""
    snapshot = ensure_project_snapshot(Path.cwd().resolve(), force_refresh=True)
    _render_snapshot_report(snapshot, title="Refreshed Snapshot")


@app.command()
def ask(intent: str = typer.Argument(..., help="What you want to accomplish.")) -> None:
    """Generate suggestion-only plan for an intent."""
    decision = classify_input(intent)
    route = decision.route
    _debug(f"raw user input={intent!r}")
    _debug(f"classified route={route}")

    if route == ROUTE_BUILTIN_HELP:
        print_repl_cheatsheet()
        return
    if route == ROUTE_BUILTIN_DOCTOR:
        doctor(verbose=False)
        return
    if route == ROUTE_BUILTIN_AFTER:
        console.print("`after` is available in interactive shell mode only.")
        return
    if route == ROUTE_BUILTIN_STATUS:
        console.print("`status` is available in interactive shell mode only.")
        return
    if route == ROUTE_BUILTIN_CANCEL:
        console.print("`cancel` is available in interactive shell mode only.")
        return
    if route == ROUTE_BUILTIN_EXIT:
        console.print("Use `snappy shell` for interactive exit/quit controls.")
        return
    if route == ROUTE_EXPLAIN:
        command = decision.payload.get("command", "").strip()
        if not command:
            console.print("Usage: explain <command>")
            return
        handle_explain(command)
        return
    if route == ROUTE_UNKNOWN:
        console.print(UNKNOWN_COMMAND_MESSAGE)
        return
    if route == ROUTE_OUT_OF_SCOPE:
        _render_non_project_skip(decision.payload.get("intent", intent), root=Path.cwd().resolve())
        return
    if route == ROUTE_FS_MUTATION:
        _handle_fs_intent(
            intent=decision.payload.get("intent", intent),
            prompt_reader=lambda prompt: input(prompt),
            workspace_root=Path.cwd().resolve(),
        )
        return
    if route == ROUTE_GIT_READ:
        _handle_git_read(intent=decision.payload.get("intent", intent), workspace_root=Path.cwd().resolve())
        return
    handle_ask(decision.payload.get("intent", intent), session_mode=None)


def handle_ask(intent: str, session_mode: str | None = None) -> AgentRunResult:
    """Run ask flow and render output."""
    agent_mode = get_agent_mode(session_mode)
    planning_intent = classify_planning_intent(intent)
    if agent_mode == "off" and planning_intent == PlanningIntent.PROJECT_DEVELOPER_GOAL:
        console.print("Active planning is off.")
        console.print("Broad developer goals require active LLM-assisted planning.")
        console.print("No project plan was created.")
        return AgentRunResult(
            output=AgentOutput(
                goal=intent,
                assumptions=[],
                question=None,
                plan=[],
                commands=[],
                warnings=["No project plan was created."],
                snippets=[],
            ),
            skip_reason="llm_required_but_unavailable",
        )
    if agent_mode == "active":
        root = Path.cwd().resolve()
        snapshot = ensure_project_snapshot(root)
        planning_mode = classify_planning_mode(intent)
        related, relevance_reason = assess_project_relevance(intent, snapshot)
        console.print("Inspecting project context...")
        console.print(f"Using snapshot: {snapshot.snapshot_id}")
        if planning_intent in {
            PlanningIntent.GENERAL_KNOWLEDGE_QUESTION,
            PlanningIntent.CURRENT_INFO_QUESTION,
            PlanningIntent.UNRELATED_NON_PROJECT_REQUEST,
            PlanningIntent.UNSUPPORTED_EXTERNAL_TOOL_REQUEST,
        }:
            reason = (
                "unsupported_current_info_question"
                if planning_intent == PlanningIntent.CURRENT_INFO_QUESTION
                else ("goal_not_project_related" if planning_intent == PlanningIntent.UNRELATED_NON_PROJECT_REQUEST else "non_project_question")
            )
            if reason == "unsupported_current_info_question":
                console.print("This looks like a current information request, not a project task.")
                console.print("Snappy cannot answer live market data or other current information unless current-info tools are enabled.")
            else:
                console.print("This looks like a general question, not a project task.")
            console.print("No project plan was created.")
            _record_planning_skipped_memory(root, goal=intent, reason=reason, snapshot=snapshot)
            return AgentRunResult(
                output=AgentOutput(
                    goal=intent,
                    assumptions=[f"Based on cached project snapshot: {snapshot.snapshot_id}"],
                    question=None,
                    plan=[],
                    commands=[],
                    warnings=["No project plan was created."],
                    snippets=[],
                ),
                raw_model_text=None,
                parse_error=None,
                directory_listing=None,
                plan_mode=None,
                skip_reason=reason,
            )
        if not related:
            console.print("This request does not appear to be related to the current project.")
            console.print("I did not create a grounded project plan because there is no clear connection between the request and the inspected workspace.")
            console.print("No project plan was created.")
            _record_planning_skipped_memory(root, goal=intent, reason=relevance_reason, snapshot=snapshot)
            return AgentRunResult(
                output=AgentOutput(
                    goal=intent,
                    assumptions=[f"Based on cached project snapshot: {snapshot.snapshot_id}"],
                    question=None,
                    plan=[],
                    commands=[],
                    warnings=["No changes have been applied."],
                    snippets=[],
                ),
                raw_model_text=None,
                parse_error=None,
                directory_listing=None,
                plan_mode=None,
                skip_reason=relevance_reason,
            )
        try:
            with busy(get_status_message("plan"), console=console):
                if planning_mode == PlanningMode.LLM_ASSISTED:
                    plan = create_llm_assisted_plan(intent, snapshot, session_mode=session_mode)
                    console.print("Generating LLM-assisted grounded plan...")
                else:
                    plan = build_grounded_plan(intent, snapshot, mode=PlanningMode.DETERMINISTIC)
        except LLMPlannerUnavailableError as exc:
            _debug(str(exc))
            console.print("Generating deterministic grounded plan from inspected project context...")
            with busy(get_status_message("plan"), console=console):
                plan = build_grounded_plan(intent, snapshot, mode=PlanningMode.DETERMINISTIC)
        except LLMPlanValidationError as exc:
            console.print("LLM-assisted plan was rejected by validation.")
            console.print(f"Reason: {exc}")
            _record_planning_skipped_memory(root, goal=intent, reason="llm_required_but_unavailable", snapshot=snapshot)
            return AgentRunResult(
                output=AgentOutput(
                    goal=intent,
                    assumptions=[f"Based on cached project snapshot: {snapshot.snapshot_id}"],
                    question=None,
                    plan=[],
                    commands=[],
                    warnings=["No project plan was created."],
                    snippets=[],
                ),
                raw_model_text=None,
                parse_error=None,
                directory_listing=None,
                plan_mode=None,
                skip_reason="llm_required_but_unavailable",
            )
        if plan is None:
            return AgentRunResult(
                output=AgentOutput(
                    goal=intent,
                    assumptions=[f"Based on cached project snapshot: {snapshot.snapshot_id}"],
                    question=None,
                    plan=[],
                    commands=[],
                    warnings=["No changes have been applied."],
                    snippets=[],
                ),
                raw_model_text=None,
                parse_error=None,
                directory_listing=None,
                plan_mode=None,
            )
        save_grounded_plan(root, plan, snapshot)
        event_name = "LLM-assisted plan created" if plan.mode == PlanningMode.LLM_ASSISTED.value else "Grounded plan created"
        append_history_event(
            root,
            event_name,
            {
                "Mode": plan.mode,
                "Goal": plan.goal,
                "Plan ID": plan.plan_id,
                "Based on snapshot": plan.based_on_snapshot_id,
                "Files referenced": plan.files_inspected,
                "Status": plan.status,
            },
        )
        _render_grounded_plan_report(plan)
        return AgentRunResult(
            output=AgentOutput(
                goal=plan.goal,
                assumptions=[f"Based on cached project snapshot: {snapshot.snapshot_id}", f"Inspection root: {snapshot.root_path}"],
                question=None,
                plan=_grounded_plan_to_agent_steps(plan),
                commands=[],
                warnings=plan.risks,
                snippets=[],
            ),
            raw_model_text=None,
            parse_error=None,
            directory_listing=None,
            plan_mode=plan.mode,
        )
    with busy(get_status_message("ask"), console=console):
        snapshot = collect_context()
        result = plan_with_agent(mode="ask", user_text=intent, snapshot=snapshot)
    if result.parse_error:
        render_agent_parse_error(console=console, parse_error=result.parse_error, raw_model_text=result.raw_model_text)
    if result.directory_listing is not None:
        render_directory_listing(console=console, content=result.directory_listing)
    render_agent_output(console=console, output=result.output, title="ask")
    return result


@app.command()
def explain(command: str = typer.Argument(..., help="Command to explain.")) -> None:
    """Explain a command with safety-aware suggestions."""
    handle_explain(command)


def handle_explain(command: str, session_mode: str | None = None) -> AgentRunResult:
    """Run explain flow and render output."""
    with busy(get_status_message("explain"), console=console):
        result = plan_with_agent(mode="explain", user_text=command, snapshot=None, session_mode=session_mode)
    if result.parse_error:
        render_agent_parse_error(console=console, parse_error=result.parse_error, raw_model_text=result.raw_model_text)
    render_agent_output(console=console, output=result.output, title="explain")
    return result


@app.command()
def doctor(verbose: Optional[bool] = typer.Option(False, "--verbose", help="Show extra diagnostics.")) -> None:
    """Show local context snapshot for planning."""
    snapshot = collect_context()
    render_doctor_report(console=console, snapshot=snapshot, verbose=verbose)


@app.command()
def agent() -> None:
    """Show a summary of the currently loaded .snappy agent."""
    _handle_agent_summary()


@app.command("agent-doctor")
def agent_doctor() -> None:
    """Inspect the .snappy runtime surface and loaded agent artifacts."""
    _handle_agent_doctor()


@app.command()
def init(force: bool = typer.Option(False, "--force", help="Overwrite scaffold files if .snappy already exists.")) -> None:
    """Scaffold a minimal .snappy/ directory."""
    result = init_agent_project(Path.cwd(), force=force)
    console.print(result.message)


@app.command()
def skills(agent_mode_override: str | None = None) -> None:
    """List skills loaded from .snappy/skills/*.md."""
    registry = load_agent_skill_registry(Path.cwd(), session_mode=agent_mode_override)
    if not registry.skills:
        console.print("No skills loaded.")
    else:
        console.print("Loaded skills:")
        for skill in registry.skills:
            console.print(f"- {skill.name} [{skill.risk}]", markup=False)
    for warning in registry.warnings:
        console.print(warning)


@app.command()
def rules(agent_mode_override: str | None = None) -> None:
    """List rules loaded from .snappy/rules/*.md."""
    registry = load_agent_rule_registry(Path.cwd(), session_mode=agent_mode_override)
    if not registry.rules:
        console.print("No rules loaded.")
    else:
        console.print("Loaded rules:")
        for rule in registry.rules:
            classification = f"enforceable:{rule.tier}" if rule.supported_for_enforcement else "informational"
            console.print(f"- {rule.name} [{rule.identifier}] ({classification})", markup=False)
    for warning in registry.warnings:
        console.print(warning)


@app.command()
def shell() -> None:
    """Start interactive REPL mode."""
    run_shell()


def _set_fs_confirmation_state(
    state: SessionState,
    *,
    plan: FsPlan,
    workspace_root: Path,
    stage: str,
    allow_overwrite: bool,
    allow_excess_ops: bool,
    excess_ops: bool,
) -> None:
    state.pending_plan = plan
    state.pending_question = None
    state.awaiting_confirmation = True
    state.update_workflow_context(
        ConfirmationContext(
            operation_count=len(plan.ops),
            overwrite_detected=stage == "overwrite",
            stage=stage,
            workspace_root=str(workspace_root),
            allow_overwrite=allow_overwrite,
            allow_excess_ops=allow_excess_ops,
            excess_ops=excess_ops,
        )
    )
    _set_state(state, LifecycleState.CONFIRMATION)


def _consume_confirmation_response(response: str, state: SessionState, workspace_root: Path) -> None:
    value = _normalized_confirmation_token(response)
    if value not in {"YES", "NO"}:
        return
    if value == "NO":
        _cancel_active_goal(state, message="Cancelled pending action.")
        console.print(Panel.fit("Cancelled. No pending action was applied.", title="Apply Cancelled", border_style="yellow"))
        return

    context = state.pending_context
    if not isinstance(context, ConfirmationContext):
        _fail_active_goal(state, message="Confirmation received, but no actionable pending state remained.")
        return
    if not isinstance(state.pending_plan, FsPlan):
        _fail_active_goal(state, message="Confirmation received, but no plan was available.")
        return

    stage = context.stage
    allow_overwrite = context.allow_overwrite
    allow_excess_ops = context.allow_excess_ops
    excess_ops = context.excess_ops
    root = Path(context.workspace_root or str(workspace_root)).resolve()

    if stage == "overwrite":
        allow_overwrite = True
        if excess_ops:
            _set_fs_confirmation_state(
                state,
                plan=state.pending_plan,
                workspace_root=root,
                stage="limit",
                allow_overwrite=allow_overwrite,
                allow_excess_ops=allow_excess_ops,
                excess_ops=excess_ops,
            )
            _render_confirmation_prompt(state)
            return
        _set_fs_confirmation_state(
            state,
            plan=state.pending_plan,
            workspace_root=root,
            stage="apply",
            allow_overwrite=allow_overwrite,
            allow_excess_ops=allow_excess_ops,
            excess_ops=excess_ops,
        )
        _render_confirmation_prompt(state)
        return

    if stage == "limit":
        allow_excess_ops = True
        _set_fs_confirmation_state(
            state,
            plan=state.pending_plan,
            workspace_root=root,
            stage="apply",
            allow_overwrite=allow_overwrite,
            allow_excess_ops=allow_excess_ops,
            excess_ops=excess_ops,
        )
        _render_confirmation_prompt(state)
        return

    registry = load_agent_rule_registry(root, session_mode=state.agent_mode)
    rule_decision = before_filesystem_mutation_plan_or_execute(
        plan=state.pending_plan,
        cwd=Path.cwd(),
        workspace_root=root,
        rule_registry=registry,
    )
    if rule_decision.blocked:
        message = rule_decision.message or "Operation blocked by loaded agent rules."
        console.print(message)
        result = _execution_result(state=state, status="blocked", message=message, error=message)
        _reflect_execution_result(state, result)
        return

    _set_state(state, LifecycleState.EXECUTING)
    with busy(get_status_message("fs"), console=console):
        result = apply_fs_plan(
            plan=state.pending_plan,
            cwd=Path.cwd(),
            workspace_root=root,
            allow_overwrite=allow_overwrite,
            allow_excess_ops=allow_excess_ops,
        )
    render_fs_apply_result(console=console, result=result)
    operations = [
        ExecutionOperation(action=item.action, status=item.status, message=item.message)
        for item in result.results
    ]
    applied_count = sum(1 for item in result.results if item.status == "applied")
    failed_messages = [item.message for item in result.results if item.status == "failed" and item.message]
    message = f"Applied {applied_count} filesystem operation(s)."
    if any(item.status == "failed" for item in result.results):
        if failed_messages:
            message = f"{message} Failure: {failed_messages[0]}"
        failure_result = _execution_result(
            state=state,
            status="failed",
            message=message,
            operations=operations,
            warnings=result.warnings,
            error=message,
        )
        _reflect_execution_result(state, failure_result)
        return
    success_result = _execution_result(
        state=state,
        status="completed",
        message=message,
        operations=operations,
        warnings=result.warnings,
    )
    _reflect_execution_result(state, success_result)


def _consume_pending_question_answer(answer: str, state: SessionState) -> None:
    question_context = state.pending_context
    prompt_kind = question_context.prompt_kind if isinstance(question_context, ClarificationContext) else None
    if prompt_kind == "guided_listing_choice":
        selected = answer.strip()
        if selected == "custom":
            _record_clarification(
                state,
                question={"type": "path", "prompt": "Enter custom path:"},
                pending_context={"type": "guided_listing_custom_path", "base_intent": question_context.base_intent or ""},
            )
            state.last_result = "Awaiting custom listing path."
            return
        state.pending_question = None
        state.update_workflow_context(None)
        _enter_planning(state)
        _handle_safe_inspect_repl(
            intent=f'give me a file listing for "{selected}"',
            state=state,
            start_new_goal=False,
        )
        return

    if prompt_kind == "guided_listing_custom_path":
        state.pending_question = None
        state.update_workflow_context(None)
        _enter_planning(state)
        _handle_safe_inspect_repl(
            intent=f'give me a file listing for "{answer.strip()}"',
            state=state,
            start_new_goal=False,
        )
        return

    if prompt_kind == "fs_destination":
        action = (question_context.action or "copy") if isinstance(question_context, ClarificationContext) else "copy"
        src = (question_context.source_path or "").strip() if isinstance(question_context, ClarificationContext) else ""
        root = Path((question_context.workspace_root if isinstance(question_context, ClarificationContext) and question_context.workspace_root else str(Path.cwd()))).resolve()
        state.pending_question = None
        state.update_workflow_context(None)
        _enter_planning(state)
        _handle_fs_intent_repl(
            intent=f"{action} {src} to {answer.strip()}",
            workspace_root=root,
            state=state,
            start_new_goal=False,
        )
        return

    base_intent = ((question_context.base_intent or "") if isinstance(question_context, ClarificationContext) else (state.active_goal or "")).strip()
    state.pending_question = None
    state.update_workflow_context(None)
    followup_intent = f"{base_intent} for {answer.strip()}" if base_intent else answer.strip()
    state.active_goal = followup_intent
    state.last_route = ROUTE_ASK
    state.error_message = None
    state.sync_active_workflow()
    _enter_planning(state)
    result = handle_ask(intent=followup_intent, session_mode=state.agent_mode)
    state.last_result = result.output.goal
    state.pending_plan = result.output.plan
    state.pending_question = result.output.question
    state.awaiting_confirmation = False
    if result.output.question:
        state.update_workflow_context(
            ClarificationContext(
                source_path=None,
                expected_input="answer",
                action=None,
                base_intent=base_intent or followup_intent,
                workspace_root=None,
                prompt_kind="ask_followup",
            )
        )
        _set_state(state, LifecycleState.CLARIFICATION)
    else:
        state.update_workflow_context(None)


def _handle_after(state: SessionState) -> None:
    if state.pending_question:
        console.print(f"Pending question: {_workflow_pending_question(state)}")
        return
    if _workflow_awaiting_confirmation(state):
        console.print(f"Awaiting confirmation: {_confirmation_prompt_message(state)}")
        return
    if isinstance(state.pending_plan, list) and state.pending_plan:
        next_step = state.pending_plan[0]
        action = getattr(next_step, "action", None)
        if not action and isinstance(next_step, dict):
            action = next_step.get("action")
        console.print(f"Next suggested step: {action or 'Review latest plan details.'}")
        return
    if isinstance(state.pending_plan, FsPlan) and state.pending_plan.ops:
        first_op = state.pending_plan.ops[0]
        console.print(f"Next planned filesystem step: {first_op.action} {first_op.dst or ''}".strip())
        return
    console.print("No pending next step.")


def _handle_status(state: SessionState) -> None:
    root = Path.cwd().resolve()
    current_state = state.current_state.value
    snapshot = _workflow_snapshot(state)
    active_goal = (snapshot.goal if snapshot else state.active_goal) or "(none)"
    last_route = (snapshot.route if snapshot else state.last_route) or "(none)"
    pending_question = _workflow_pending_question(state)
    pending_plan = _workflow_pending_plan_summary(state)
    awaiting = "yes" if _workflow_awaiting_confirmation(state) else "no"
    last_completed_goal = state.last_completed_goal or "(none)"
    last_cancelled_goal = state.last_cancelled_goal or "(none)"
    last_failed_goal = state.last_failed_goal or "(none)"
    last_blocked_goal = state.last_blocked_goal or "(none)"
    session_payload = load_session_payload(root)
    last_skipped_goal = state.last_skipped_goal or session_payload.get("last_skipped_goal") or "(none)"
    last_skip_reason = state.last_skip_reason or session_payload.get("last_skip_reason") or "(none)"
    error_message = state.error_message or "(none)"
    control_state = _workflow_control_state(state)
    lines = [
        f"Current state: {current_state}",
        f"Active goal: {active_goal}",
        f"Last route: {last_route}",
        f"Pending question: {pending_question}",
        f"Pending plan: {pending_plan}",
        f"Awaiting confirmation: {awaiting}",
        f"Current control state: {control_state}",
    ]
    if state.workflow_restored_from_memory and state.active_goal:
        lines.append("Workflow restored from memory: yes")
        if state.restore_source:
            lines.append(f"Restore source: {state.restore_source}")
    lines.extend(
        [
            f"Last completed goal: {last_completed_goal}",
            f"Last cancelled goal: {last_cancelled_goal}",
            f"Last failed goal: {last_failed_goal}",
            f"Last blocked goal: {last_blocked_goal}",
            f"Last skipped goal: {last_skipped_goal}",
            f"Last skip reason: {last_skip_reason}",
            f"Error message: {error_message}",
        ]
    )
    project_snapshot = load_current_snapshot_metadata(root)
    snapshot_present = project_snapshot_path(root).is_file()
    snapshot_valid = project_snapshot is not None
    current_plan = load_grounded_plan(root)
    if current_plan is not None and not snapshot_valid:
        current_plan = invalidate_grounded_plan(root, current_plan, "Project snapshot changed")
    if current_plan is not None and project_snapshot is not None and current_plan.based_on_snapshot_id != project_snapshot.snapshot_id:
        current_plan = invalidate_grounded_plan(root, current_plan, "Project snapshot changed")
    lines.append(f"Agent mode: {get_agent_mode(state.agent_mode)}")
    lines.append(f"Project snapshot: {'present' if snapshot_present else 'absent'}")
    lines.append(f"Snapshot valid: {'yes' if snapshot_valid else 'no'}")
    if project_snapshot is not None:
        lines.append(f"Snapshot ID: {project_snapshot.snapshot_id}")
        lines.append(f"Snapshot root: {project_snapshot.root_path}")
        lines.append(f"Snapshot status: {project_snapshot.git_status_summary or '(none)'}")
        try:
            created_at = datetime.fromisoformat(project_snapshot.created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_seconds = max(0, int((datetime.now(created_at.tzinfo) - created_at).total_seconds()))
            lines.append(f"Snapshot age: {age_seconds // 60}m")
        except ValueError:
            lines.append("Snapshot age: unknown")
    lines.append(f"Grounded planning: {'yes' if current_plan is not None else 'no'}")
    if current_plan is not None:
        lines.append("Last plan: present")
        lines.append(f"Last plan mode: {current_plan.mode}")
        lines.append(f"Last plan status: {current_plan.status}")
        lines.append(f"Last plan based on snapshot: {current_plan.based_on_snapshot_id}")
        lines.append(f"Last plan id: {current_plan.plan_id}")
    else:
        lines.append("Last plan: absent")
    lines.append(f"Writes allowed: confirmation only")
    lines.append(f"History log: {history_path(root)}")
    lines.extend(_build_status_agent_lines(session_mode=state.agent_mode))
    console.print(Panel.fit("\n".join(lines), title="Session Status", border_style="bright_blue"))


def _current_control_state(state: SessionState) -> str:
    if state.awaiting_confirmation:
        return "awaiting_confirm"
    if state.current_state == LifecycleState.BLOCKED:
        return "blocked"
    if state.current_state == LifecycleState.FAILED and state.error_message and "Operation blocked by rule:" in state.error_message:
        return "blocked"
    return "allowed"


def _handle_git_read_repl(intent: str, workspace_root: Path, state: SessionState) -> bool:
    git_intent = parse_git_read_intent(intent)
    _begin_goal(state, goal=intent, route=ROUTE_GIT_READ)
    _enter_planning(state)
    if git_intent is None:
        _fail_active_goal(state, message="Could not map the Git request to a supported read-only action.")
        render_git_read(console=console, title="Git Read Failed", content="Supported Git reads: status, recent commits, current branch, branches, remotes, diff summary, and show commit <sha>.", ok=False)
        return True

    _set_state(state, LifecycleState.EXECUTING)
    with busy(get_status_message("ask"), console=console):
        result = execute_git_read(git_intent, workspace_root.resolve())
    render_git_read(console=console, title=result.title, content=result.body, ok=result.ok)
    execution_result = _execution_result(
        state=state,
        status="completed" if result.ok else "failed",
        message=result.summary if result.ok else (result.error_message or result.summary),
        operations=[
            ExecutionOperation(
                action=git_intent.kind,
                status="applied" if result.ok else "failed",
                message=result.summary if result.ok else (result.error_message or result.summary),
            )
        ],
        error=result.error_message,
    )
    if result.ok:
        _reflect_execution_result(state, execution_result)
    else:
        _reflect_execution_result(state, execution_result)
    return True


def _handle_fs_intent_repl(intent: str, workspace_root: Path, state: SessionState, *, start_new_goal: bool = True) -> bool:
    root = workspace_root.resolve()
    _debug(f"raw fs intent={intent!r}")
    if start_new_goal:
        _begin_goal(state, goal=intent, route=ROUTE_FS_MUTATION)
        _enter_planning(state)
    else:
        state.active_goal = intent
        state.last_route = ROUTE_FS_MUTATION
        state.error_message = None
        state.sync_active_workflow()
    plan = plan_fs_intent(intent=intent, cwd=Path.cwd(), workspace_root=root)

    if plan is None:
        partial = parse_incomplete_fs_intent(intent)
        if partial is not None:
            action, src = partial
            _record_clarification(
                state,
                question={"type": "path", "prompt": "destination path>"},
                pending_context={"type": "fs_destination", "action": action, "src": src, "workspace_root": str(root)},
            )
            state.last_result = "Awaiting destination path."
            return True
        if looks_like_fs_mutation_intent(intent):
            console.print("Could not parse filesystem action. Try examples: copy A to B, move A to B, rename A to B, make a folder called X.")
            _fail_active_goal(state, message="Failed to parse filesystem action.")
            return True
        return False

    registry = load_agent_rule_registry(root, session_mode=state.agent_mode)
    rule_decision = before_filesystem_mutation_plan_or_execute(
        plan=plan,
        cwd=Path.cwd(),
        workspace_root=root,
        rule_registry=registry,
    )
    if rule_decision.blocked:
        message = rule_decision.message or "Operation blocked by loaded agent rules."
        message = block_message_from_decision(message, rule_decision.policy_decision)
        render_fs_rule_block(
            console=console,
            goal=plan.goal or intent,
            message=message,
            next_step_hint="Adjust the target path or request, then try again.",
        )
        blocked_result = _execution_result(state=state, status="blocked", message=message, error=message)
        _reflect_execution_result(state, blocked_result)
        return True

    if not plan.ops:
        title, summary, details, next_step_hint = _empty_fs_plan_feedback(plan)
        render_fs_cannot_proceed(
            console=console,
            goal=plan.goal or intent,
            title=title,
            summary=summary,
            details=details,
            next_step_hint=next_step_hint,
        )
        _fail_active_goal(state, message=summary)
        return True

    policy_notes = policy_notes_from_decision(rule_decision.policy_decision)
    render_fs_plan(console=console, plan=plan, policy_notes=policy_notes)
    state.pending_plan = plan
    state.pending_question = None
    state.sync_active_workflow()

    requires_confirmation = plan.requires_confirmation or rule_decision.requires_confirmation
    if not requires_confirmation:
        state.awaiting_confirmation = False
        state.update_workflow_context(None)
        state.last_result = "Planned filesystem change(s) with no apply confirmation needed."
        return True

    overwrite_needed = False
    for op in plan.ops:
        if op.action in {"copy", "move", "rename"} and op.dst:
            destination = (Path.cwd() / op.dst).resolve()
            if destination.exists():
                overwrite_needed = True
                break
    excess_ops = len(plan.ops) > MAX_OPS

    if overwrite_needed:
        _set_fs_confirmation_state(
            state,
            plan=plan,
            workspace_root=root,
            stage="overwrite",
            allow_overwrite=False,
            allow_excess_ops=False,
            excess_ops=excess_ops,
        )
        _render_confirmation_prompt(state)
        state.last_result = "Awaiting overwrite confirmation."
        return True

    if excess_ops:
        _set_fs_confirmation_state(
            state,
            plan=plan,
            workspace_root=root,
            stage="limit",
            allow_overwrite=False,
            allow_excess_ops=False,
            excess_ops=excess_ops,
        )
        _render_confirmation_prompt(state)
        state.last_result = "Awaiting large-plan confirmation."
        return True

    _set_fs_confirmation_state(
        state,
        plan=plan,
        workspace_root=root,
        stage="apply",
        allow_overwrite=False,
        allow_excess_ops=False,
        excess_ops=False,
    )
    _render_confirmation_prompt(state)
    state.last_result = "Awaiting apply confirmation."
    return True


def _prompt_reader(session) -> Callable[[str], str]:
    if session is None:
        return lambda prompt: input(prompt)
    return lambda prompt: session.prompt(prompt)


def _handle_git_read(intent: str, workspace_root: Path | None = None) -> bool:
    git_intent = parse_git_read_intent(intent)
    if git_intent is None:
        return False
    with busy(get_status_message("ask"), console=console):
        result = execute_git_read(git_intent, (workspace_root or Path.cwd()).resolve())
    render_git_read(console=console, title=result.title, content=result.body, ok=result.ok)
    return True


def _handle_fs_intent(intent: str, prompt_reader: Callable[[str], str] | None, workspace_root: Path | None = None) -> bool:
    root = (workspace_root or Path.cwd()).resolve()
    _debug(f"raw fs intent={intent!r}")
    plan = plan_fs_intent(intent=intent, cwd=Path.cwd(), workspace_root=root)
    if plan is None:
        partial = parse_incomplete_fs_intent(intent)
        if partial is not None:
            action, src = partial
            _debug(f"incomplete fs parse action={action!r} src={src!r} dst=None")
            if prompt_reader is None:
                console.print(f"Usage: {action} <source> to <destination>")
                return True
            try:
                destination = prompt_reader("destination path> ").strip()
            except EOFError:
                destination = ""
            except KeyboardInterrupt:
                destination = ""
            if not destination:
                console.print(Panel.fit("Cancelled. No destination was provided.", title="Apply Cancelled", border_style="yellow"))
                return True
            _debug(f"destination prompt value={destination!r}")
            plan = plan_fs_intent(intent=f"{action} {src} to {destination}", cwd=Path.cwd(), workspace_root=root)
        elif looks_like_fs_mutation_intent(intent):
            console.print("Could not parse filesystem action. Try examples: copy A to B, move A to B, rename A to B, make a folder called X.")
            return True

    if plan is None:
        if looks_like_fs_mutation_intent(intent):
            console.print(Panel.fit("No valid filesystem changes were planned.", title="Planned Changes", border_style="yellow"))
            return True
        return False

    registry = load_agent_rule_registry(root)
    rule_decision = before_filesystem_mutation_plan_or_execute(
        plan=plan,
        cwd=Path.cwd(),
        workspace_root=root,
        rule_registry=registry,
    )
    if rule_decision.blocked:
        message = rule_decision.message or "Operation blocked by loaded agent rules."
        message = block_message_from_decision(message, rule_decision.policy_decision)
        render_fs_rule_block(
            console=console,
            goal=plan.goal or intent,
            message=message,
            next_step_hint="Adjust the target path or request, then try again.",
        )
        return True

    if not plan.ops:
        title, summary, details, next_step_hint = _empty_fs_plan_feedback(plan)
        render_fs_cannot_proceed(
            console=console,
            goal=plan.goal or intent,
            title=title,
            summary=summary,
            details=details,
            next_step_hint=next_step_hint,
        )
        return True

    policy_notes = policy_notes_from_decision(rule_decision.policy_decision)
    render_fs_plan(console=console, plan=plan, policy_notes=policy_notes)

    requires_confirmation = plan.requires_confirmation or rule_decision.requires_confirmation
    if not requires_confirmation:
        return True

    if prompt_reader is None:
        console.print("Skipping apply: confirmation input is unavailable.")
        return True

    overwrite_needed = False
    for op in plan.ops:
        if op.action in {"copy", "move", "rename"} and op.dst:
            destination = (Path.cwd() / op.dst).resolve()
            if destination.exists():
                overwrite_needed = True
                break

    if overwrite_needed:
        _debug("overwrite protection required=True")
        try:
            overwrite_confirmation = prompt_reader("Destination exists. Type OVERWRITE to replace, or anything else to cancel: ").strip()
        except EOFError:
            overwrite_confirmation = ""
        except KeyboardInterrupt:
            overwrite_confirmation = ""
        if _normalized_confirmation_token(overwrite_confirmation) != "OVERWRITE":
            console.print(Panel.fit("Cancelled. Existing files were not overwritten.", title="Apply Cancelled", border_style="yellow"))
            return True

    excess_ops = len(plan.ops) > MAX_OPS
    if excess_ops:
        _debug(f"operation limit exceeded count={len(plan.ops)}")
        try:
            limit_confirmation = prompt_reader(
                f"Plan exceeds {MAX_OPS} operations. Type PROCEED to continue, or anything else to cancel: "
            ).strip()
        except EOFError:
            limit_confirmation = ""
        except KeyboardInterrupt:
            limit_confirmation = ""
        if _normalized_confirmation_token(limit_confirmation) != "PROCEED":
            console.print(Panel.fit("Cancelled. Large plan was not applied.", title="Apply Cancelled", border_style="yellow"))
            return True

    try:
        confirmation = prompt_reader("Type YES to apply, or anything else to cancel: ").strip()
    except EOFError:
        confirmation = ""
    except KeyboardInterrupt:
        confirmation = ""

    if _normalized_confirmation_token(confirmation) != "YES":
        console.print(Panel.fit("Cancelled. No filesystem changes were applied.", title="Apply Cancelled", border_style="yellow"))
        return True

    with busy(get_status_message("fs"), console=console):
        result = apply_fs_plan(
            plan=plan,
            cwd=Path.cwd(),
            workspace_root=root,
            allow_overwrite=overwrite_needed,
            allow_excess_ops=excess_ops,
        )
    render_fs_apply_result(console=console, result=result)
    return True


if __name__ == "__main__":
    app()
