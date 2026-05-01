from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.agent_fixtures import load_agent_fixture
from snappy_putty.agent_discovery import (
    AgentManifest,
    classify_rule_tier,
    discover_agent_project,
    get_agent_mode,
    get_agent_mode_source,
    load_agent_memory,
    load_agent_project_config,
    load_agent_rule_registry,
    load_agent_skill_registry,
    resolve_agent_mode,
)


def test_discover_agent_project_without_snappy_dir(tmp_path: Path) -> None:
    result = discover_agent_project(tmp_path)

    assert result.agent_found is False
    assert result.agent_root is None
    assert result.manifest_path is None


def test_discover_agent_project_with_snappy_dir_without_manifest(monkeypatch, tmp_path: Path) -> None:
    agent_root = load_agent_fixture("missing_manifest", tmp_path)
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    result = discover_agent_project(tmp_path)

    assert result.agent_found is True
    assert result.agent_root == agent_root.resolve()
    assert result.manifest_path is None


def test_discover_agent_project_with_manifest(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    manifest_path = agent_root / "snappy.yaml"
    manifest_path.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    result = discover_agent_project(tmp_path)

    assert result.agent_found is True
    assert result.agent_root == agent_root.resolve()
    assert result.manifest_path == manifest_path.resolve()


def test_load_agent_project_config_parses_valid_manifest(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    manifest_path = agent_root / "snappy.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "name: Snappy Dev Agent",
                "version: 1",
                "mode: supervised",
                "confirmations: true",
                "dry_run: false",
                "skills:",
                "  - git",
                "  - deploy",
                "rules: [safe, review]",
                "memory: true",
                "future_flag: ignore-me",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    result = load_agent_project_config(tmp_path)

    assert result.warning is None
    assert result.manifest == AgentManifest(
        name="Snappy Dev Agent",
        version=1,
        mode="supervised",
        confirmations=True,
        dry_run=False,
        skills=["git", "deploy"],
        rules=["safe", "review"],
        memory=True,
    )


def test_load_agent_project_config_allows_missing_optional_fields(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Minimal Agent\n", encoding="utf-8")

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    result = load_agent_project_config(tmp_path)

    assert result.warning is None
    assert result.manifest == AgentManifest(name="Minimal Agent")


def test_load_agent_project_config_reports_malformed_yaml(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Snappy: Dev Agent\n", encoding="utf-8")

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    result = load_agent_project_config(tmp_path)

    assert result.manifest is None
    assert result.warning is not None
    assert "Invalid agent manifest:" in result.warning


def test_load_agent_project_config_reports_wrong_field_types(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("version: one\nskills: true\n", encoding="utf-8")

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    result = load_agent_project_config(tmp_path)

    assert result.manifest is None
    assert result.warning is not None
    assert "Invalid agent manifest:" in result.warning


def test_load_agent_skill_registry_parses_valid_skill_file(monkeypatch, tmp_path: Path) -> None:
    skills_dir = tmp_path / ".snappy" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "docker.md").write_text(
        "\n".join(
            [
                "# Skill: Docker Logs",
                "Description:",
                "Inspect running container logs safely.",
                "Intent examples:",
                "- show docker logs for api",
                "- inspect logs for worker container",
                "Risk: low",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_skill_registry(tmp_path)

    assert registry.warnings == []
    assert [skill.name for skill in registry.skills] == ["Docker Logs"]
    assert registry.skills[0].intent_examples == [
        "show docker logs for api",
        "inspect logs for worker container",
    ]


def test_load_agent_skill_registry_skips_invalid_skill_files(monkeypatch, tmp_path: Path) -> None:
    skills_dir = tmp_path / ".snappy" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "broken.md").write_text(
        "# Skill: Broken Skill\nDescription:\nMissing sections only.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_skill_registry(tmp_path)

    assert registry.skills == []
    assert len(registry.warnings) == 1
    assert (
        registry.warnings[0]
        == "Warning: skipped .snappy/skills/broken.md because Intent examples section was missing or malformed."
    )


def test_load_agent_skill_registry_reports_missing_or_malformed_risk_value(monkeypatch, tmp_path: Path) -> None:
    skills_dir = tmp_path / ".snappy" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "copy.md").write_text(
        "\n".join(
            [
                "# Skill: copy",
                "Description:",
                "Copy files from one place to another.",
                "Intent examples:",
                "- copy README.md to docs/",
                "Risk:",
                "LOW",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_skill_registry(tmp_path)

    assert registry.skills == []
    assert registry.warnings == [
        "Warning: skipped .snappy/skills/copy.md because Risk value was missing or malformed."
    ]


def test_load_agent_rule_registry_parses_valid_rules(monkeypatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "safety.md").write_text(
        "# Rule: Confirm Destructive Actions\nAlways ask for confirmation before destructive commands.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_rule_registry(tmp_path)

    assert registry.warnings == []
    assert [rule.name for rule in registry.rules] == ["Confirm Destructive Actions"]
    assert registry.rules[0].body == "Always ask for confirmation before destructive commands."
    assert registry.rules[0].identifier == "confirm_destructive_actions"
    assert registry.rules[0].supported_for_enforcement is False


def test_load_agent_rule_registry_marks_supported_rule_enforceable(monkeypatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_rule_registry(tmp_path)

    assert registry.warnings == []
    assert len(registry.rules) == 1
    assert registry.rules[0].identifier == "require_confirm"
    assert registry.rules[0].supported_for_enforcement is True
    assert registry.rules[0].tier == "confirm"
    assert registry.is_active("require_confirm") is True
    assert [rule.identifier for rule in registry.enforceable_rules] == ["require_confirm"]


def test_load_agent_rule_registry_keeps_unsupported_rule_informational(monkeypatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "team_policy.md").write_text(
        "# Rule: Team Policy\nHuman-readable guidance only.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_rule_registry(tmp_path)

    assert registry.warnings == []
    assert len(registry.rules) == 1
    assert registry.rules[0].identifier == "team_policy"
    assert registry.rules[0].supported_for_enforcement is False
    assert registry.rules[0].tier == "info"
    assert registry.is_active("team_policy") is False
    assert [rule.identifier for rule in registry.informational_rules] == ["team_policy"]


def test_classify_rule_tier_marks_block_rule_correctly() -> None:
    assert classify_rule_tier("protect_project_root", supported_for_enforcement=True) == "block"


def test_classify_rule_tier_marks_confirm_rule_correctly() -> None:
    assert classify_rule_tier("require_confirm", supported_for_enforcement=True) == "confirm"


def test_classify_rule_tier_marks_info_rule_correctly() -> None:
    assert classify_rule_tier("custom_note", supported_for_enforcement=False) == "info"


def test_load_agent_rule_registry_allows_empty_rules_directory(monkeypatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_rule_registry(tmp_path)

    assert registry.rules == []
    assert registry.warnings == []


def test_load_agent_rule_registry_skips_malformed_markdown(monkeypatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "broken.md").write_text("Rule without heading\n", encoding="utf-8")

    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    registry = load_agent_rule_registry(tmp_path)

    assert registry.rules == []
    assert len(registry.warnings) == 1
    assert "Skipped invalid rule file broken.md" in registry.warnings[0]


def test_load_agent_memory_without_memory_folder(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    memory = load_agent_memory(tmp_path)

    assert memory.memory_found is False
    assert memory.memory_root is None
    assert memory.session_path is None
    assert memory.session_data is None
    assert memory.warning is None


def test_load_agent_memory_parses_valid_session_json(monkeypatch, tmp_path: Path) -> None:
    memory_dir = tmp_path / ".snappy" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "session.json").write_text(
        '{"last_goal": "inspect logs", "notes": ["safe", "read-only"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    memory = load_agent_memory(tmp_path)

    assert memory.memory_found is True
    assert memory.memory_root == memory_dir
    assert memory.session_path == memory_dir / "session.json"
    assert memory.session_data == {"last_goal": "inspect logs", "notes": ["safe", "read-only"]}
    assert memory.warning is None


def test_load_agent_memory_reports_malformed_session_json(monkeypatch, tmp_path: Path) -> None:
    memory_dir = tmp_path / ".snappy" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "session.json").write_text('{"last_goal": invalid}\n', encoding="utf-8")
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    memory = load_agent_memory(tmp_path)

    assert memory.memory_found is True
    assert memory.session_data is None
    assert memory.warning is not None
    assert "Invalid agent memory session:" in memory.warning


def test_agent_mode_defaults_to_off(monkeypatch) -> None:
    monkeypatch.delenv("SNAPPY_AGENT_MODE", raising=False)

    assert get_agent_mode() == "off"
    assert get_agent_mode_source() == "default"


def test_agent_mode_respects_environment(monkeypatch) -> None:
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    assert resolve_agent_mode() == ("active", "environment")


def test_agent_mode_session_override_beats_environment(monkeypatch) -> None:
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    assert resolve_agent_mode("off") == ("off", "session")


def test_agent_mode_off_ignores_snappy_project(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Hidden Agent\n", encoding="utf-8")
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "off")

    discovery = discover_agent_project(tmp_path)
    config = load_agent_project_config(tmp_path)

    assert discovery.agent_found is False
    assert config.manifest is None
    assert config.warning is None


def test_agent_mode_active_loads_agent_metadata(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Visible Agent\nmode: supervised\n", encoding="utf-8")
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    discovery = discover_agent_project(tmp_path)
    config = load_agent_project_config(tmp_path)

    assert discovery.agent_found is True
    assert config.manifest == AgentManifest(name="Visible Agent", mode="supervised")


def test_agent_mode_active_loads_agent_metadata_for_active_mode(monkeypatch, tmp_path: Path) -> None:
    agent_root = tmp_path / ".snappy"
    agent_root.mkdir()
    (agent_root / "snappy.yaml").write_text("name: Active Agent\n", encoding="utf-8")
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")

    config = load_agent_project_config(tmp_path)

    assert config.manifest == AgentManifest(name="Active Agent")
