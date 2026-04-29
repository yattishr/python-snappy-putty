from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from snappy_putty.project_inspector import ProjectSnapshot, is_project_snapshot_valid


class PlanningMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    description: str
    files: list[str] = field(default_factory=list)
    proposed_new_files: list[str] = field(default_factory=list)
    risk: str = "LOW"
    requires_confirmation: bool = True


@dataclass(frozen=True)
class LLMPlanResponse:
    goal: str
    summary: str
    files_inspected: list[str]
    steps: list[dict[str, Any]]
    risks: list[str]
    assumptions: list[str]


@dataclass(frozen=True)
class GroundedPlan:
    plan_id: str
    goal: str
    mode: str
    created_at: str
    based_on_snapshot_id: str
    files_inspected: list[str]
    steps: list[PlanStep]
    risks: list[str]
    assumptions: list[str]
    status: str
    summary: str | None = None


class LLMPlannerClient(Protocol):
    def create_plan(self, prompt: str) -> dict[str, Any]: ...


class LLMPlannerUnavailableError(RuntimeError):
    pass


class LLMPlanValidationError(ValueError):
    pass


_LLM_ASSISTED_TRIGGERS = (
    "help me",
    "add ",
    "improve",
    "refactor",
    "design",
    "implement",
    "extend",
    "clean up",
    "make ",
    "make the",
    "explain project architecture",
    "increase test coverage",
    "better",
    "onboarding",
)

_DETERMINISTIC_PREFIXES = (
    "copy ",
    "move ",
    "rename ",
    "delete ",
    "remove ",
    "list ",
    "show ",
    "inspect ",
    "git ",
    "status",
    "branch",
    "diff ",
    "refresh snapshot",
    "inspect project",
    "inspect files",
    "inspect structure",
    "inspect file",
)

_FORBIDDEN_PATTERNS = (
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"curl\s*\|\s*sh",
    r"wget\s*\|\s*sh",
    r"chmod\s+-R\b",
    r"chown\s+-R\b",
    r"format\s+disk\b",
    r"install\s+global\s+dependency\b",
    r"delete\s+project\s+root\b",
    r"modify\s+files\s+outside\s+project\s+root\b",
)

_SENSITIVE_PATH_PREFIXES = (
    ".snappy/",
    ".github/workflows/",
)
_SENSITIVE_PATH_NAMES = {
    "pyproject.toml",
    "package.json",
    ".env",
    ".env.example",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
}

_RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
_PROJECT_RELATED_TERMS = (
    "code",
    "file",
    "folder",
    "directory",
    "test",
    "bug",
    "fix",
    "refactor",
    "function",
    "class",
    "module",
    "cli",
    "command",
    "route",
    "package",
    "dependency",
    "readme",
    "docs",
    "logging",
    "config",
    "implementation",
    "project",
)


def classify_planning_mode(user_input: str) -> PlanningMode:
    lowered = user_input.strip().lower()
    if not lowered:
        return PlanningMode.DETERMINISTIC
    if lowered.startswith(_DETERMINISTIC_PREFIXES):
        return PlanningMode.DETERMINISTIC
    if any(trigger in lowered for trigger in _LLM_ASSISTED_TRIGGERS):
        return PlanningMode.LLM_ASSISTED
    return PlanningMode.DETERMINISTIC


def assess_project_relevance(goal: str, snapshot: ProjectSnapshot) -> tuple[bool, str]:
    lowered = goal.strip().lower()
    if not lowered:
        return False, "goal_not_project_related"

    if any(term in lowered for term in _PROJECT_RELATED_TERMS):
        return True, "project_terms_matched"

    goal_tokens = {token.strip(".,:;!?()[]{}\"'") for token in re.split(r"\s+", lowered) if token}
    known_paths = {
        *snapshot.sampled_files,
        *snapshot.config_files,
        *snapshot.docs,
        *snapshot.test_files,
        *snapshot.source_files,
        *snapshot.entry_points,
    }
    for path in known_paths:
        normalized = path.lower().replace("\\", "/")
        basename = Path(normalized).name
        if normalized in lowered or basename in goal_tokens:
            return True, "snapshot_reference_matched"

    if any(token in lowered for token in ("inspect ", "explain ", "improve ", "update ", "modify ", "add ", "refactor ")):
        return True, "project_action_matched"

    return False, "goal_not_project_related"


