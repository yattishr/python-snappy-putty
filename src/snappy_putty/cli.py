from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from snappy_putty.agent import AgentRunResult, plan_with_agent
from snappy_putty.context import collect_context
from snappy_putty.render import render_agent_output, render_agent_parse_error, render_directory_listing, render_doctor_report

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

        history_path = str(Path.home() / ".snappy_putty_history")
        session = PromptSession(history=FileHistory(history_path))
    except ImportError:
        session = None

    print_repl_cheatsheet()

    while True:
        try:
            if session is None:
                line = input("snappy_putty [ask]> ")
            else:
                line = session.prompt("snappy_putty [ask]> ")
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        text = line.strip()
        if not text:
            continue
        if text in {"exit", "quit"}:
            break
        if text == "help":
            print_repl_cheatsheet()
            continue
        if text == "doctor":
            doctor(verbose=False)
            continue
        if text.startswith("explain"):
            command = text[len("explain") :].strip()
            if not command:
                console.print("Usage: explain <command>")
                continue
            handle_explain(command=command)
            continue
        result = handle_ask(intent=text)
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
    handle_ask(intent)


def handle_ask(intent: str) -> AgentRunResult:
    """Run ask flow and render output."""
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


if __name__ == "__main__":
    app()
