from __future__ import annotations

import ast
from datetime import datetime
from dataclasses import dataclass, field, replace
import os
from pathlib import Path
import shutil
from typing import Any, Mapping


CONFIG_RELATIVE_PATH = Path(".snappy") / "snappy.yaml"
VALID_AGENT_MODES = {"off", "active"}
VALID_LOGGING_LEVELS = {"debug", "info", "warning", "error"}
TOP_LEVEL_KEYS = {"version", "agent", "planning", "skills", "rules", "memory", "logging"}
BUILT_IN_PROTECTED_PATHS = (".env", ".git/")


@dataclass(frozen=True)
class ConfigIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class AgentConfig:
    name: str = "Snappy"
    mode: str = "off"
    description: str = ""


@dataclass(frozen=True)
class PlanningConfig:
    allow_project_extensions: bool = True
    prefer_small_steps: bool = True
    inspect_before_mutation: bool = True
    max_context_files: int | None = None


@dataclass(frozen=True)
class SkillsConfig:
    enabled: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RulesConfig:
    confirmation_required: bool = True
    allow_file_writes: bool = True
    allow_shell_commands: bool = False
    protected_paths: list[str] = field(default_factory=lambda: list(BUILT_IN_PROTECTED_PATHS))


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool = True
    snapshot_on_inspect: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "info"
    trace_enabled: bool = True


