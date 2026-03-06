from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from snappy_putty.agent import AgentRunResult, plan_with_agent
from snappy_putty.context import collect_context
from snappy_putty.fs_ops import apply_fs_plan, looks_like_fs_mutation_intent, parse_incomplete_fs_intent, plan_fs_intent
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
    ROUTE_BUILTIN_DOCTOR,
    ROUTE_BUILTIN_EXIT,
    ROUTE_BUILTIN_HELP,
    ROUTE_EXPLAIN,
    ROUTE_FS_MUTATION,
    ROUTE_SAFE_INSPECT,
    classify_input,
)
from snappy_putty.status import busy, get_status_message

app = typer.Typer(help="Snappy PuTTy CLI", invoke_without_command=True)
console = Console()


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
    session = None
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
        if route == ROUTE_BUILTIN_EXIT:
            break
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
            handle_explain(command=command)
            continue

        if route == ROUTE_FS_MUTATION:
            _handle_fs_intent(intent=decision.payload.get("intent", text), prompt_reader=_prompt_reader(session))
            continue

        if route not in {ROUTE_SAFE_INSPECT, ROUTE_ASK}:
            continue

        result = handle_ask(intent=decision.payload.get("intent", text))
        question = result.output.question.lower() if result.output.question else ""
        if "directory" in question and session is not None:
            followup = session.prompt("path> ").strip()
            if followup:
                handle_ask(intent=f"{text} for {followup}")
        elif "directory" in question and session is None:
            followup = input("path> ").strip()
            if followup:
                handle_ask(intent=f"{text} for {followup}")


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

    if route == ROUTE_BUILTIN_HELP:
        print_repl_cheatsheet()
        return
    if route == ROUTE_BUILTIN_DOCTOR:
        doctor(verbose=False)
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
        _handle_fs_intent(intent=decision.payload.get("intent", intent), prompt_reader=lambda prompt: input(prompt))
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


def _prompt_reader(session) -> Callable[[str], str]:
    if session is None:
        return lambda prompt: input(prompt)
    return lambda prompt: session.prompt(prompt)


def _handle_fs_intent(intent: str, prompt_reader: Callable[[str], str] | None) -> bool:
    plan = plan_fs_intent(intent=intent, cwd=Path.cwd())
    if plan is None:
        partial = parse_incomplete_fs_intent(intent)
        if partial is not None:
            action, src = partial
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
            plan = plan_fs_intent(intent=f"{action} {src} to {destination}", cwd=Path.cwd())
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
        result = apply_fs_plan(plan=plan, cwd=Path.cwd())
    render_fs_apply_result(console=console, result=result)
    return True


if __name__ == "__main__":
    app()
