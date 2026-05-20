from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
import os
from pathlib import Path
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


def starter_config_text() -> str:
    return """version: 1

agent:
  name: Snappy
  mode: off
  description: Project-local Snappy configuration.

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: null

skills:
  enabled: []
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