def build_grounded_plan(
    goal: str,
    snapshot: ProjectSnapshot,
    *,
    mode: PlanningMode = PlanningMode.DETERMINISTIC,
    llm_client: LLMPlannerClient | None = None,
) -> GroundedPlan:
    if mode == PlanningMode.LLM_ASSISTED:
        return create_llm_assisted_plan(goal, snapshot, client=llm_client)

    files_inspected = _select_deterministic_files(goal, snapshot)
    steps = _deterministic_steps(goal, files_inspected, snapshot)
    risks = _deterministic_risks(goal, files_inspected, snapshot)
    assumptions = [
        f"Snapshot root: {snapshot.root_path}",
        "Planning is grounded in the current cached snapshot.",
    ]
    return GroundedPlan(
        plan_id=_plan_id(goal, snapshot.snapshot_id, mode.value),
        goal=goal.strip(),
        mode=mode.value,
        created_at=_utc_now(),
        based_on_snapshot_id=snapshot.snapshot_id,
        files_inspected=files_inspected,
        steps=steps,
        risks=risks,
        assumptions=assumptions,
        status="awaiting_confirmation",
        summary=f"Deterministic grounded plan for: {goal.strip()}",
    )


def create_llm_assisted_plan(
    goal: str,
    snapshot: ProjectSnapshot,
    *,
    client: LLMPlannerClient | None = None,
) -> GroundedPlan:
    planner_client = client or default_llm_planner_client()
    if planner_client is None:
        raise LLMPlannerUnavailableError(
            "LLM-assisted planning is unavailable. Deterministic planning and inspection remain available."
        )

    prompt = build_llm_prompt(goal, snapshot)
    raw_response = planner_client.create_plan(prompt)
    return validate_llm_plan(raw_response, snapshot, Path(snapshot.root_path))


def validate_llm_plan(
    raw_plan: dict[str, Any] | LLMPlanResponse,
    snapshot: ProjectSnapshot,
    project_root: Path,
) -> GroundedPlan:
    if not is_project_snapshot_valid(project_root, snapshot):
        raise LLMPlanValidationError("Project snapshot is stale.")

    payload = _coerce_llm_plan_payload(raw_plan)
    _require_keys(payload, {"goal", "summary", "files_inspected", "steps", "risks", "assumptions"})
    raw_snapshot_id = _optional_str(payload, "based_on_snapshot_id")
    if raw_snapshot_id is not None and raw_snapshot_id != snapshot.snapshot_id:
        raise LLMPlanValidationError("based_on_snapshot_id does not match the active snapshot.")

    goal = _require_str(payload, "goal")
    summary = _require_str(payload, "summary")
    files_inspected = _validate_existing_files(payload["files_inspected"], snapshot, project_root, field_name="files_inspected")
    if not isinstance(payload["steps"], list) or not payload["steps"]:
        raise LLMPlanValidationError("steps must be a non-empty list")
    risks = _require_str_list(payload, "risks")
    assumptions = _require_str_list(payload, "assumptions")

    step_models: list[PlanStep] = []
    normalized_risks = list(risks)
    for index, raw_step in enumerate(payload["steps"], start=1):
        if not isinstance(raw_step, dict):
            raise LLMPlanValidationError("Each step must be an object")
        _require_keys(raw_step, {"description", "files", "proposed_new_files", "risk", "requires_confirmation"})

        description = _require_str(raw_step, "description")
        _reject_forbidden_content(description)
        step_files = _validate_existing_files(raw_step["files"], snapshot, project_root, field_name="files")
        proposed_new_files = _validate_proposed_files(raw_step["proposed_new_files"], project_root, field_name="proposed_new_files")
        risk = _normalize_risk(raw_step["risk"])
        requires_confirmation = _require_bool(raw_step, "requires_confirmation")
        if not requires_confirmation:
            requires_confirmation = True

        step_risk = _normalize_risk_upwards(
            risk,
            *step_files,
            *proposed_new_files,
        )
        if _references_sensitive_file(step_files, proposed_new_files):
            step_risk = _normalize_risk_upwards(step_risk, "pyproject.toml")
            if "Confirm manually before applying this plan." not in normalized_risks:
                normalized_risks.append("Confirm manually before applying this plan.")

        if _contains_forbidden_operation(description):
            raise LLMPlanValidationError(f"Rejected unsafe instruction in step {index}: {description}")

        step_models.append(
            PlanStep(
                step_id=f"step_{index}",
                description=description,
                files=step_files,
                proposed_new_files=proposed_new_files,
                risk=step_risk,
                requires_confirmation=True,
            )
        )

    if not files_inspected:
        raise LLMPlanValidationError("files_inspected must not be empty")

    grounded_plan = GroundedPlan(
        plan_id=_plan_id(goal, snapshot.snapshot_id, PlanningMode.LLM_ASSISTED.value),
        goal=goal,
        mode=PlanningMode.LLM_ASSISTED.value,
        created_at=_utc_now(),
        based_on_snapshot_id=snapshot.snapshot_id,
        files_inspected=files_inspected,
        steps=step_models,
        risks=_dedupe_list(normalized_risks),
        assumptions=assumptions,
        status="awaiting_confirmation",
        summary=summary,
    )
    return grounded_plan


