from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from snappy_putty.context import ContextSnapshot
from snappy_putty.fs_models import FsApplyResult, FsPlan
from snappy_putty.models import AgentOutput


def render_agent_parse_error(
    console: Console,
    parse_error: str,
    raw_model_text: str | None,
) -> None:
    body = f"[bold]Parsing failed:[/bold] {parse_error}"
    if raw_model_text:
        body = f"{body}\n\n[bold]Raw model text:[/bold]\n{raw_model_text}"
    console.print(Panel(body, title="Agent Parse Error", border_style="red"))


def single_line_command(command: str) -> str:
    return " ".join(command.splitlines()).strip()


def render_directory_listing(console: Console, content: str) -> None:
    console.print(Panel(content, title="Directory Listing", border_style="bright_green"))


def render_git_read(console: Console, *, title: str, content: str, ok: bool = True) -> None:
    border = "bright_blue" if ok else "red"
    console.print(Panel(content, title=title, border_style=border))


def render_dir_listing(console: Console, listing_text: str) -> None:
    render_directory_listing(console=console, content=listing_text)


def render_fs_plan(console: Console, plan: FsPlan) -> None:
    ops_table = Table(title="Planned Changes")
    ops_table.add_column("Op", style="cyan")
    ops_table.add_column("Action", style="green")
    ops_table.add_column("From", style="magenta")
    ops_table.add_column("To", style="blue")
    ops_table.add_column("Risk", style="yellow")
    for op in plan.ops:
        ops_table.add_row(op.op_id, op.action, op.src or "-", op.dst or "-", op.risk.upper())

    if not plan.ops:
        console.print(Panel.fit("No filesystem changes planned.", title="Planned Changes", border_style="yellow"))
    else:
        console.print(ops_table)

    warning_text = "\n".join(f"- {item}" for item in plan.warnings) or "- none"
    console.print(Panel(Markdown(warning_text), title="Plan Warnings", border_style="yellow"))


def render_fs_apply_result(console: Console, result: FsApplyResult) -> None:
    table = Table(title="Applied Changes")
    table.add_column("Op", style="cyan")
    table.add_column("Action", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Message", style="blue")
    for item in result.results:
        table.add_row(item.op_id, item.action, item.status.upper(), item.message)
    console.print(table)
    warning_text = "\n".join(f"- {item}" for item in result.warnings) or "- none"
    console.print(Panel(Markdown(warning_text), title="Apply Warnings", border_style="yellow"))


def render_agent_output(console: Console, output: AgentOutput, title: str) -> None:
    assumptions = "\n".join(f"- {item}" for item in output.assumptions) or "- none"
    warnings = "\n".join(f"- {item}" for item in output.warnings) or "- none"

    console.print(Panel.fit(output.goal, title="Goal", border_style="blue", subtitle=title))
    console.print(Panel(Markdown(assumptions), title="Assumptions", border_style="cyan"))

    if output.question:
        console.print(Panel.fit(output.question, title="Question", border_style="magenta"))

    plan_text = "\n".join(f"{item.step}. {item.action} - {item.why}" for item in output.plan) or "No plan provided."
    console.print(Panel(Markdown(plan_text), title="Plan", border_style="green"))

    for snippet in output.snippets:
        syntax = Syntax(snippet.content, snippet.language or "text", word_wrap=True)
        console.print(Panel(syntax, title=f"Snippet: {snippet.title}", border_style="bright_blue"))

    cmd_table = Table(title="Commands")
    cmd_table.add_column("Command", style="cyan")
    cmd_table.add_column("Risk", style="magenta")
    cmd_table.add_column("Explain", style="green")
    for item in output.commands:
        cmd_table.add_row(single_line_command(item.cmd), item.risk.upper(), item.explain)
    console.print(cmd_table)

    console.print(Panel(Markdown(warnings), title="Warnings", border_style="yellow"))


def render_doctor_report(console: Console, snapshot: ContextSnapshot, verbose: bool = False) -> None:
    system = Table(title="System Snapshot")
    system.add_column("Field", style="cyan")
    system.add_column("Value", style="green")
    system.add_row("OS", snapshot.os_name)
    system.add_row("Platform", snapshot.platform_info)
    system.add_row("CWD", snapshot.cwd)
    system.add_row("Git Repo", "yes" if snapshot.in_git_repo else "no")
    if snapshot.in_git_repo:
        system.add_row("Git Branch", snapshot.git_branch or "unknown")
        system.add_row("Git State", snapshot.git_state or "unknown")

    tools = Table(title="Tool Detection")
    tools.add_column("Tool", style="cyan")
    tools.add_column("Detected", style="green")
    for tool, exists in snapshot.tools.items():
        tools.add_row(tool, "yes" if exists else "no")

    projects = Table(title="Project Types")
    projects.add_column("Marker", style="cyan")
    if snapshot.project_types:
        for marker in snapshot.project_types:
            projects.add_row(marker)
    else:
        projects.add_row("none detected")

    console.print(Panel.fit("Context snapshot report", title="doctor", border_style="green"))
    console.print(system)
    console.print(tools)
    console.print(projects)

    if verbose:
        console.print(
            Panel.fit(
                "Verbose mode: report includes git metadata, tool detection, and project markers.",
                border_style="yellow",
            )
        )
