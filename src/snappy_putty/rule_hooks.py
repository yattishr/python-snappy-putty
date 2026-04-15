from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from snappy_putty.agent_discovery import AgentRuleRegistry
from snappy_putty.fs_models import FsPlan


REQUIRE_CONFIRM_RULE = "require_confirm"
PROTECT_PROJECT_ROOT_RULE = "protect_project_root"
NO_ACTIVE_MODE_RULE = "no_active_mode"


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str
    block_rules: tuple[str, ...] = ()
    confirm_rules: tuple[str, ...] = ()
    warn_rules: tuple[str, ...] = ()
    info_rules: tuple[str, ...] = ()


def resolve_policy_decision(
    *,
    block_rules: Iterable[str] = (),
    confirm_rules: Iterable[str] = (),
    warn_rules: Iterable[str] = (),
    info_rules: Iterable[str] = (),
) -> PolicyDecision:
    resolved_block_rules = tuple(block_rules)
    resolved_confirm_rules = tuple(confirm_rules)
    resolved_warn_rules = tuple(warn_rules)
    resolved_info_rules = tuple(info_rules)

    if resolved_block_rules:
        outcome = "block"
    elif resolved_confirm_rules:
        outcome = "confirm"
    else:
        outcome = "allow"

    return PolicyDecision(
        outcome=outcome,
        block_rules=resolved_block_rules,
        confirm_rules=resolved_confirm_rules,
        warn_rules=resolved_warn_rules,
        info_rules=resolved_info_rules,
    )


@dataclass(frozen=True)
class FilesystemRuleDecision:
    requires_confirmation: bool = False
    blocked: bool = False
    message: str | None = None
    policy_decision: PolicyDecision = field(default_factory=resolve_policy_decision)


def evaluate_filesystem_policy(
    *,
    plan: FsPlan,
    cwd: Path,
    workspace_root: Path,
    rule_registry: AgentRuleRegistry,
) -> tuple[PolicyDecision, str | None]:
    block_rules: list[str] = []
    confirm_rules: list[str] = []
    warn_rules: list[str] = []
    info_rules = [rule.identifier for rule in rule_registry.informational_rules]
    blocked_message: str | None = None

    if rule_registry.is_active(PROTECT_PROJECT_ROOT_RULE):
        blocked_message = _protect_project_root_message(plan=plan, cwd=cwd, workspace_root=workspace_root)
        if blocked_message is not None:
            block_rules.append(PROTECT_PROJECT_ROOT_RULE)

    if plan.ops and rule_registry.is_active(REQUIRE_CONFIRM_RULE):
        confirm_rules.append(REQUIRE_CONFIRM_RULE)

    return (
        resolve_policy_decision(
            block_rules=block_rules,
            confirm_rules=confirm_rules,
            warn_rules=warn_rules,
            info_rules=info_rules,
        ),
        blocked_message,
    )


def evaluate_agent_mode_policy(*, target_mode: str, rule_registry: AgentRuleRegistry) -> PolicyDecision:
    block_rules: list[str] = []
    info_rules = [rule.identifier for rule in rule_registry.informational_rules]

    if target_mode == "active" and rule_registry.is_active(NO_ACTIVE_MODE_RULE):
        block_rules.append(NO_ACTIVE_MODE_RULE)

    return resolve_policy_decision(block_rules=block_rules, info_rules=info_rules)


def before_filesystem_mutation_plan_or_execute(
    *,
    plan: FsPlan,
    cwd: Path,
    workspace_root: Path,
    rule_registry: AgentRuleRegistry,
) -> FilesystemRuleDecision:
    policy_decision, blocked_message = evaluate_filesystem_policy(
        plan=plan,
        cwd=cwd,
        workspace_root=workspace_root,
        rule_registry=rule_registry,
    )
    if policy_decision.outcome == "block":
        return FilesystemRuleDecision(blocked=True, message=blocked_message, policy_decision=policy_decision)

    if not plan.ops:
        return FilesystemRuleDecision(policy_decision=policy_decision)

    return FilesystemRuleDecision(
        requires_confirmation=policy_decision.outcome == "confirm",
        policy_decision=policy_decision,
    )


def before_agent_mode_change(*, target_mode: str, rule_registry: AgentRuleRegistry) -> str | None:
    policy_decision = evaluate_agent_mode_policy(target_mode=target_mode, rule_registry=rule_registry)
    if NO_ACTIVE_MODE_RULE in policy_decision.block_rules:
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
