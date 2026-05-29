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
    assert "Code Review Report" in rendered
    assert "Findings" in rendered
    assert "current workspace snapshot, not a line-by-line MR diff" in rendered
    assert "_Displayed in the terminal only. No files were created or changed._" in rendered
    assert "No files were changed." in rendered
    assert "do not claim files were changed or commands were run" in prompt
    assert all(path in request.files_considered for path in output.files_referenced)


def test_unknown_skill_output_kind_warns_and_falls_back_to_task_intent(tmp_path: Path) -> None:
    _write_review_skill(tmp_path, output_kind="astral_report")
    registry = discover_skills(tmp_path)

    kind, warnings = output_kind_for_request("code_review", ["codeguardian-review"], registry.skills)

    assert kind == "code_review_report"
    assert warnings == ["Unknown skill output kind ignored: astral_report"]


def test_documentation_and_frontend_outputs_render_polished_sections(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"dev":"vite"}}\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    snapshot = inspect_project(tmp_path)
    registry = discover_skills(tmp_path)

    docs_route = route_task("Write README documentation for this project.", registry.skills, snapshot=snapshot)
    docs_plan = build_grounded_plan(
        "Write README documentation for this project.",
        snapshot,
        skill_matches=route_to_skill_matches(docs_route, registry.skills),
        skill_route=docs_route,
    )
    docs_rendered = render_skill_output(generate_skill_output(build_skill_output_request(plan=docs_plan, skills=registry.skills), registry.skills))

    frontend_route = route_task("Build a frontend interface for this application.", registry.skills, snapshot=snapshot)
    frontend_plan = build_grounded_plan(
        "Build a frontend interface for this application.",
        snapshot,
        skill_matches=route_to_skill_matches(frontend_route, registry.skills),
        skill_route=frontend_route,
    )
    frontend_rendered = render_skill_output(generate_skill_output(build_skill_output_request(plan=frontend_plan, skills=registry.skills), registry.skills))

    for heading in ["Documentation Draft", "Overview", "Setup", "Usage", "Project Structure", "Examples", "Documentation Gaps"]:
        assert heading in docs_rendered
    for heading in ["Frontend Design Brief", "UI Direction", "Screens / Components", "API Integration Points", "Suggested File Structure", "Accessibility Notes", "Implementation Sequence"]:
        assert heading in frontend_rendered
    assert "No files were changed." in docs_rendered
    assert "No files were changed." in frontend_rendered
