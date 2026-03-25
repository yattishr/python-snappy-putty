from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AgentProjectDiscovery:
    agent_found: bool
    agent_root: Path | None
    manifest_path: Path | None


@dataclass(frozen=True)
class AgentManifest:
    name: str | None = None
    version: int | None = None
    mode: str | None = None
    confirmations: bool | None = None
    dry_run: bool | None = None
    skills: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    memory: bool | None = None


@dataclass(frozen=True)
class AgentProjectConfig:
    discovery: AgentProjectDiscovery
    manifest: AgentManifest | None
    warning: str | None = None


@dataclass(frozen=True)
class AgentSkill:
    name: str
    description: str
    intent_examples: list[str]
    risk: str


@dataclass(frozen=True)
class AgentSkillRegistry:
    skills: list[AgentSkill] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentRule:
    name: str
    body: str


@dataclass(frozen=True)
class AgentRuleRegistry:
    rules: list[AgentRule] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentMemory:
    memory_found: bool
    memory_root: Path | None
    session_path: Path | None
    session_data: dict[str, object] | None
    warning: str | None = None


_KNOWN_FIELDS: dict[str, type | tuple[type, ...]] = {
    "name": str,
    "version": int,
    "mode": str,
    "confirmations": bool,
    "dry_run": bool,
    "skills": list,
    "rules": list,
    "memory": bool,
}

_ALLOWED_AGENT_MODES = {"off", "passive", "active"}


def get_agent_mode() -> str:
    value = os.getenv("SNAPPY_AGENT_MODE", "off").strip().lower()
    return value if value in _ALLOWED_AGENT_MODES else "off"


def discover_agent_project(cwd: Path | None = None) -> AgentProjectDiscovery:
    if get_agent_mode() == "off":
        return AgentProjectDiscovery(agent_found=False, agent_root=None, manifest_path=None)

    root = (cwd or Path.cwd()).resolve()
    agent_root = root / ".snappy"
    manifest_path = agent_root / "snappy.yaml"

    if not agent_root.is_dir():
        return AgentProjectDiscovery(agent_found=False, agent_root=None, manifest_path=None)

    return AgentProjectDiscovery(
        agent_found=True,
        agent_root=agent_root,
        manifest_path=manifest_path if manifest_path.is_file() else None,
    )


def load_agent_project_config(cwd: Path | None = None) -> AgentProjectConfig:
    discovery = discover_agent_project(cwd)
    if discovery.manifest_path is None:
        return AgentProjectConfig(discovery=discovery, manifest=None, warning=None)

    try:
        raw_data = _parse_simple_yaml(discovery.manifest_path.read_text(encoding="utf-8"))
        manifest = _validate_manifest(raw_data)
    except (OSError, ValueError) as exc:
        warning = f"Invalid agent manifest: {exc}"
        return AgentProjectConfig(discovery=discovery, manifest=None, warning=warning)

    return AgentProjectConfig(discovery=discovery, manifest=manifest, warning=None)


def _parse_simple_yaml(text: str) -> dict[str, object]:
    result: dict[str, object] = {}
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        index += 1

        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[: len(raw_line) - len(raw_line.lstrip(" "))]:
            raise ValueError("only top-level manifest keys are supported")
        if ":" not in raw_line:
            raise ValueError(f"malformed line: {stripped}")

        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value_text = raw_value.strip()
        if not key:
            raise ValueError("manifest key cannot be empty")

        if not value_text:
            items: list[object] = []
            while index < len(lines):
                item_line = lines[index]
                item_stripped = item_line.strip()
                if not item_stripped or item_stripped.startswith("#"):
                    index += 1
                    continue
                indent = len(item_line) - len(item_line.lstrip(" "))
                if indent == 0:
                    break
                if indent < 2 or not item_line.lstrip().startswith("- "):
                    raise ValueError(f"malformed list for key '{key}'")
                items.append(_parse_scalar(item_line.lstrip()[2:].strip()))
                index += 1
            result[key] = items
            continue

        result[key] = _parse_scalar(value_text)

    return result


def _parse_scalar(value: str) -> object:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if lowered.startswith("[") and lowered.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [_parse_scalar(item.strip()) for item in inner.split(",")]
        if not isinstance(parsed, list):
            raise ValueError(f"invalid list syntax: {value}")
        return parsed
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    if value.lstrip("-").isdigit():
        return int(value)
    if ":" in value and not value.startswith(("'", '"')):
        raise ValueError(f"malformed scalar: {value}")
    return value


def _validate_manifest(data: dict[str, object]) -> AgentManifest:
    payload: dict[str, object] = {}
    for key, value in data.items():
        if key not in _KNOWN_FIELDS:
            continue
        expected_type = _KNOWN_FIELDS[key]
        if key in {"skills", "rules"}:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"field '{key}' must be a list of strings")
            payload[key] = value
            continue
        if value is not None and not isinstance(value, expected_type):
            raise ValueError(f"field '{key}' must be of type {expected_type.__name__}")
        payload[key] = value
    return AgentManifest(**payload)


