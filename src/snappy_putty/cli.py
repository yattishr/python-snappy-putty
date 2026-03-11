from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Callable, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from snappy_putty.agent import AgentRunResult, plan_with_agent
from snappy_putty.context import collect_context
from snappy_putty.fs_ops import MAX_OPS, apply_fs_plan, looks_like_fs_mutation_intent, parse_incomplete_fs_intent, plan_fs_intent
from snappy_putty.fs_models import FsPlan
from snappy_putty.render import (
    render_agent_output,
    render_agent_parse_error,
    render_directory_listing,
    render_doctor_report,
    render_fs_apply_result,
    render_fs_plan,
)
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
    ROUTE_SAFE_INSPECT,
    classify_input,
)
from snappy_putty.session import SessionState
from snappy_putty.status import busy, get_status_message

app = typer.Typer(help="Snappy PuTTy CLI", invoke_without_command=True)
console = Console()
RESERVED_CONTROL_ROUTES = {
    ROUTE_BUILTIN_HELP,
    ROUTE_BUILTIN_DOCTOR,
    ROUTE_BUILTIN_STATUS,
    ROUTE_BUILTIN_AFTER,
    ROUTE_BUILTIN_CANCEL,
    ROUTE_BUILTIN_EXIT,
}


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
            "",
            "[bold]Quick commands[/bold]",
            "- doctor",
            "- explain <command>",
            "- after",
            "- status",
            "- cancel",
            "- help",
            "- exit / quit",
            "",
            "[bold]Try[/bold]",
            '- "give me a file listing"',
            '- "give me a file listing for src"',
            '- "deploy this to google cloud"',
            "",
            f"[bold]CWD[/bold]: {snapshot.cwd}",
            f"[bold]Tools[/bold]: {tools}",
        ]
    )
    console.print(Panel(content, title="Welcome", border_style="bright_blue"))


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
            if session is None:
                line = input("snappy [ask]> ")
            else:
                line = session.prompt("snappy [ask]> ")
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        text = line.strip()
        if not text:
            continue

        decision = classify_input(text)
        route = decision.route
        _debug(f"raw user input={text!r}")
        _debug(f"classified route={route}")

        if state.awaiting_confirmation and text.upper() in {"YES", "NO"}:
            _consume_confirmation_response(response=text, state=state, workspace_root=workspace_root)
            continue

        if state.pending_question and route not in RESERVED_CONTROL_ROUTES:
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
            if state.active_goal:
                state.last_cancelled_goal = state.active_goal
            state.clear_pending()
            state.active_goal = None
            state.last_route = route
            state.last_result = "Cancelled active task state."
            console.print("Cleared pending question/plan state.")
            continue
        if route == ROUTE_BUILTIN_HELP:
            print_repl_cheatsheet()
            continue
        if route == ROUTE_BUILTIN_DOCTOR:
            doctor(verbose=False)
            continue
        if route == ROUTE_EXPLAIN:
            command = decision.payload.get("command", "").strip()
            if not command:
                console.print("Usage: explain <command>")
                continue
            result = handle_explain(command=command)
            state.active_goal = command
            state.last_route = route
            state.last_result = result.output.goal
            state.pending_plan = result.output.plan
            state.pending_question = result.output.question
            state.awaiting_confirmation = False
            state.pending_context = {"type": "ask_followup", "base_intent": command} if result.output.question else {}
            continue

        if route == ROUTE_FS_MUTATION:
            _handle_fs_intent_repl(
                intent=decision.payload.get("intent", text),
                workspace_root=workspace_root,
                state=state,
            )
            continue

        if route not in {ROUTE_SAFE_INSPECT, ROUTE_ASK}:
            continue

        current_intent = decision.payload.get("intent", text)
        result = handle_ask(intent=current_intent)
        state.active_goal = current_intent
        state.last_route = route
        state.last_result = result.output.goal
        state.pending_plan = result.output.plan
        state.pending_question = result.output.question
        state.awaiting_confirmation = False
        state.pending_context = {"type": "ask_followup", "base_intent": current_intent} if result.output.question else {}


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
    if route == ROUTE_FS_MUTATION:
        _handle_fs_intent(
            intent=decision.payload.get("intent", intent),
            prompt_reader=lambda prompt: input(prompt),
            workspace_root=Path.cwd().resolve(),
        )
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
    state.awaiting_confirmation = True
    state.pending_context = {
        "type": "fs_confirmation",
        "stage": stage,
        "workspace_root": str(workspace_root),
        "allow_overwrite": allow_overwrite,
        "allow_excess_ops": allow_excess_ops,
        "excess_ops": excess_ops,
    }


def _consume_confirmation_response(response: str, state: SessionState, workspace_root: Path) -> None:
    value = response.strip().upper()
    if value not in {"YES", "NO"}:
        return
    if value == "NO":
        state.clear_pending()
        state.last_result = "Cancelled pending action."
        console.print(Panel.fit("Cancelled. No pending action was applied.", title="Apply Cancelled", border_style="yellow"))
        return

    context = state.pending_context
    if context.get("type") != "fs_confirmation":
        state.clear_pending()
        state.last_result = "Confirmation received, but no actionable pending state remained."
        return
    if not isinstance(state.pending_plan, FsPlan):
        state.clear_pending()
        state.last_result = "Confirmation received, but no plan was available."
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
            console.print(f"Plan exceeds {MAX_OPS} operations. Type YES to continue, or NO to cancel.")
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
        console.print("Type YES to apply, or NO to cancel.")
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
        console.print("Type YES to apply, or NO to cancel.")
        return

    with busy(get_status_message("fs"), console=console):
        result = apply_fs_plan(
            plan=state.pending_plan,
            cwd=Path.cwd(),
            workspace_root=root,
            allow_overwrite=allow_overwrite,
            allow_excess_ops=allow_excess_ops,
        )
    render_fs_apply_result(console=console, result=result)
    state.last_result = f"Applied {sum(1 for item in result.results if item.status == 'applied')} filesystem operation(s)."
    state.last_completed_goal = state.active_goal
    state.active_goal = None
    state.clear_pending()