def grounded_plan_to_lines(plan: GroundedPlan) -> list[str]:
    lines = [
        "Grounded Plan",
        "",
        f"Goal: {plan.goal}",
        f"Mode: {plan.mode}",
        f"Based on snapshot: {plan.based_on_snapshot_id}",
        "",
        "Files considered:",
    ]
    if plan.files_inspected:
        lines.extend(f"- {item}" for item in plan.files_inspected)
    else:
        lines.append("- (none)")

    if plan.summary:
        lines.extend(["", f"Summary: {plan.summary}"])

    lines.extend(["", "Steps:"])
    if plan.steps:
        for index, step in enumerate(plan.steps, start=1):
            suffix = f" [{step.risk}]"
            lines.append(f"{index}. {step.description}{suffix}")
            if step.files:
                lines.append(f"   Files: {', '.join(step.files)}")
            if step.proposed_new_files:
                lines.append(f"   Proposed new files: {', '.join(step.proposed_new_files)}")
    else:
        lines.append("1. Review the current project snapshot. [LOW]")

    lines.extend(["", "Risks:"])
    if plan.risks:
        lines.extend(f"- {item}" for item in plan.risks)
    else:
        lines.append("- (none)")

    lines.extend(["", "Assumptions:"])
    if plan.assumptions:
        lines.extend(f"- {item}" for item in plan.assumptions)
    else:
        lines.append("- (none)")

    lines.extend(["", f"Status: {plan.status}", "No changes have been applied."])
    return lines


