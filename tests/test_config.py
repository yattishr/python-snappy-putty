from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from snappy_putty.config import init_project_config, load_effective_config, load_project_config
from snappy_putty.project_inspector import inspect_project
from snappy_putty.rule_hooks import before_filesystem_mutation_plan_or_execute
from snappy_putty.agent_discovery import AgentRule, AgentRuleRegistry
from snappy_putty.fs_ops import plan_fs_intent
from snappy_putty.skills import discover_skills, match_skills
from snappy_putty import active_planner


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    env.pop("OPENAI_API_KEY", None)
    return env


def _write_config(root: Path, text: str) -> None:
    path = root / ".snappy" / "snappy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_skill(root: Path, name: str, description: str = "Use when the user asks for project help.") -> None:
    skill_dir = root / ".snappy" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_missing_config_returns_defaults(tmp_path: Path) -> None:
    config = load_project_config(tmp_path)

    assert config.source == "defaults"
    assert config.agent.mode == "off"
    assert config.planning.allow_project_extensions is True
    assert config.skills.enabled == []
    assert config.rules.protected_paths[:2] == [".env", ".git/"]


def test_valid_config_loads_and_merges_protected_paths(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        """
version: 1
agent:
  name: Repo Agent
  mode: active
  description: Local helper.
planning:
  allow_project_extensions: false
  max_context_files: 4
skills:
  enabled:
    - doc-coauthoring
  disabled:
    - brand-guidelines
rules:
  protected_paths:
    - package-lock.json
logging:
  level: debug
""".strip()
        + "\n",
    )

    config = load_project_config(tmp_path)

    assert config.agent.name == "Repo Agent"
    assert config.agent.mode == "active"
    assert config.planning.allow_project_extensions is False
    assert config.planning.max_context_files == 4
    assert config.skills.enabled == ["doc-coauthoring"]
    assert config.skills.disabled == ["brand-guidelines"]
    assert config.logging.level == "debug"
    assert config.rules.protected_paths == [".env", ".git/", "package-lock.json"]


def test_malformed_config_produces_issue_and_safe_fallback(tmp_path: Path) -> None:
    _write_config(tmp_path, "version: 1\n  bad: true\n")

    config = load_project_config(tmp_path)

    assert config.agent.mode == "off"
    assert any(issue.code == "malformed_config" for issue in config.issues)


def test_invalid_values_fall_back_safely(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        """
version: 1
unknown: value
agent:
  mode: passive
logging:
  level: loud
""".strip()
        + "\n",
    )

    config = load_project_config(tmp_path)

    assert config.agent.mode == "off"
    assert config.logging.level == "info"
    assert {issue.code for issue in config.issues} >= {
        "unknown_top_level_field",
        "invalid_agent_mode",
        "invalid_logging_level",
    }


def test_env_disables_project_config_and_agent_mode_overrides(tmp_path: Path) -> None:
    _write_config(tmp_path, "version: 1\nagent:\n  mode: active\n")

    disabled = load_effective_config(tmp_path, env={"SNAPPY_DISABLE_PROJECT_CONFIG": "1"})
    overridden = load_effective_config(tmp_path, env={"SNAPPY_AGENT_MODE": "off"})

    assert disabled.agent.mode == "off"
    assert disabled.source.startswith("defaults")
    assert overridden.agent.mode == "off"


def test_config_cli_show_init_and_validate(tmp_path: Path) -> None:
    init = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "config", "init"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    show = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "config"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    validate = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "config", "validate"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    second_init = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "config", "init"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert init.returncode == 0
    assert (tmp_path / ".snappy" / "snappy.yaml").is_file()
    assert "Agent mode: off" in show.stdout
    assert validate.returncode == 0
    assert "Config validation passed." in validate.stdout
    assert ".snappy/snappy.yaml already exists and is valid. No changes made." in second_init.stdout


def test_config_validate_reports_malformed_config(tmp_path: Path) -> None:
    _write_config(tmp_path, "version: 1\n  bad: true\n")

    result = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "config", "validate"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 1
    assert "malformed_config" in result.stdout


