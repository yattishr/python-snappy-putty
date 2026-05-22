from __future__ import annotations

from pathlib import Path

from snappy_putty.active_planner import build_grounded_plan
from snappy_putty.project_inspector import inspect_project
from snappy_putty.skill_outputs import (
    build_skill_output_prompt,
    build_skill_output_request,
    generate_skill_output,
    output_kind_for_request,
    render_skill_output,
)
from snappy_putty.skills import discover_skills
from snappy_putty.task_router import route_task, route_to_skill_matches


def _write_review_skill(root: Path, *, output_kind: str = "code_review_report") -> None:
    skill_dir = root / ".snappy" / "skills" / "codeguardian-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: codeguardian-review",
                "description: Use when the user asks for code review feedback on current changes.",
                "x-snappy:",
                "  task_intents:",
                "    - code_review",
                "  output_kinds:",
                f"    - {output_kind}",
                "---",
                "",
                "# CodeGuardian",
                "",
                "Use grounded review evidence only.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_code_review_skill_output_is_grounded_and_non_mutating(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    _write_review_skill(tmp_path)
    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)
    route = route_task("Review my latest changes and give MR feedback.", registry.skills, snapshot=snapshot)
    plan = build_grounded_plan(
        "Review my latest changes and give MR feedback.",
        snapshot,
        skill_matches=route_to_skill_matches(route, registry.skills),
        skill_route=route,
    )

    request = build_skill_output_request(plan=plan, skills=registry.skills)
    output = generate_skill_output(request, registry.skills)
    rendered = render_skill_output(output)
    prompt = build_skill_output_prompt(request, output.output_kind)

    assert output.output_kind == "code_review_report"
    assert output.mutations_applied is False
    assert output.files_referenced == plan.files_inspected
    assert "## Findings" in rendered
    assert "current workspace snapshot, not a line-by-line MR diff" in rendered
    assert "_No files were changed._" in rendered
    assert "do not claim files were changed or commands were run" in prompt
    assert all(path in request.files_considered for path in output.files_referenced)


def test_unknown_skill_output_kind_warns_and_falls_back_to_task_intent(tmp_path: Path) -> None:
    _write_review_skill(tmp_path, output_kind="astral_report")
    registry = discover_skills(tmp_path)

    kind, warnings = output_kind_for_request("code_review", ["codeguardian-review"], registry.skills)

    assert kind == "code_review_report"
    assert warnings == ["Unknown skill output kind ignored: astral_report"]