def plan_to_payload(plan: GroundedPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["steps"] = [asdict(step) for step in plan.steps]
    return payload


def plan_from_payload(payload: Any) -> GroundedPlan:
    if not isinstance(payload, dict):
        raise ValueError("grounded plan must be a JSON object")

    mode = _optional_str(payload, "mode") or PlanningMode.DETERMINISTIC.value
    summary = _optional_str(payload, "summary")
    files_inspected = _require_str_list(payload, "files_inspected", required=False)
    assumptions = _require_str_list(payload, "assumptions", required=False)
    risks = _require_str_list(payload, "risks", required=False)
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise ValueError("steps must be a list")

    steps = [_coerce_step(item, index) for index, item in enumerate(raw_steps, start=1)]
    return GroundedPlan(
        plan_id=_require_str(payload, "plan_id"),
        goal=_require_str(payload, "goal"),
        mode=mode,
        created_at=_require_str(payload, "created_at"),
        based_on_snapshot_id=_require_str(payload, "based_on_snapshot_id"),
        files_inspected=files_inspected,
        steps=steps,
        risks=risks,
        assumptions=assumptions,
        status=_require_str(payload, "status"),
        summary=summary,
    )


def invalidate_plan(plan: GroundedPlan, *, reason: str | None = None) -> GroundedPlan:
    return GroundedPlan(
        plan_id=plan.plan_id,
        goal=plan.goal,
        mode=plan.mode,
        created_at=plan.created_at,
        based_on_snapshot_id=plan.based_on_snapshot_id,
        files_inspected=list(plan.files_inspected),
        steps=list(plan.steps),
        risks=list(plan.risks),
        assumptions=list(plan.assumptions),
        status="invalidated",
        summary=plan.summary,
    )


def build_llm_prompt(goal: str, snapshot: ProjectSnapshot) -> str:
    relevant_files = ", ".join(_select_deterministic_files(goal, snapshot)) or "(none)"
    project_summary = _project_summary(snapshot)
    return (
        "You are assisting Snappy PuTTy, a supervised agentic CLI.\n\n"
        "Your task is to create a grounded implementation plan based only on the provided project context.\n"
        "You may suggest files to inspect or modify, but you must not invent files unless you mark them as proposed_new_files.\n"
        "You must not output shell commands.\n"
        "You must not output code patches.\n"
        "You must not claim that changes have been made.\n"
        "You must return valid JSON only.\n\n"
        f"User goal:\n{goal}\n\n"
        f"Project snapshot id:\n{snapshot.snapshot_id}\n\n"
        f"Project summary:\n{project_summary}\n\n"
        f"Relevant files:\n{relevant_files}\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "goal": string,\n'
        '  "summary": string,\n'
        '  "files_inspected": string[],\n'
        '  "steps": [\n'
        "    {\n"
        '      "description": string,\n'
        '      "files": string[],\n'
        '      "proposed_new_files": string[],\n'
        '      "risk": "LOW" | "MEDIUM" | "HIGH",\n'
        '      "requires_confirmation": boolean\n'
        "    }\n"
        "  ],\n"
        '  "risks": string[],\n'
        '  "assumptions": string[]\n'
        "}\n"
    )


def default_llm_planner_client() -> LLMPlannerClient | None:
    return None


def _select_deterministic_files(goal: str, snapshot: ProjectSnapshot) -> list[str]:
    candidates = list(snapshot.sampled_files)
    goal_lower = goal.lower()
    if any(token in goal_lower for token in ("cli", "logging", "workflow")):
        _append_if_missing(candidates, "src/snappy_putty/cli.py")
        _append_if_missing(candidates, "src/snappy_putty/session.py")
    if any(token in goal_lower for token in ("test", "coverage", "regression")):
        for item in snapshot.test_files[:3]:
            _append_if_missing(candidates, item)
    if any(token in goal_lower for token in ("readme", "docs", "document", "architecture")):
        for item in snapshot.docs[:3]:
            _append_if_missing(candidates, item)
    return _dedupe_list(candidates)[:6]


def _deterministic_steps(goal: str, files_inspected: list[str], snapshot: ProjectSnapshot) -> list[PlanStep]:
    focus = ", ".join(files_inspected[:3]) if files_inspected else "the current snapshot"
    return [
        PlanStep(
            step_id="step_1",
            description=f"Inspect the current implementation in {focus}.",
            files=list(files_inspected[:3]),
            proposed_new_files=[],
            risk="LOW",
            requires_confirmation=True,
        ),
        PlanStep(
            step_id="step_2",
            description=f"Apply the smallest project change that addresses: {goal.strip()}.",
            files=list(files_inspected[:3]),
            proposed_new_files=[],
            risk="MEDIUM" if any(path.endswith(".toml") for path in files_inspected) else "LOW",
            requires_confirmation=True,
        ),
        PlanStep(
            step_id="step_3",
            description="Add or update tests so the change remains grounded in the current repository.",
            files=list(snapshot.test_files[:3]),
            proposed_new_files=[],
            risk="MEDIUM",
            requires_confirmation=True,
        ),
    ]


def _deterministic_risks(goal: str, files_inspected: list[str], snapshot: ProjectSnapshot) -> list[str]:
    risks = [
        "The plan is advisory only and must not mutate source files without confirmation.",
    ]
    if any(path.endswith("cli.py") for path in files_inspected):
        risks.append("Terminal output or REPL flow may change if CLI behavior is altered.")
    if snapshot.file_count > 100:
        risks.append("Large repositories may need a narrower inspection scope.")
    if "logging" in goal.lower():
        risks.append("Logging could clutter the REPL if enabled by default.")
    return risks


def _plan_id(goal: str, snapshot_id: str, mode: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", f"{mode}-{goal}-{snapshot_id}".lower()).strip("-")
    return f"plan_{normalized[:24] or 'draft'}"


def _project_summary(snapshot: ProjectSnapshot) -> str:
    return "; ".join(
        [
            f"root={snapshot.root_path}",
            f"languages={', '.join(snapshot.languages) if snapshot.languages else '(none)'}",
            f"frameworks={', '.join(snapshot.frameworks) if snapshot.frameworks else '(none)'}",
            f"tests={len(snapshot.test_files)}",
            f"source={len(snapshot.source_files)}",
        ]
    )


def _coerce_llm_plan_payload(raw_plan: dict[str, Any] | LLMPlanResponse) -> dict[str, Any]:
    if isinstance(raw_plan, LLMPlanResponse):
        return asdict(raw_plan)
    if isinstance(raw_plan, dict):
        return dict(raw_plan)
    raise LLMPlanValidationError("LLM plan must be a JSON object")


def _require_keys(payload: dict[str, Any], required: set[str]) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise LLMPlanValidationError(f"Missing required key(s): {', '.join(sorted(missing))}")


def _require_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise LLMPlanValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_bool(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise LLMPlanValidationError(f"{field_name} must be a boolean")
    return value


def _require_str_list(payload: dict[str, Any], field_name: str, *, required: bool = True) -> list[str]:
    if field_name not in payload:
        if required:
            raise LLMPlanValidationError(f"Missing required key: {field_name}")
        return []
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise LLMPlanValidationError(f"{field_name} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise LLMPlanValidationError(f"{field_name} must contain strings only")
        result.append(item)
    return result


def _normalize_risk(value: Any) -> str:
    if not isinstance(value, str):
        raise LLMPlanValidationError("risk must be a string")
    normalized = value.strip().upper()
    if normalized not in {"LOW", "MEDIUM", "HIGH"}:
        raise LLMPlanValidationError(f"Unsupported risk level: {value!r}")
    return normalized


def _normalize_risk_upwards(base: str, *paths: str) -> str:
    risk = base
    if any(_is_sensitive_path(path) for path in paths):
        risk = _max_risk(risk, "MEDIUM")
    return risk


def _max_risk(*values: str) -> str:
    return max(values, key=lambda item: _RISK_ORDER.get(item, 0))


def _references_sensitive_file(files: list[str], proposed_new_files: list[str]) -> bool:
    for path in [*files, *proposed_new_files]:
        if _is_sensitive_path(path):
            return True
    return False


def _is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in _SENSITIVE_PATH_NAMES or any(
        normalized.startswith(prefix) for prefix in _SENSITIVE_PATH_PREFIXES
    )


def _validate_existing_files(
    paths: Any,
    snapshot: ProjectSnapshot,
    project_root: Path,
    *,
    field_name: str,
) -> list[str]:
    values = _coerce_paths_list(paths, field_name)
    known_paths = set(_known_snapshot_paths(snapshot))
    validated: list[str] = []
    for raw_path in values:
        rel_path = _validate_project_path(raw_path, project_root, field_name=field_name)
        if rel_path not in known_paths and not (project_root / rel_path).exists():
            raise LLMPlanValidationError(f"Referenced file does not exist: {rel_path}")
        validated.append(rel_path)
    return _dedupe_list(validated)


def _validate_proposed_files(paths: Any, project_root: Path, *, field_name: str) -> list[str]:
    values = _coerce_paths_list(paths, field_name)
    validated: list[str] = []
    for raw_path in values:
        rel_path = _validate_project_path(raw_path, project_root, field_name=field_name)
        validated.append(rel_path)
    return _dedupe_list(validated)


def _validate_project_path(path_text: str, project_root: Path, *, field_name: str) -> str:
    candidate = Path(path_text)
    if candidate.is_absolute():
        raise LLMPlanValidationError(f"{field_name} must be relative: {path_text}")
    if ".." in candidate.parts:
        raise LLMPlanValidationError(f"{field_name} must not contain '..': {path_text}")
    resolved = (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as exc:
        raise LLMPlanValidationError(f"{field_name} escapes project root: {path_text}") from exc
    return str(candidate).replace("\\", "/")


def _coerce_paths_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise LLMPlanValidationError(f"{field_name} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise LLMPlanValidationError(f"{field_name} must contain strings only")
        result.append(item)
    return result


def _contains_forbidden_operation(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _FORBIDDEN_PATTERNS)


def _reject_forbidden_content(text: str) -> None:
    if _contains_forbidden_operation(text):
        raise LLMPlanValidationError("Rejected unsafe instruction in plan content.")


def _coerce_step(item: Any, index: int) -> PlanStep:
    if isinstance(item, str):
        return PlanStep(
            step_id=f"step_{index}",
            description=item,
            files=[],
            proposed_new_files=[],
            risk="LOW",
            requires_confirmation=True,
        )
    if not isinstance(item, dict):
        raise ValueError("grounded plan step must be an object or string")
    return PlanStep(
        step_id=str(item.get("step_id") or f"step_{index}"),
        description=str(item.get("description") or item.get("action") or item.get("why") or "").strip(),
        files=list(item.get("files") or []),
        proposed_new_files=list(item.get("proposed_new_files") or []),
        risk=str(item.get("risk") or "LOW").upper(),
        requires_confirmation=bool(item.get("requires_confirmation", True)),
    )


def _known_snapshot_paths(snapshot: ProjectSnapshot) -> list[str]:
    return _dedupe_list(
        [
            *snapshot.config_files,
            *snapshot.docs,
            *snapshot.test_files,
            *snapshot.source_files,
            *snapshot.entry_points,
            *snapshot.sampled_files,
        ]
    )


def _append_if_missing(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _dedupe_list(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when present")
    return value


def _project_summary_from_snapshot(snapshot: ProjectSnapshot) -> str:
    return _project_summary(snapshot)