def test_skill_config_filters_allowlist_and_disabled_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "frontend-design", "Use when building frontend interfaces.")
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")
    _write_skill(tmp_path, "brand-guidelines", "Use when applying brand guidelines.")
    _write_config(
        tmp_path,
        "version: 1\nskills:\n  enabled:\n    - frontend-design\n    - brand-guidelines\n  disabled:\n    - brand-guidelines\n",
    )

    config = load_project_config(tmp_path)
    registry = discover_skills(tmp_path, config=config)

    assert [skill.metadata.name for skill in registry.skills] == ["frontend-design"]
    assert any(issue.code == "skill_disabled_by_config" for issue in registry.issues)
    assert any(issue.code == "skill_not_enabled_by_config" for issue in registry.issues)


def test_init_project_config_creates_modern_config_with_detected_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "frontend-design", "Use when building frontend interfaces.")
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")

    result = init_project_config(tmp_path)
    config = load_project_config(tmp_path)

    assert result.created is True
    assert (tmp_path / ".snappy" / "snappy.yaml").is_file()
    assert config.agent.name == tmp_path.name
    assert config.agent.mode == "off"
    assert config.skills.enabled == ["doc-coauthoring", "frontend-design"]
    assert "Enabled all detected skills by default." in result.message


def test_init_project_config_no_skills_means_empty_enabled(tmp_path: Path) -> None:
    result = init_project_config(tmp_path)
    config = load_project_config(tmp_path)

    assert config.skills.enabled == []
    assert "No skills detected. skills.enabled is empty." in result.message


