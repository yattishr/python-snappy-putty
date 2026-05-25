from __future__ import annotations

from pathlib import Path

from snappy_putty.config import load_project_config
from snappy_putty.project_inspector import inspect_project
from snappy_putty.skills import discover_skills
from snappy_putty.task_router import classify_task_intent, route_task, route_to_skill_matches


def _write_skill(
    root: Path,
    name: str,
    description: str,
    *,
    task_intents: list[str] | None = None,
    relationships: list[str] | None = None,
    targets: list[str] | None = None,
    indicators: list[str] | None = None,
) -> None:
    skill_dir = root / ".snappy" / "skills" / name
    skill_dir.mkdir(parents=True)
    lines = ["---", f"name: {name}", f"description: {description}"]
    if task_intents or relationships or targets or indicators:
        lines.append("x-snappy:")
        if task_intents:
            lines.append("  task_intents:")
            lines.extend(f"    - {item}" for item in task_intents)
        if relationships:
            lines.append("  project_relationships:")
            lines.extend(f"    - {item}" for item in relationships)
        if targets:
            lines.append("  extension_targets:")
            lines.extend(f"    - {item}" for item in targets)
        if indicators:
            lines.append("  indicators:")
            lines.extend(f"    - {item}" for item in indicators)
    lines.extend(["---", "", "# Skill", "", "Use as planning guidance only."])
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def _write_common_project(root: Path) -> None:
    (root / "package.json").write_text('{"scripts":{"test":"vitest","start":"vite"}}\n', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.tsx").write_text("export function App() { return null }\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")


def _write_common_skills(root: Path) -> None:
    _write_skill(
        root,
        "codeguardian-review",
        "Use this skill when the user asks to review code changes, inspect diffs, generate merge request feedback, identify risks, or produce PR/MR-style review notes.",
        task_intents=["code_review"],
        relationships=["direct_project_work"],
        indicators=["code review", "review changes", "inspect diff", "MR feedback", "PR feedback"],
    )
    _write_skill(
        root,
        "frontend-design",
        "Use this skill when building frontend interfaces, dashboards, React components, UI polish, and HTML/CSS layouts.",
        task_intents=["frontend_build"],
        relationships=["project_extension"],
        targets=["typescript"],
        indicators=["frontend", "dashboard", "interface"],
    )
    _write_skill(
        root,
        "doc-coauthoring",
        "Use this skill when the user wants to write documentation, create README material, draft usage guides, or document APIs.",
        task_intents=["documentation"],
        relationships=["direct_project_work", "project_extension"],
        indicators=["write docs", "create README", "usage guide"],
    )
    _write_skill(
        root,
        "docker-support",
        "Use this skill when the user asks to add Docker, create a Dockerfile, configure deployment, or set up CI/CD.",
        task_intents=["deployment"],
        relationships=["project_extension"],
        indicators=["add Docker", "create Dockerfile", "CI/CD"],
    )


def test_code_review_request_routes_to_codeguardian(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)
    snapshot = inspect_project(tmp_path)

    route = route_task("Review my latest changes and give me MR-style feedback.", registry.skills, snapshot=snapshot)

    assert route.task_intent.label == "code_review"
    assert route.selected_skills == ["codeguardian-review"]
    assert route.candidates[0].skill_name == "codeguardian-review"


def test_frontend_and_documentation_requests_do_not_route_to_codeguardian(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)
    snapshot = inspect_project(tmp_path)

    frontend = route_task("Build a frontend interface for this application.", registry.skills, snapshot=snapshot)
    docs = route_task("Write README documentation for this project.", registry.skills, snapshot=snapshot)

    assert frontend.task_intent.label == "frontend_build"
    assert frontend.selected_skills == ["frontend-design"]
    assert "codeguardian-review" not in frontend.selected_skills
    assert docs.task_intent.label == "documentation"
    assert docs.selected_skills == ["doc-coauthoring"]
    assert "codeguardian-review" not in docs.selected_skills


def test_deployment_request_routes_to_deployment_skill(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Add Docker and CI/CD deployment setup for this app.", registry.skills)

    assert route.task_intent.label == "deployment"
    assert route.selected_skills == ["docker-support"]


def test_unrelated_request_selects_no_project_skill(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Design a Batman poster.", registry.skills)

    assert route.task_intent.label == "unrelated"
    assert route.selected_skills == []


def test_explicit_skill_request_routes_if_enabled(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Use CodeGuardian to review this repo.", registry.skills)

    assert route.selected_skills == ["codeguardian-review"]


def test_disabled_and_allowlist_skills_are_not_selected(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    snappy_dir = tmp_path / ".snappy"
    (snappy_dir / "snappy.yaml").write_text(
        "version: 1\nskills:\n  enabled:\n    - doc-coauthoring\n  disabled:\n    - codeguardian-review\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Review my latest changes and give me PR feedback.", registry.skills, config=config)

    assert route.selected_skills == []
    assert route.disabled_best_match == "codeguardian-review"
    metadata = route.as_metadata()
    assert metadata["disabled_best_match"] == "codeguardian-review"
    assert metadata["disabled_best_match_score"] > 0


def test_disabled_best_match_not_recorded_when_enabled_alternative_selected(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    _write_skill(
        tmp_path,
        "enabled-review-helper",
        "Use this skill when reviewing code changes and writing PR feedback.",
        task_intents=["code_review"],
        relationships=["direct_project_work"],
        indicators=["PR feedback"],
    )
    snappy_dir = tmp_path / ".snappy"
    (snappy_dir / "snappy.yaml").write_text(
        "version: 1\nskills:\n  enabled:\n    - enabled-review-helper\n  disabled:\n    - codeguardian-review\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Review my latest changes and give me PR feedback.", registry.skills, config=config)

    assert route.selected_skills == ["enabled-review-helper"]
    assert route.disabled_best_match is None


def test_description_only_skill_still_routes_without_x_snappy(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_skill(
        tmp_path,
        "plain-doc-helper",
        "Use when the user wants to write documentation, improve docs, create README files, or draft usage guides.",
    )
    registry = discover_skills(tmp_path)

    route = route_task("Improve docs for this project.", registry.skills)

    assert route.task_intent.label == "documentation"
    assert route.selected_skills == ["plain-doc-helper"]


def test_route_converts_to_planner_skill_matches(tmp_path: Path) -> None:
    _write_common_project(tmp_path)
    _write_common_skills(tmp_path)
    registry = discover_skills(tmp_path)

    route = route_task("Create a dashboard UI for this app.", registry.skills)
    matches = route_to_skill_matches(route, registry.skills)

    assert [match.skill.metadata.name for match in matches] == ["frontend-design"]
    assert matches[0].reasons


def test_intent_classifier_marks_unrelated_without_project_context() -> None:
    intent = classify_task_intent("Design a Batman poster.")

    assert intent.label == "unrelated"
