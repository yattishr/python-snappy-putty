from pathlib import Path
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.fs_models import FsPlan, PlannedOp
from snappy_putty.models import AgentOutput, PlanStep, Snippet, SuggestedCommand
from snappy_putty.render import render_agent_output, render_fs_plan, render_fs_rule_block, single_line_command


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


def test_render_fs_plan_displays_goal_policy_plan_and_warnings_in_order() -> None:
    console = Console(record=True, width=120)
    plan = FsPlan(
        goal="copy README.md README-copy.md",
        cwd="/tmp/demo",
        ops=[PlannedOp(op_id="op1", action="copy", src="README.md", dst="README-copy.md", notes=[], risk="low")],
        warnings=["Existing destination will require confirmation."],
        requires_confirmation=True,
    )

    render_fs_plan(
        console,
        plan,
        policy_notes=["Loaded rules require confirmation before filesystem changes are applied."],
    )

    output = console.export_text()
    goal_index = output.index("Goal")
    policy_index = output.index("Policy")
    changes_index = output.index("Planned Changes")
    warnings_index = output.index("Plan Warnings")
    assert goal_index < policy_index < changes_index < warnings_index


def test_render_fs_rule_block_displays_goal_then_policy_block_then_next_step() -> None:
    console = Console(record=True, width=120)

    render_fs_rule_block(
        console,
        goal="copy README.md to /",
        message="Operation blocked by rule: protect_project_root\n\nThe requested filesystem mutation targets a protected path.",
        next_step_hint="Adjust the target path or request, then try again.",
    )

    output = console.export_text()
    goal_index = output.index("Goal")
    block_index = output.index("Policy Block")
    next_step_index = output.index("Next Step")
    assert goal_index < block_index < next_step_index
