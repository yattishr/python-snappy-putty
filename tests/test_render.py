from pathlib import Path
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.models import AgentOutput, PlanStep, Snippet, SuggestedCommand
from snappy_putty.render import render_agent_output, single_line_command


def _sample_output(command_text: str) -> AgentOutput:
    return AgentOutput(
        goal="Sample goal",
        assumptions=["assume local context"],
        question=None,
        plan=[PlanStep(step=1, action="Do thing", why="Because")],
        commands=[SuggestedCommand(cmd=command_text, explain="sample", risk="low")],
        warnings=["sample warning"],
        snippets=[Snippet(title="Dockerfile", language="dockerfile", content="FROM python:3.10\nRUN echo hi")],
    )


def test_render_agent_output_displays_snippet_panel() -> None:
    console = Console(record=True, width=120)
    render_agent_output(console, _sample_output("ls -la"), title="ask")
    output = console.export_text()
    assert "Snippet: Dockerfile" in output
    assert "FROM python:3.10" in output


def test_commands_are_single_line_for_table() -> None:
    multiline = "echo one\necho two"
    assert "\n" not in single_line_command(multiline)

    console = Console(record=True, width=120)
    render_agent_output(console, _sample_output(multiline), title="ask")
    output = console.export_text()
    assert "echo one echo two" in output
    assert "echo one\necho two" not in output