@dataclass(frozen=True)
class SnappyConfig:
    version: int = 1
    source: str = "defaults"
    path: Path | None = None
    agent: AgentConfig = field(default_factory=AgentConfig)
    planning: PlanningConfig = field(default_factory=PlanningConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    issues: list[ConfigIssue] = field(default_factory=list)


@dataclass(frozen=True)
class InitConfigResult:
    changed: bool
    created: bool
    migrated: bool
    repaired: bool
    path: Path
    backup_path: Path | None
    detected_skills: list[str]
    warnings: list[str]
    message: str


@dataclass(frozen=True)
class SkillConfigUpdateResult:
    changed: bool
    path: Path
    skill_name: str
    enabled: list[str]
    disabled: list[str]
    message: str


def default_config(*, source: str = "defaults", path: Path | None = None, issues: list[ConfigIssue] | None = None) -> SnappyConfig:
    return SnappyConfig(source=source, path=path, issues=list(issues or []))


def config_path(root: Path) -> Path:
    return root.resolve() / CONFIG_RELATIVE_PATH


def load_project_config(root: Path) -> SnappyConfig:
    path = config_path(root)
    if not path.is_file():
        return default_config()
    try:
        payload = _parse_yaml_mapping(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return default_config(
            source=str(path),
            path=path,
            issues=[ConfigIssue("error", "malformed_config", f"Could not parse .snappy/snappy.yaml: {exc}")],
        )
    return _coerce_config(payload, path=path, root=root.resolve())


def load_effective_config(root: Path, env: Mapping[str, str] | None = None) -> SnappyConfig:
    active_env = env if env is not None else os.environ
    if active_env.get("SNAPPY_DISABLE_PROJECT_CONFIG") == "1":
        config = default_config(
            source="defaults (project config disabled)",
            issues=[ConfigIssue("warning", "project_config_disabled", "SNAPPY_DISABLE_PROJECT_CONFIG=1 ignored project config.")],
        )
    else:
        config = load_project_config(root)
    return _apply_env_overrides(config, active_env)


def validate_config(config: SnappyConfig) -> list[ConfigIssue]:
    return list(config.issues)


def enable_project_skill(root: Path, skill_name: str) -> SkillConfigUpdateResult:
    config = _load_writable_project_config(root)
    name = skill_name.strip()
    if name not in config.skills.disabled:
        raise ValueError(f"Skill is not disabled in config: {name}")
    enabled = _dedupe([*config.skills.enabled, name])
    disabled = [item for item in config.skills.disabled if item != name]
    path = _write_skill_lists(config, root=root, enabled=enabled, disabled=disabled)
    return SkillConfigUpdateResult(
        changed=True,
        path=path,
        skill_name=name,
        enabled=enabled,
        disabled=disabled,
        message=f"Enabled skill: {name}",
    )


def disable_project_skill(root: Path, skill_name: str) -> SkillConfigUpdateResult:
    config = _load_writable_project_config(root)
    name = skill_name.strip()
    if name not in config.skills.enabled:
        raise ValueError(f"Skill is not enabled in config: {name}")
    enabled = [item for item in config.skills.enabled if item != name]
    disabled = _dedupe([*config.skills.disabled, name])
    path = _write_skill_lists(config, root=root, enabled=enabled, disabled=disabled)
    return SkillConfigUpdateResult(
        changed=True,
        path=path,
        skill_name=name,
        enabled=enabled,
        disabled=disabled,
        message=f"Disabled skill: {name}",
    )


def _load_writable_project_config(root: Path) -> SnappyConfig:
    active_root = root.resolve()
    path = config_path(active_root)
    if not path.is_file():
        raise ValueError("Project config not initialized. Run `snappy config init` first.")
    config = load_project_config(active_root)
    errors = [issue for issue in config.issues if issue.severity == "error"]
    if errors:
        raise ValueError("Project config is invalid. Run `snappy config validate`.")
    return config


def _write_skill_lists(config: SnappyConfig, *, root: Path, enabled: list[str], disabled: list[str]) -> Path:
    active_root = root.resolve()
    path = config.path or config_path(active_root)
    payload = _payload_from_config(config)
    payload["skills"]["enabled"] = sorted(enabled)
    payload["skills"]["disabled"] = sorted(disabled)
    path.write_text(_config_text_from_payload(payload), encoding="utf-8")
    return path


def init_project_config(root: Path, *, migrate: bool = True) -> InitConfigResult:
    root = root.resolve()
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    detected_skills = _detect_valid_skill_names(root)
    warnings: list[str] = []

    if not path.exists():
        path.write_text(starter_config_text(project_name=root.name or "snappy-project", enabled_skills=detected_skills), encoding="utf-8")
        lines = [f"Created {_relative_display(path, root)}"]
        if detected_skills:
            lines.append(f"Detected {len(detected_skills)} skills:")
            lines.extend(f"- {name}" for name in detected_skills)
            lines.append("Enabled all detected skills by default.")
        else:
            lines.append("No skills detected. skills.enabled is empty.")
        return InitConfigResult(True, True, False, False, path, None, detected_skills, warnings, "\n".join(lines))

    try:
        payload = _parse_yaml_mapping(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        backup_path = _write_backup(path)
        path.write_text(starter_config_text(project_name=root.name or "snappy-project", enabled_skills=detected_skills), encoding="utf-8")
        lines = [
            "Detected malformed Snappy config.",
            f"Backup written to {_relative_display(backup_path, root)}",
            "Repaired config to current schema.",
        ]
        if detected_skills:
            lines.append(f"Enabled detected skills: {', '.join(detected_skills)}")
        else:
            lines.append("No skills detected. skills.enabled is empty.")
        return InitConfigResult(True, False, False, True, path, backup_path, detected_skills, warnings, "\n".join(lines))

    if _is_legacy_config(payload):
        if not migrate:
            return InitConfigResult(False, False, False, False, path, None, detected_skills, warnings, "Detected legacy Snappy config. Migration disabled.")
        backup_path = _write_backup(path)
        migrated_payload = _migrate_legacy_payload(payload, root=root, detected_skills=detected_skills, warnings=warnings)
        path.write_text(_config_text_from_payload(migrated_payload), encoding="utf-8")
        lines = [
            "Detected legacy Snappy config.",
            f"Backup written to {_relative_display(backup_path, root)}",
            "Migrated config to current schema.",
        ]
        if detected_skills:
            lines.append(f"Enabled detected skills: {', '.join(detected_skills)}")
        else:
            lines.append("No skills detected. skills.enabled is empty.")
        lines.extend(warnings)
        return InitConfigResult(True, False, True, False, path, backup_path, detected_skills, warnings, "\n".join(lines))

    config = _coerce_config(payload, path=path, root=root)
    errors = [issue for issue in config.issues if issue.severity == "error"]
    if not errors:
        if detected_skills and not config.skills.enabled and not config.skills.disabled:
            backup_path = _write_backup(path)
            payload = _payload_from_config(config)
            payload["skills"]["enabled"] = detected_skills
            path.write_text(_config_text_from_payload(payload), encoding="utf-8")
            lines = [
                f"{_relative_display(path, root)} already exists and is valid.",
                f"Backup written to {_relative_display(backup_path, root)}",
                f"Detected {len(detected_skills)} skills and enabled them.",
            ]
            return InitConfigResult(True, False, False, True, path, backup_path, detected_skills, warnings, "\n".join(lines))
        return InitConfigResult(
            False,
            False,
            False,
            False,
            path,
            None,
            detected_skills,
            warnings,
            f"{_relative_display(path, root)} already exists and is valid. No changes made.",
        )

    backup_path = _write_backup(path)
    path.write_text(starter_config_text(project_name=root.name or "snappy-project", enabled_skills=detected_skills), encoding="utf-8")
    lines = [
        "Detected invalid Snappy config.",
        f"Backup written to {_relative_display(backup_path, root)}",
        "Repaired config to current schema.",
    ]
    if detected_skills:
        lines.append(f"Enabled detected skills: {', '.join(detected_skills)}")
    else:
        lines.append("No skills detected. skills.enabled is empty.")
    return InitConfigResult(True, False, False, True, path, backup_path, detected_skills, warnings, "\n".join(lines))


def starter_config_text(*, project_name: str = "Snappy", enabled_skills: list[str] | None = None) -> str:
    enabled = sorted(enabled_skills or [])
    enabled_text = "[]"
    if enabled:
        enabled_text = "\n" + "\n".join(f"    - {name}" for name in enabled)
    return f"""version: 1

agent:
  name: {project_name}
  mode: off
  description: Project-local Snappy configuration.

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: null

skills:
  enabled: {enabled_text}
  disabled: []

rules:
  confirmation_required: true
  allow_file_writes: true
  allow_shell_commands: false
  protected_paths:
    - .env
    - .git/

memory:
  enabled: true
  snapshot_on_inspect: true

logging:
  level: info
  trace_enabled: true
"""


def _detect_valid_skill_names(root: Path) -> list[str]:
    from snappy_putty.skills import load_skill_registry

    registry = load_skill_registry(root / ".snappy" / "skills")
    return sorted(skill.metadata.name for skill in registry.skills)


def _is_legacy_config(payload: dict[str, Any]) -> bool:
    legacy_keys = {"name", "mode", "confirmations", "dry_run"}
    return bool(legacy_keys & set(payload)) or not isinstance(payload.get("skills", {}), dict) or not isinstance(payload.get("rules", {}), dict)


def _migrate_legacy_payload(payload: dict[str, Any], *, root: Path, detected_skills: list[str], warnings: list[str]) -> dict[str, Any]:
    raw_mode = str(payload.get("mode") or "off").lower()
    mode = raw_mode if raw_mode in {"active", "off"} else "off"
    if "dry_run" in payload:
        warnings.append("warning: unsupported legacy field dry_run was removed.")
    default = _payload_from_config_text(starter_config_text(project_name=root.name or "snappy-project", enabled_skills=detected_skills))
    default["agent"]["name"] = str(payload.get("name") or root.name or "snappy-project")
    default["agent"]["mode"] = mode
    default["rules"]["confirmation_required"] = bool(payload.get("confirmations", True))
    default["memory"]["enabled"] = bool(payload.get("memory", True))
    return default


def _payload_from_config_text(text: str) -> dict[str, Any]:
    return _parse_yaml_mapping(text)


def _payload_from_config(config: SnappyConfig) -> dict[str, Any]:
    return {
        "version": 1,
        "agent": {
            "name": config.agent.name,
            "mode": config.agent.mode,
            "description": config.agent.description,
        },
        "planning": {
            "allow_project_extensions": config.planning.allow_project_extensions,
            "prefer_small_steps": config.planning.prefer_small_steps,
            "inspect_before_mutation": config.planning.inspect_before_mutation,
            "max_context_files": config.planning.max_context_files,
        },
        "skills": {
            "enabled": list(config.skills.enabled),
            "disabled": list(config.skills.disabled),
        },
        "rules": {
            "confirmation_required": config.rules.confirmation_required,
            "allow_file_writes": config.rules.allow_file_writes,
            "allow_shell_commands": config.rules.allow_shell_commands,
            "protected_paths": list(config.rules.protected_paths),
        },
        "memory": {
            "enabled": config.memory.enabled,
            "snapshot_on_inspect": config.memory.snapshot_on_inspect,
        },
        "logging": {
            "level": config.logging.level,
            "trace_enabled": config.logging.trace_enabled,
        },
    }


def _config_text_from_payload(payload: dict[str, Any]) -> str:
    enabled = payload["skills"]["enabled"]
    enabled_text = "[]"
    if enabled:
        enabled_text = "\n" + "\n".join(f"    - {name}" for name in enabled)
    disabled = payload["skills"]["disabled"]
    disabled_text = "[]"
    if disabled:
        disabled_text = "\n" + "\n".join(f"    - {name}" for name in disabled)
    protected = "\n".join(f"    - {item}" for item in payload["rules"]["protected_paths"])
    max_context_files = payload["planning"]["max_context_files"]
    max_context_text = "null" if max_context_files is None else str(max_context_files)
    return f"""version: 1

agent:
  name: {payload["agent"]["name"]}
  mode: {payload["agent"]["mode"]}
  description: {payload["agent"]["description"]}

planning:
  allow_project_extensions: {_yaml_bool(payload["planning"]["allow_project_extensions"])}
  prefer_small_steps: {_yaml_bool(payload["planning"]["prefer_small_steps"])}
  inspect_before_mutation: {_yaml_bool(payload["planning"]["inspect_before_mutation"])}
  max_context_files: {max_context_text}

skills:
  enabled: {enabled_text}
  disabled: {disabled_text}

rules:
  confirmation_required: {_yaml_bool(payload["rules"]["confirmation_required"])}
  allow_file_writes: {_yaml_bool(payload["rules"]["allow_file_writes"])}
  allow_shell_commands: {_yaml_bool(payload["rules"]["allow_shell_commands"])}
  protected_paths:
{protected}

memory:
  enabled: {_yaml_bool(payload["memory"]["enabled"])}
  snapshot_on_inspect: {_yaml_bool(payload["memory"]["snapshot_on_inspect"])}

logging:
  level: {payload["logging"]["level"]}
  trace_enabled: {_yaml_bool(payload["logging"]["trace_enabled"])}
"""


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _write_backup(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.bak")
    if backup.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def _relative_display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _apply_env_overrides(config: SnappyConfig, env: Mapping[str, str]) -> SnappyConfig:
    raw_mode = env.get("SNAPPY_AGENT_MODE")
    if raw_mode is None:
        return config
    mode = raw_mode.strip().lower()
    issues = list(config.issues)
    if mode not in VALID_AGENT_MODES:
        issues.append(ConfigIssue("warning", "invalid_env_agent_mode", f"Invalid SNAPPY_AGENT_MODE '{raw_mode}'; using safe mode off."))
        mode = "off"
    return replace(config, agent=replace(config.agent, mode=mode), issues=issues)


def _coerce_config(payload: dict[str, Any], *, path: Path, root: Path) -> SnappyConfig:
    issues: list[ConfigIssue] = []
    for key in sorted(set(payload) - TOP_LEVEL_KEYS):
        issues.append(ConfigIssue("warning", "unknown_top_level_field", f"Unknown top-level config field: {key}"))

    version = payload.get("version")
    if version is None:
        return default_config(
            source=str(path),
            path=path,
            issues=[*issues, ConfigIssue("error", "missing_version", "Config field 'version' is required.")],
        )
    if version != 1:
        return default_config(
            source=str(path),
            path=path,
            issues=[*issues, ConfigIssue("error", "unsupported_version", f"Unsupported config version: {version}")],
        )

    agent = _coerce_agent(_section(payload, "agent", issues), issues)
    planning = _coerce_planning(_section(payload, "planning", issues), issues)
    skills = _coerce_skills(_section(payload, "skills", issues), root, issues)
    rules = _coerce_rules(_section(payload, "rules", issues), issues)
    memory = _coerce_memory(_section(payload, "memory", issues), issues)
    logging = _coerce_logging(_section(payload, "logging", issues), issues)
    return SnappyConfig(
        version=1,
        source=str(path),
        path=path,
        agent=agent,
        planning=planning,
        skills=skills,
        rules=rules,
        memory=memory,
        logging=logging,
        issues=issues,
    )


def _section(payload: dict[str, Any], key: str, issues: list[ConfigIssue]) -> dict[str, Any]:
    value = payload.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        issues.append(ConfigIssue("warning", f"invalid_{key}_section", f"Config section '{key}' must be a mapping; using defaults."))
        return {}
    return value


def _coerce_agent(payload: dict[str, Any], issues: list[ConfigIssue]) -> AgentConfig:
    default = AgentConfig()
    name = _string(payload.get("name"), default.name, "agent.name", issues)
    mode = _string(payload.get("mode"), default.mode, "agent.mode", issues).lower()
    if mode not in VALID_AGENT_MODES:
        issues.append(ConfigIssue("warning", "invalid_agent_mode", f"Invalid agent.mode '{mode}'; using safe default off."))
        mode = "off"
    description = _string(payload.get("description"), default.description, "agent.description", issues)
    return AgentConfig(name=name, mode=mode, description=description)


def _coerce_planning(payload: dict[str, Any], issues: list[ConfigIssue]) -> PlanningConfig:
    default = PlanningConfig()
    max_context_files = payload.get("max_context_files", default.max_context_files)
    if max_context_files is not None and (not isinstance(max_context_files, int) or max_context_files <= 0):
        issues.append(ConfigIssue("warning", "invalid_max_context_files", "planning.max_context_files must be a positive integer or null."))
        max_context_files = None
    return PlanningConfig(
        allow_project_extensions=_bool(payload.get("allow_project_extensions"), default.allow_project_extensions, "planning.allow_project_extensions", issues),
        prefer_small_steps=_bool(payload.get("prefer_small_steps"), default.prefer_small_steps, "planning.prefer_small_steps", issues),
        inspect_before_mutation=_bool(payload.get("inspect_before_mutation"), default.inspect_before_mutation, "planning.inspect_before_mutation", issues),
        max_context_files=max_context_files,
    )


def _coerce_skills(payload: dict[str, Any], root: Path, issues: list[ConfigIssue]) -> SkillsConfig:
    enabled = _string_list(payload.get("enabled"), "skills.enabled", issues)
    disabled = _string_list(payload.get("disabled"), "skills.disabled", issues)
    for name in [*enabled, *disabled]:
        if not _valid_skill_name(name):
            issues.append(ConfigIssue("warning", "invalid_skill_name", f"Invalid configured skill name: {name}"))
    configured = sorted(set(enabled + disabled))
    missing = [name for name in configured if not (root / ".snappy" / "skills" / name / "SKILL.md").is_file()]
    for name in missing:
        issues.append(ConfigIssue("warning", "configured_skill_missing", f"Configured skill is missing: {name}"))
    return SkillsConfig(enabled=enabled, disabled=disabled, missing=missing)


def _coerce_rules(payload: dict[str, Any], issues: list[ConfigIssue]) -> RulesConfig:
    default = RulesConfig()
    protected = _string_list(payload.get("protected_paths", list(BUILT_IN_PROTECTED_PATHS)), "rules.protected_paths", issues)
    merged = _dedupe([*BUILT_IN_PROTECTED_PATHS, *[item for item in protected if _valid_protected_path(item)]])
    for item in protected:
        if not _valid_protected_path(item):
            issues.append(ConfigIssue("warning", "invalid_protected_path", f"Ignoring invalid protected path: {item}"))
    confirmation_required = _bool(payload.get("confirmation_required"), default.confirmation_required, "rules.confirmation_required", issues)
    if confirmation_required is False:
        issues.append(ConfigIssue("warning", "confirmation_required_soft_preference", "rules.confirmation_required=false is treated as a soft preference and does not bypass mutation confirmations."))
    allow_file_writes = _bool(payload.get("allow_file_writes"), default.allow_file_writes, "rules.allow_file_writes", issues)
    if allow_file_writes is False:
        issues.append(ConfigIssue("warning", "file_writes_disabled_soft_preference", "rules.allow_file_writes=false is recorded but current mutation safety gates still apply."))
    allow_shell_commands = _bool(payload.get("allow_shell_commands"), default.allow_shell_commands, "rules.allow_shell_commands", issues)
    if allow_shell_commands is True:
        issues.append(ConfigIssue("warning", "unsafe_shell_command_override_ignored", "rules.allow_shell_commands=true cannot enable shell execution."))
        allow_shell_commands = False
    return RulesConfig(
        confirmation_required=confirmation_required,
        allow_file_writes=allow_file_writes,
        allow_shell_commands=allow_shell_commands,
        protected_paths=merged,
    )


def _coerce_memory(payload: dict[str, Any], issues: list[ConfigIssue]) -> MemoryConfig:
    default = MemoryConfig()
    return MemoryConfig(
        enabled=_bool(payload.get("enabled"), default.enabled, "memory.enabled", issues),
        snapshot_on_inspect=_bool(payload.get("snapshot_on_inspect"), default.snapshot_on_inspect, "memory.snapshot_on_inspect", issues),
    )


def _coerce_logging(payload: dict[str, Any], issues: list[ConfigIssue]) -> LoggingConfig:
    default = LoggingConfig()
    level = _string(payload.get("level"), default.level, "logging.level", issues).lower()
    if level not in VALID_LOGGING_LEVELS:
        issues.append(ConfigIssue("warning", "invalid_logging_level", f"Invalid logging.level '{level}'; using info."))
        level = "info"
    return LoggingConfig(
        level=level,
        trace_enabled=_bool(payload.get("trace_enabled"), default.trace_enabled, "logging.trace_enabled", issues),
    )


def _bool(value: Any, default: bool, field_name: str, issues: list[ConfigIssue]) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    issues.append(ConfigIssue("warning", "invalid_boolean", f"{field_name} must be boolean; using default."))
    return default


def _string(value: Any, default: str, field_name: str, issues: list[ConfigIssue]) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    issues.append(ConfigIssue("warning", "invalid_string", f"{field_name} must be a string; using default."))
    return default


def _string_list(value: Any, field_name: str, issues: list[ConfigIssue]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    issues.append(ConfigIssue("warning", "invalid_string_list", f"{field_name} must be a list of strings; using an empty list."))
    return []


def _valid_skill_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char == "-" for char in name) and not name.startswith("-") and not name.endswith("-")


def _valid_protected_path(path: str) -> bool:
    return bool(path.strip()) and path.strip() not in {".", "/"} and ".." not in Path(path).parts


def _dedupe(items: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _parse_yaml_mapping(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        index += 1
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent(raw_line)
        if indent != 0:
            raise ValueError("top-level keys must not be indented")
        if ":" not in raw_line:
            raise ValueError(f"malformed line: {stripped}")
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value_text = _strip_inline_comment(raw_value.strip())
        if not key:
            raise ValueError("config key cannot be empty")
        if value_text:
            result[key] = _parse_scalar(value_text)
            continue
        value, index = _parse_nested_block(lines, index, parent=key)
        result[key] = value
    return result


def _parse_nested_block(lines: list[str], index: int, *, parent: str) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        indent = _indent(raw_line)
        if indent == 0:
            break
        if indent != 2:
            raise ValueError(f"unsupported indentation in section '{parent}'")
        if ":" not in raw_line:
            raise ValueError(f"malformed line in section '{parent}': {stripped}")
        key, raw_value = raw_line.strip().split(":", 1)
        key = key.strip()
        value_text = _strip_inline_comment(raw_value.strip())
        index += 1
        if value_text:
            result[key] = _parse_scalar(value_text)
            continue
        items: list[Any] = []
        while index < len(lines):
            item_line = lines[index]
            item_stripped = item_line.strip()
            if not item_stripped or item_stripped.startswith("#"):
                index += 1
                continue
            item_indent = _indent(item_line)
            if item_indent <= 2:
                break
            if item_indent != 4 or not item_line.strip().startswith("- "):
                raise ValueError(f"malformed list for '{parent}.{key}'")
            items.append(_parse_scalar(_strip_inline_comment(item_line.strip()[2:].strip())))
            index += 1
        result[key] = items
    return result, index


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if lowered.startswith("[") and lowered.endswith("]"):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            inner = value[1:-1].strip()
            return [] if not inner else [_parse_scalar(item.strip()) for item in inner.split(",")]
        return parsed
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _strip_inline_comment(value: str) -> str:
    if not value or value.startswith(("#", "'", '"')):
        return value
    marker = value.find(" #")
    return value if marker == -1 else value[:marker].rstrip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
