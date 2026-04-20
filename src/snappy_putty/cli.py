from __future__ import annotations

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
from snappy_putty.agent_init import init_agent_project
from snappy_putty.context import collect_context
from snappy_putty.fs_ops import MAX_OPS, apply_fs_plan, looks_like_fs_mutation_intent, parse_incomplete_fs_intent, plan_fs_intent
from snappy_putty.fs_models import FsPlan
from snappy_putty.git_read import execute_git_read, parse_git_read_intent
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
    ROUTE_SAFE_INSPECT,
    ROUTE_UNKNOWN,
    classify_input,
)
from snappy_putty.session import (
    ActiveGoalConflictError,
    ExecutionOperation,
    ExecutionResult,
    InvalidLifecycleTransition,
    LifecycleState,
    SessionState,
)
from snappy_putty.status import busy, get_status_message

app = typer.Typer(help="Snappy PuTTy CLI", invoke_without_command=True)
console = Console()
UNKNOWN_COMMAND_MESSAGE = "I don't recognize that command. Try 'help' to see what I can do."
RESERVED_CONTROL_ROUTES = {
    ROUTE_BUILTIN_HELP,
    ROUTE_BUILTIN_DOCTOR,
    ROUTE_BUILTIN_STATUS,
    ROUTE_BUILTIN_AFTER,
    ROUTE_BUILTIN_CANCEL,
    ROUTE_BUILTIN_EXIT,
}
_AGENT_MODE_PATTERN = re.compile(r"^\s*agent\s+mode(?:\s+(?P<mode>\S+))?\s*$", flags=re.IGNORECASE)


