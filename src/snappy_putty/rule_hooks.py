from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from snappy_putty.agent_discovery import AgentRuleRegistry
from snappy_putty.fs_models import FsPlan


REQUIRE_CONFIRM_RULE = "require_confirm"
PROTECT_PROJECT_ROOT_RULE = "protect_project_root"
NO_ACTIVE_MODE_RULE = "no_active_mode"


@dataclass(frozen=True)
class FilesystemRuleDecision:
    requires_confirmation: bool = False
    blocked: bool = False
    message: str | None = None


def before_filesystem_mutation_plan_or_execute(
    *,
    plan: FsPlan,
    cwd: Path,
    workspace_root: Path,
    rule_registry: AgentRuleRegistry,
) -> FilesystemRuleDecision:
    if rule_registry.is_active(PROTECT_PROJECT_ROOT_RULE):
        blocked_message = _protect_project_root_message(plan=plan, cwd=cwd, workspace_root=workspace_root)
        if blocked_message is not None:
            return FilesystemRuleDecision(blocked=True, message=blocked_message)

    if not plan.ops:
        return FilesystemRuleDecision()

    return FilesystemRuleDecision(requires_confirmation=rule_registry.is_active(REQUIRE_CONFIRM_RULE))


def before_agent_mode_change(*, target_mode: str, rule_registry: AgentRuleRegistry) -> str | None:
    if target_mode == "active" and rule_registry.is_active(NO_ACTIVE_MODE_RULE):
        return "Active mode is disabled by the loaded agent rules."
    return None


def _protect_project_root_message(*, plan: FsPlan, cwd: Path, workspace_root: Path) -> str | None:
    if any("Path escapes workspace root:" in warning for warning in plan.warnings):
        return (
            "Operation blocked by rule: protect_project_root\n\n"
            "The requested filesystem mutation targets a protected path."
        )

    protected_paths = _protected_paths(cwd=cwd, workspace_root=workspace_root)
    for op in plan.ops:
        for candidate in _relevant_op_paths(op=op, cwd=cwd):
            if candidate in protected_paths:
                return (
                    "Operation blocked by rule: protect_project_root\n\n"
                    "The requested filesystem mutation targets a protected path."
                )
    return None


def _protected_paths(*, cwd: Path, workspace_root: Path) -> set[Path]:
    protected = {workspace_root.resolve()}
    cwd_root = cwd.resolve().anchor or "/"
    protected.add(Path(cwd_root).resolve())
    protected.add(Path.home().resolve())
    return protected


def _relevant_op_paths(*, op, cwd: Path) -> list[Path]:
    candidates: list[Path] = []
    if op.src:
        candidates.append((cwd / op.src).resolve())
    if op.dst:
        candidates.append((cwd / op.dst).resolve())
    return candidates