def load_agent_skill_registry(cwd: Path | None = None) -> AgentSkillRegistry:
    if get_agent_mode() == "off":
        return AgentSkillRegistry()

    discovery = discover_agent_project(cwd)
    if not discovery.agent_root:
        return AgentSkillRegistry()

    skills_dir = discovery.agent_root / "skills"
    if not skills_dir.is_dir():
        return AgentSkillRegistry()

    skills: list[AgentSkill] = []
    warnings: list[str] = []
    for path in sorted(skills_dir.glob("*.md")):
        try:
            skills.append(_parse_skill_file(path))
        except (OSError, ValueError) as exc:
            warnings.append(f"Skipped invalid skill file {path.name}: {exc}")
    return AgentSkillRegistry(skills=skills, warnings=warnings)


def _parse_skill_file(path: Path) -> AgentSkill:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("file is empty")

    heading = lines[0].strip()
    prefix = "# Skill:"
    if not heading.startswith(prefix):
        raise ValueError("missing '# Skill: <name>' heading")
    name = heading[len(prefix) :].strip()
    if not name:
        raise ValueError("skill name cannot be empty")

    description: str | None = None
    intent_examples: list[str] = []
    risk: str | None = None
    current_section: str | None = None

    for raw_line in lines[1:]:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped == "Description:":
            current_section = "description"
            continue
        if stripped == "Intent examples:":
            current_section = "intent_examples"
            continue
        if stripped.startswith("Risk:"):
            risk = stripped.split(":", 1)[1].strip()
            current_section = None
            continue

        if current_section == "description":
            description = f"{description} {stripped}".strip() if description else stripped
            continue
        if current_section == "intent_examples":
            if stripped.startswith(("-", "*")):
                example = stripped[1:].strip()
            else:
                example = stripped
            if example:
                intent_examples.append(example)
            continue

    if not description:
        raise ValueError("missing Description section")
    if not intent_examples:
        raise ValueError("missing Intent examples section")
    if not risk:
        raise ValueError("missing Risk field")

    return AgentSkill(
        name=name,
        description=description,
        intent_examples=intent_examples,
        risk=risk,
    )


def load_agent_rule_registry(cwd: Path | None = None) -> AgentRuleRegistry:
    if get_agent_mode() == "off":
        return AgentRuleRegistry()

    discovery = discover_agent_project(cwd)
    if not discovery.agent_root:
        return AgentRuleRegistry()

    rules_dir = discovery.agent_root / "rules"
    if not rules_dir.is_dir():
        return AgentRuleRegistry()

    rules: list[AgentRule] = []
    warnings: list[str] = []
    for path in sorted(rules_dir.glob("*.md")):
        try:
            rules.append(_parse_rule_file(path))
        except (OSError, ValueError) as exc:
            warnings.append(f"Skipped invalid rule file {path.name}: {exc}")
    return AgentRuleRegistry(rules=rules, warnings=warnings)


def _parse_rule_file(path: Path) -> AgentRule:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("file is empty")

    heading = lines[0].strip()
    prefix = "# Rule:"
    if not heading.startswith(prefix):
        raise ValueError("missing '# Rule: <name>' heading")
    name = heading[len(prefix) :].strip()
    if not name:
        raise ValueError("rule name cannot be empty")

    body = "\n".join(line.rstrip() for line in lines[1:]).strip()
    if not body:
        raise ValueError("rule body cannot be empty")

    return AgentRule(name=name, body=body)


def load_agent_memory(cwd: Path | None = None) -> AgentMemory:
    if get_agent_mode() == "off":
        return AgentMemory(
            memory_found=False,
            memory_root=None,
            session_path=None,
            session_data=None,
            warning=None,
        )

    discovery = discover_agent_project(cwd)
    if not discovery.agent_root:
        return AgentMemory(
            memory_found=False,
            memory_root=None,
            session_path=None,
            session_data=None,
            warning=None,
        )

    memory_root = discovery.agent_root / "memory"
    session_path = memory_root / "session.json"
    if not memory_root.is_dir():
        return AgentMemory(
            memory_found=False,
            memory_root=None,
            session_path=None,
            session_data=None,
            warning=None,
        )

    if not session_path.is_file():
        return AgentMemory(
            memory_found=True,
            memory_root=memory_root,
            session_path=None,
            session_data=None,
            warning=None,
        )

    try:
        raw_data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return AgentMemory(
            memory_found=True,
            memory_root=memory_root,
            session_path=session_path,
            session_data=None,
            warning=f"Invalid agent memory session: {exc}",
        )

    if not isinstance(raw_data, dict):
        return AgentMemory(
            memory_found=True,
            memory_root=memory_root,
            session_path=session_path,
            session_data=None,
            warning="Invalid agent memory session: top-level JSON must be an object",
        )

    return AgentMemory(
        memory_found=True,
        memory_root=memory_root,
        session_path=session_path,
        session_data=raw_data,
        warning=None,
    )