def _consume_pending_question_answer(answer: str, state: SessionState) -> None:
    question_context = dict(state.pending_context)
    if question_context.get("type") == "fs_destination":
        action = str(question_context.get("action", "copy"))
        src = str(question_context.get("src", "")).strip()
        root = Path(str(question_context.get("workspace_root", Path.cwd()))).resolve()
        state.pending_question = None
        state.pending_context = {}
        _handle_fs_intent_repl(intent=f"{action} {src} to {answer.strip()}", workspace_root=root, state=state)
        return

    base_intent = str(question_context.get("base_intent") or state.active_goal or "").strip()
    state.pending_question = None
    state.pending_context = {}
    followup_intent = f"{base_intent} for {answer.strip()}" if base_intent else answer.strip()
    result = handle_ask(intent=followup_intent)
    state.active_goal = followup_intent
    state.last_route = ROUTE_ASK
    state.last_result = result.output.goal
    state.pending_plan = result.output.plan
    state.pending_question = result.output.question
    state.awaiting_confirmation = False
    if result.output.question:
        state.pending_context = {"type": "ask_followup", "base_intent": base_intent or followup_intent}
    else:
        state.pending_context = {}


def _handle_after(state: SessionState) -> None:
    if state.pending_question:
        console.print(f"Pending question: {state.pending_question}")
        return
    if state.awaiting_confirmation:
        console.print("Pending confirmation: type YES to continue or NO to cancel.")
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
    console.print("No active task.")


def _handle_status(state: SessionState) -> None:
    active_goal = state.active_goal or "(none)"
    last_route = state.last_route or "(none)"
    pending_question = state.pending_question or "(none)"
    if isinstance(state.pending_plan, FsPlan):
        pending_plan = f"filesystem plan with {len(state.pending_plan.ops)} op(s)"
    elif isinstance(state.pending_plan, list):
        pending_plan = f"agent plan with {len(state.pending_plan)} step(s)"
    else:
        pending_plan = "(none)"
    awaiting = "yes" if state.awaiting_confirmation else "no"
    last_completed_goal = state.last_completed_goal or "(none)"
    last_cancelled_goal = state.last_cancelled_goal or "(none)"
    lines = [
        f"Active goal: {active_goal}",
        f"Last route: {last_route}",
        f"Pending question: {pending_question}",
        f"Pending plan: {pending_plan}",
        f"Awaiting confirmation: {awaiting}",
        f"Last completed goal: {last_completed_goal}",
        f"Last cancelled goal: {last_cancelled_goal}",
    ]
    console.print(Panel.fit("\n".join(lines), title="Session Status", border_style="bright_blue"))


def _handle_fs_intent_repl(intent: str, workspace_root: Path, state: SessionState) -> bool:
    root = workspace_root.resolve()
    _debug(f"raw fs intent={intent!r}")
    plan = plan_fs_intent(intent=intent, cwd=Path.cwd(), workspace_root=root)
    state.active_goal = intent
    state.last_route = ROUTE_FS_MUTATION

    if plan is None:
        partial = parse_incomplete_fs_intent(intent)
        if partial is not None:
            action, src = partial
            state.pending_question = "destination path>"
            state.pending_plan = None
            state.awaiting_confirmation = False
            state.pending_context = {"type": "fs_destination", "action": action, "src": src, "workspace_root": str(root)}
            state.last_result = "Awaiting destination path."
            console.print("destination path>")
            return True
        if looks_like_fs_mutation_intent(intent):
            console.print("Could not parse filesystem action. Try examples: copy A to B, move A to B, rename A to B, make a folder called X.")
            state.last_result = "Failed to parse filesystem action."
            return True
        return False

    render_fs_plan(console=console, plan=plan)
    state.pending_plan = plan
    state.pending_question = None
    if not plan.requires_confirmation:
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
        console.print("Destination exists. Type YES to overwrite, or NO to cancel.")
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
        console.print(f"Plan exceeds {MAX_OPS} operations. Type YES to continue, or NO to cancel.")
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
    console.print("Type YES to apply, or NO to cancel.")
    state.last_result = "Awaiting apply confirmation."
    return True


def _prompt_reader(session) -> Callable[[str], str]:
    if session is None:
        return lambda prompt: input(prompt)
    return lambda prompt: session.prompt(prompt)


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

    render_fs_plan(console=console, plan=plan)
    if not plan.requires_confirmation:
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
        if overwrite_confirmation != "OVERWRITE":
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
        if limit_confirmation != "PROCEED":
            console.print(Panel.fit("Cancelled. Large plan was not applied.", title="Apply Cancelled", border_style="yellow"))
            return True

    try:
        confirmation = prompt_reader("Type YES to apply, or anything else to cancel: ").strip()
    except EOFError:
        confirmation = ""
    except KeyboardInterrupt:
        confirmation = ""

    if confirmation != "YES":
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
