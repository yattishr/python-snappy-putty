from __future__ import annotations

from pathlib import Path

from snappy_putty.skills import discover_skills
from snappy_putty.workflow_orchestrator import build_workflow_plan, skill_workflow_metadata


def _write_skill(
    root: Path,
    name: str,
    *,
    accepts: list[str] | None = None,
    produces: list[str] | None = None,
    preferred_position: str | None = None,
) -> None:
    skill_dir = root / ".snappy" / "skills" / name
    skill_dir.mkdir(parents=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: Use when the user asks for {name.replace('-', ' ')} help.",
    ]
    if accepts:
        lines.append("accepts:")
        lines.extend(f"  - {item}" for item in accepts)
    if produces:
        lines.append("produces:")
        lines.extend(f"  - {item}" for item in produces)
    if preferred_position:
        lines.append(f"preferred_position: {preferred_position}")
    lines.extend(["---", "", "# Skill", "", "Use as planning guidance only."])
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def test_single_skill_does_not_require_workflow(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-coauthoring", produces=["pr_summary"], preferred_position="synthesis")
    skill = discover_skills(tmp_path).skills[0]

    plan = build_workflow_plan("write a PR summary", [skill])

    assert plan.workflow_required is False
    assert plan.status == "not_required"


def test_review_then_pr_summary_creates_ordered_workflow(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "doc-coauthoring",
        accepts=["project_context", "review_report"],
        produces=["markdown_document", "pr_summary"],
        preferred_position="synthesis",
    )
    _write_skill(
        tmp_path,
        "codeguardian-review",
        accepts=["project_context", "source_files"],
        produces=["review_report"],
        preferred_position="analysis",
    )
    skills = discover_skills(tmp_path).skills

    plan = build_workflow_plan("help me review this API and generate a PR summary", skills)

    assert plan.workflow_required is True
    assert [step.skill_name for step in plan.steps] == ["codeguardian-review", "doc-coauthoring"]
    assert plan.steps[0].output_artifact == "review_report"
    assert "review_report" in plan.steps[1].input_artifacts
    assert plan.steps[1].depends_on == ["step_1"]
    assert plan.final_output_kind == "pr_summary"
    assert plan.status == "awaiting_confirmation"


def test_disabled_skills_are_not_included_when_not_passed_to_orchestrator(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-coauthoring", produces=["pr_summary"], preferred_position="synthesis")
    _write_skill(tmp_path, "codeguardian-review", produces=["review_report"], preferred_position="analysis")
    skills = [skill for skill in discover_skills(tmp_path).skills if skill.metadata.name != "codeguardian-review"]

    plan = build_workflow_plan("help me review this API and generate a PR summary", skills)

    assert "codeguardian-review" not in [step.skill_name for step in plan.steps]
    assert plan.workflow_required is False


def test_unknown_metadata_defaults_safely(tmp_path: Path) -> None:
    _write_skill(tmp_path, "plain-one")
    skill = discover_skills(tmp_path).skills[0]

    metadata = skill_workflow_metadata(skill)

    assert metadata.accepts == ["project_context"]
    assert metadata.produces == ["general_skill_report"]
    assert metadata.preferred_position == "general"


def test_unrelated_multiple_skills_fall_back_to_flat_report(tmp_path: Path) -> None:
    _write_skill(tmp_path, "plain-one")
    _write_skill(tmp_path, "plain-two")
    skills = discover_skills(tmp_path).skills

    plan = build_workflow_plan("help me with this project", skills)

    assert plan.workflow_required is False
    assert plan.final_output_kind == "general_skill_report"


def test_known_review_and_doc_skills_infer_workflow_without_metadata(tmp_path: Path) -> None:
    _write_skill(tmp_path, "codeguardian-review")
    _write_skill(tmp_path, "doc-coauthoring")
    skills = discover_skills(tmp_path).skills

    plan = build_workflow_plan("help me review this API and generate a PR summary", skills)

    assert plan.workflow_required is True
    assert [step.skill_name for step in plan.steps] == ["codeguardian-review", "doc-coauthoring"]
    assert plan.steps[0].output_artifact == "review_report"
    assert "review_report" in plan.steps[1].input_artifacts
    assert plan.final_output_kind == "pr_summary"