def looks_like_new_command(text: str) -> bool:
    lowered = text.strip().lower()
    command_prefixes = (
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
    return any(lowered.startswith(prefix) for prefix in command_prefixes)


def is_valid_clarification_response(user_input: str, state: SessionState) -> bool:
    raw_text = user_input.strip()
    text = raw_text.lower()
    if text in {"yes", "no"}:
        return True
    if isinstance(state.pending_question, dict):
        question_type = state.pending_question.get("type")
        if question_type == "path":
            return looks_like_path(raw_text)
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


def _clarification_input_is_locked(*, text: str, route: str, state: SessionState) -> bool:
    if state.current_state != LifecycleState.CLARIFICATION:
        return False
    if not state.pending_question:
        return False
    if state.pending_context.get("type") in {"fs_destination", "guided_listing_choice", "guided_listing_custom_path"}:
        if is_valid_clarification_response(text, state):
            return False
        return route not in {ROUTE_GIT_READ}
    if _is_choice_question(state.pending_question):
        return False
    if route in RESERVED_CONTROL_ROUTES or route == ROUTE_BUILTIN_EXIT:
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


def _confirmation_prompt_message(state: SessionState) -> str:
    context = state.pending_context if isinstance(state.pending_context, dict) else {}
    stage = str(context.get("stage", "apply"))
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
        {"label": "passive", "value": "passive"},
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

    question_context = dict(state.pending_context)
    context_type = question_context.get("type")

    if context_type == "fs_destination":
        if isinstance(state.pending_question, dict) and state.pending_question.get("type") == "path":
            return looks_like_path(text)
        return route == ROUTE_ASK

    if context_type == "ask_followup":
        return route == ROUTE_ASK or is_valid_clarification_response(text, state)

    if context_type == "guided_listing_choice":
        if isinstance(state.pending_question, dict):
            return _is_choice_input(text, state.pending_question)
        return True

    if context_type == "guided_listing_custom_path":
        if isinstance(state.pending_question, dict) and state.pending_question.get("type") == "path":
            return looks_like_path(text)
        return True

    return True


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
    state.pending_context = pending_context
    _set_state(state, LifecycleState.CLARIFICATION)


def _record_agent_planning_result(
    state: SessionState,
    *,
    route: str,
    goal: str,
    result: AgentRunResult,
    pending_context: dict[str, object] | None = None,
) -> None:
    _begin_goal(state, goal=goal, route=route)
    _enter_planning(state)
    state.last_result = result.output.goal
    state.pending_plan = result.output.plan
    state.pending_question = result.output.question
    state.awaiting_confirmation = False
    state.pending_context = dict(pending_context or {})
    if result.output.question:
        _set_state(state, LifecycleState.CLARIFICATION)


def _handle_safe_inspect_repl(intent: str, state: SessionState, *, start_new_goal: bool = True) -> bool:
    if _is_listing_request(intent) and _extract_requested_path(intent) is None and not _listing_request_is_ambiguous(intent):
        if start_new_goal:
            _begin_goal(state, goal=intent, route=ROUTE_SAFE_INSPECT)
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
    result = handle_ask(intent=intent)
    if result.output.question:
        state.last_result = result.output.goal
        state.pending_plan = result.output.plan
        state.pending_question = result.output.question
        state.awaiting_confirmation = False
        state.pending_context = {"type": "ask_followup", "base_intent": intent}
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
            "- doctor            Show local planning diagnostics.",
            "- agent             Show the loaded agent summary.",
            "- agent mode        Inspect or change agent runtime mode.",
            "- init              Scaffold a .snappy/ agent directory.",
            "- skills            List loaded .snappy skills.",
            "- rules             List loaded .snappy rules.",
            "- explain <command> Explain a command safely.",
            "- after             Show the next expected input or step.",
            "- status            Show diagnostic session and agent status.",
            "- cancel            Clear pending workflow state.",
            "- help              Show this help panel.",
            "- exit / quit       Leave the interactive shell.",
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
        selected = {"1": "off", "2": "passive", "3": "active"}.get(choice, normalize_agent_mode(choice))
        if selected is None:
            console.print("Invalid mode. Choose: off, passive, active")
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
        console.print("Invalid mode. Choose: off, passive, active")
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


def run_shell() -> None:
    workspace_root = Path.cwd().resolve()
    state = SessionState()
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
            _cancel_active_goal(state, message="Cancelled active task state.")
            console.print("Cleared pending question/plan state.")
            continue
        if route == ROUTE_BUILTIN_HELP:
            print_repl_cheatsheet()
            if state.current_state == LifecycleState.CLARIFICATION and state.pending_question and not _is_choice_question(state.pending_question):
                _render_clarification_followup(state, blocked=False)
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
        if route == ROUTE_EXPLAIN:
            command = decision.payload.get("command", "").strip()
            if not command:
                console.print("Usage: explain <command>")
                continue
            result = handle_explain(command=command)
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
        result = handle_ask(intent=current_intent)
        pending_context = {"type": "ask_followup", "base_intent": current_intent} if result.output.question else {}
        _record_agent_planning_result(state, route=route, goal=current_intent, result=result, pending_context=pending_context)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Start shell when no subcommand is provided."""
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        run_shell()


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
    handle_ask(decision.payload.get("intent", intent))


def handle_ask(intent: str) -> AgentRunResult:
    """Run ask flow and render output."""
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


def handle_explain(command: str) -> AgentRunResult:
    """Run explain flow and render output."""
    with busy(get_status_message("explain"), console=console):
        result = plan_with_agent(mode="explain", user_text=command, snapshot=None)
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
    """List passive skills loaded from .snappy/skills/*.md."""
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
    """List passive rules loaded from .snappy/rules/*.md."""
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
    state.pending_context = {
        "type": "fs_confirmation",
        "stage": stage,
        "workspace_root": str(workspace_root),
        "allow_overwrite": allow_overwrite,
        "allow_excess_ops": allow_excess_ops,
        "excess_ops": excess_ops,
    }
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
    if context.get("type") != "fs_confirmation":
        _fail_active_goal(state, message="Confirmation received, but no actionable pending state remained.")
        return
    if not isinstance(state.pending_plan, FsPlan):
        _fail_active_goal(state, message="Confirmation received, but no plan was available.")
        return

    stage = str(context.get("stage", "apply"))
    allow_overwrite = bool(context.get("allow_overwrite", False))
    allow_excess_ops = bool(context.get("allow_excess_ops", False))
    excess_ops = bool(context.get("excess_ops", False))
    root = Path(str(context.get("workspace_root") or workspace_root)).resolve()

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
    question_context = dict(state.pending_context)
    if question_context.get("type") == "guided_listing_choice":
        selected = answer.strip()
        if selected == "custom":
            _record_clarification(
                state,
                question={"type": "path", "prompt": "Enter custom path:"},
                pending_context={"type": "guided_listing_custom_path", "base_intent": str(question_context.get("base_intent", ""))},
            )
            state.last_result = "Awaiting custom listing path."
            return
        state.pending_question = None
        state.pending_context = {}
        _enter_planning(state)
        _handle_safe_inspect_repl(
            intent=f'give me a file listing for "{selected}"',
            state=state,
            start_new_goal=False,
        )
        return

    if question_context.get("type") == "guided_listing_custom_path":
        state.pending_question = None
        state.pending_context = {}
        _enter_planning(state)
        _handle_safe_inspect_repl(
            intent=f'give me a file listing for "{answer.strip()}"',
            state=state,
            start_new_goal=False,
        )
        return

    if question_context.get("type") == "fs_destination":
        action = str(question_context.get("action", "copy"))
        src = str(question_context.get("src", "")).strip()
        root = Path(str(question_context.get("workspace_root", Path.cwd()))).resolve()
        state.pending_question = None
        state.pending_context = {}
        _enter_planning(state)
        _handle_fs_intent_repl(
            intent=f"{action} {src} to {answer.strip()}",
            workspace_root=root,
            state=state,
            start_new_goal=False,
        )
        return

    base_intent = str(question_context.get("base_intent") or state.active_goal or "").strip()
    state.pending_question = None
    state.pending_context = {}
    followup_intent = f"{base_intent} for {answer.strip()}" if base_intent else answer.strip()
    state.active_goal = followup_intent
    state.last_route = ROUTE_ASK
    state.error_message = None
    _enter_planning(state)
    result = handle_ask(intent=followup_intent)
    state.last_result = result.output.goal
    state.pending_plan = result.output.plan
    state.pending_question = result.output.question
    state.awaiting_confirmation = False
    if result.output.question:
        state.pending_context = {"type": "ask_followup", "base_intent": base_intent or followup_intent}
        _set_state(state, LifecycleState.CLARIFICATION)
    else:
        state.pending_context = {}


def _handle_after(state: SessionState) -> None:
    if state.pending_question:
        console.print(f"Pending question: {_pending_question_message(state.pending_question)}")
        return
    if state.awaiting_confirmation:
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
    current_state = state.current_state.value
    active_goal = state.active_goal or "(none)"
    last_route = state.last_route or "(none)"
    pending_question = _pending_question_message(state.pending_question)
    if isinstance(state.pending_plan, FsPlan):
        pending_plan = f"filesystem plan with {len(state.pending_plan.ops)} op(s)"
    elif isinstance(state.pending_plan, list):
        pending_plan = f"agent plan with {len(state.pending_plan)} step(s)"
    else:
        pending_plan = "(none)"
    awaiting = "yes" if state.awaiting_confirmation else "no"
    last_completed_goal = state.last_completed_goal or "(none)"
    last_cancelled_goal = state.last_cancelled_goal or "(none)"
    last_failed_goal = state.last_failed_goal or "(none)"
    last_blocked_goal = state.last_blocked_goal or "(none)"
    error_message = state.error_message or "(none)"
    control_state = _current_control_state(state)
    lines = [
        f"Current state: {current_state}",
        f"Active goal: {active_goal}",
        f"Last route: {last_route}",
        f"Pending question: {pending_question}",
        f"Pending plan: {pending_plan}",
        f"Awaiting confirmation: {awaiting}",
        f"Current control state: {control_state}",
        f"Last completed goal: {last_completed_goal}",
        f"Last cancelled goal: {last_cancelled_goal}",
        f"Last failed goal: {last_failed_goal}",
        f"Last blocked goal: {last_blocked_goal}",
        f"Error message: {error_message}",
    ]
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

    requires_confirmation = plan.requires_confirmation or rule_decision.requires_confirmation
    if not requires_confirmation:
        state.awaiting_confirmation = False
        state.pending_context = {}
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
