from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from snappy_putty.skills import discover_skills, match_skills, validate_skill_path


def _write_skill(root: Path, name: str = "git-commit-helper", *, description: str | None = None, body: str | None = None) -> Path:
    skill_dir = root / ".snappy" / "skills" / name
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "examples.md").write_text("# Examples\n", encoding="utf-8")
    (skill_dir / "scripts" / "validate_diff.py").write_text("raise SystemExit('should not run')\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "description: "
                + (
                    description
                    or "Helps generate clear git commit messages. Use when the user asks to write or improve a commit message."
                ),
                "x-snappy:",
                "  risk: low",
                "  tools:",
                "    - git.diff",
                "  requires_confirmation: false",
                "---",
                "",
                body
                or "\n".join(
                    [
                        "# Git Commit Helper",
                        "",
                        "## Workflow",
                        "",
                        "Draft a concise commit message from staged changes.",
                    ]
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return skill_dir


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    env["SNAPPY_AGENT_MODE"] = "active"
    env.pop("OPENAI_API_KEY", None)
    return env


def test_valid_skill_loads_with_snappy_metadata_and_scripts_are_not_executed(tmp_path: Path) -> None:
    _write_skill(tmp_path)

    registry = discover_skills(tmp_path)

    assert registry.errors == []
    assert [skill.metadata.name for skill in registry.skills] == ["git-commit-helper"]
    assert registry.skills[0].metadata.snappy["risk"] == "low"
    assert registry.skills[0].scripts
    assert any(issue.code == "scripts_present" for issue in registry.warnings)


def test_validation_reports_missing_skill_md_and_malformed_frontmatter(tmp_path: Path) -> None:
    missing_dir = tmp_path / ".snappy" / "skills" / "missing"
    missing_dir.mkdir(parents=True)
    broken_dir = tmp_path / ".snappy" / "skills" / "broken"
    broken_dir.mkdir()
    (broken_dir / "SKILL.md").write_text("---\nname: broken\n", encoding="utf-8")

    registry = validate_skill_path(tmp_path / ".snappy" / "skills")

    assert {issue.code for issue in registry.errors} == {"missing_skill_md", "malformed_frontmatter"}


def test_validation_reports_required_fields_and_duplicate_names(tmp_path: Path) -> None:
    first = _write_skill(tmp_path, "one", description="Use when the user asks about commits.")
    second = _write_skill(tmp_path, "two", description="Use when the user asks about commits.")
    text = (second / "SKILL.md").read_text(encoding="utf-8").replace("name: two", "name: one")
    (second / "SKILL.md").write_text(text, encoding="utf-8")
    bad_dir = tmp_path / ".snappy" / "skills" / "bad"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("---\nname: bad\n---\n# Bad\n", encoding="utf-8")

    registry = validate_skill_path(tmp_path / ".snappy" / "skills")

    assert "duplicate_name" in {issue.code for issue in registry.errors}
    assert "missing_description" in {issue.code for issue in registry.errors}
    assert (tmp_path / ".snappy" / "skills" / "one" / "SKILL.md").is_file()
    assert first.is_dir()


def test_matching_is_bounded_deterministic_and_includes_reasons(tmp_path: Path) -> None:
    _write_skill(tmp_path, "git-commit-helper")
    _write_skill(tmp_path, "docker-logs", description="Use when the user asks to inspect docker container logs.")

    registry = discover_skills(tmp_path)
    matches = match_skills("help me write a git commit message", registry.skills, limit=1)

    assert len(matches) == 1
    assert matches[0].skill.metadata.name == "git-commit-helper"
    assert matches[0].reasons
    assert match_skills("plan a database migration", registry.skills) == []


def test_matching_uses_skill_description_for_documentation_phrasing_variants(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "doc-coauthoring",
        description=(
            "Guide users through a structured workflow for co-authoring documentation. "
            "Use when the user wants to write documentation, create a spec, draft a proposal, "
            "write up a decision, or co-author structured content."
        ),
    )
    registry = discover_skills(tmp_path)

    examples = [
        "write a doc for this API",
        "write up the API behavior",
        "create a spec for this nodejs api",
        "draft documentation for the routes",
    ]

    for goal in examples:
        matches = match_skills(goal, registry.skills)
        assert matches, goal
        assert matches[0].skill.metadata.name == "doc-coauthoring"
        assert matches[0].reasons


def test_matching_handles_long_skill_bodies_without_exhaustive_fuzzy_scan(tmp_path: Path) -> None:
    body = "\n".join(f"## Section {index}\n" + "documentation workflow " * 80 for index in range(80))
    _write_skill(
        tmp_path,
        "long-doc-coauthoring",
        description="Use when the user wants to create a spec, write documentation, or draft structured technical content.",
        body=body,
    )
    registry = discover_skills(tmp_path)

    matches = match_skills("help me create a spec for this nodejs api", registry.skills)

    assert matches
    assert matches[0].skill.metadata.name == "long-doc-coauthoring"


def test_matching_respects_skill_authored_negative_indicators(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "doc-coauthoring",
        description=(
            "Guide users through a structured workflow for co-authoring documentation. "
            "Use when the user wants to write documentation, create a spec, draft a proposal, "
            "write up a decision, or co-author structured content."
        ),
    )
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    text = text.replace(
        "  requires_confirmation: false\n",
        "  requires_confirmation: false\n"
        "  negative_indicators:\n"
        "    - write code\n"
        "    - implement endpoint\n",
    )
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")

    registry = discover_skills(tmp_path)

    assert match_skills("write code for a new API endpoint", registry.skills) == []


def test_cli_skills_list_inspect_and_validate(tmp_path: Path) -> None:
    _write_skill(tmp_path)

    listed = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "skills"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    inspected = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "skills", "inspect", "git-commit-helper"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    validated = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "skills", "validate"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert listed.returncode == 0
    assert "git-commit-helper" in listed.stdout
    assert inspected.returncode == 0
    assert "Scripts (non-executable resources)" in inspected.stdout
    assert validated.returncode == 0
    assert "scripts_present" in validated.stdout


def test_cli_skills_list_shows_migration_hint_for_folders_missing_skill_md(tmp_path: Path) -> None:
    (tmp_path / ".snappy" / "skills" / "old-layout").mkdir(parents=True)

    listed = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "skills"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert listed.returncode == 0
    assert "No skills loaded." in listed.stdout
    assert (
        "Run snappy skills validate .snappy/skills for details, or create .snappy/skills/<name>/SKILL.md."
        in listed.stdout
    )


def test_skill_metadata_is_stored_in_active_plan(tmp_path: Path) -> None:
    _write_skill(tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "cli.py").write_text("print('demo')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "ask", "help me write a commit message for my staged changes"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert proc.returncode == 0
    session = json.loads((tmp_path / ".snappy" / "memory" / "session.json").read_text(encoding="utf-8"))
    skill_selection = session["current_plan"]["context_selection"]["skill_selection"]
    assert skill_selection["matched"][0]["name"] == "git-commit-helper"
    assert "Matched skills" in proc.stdout