def test_configured_empty_enabled_loads_no_skills_when_config_exists(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")
    _write_config(tmp_path, "version: 1\nskills:\n  enabled: []\n  disabled: []\n")

    config = load_project_config(tmp_path)
    registry = discover_skills(tmp_path, config=config)

    assert registry.skills == []
    assert any(issue.code == "skill_not_enabled_by_config" for issue in registry.issues)


def test_missing_config_still_loads_valid_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")

    registry = discover_skills(tmp_path, config=load_project_config(tmp_path))

    assert [skill.metadata.name for skill in registry.skills] == ["doc-coauthoring"]


def test_init_project_config_preserves_existing_skill_folders(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")
    extra = tmp_path / ".snappy" / "skills" / "draft-skill"
    extra.mkdir()
    (tmp_path / ".snappy" / "memory").mkdir()
    (tmp_path / ".snappy" / "logs").mkdir()

    init_project_config(tmp_path)

    assert (tmp_path / ".snappy" / "skills" / "doc-coauthoring" / "SKILL.md").is_file()
    assert extra.is_dir()
    assert (tmp_path / ".snappy" / "memory").is_dir()
    assert (tmp_path / ".snappy" / "logs").is_dir()


def test_init_project_config_migrates_legacy_flat_config_with_backup(tmp_path: Path) -> None:
    _write_skill(tmp_path, "frontend-design", "Use when building frontend interfaces.")
    _write_config(
        tmp_path,
        "name: vanilla-nodejs-rest-api\n"
        "version: 1\n"
        "mode: supervised\n"
        "confirmations: true\n"
        "dry_run: false\n"
        "skills: []\n"
        "rules: []\n"
        "memory: true\n",
    )

    result = init_project_config(tmp_path)
    config = load_project_config(tmp_path)
    text = (tmp_path / ".snappy" / "snappy.yaml").read_text(encoding="utf-8")

    assert result.migrated is True
    assert result.backup_path is not None and result.backup_path.is_file()
    assert config.agent.name == "vanilla-nodejs-rest-api"
    assert config.agent.mode == "off"
    assert config.rules.confirmation_required is True
    assert config.memory.enabled is True
    assert config.skills.enabled == ["frontend-design"]
    assert "dry_run" not in text
    assert any("dry_run" in warning for warning in result.warnings)


def test_init_project_config_does_not_overwrite_valid_modern_config(tmp_path: Path) -> None:
    original = "version: 1\nagent:\n  name: Custom Agent\n  mode: active\nskills:\n  enabled: []\n  disabled: []\n"
    _write_config(tmp_path, original)

    result = init_project_config(tmp_path)

    assert result.changed is False
    assert (tmp_path / ".snappy" / "snappy.yaml").read_text(encoding="utf-8") == original
    assert "already exists and is valid" in result.message


def test_init_project_config_enables_detected_skills_for_empty_modern_config(tmp_path: Path) -> None:
    _write_skill(tmp_path, "frontend-design", "Use when building frontend interfaces.")
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")
    _write_config(
        tmp_path,
        "version: 1\n"
        "agent:\n"
        "  name: Custom Agent\n"
        "  mode: off\n"
        "skills:\n"
        "  enabled: []\n"
        "  disabled: []\n",
    )

    result = init_project_config(tmp_path)
    config = load_project_config(tmp_path)

    assert result.changed is True
    assert result.repaired is True
    assert result.backup_path is not None and result.backup_path.is_file()
    assert config.agent.name == "Custom Agent"
    assert config.skills.enabled == ["doc-coauthoring", "frontend-design"]
    assert "Detected 2 skills and enabled them." in result.message


def test_init_project_config_preserves_intentional_disabled_list(tmp_path: Path) -> None:
    _write_skill(tmp_path, "frontend-design", "Use when building frontend interfaces.")
    original = "version: 1\nskills:\n  enabled: []\n  disabled:\n    - frontend-design\n"
    _write_config(tmp_path, original)

    result = init_project_config(tmp_path)

    assert result.changed is False
    assert (tmp_path / ".snappy" / "snappy.yaml").read_text(encoding="utf-8") == original


def test_disabled_skill_does_not_influence_project_relevance(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("require('http')\n", encoding="utf-8")
    _write_skill(tmp_path, "doc-coauthoring", "Use when creating specs or documentation.")
    _write_config(tmp_path, "version: 1\nskills:\n  disabled:\n    - doc-coauthoring\n")
    config = load_project_config(tmp_path)
    registry = discover_skills(tmp_path, config=config)
    snapshot = inspect_project(tmp_path)
    matches = match_skills("help me create a spec for this nodejs api", registry.skills)

    relationship = active_planner.assess_project_relationship(
        "help me create a spec for this nodejs api",
        snapshot,
        skill_matches=matches,
        config=config,
    )

    assert matches == []
    assert relationship.matched_skills == []


def test_disabling_project_extensions_makes_extension_request_conservative(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node server.js"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text("require('http')\n", encoding="utf-8")
    _write_config(tmp_path, "version: 1\nplanning:\n  allow_project_extensions: false\n")
    config = load_project_config(tmp_path)
    snapshot = inspect_project(tmp_path)

    extension = active_planner.assess_project_relationship(
        "help me build a frontend dashboard for this API",
        snapshot,
        config=config,
    )
    direct = active_planner.assess_project_relationship("help me improve this api", snapshot, config=config)

    assert not extension.is_project_related
    assert extension.reason == "project_extensions_disabled_by_config"
    assert direct.is_project_related


def test_config_protected_paths_block_mutation_without_removing_builtins(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "copy.json").write_text("{}\n", encoding="utf-8")
    _write_config(tmp_path, "version: 1\nrules:\n  confirmation_required: false\n  protected_paths:\n    - package-lock.json\n")
    config = load_project_config(tmp_path)
    plan = plan_fs_intent("copy copy.json package-lock.json", cwd=tmp_path, workspace_root=tmp_path)
    assert plan is not None
    registry = AgentRuleRegistry(
        rules=[
            AgentRule("protect root", "protect_project_root", "", supported_for_enforcement=True),
            AgentRule("confirm", "require_confirm", "", supported_for_enforcement=True),
        ]
    )

    decision = before_filesystem_mutation_plan_or_execute(
        plan=plan,
        cwd=tmp_path,
        workspace_root=tmp_path,
        rule_registry=registry,
        protected_paths=config.rules.protected_paths,
    )

    assert decision.blocked
    assert ".env" in config.rules.protected_paths
    assert any(issue.code == "confirmation_required_soft_preference" for issue in config.issues)
