from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from snappy_putty.agent_discovery import AgentRuleRegistry
from snappy_putty.fs_models import FsPlan


REQUIRE_CONFIRM_RULE = "require_confirm"
PROTECT_PROJECT_ROOT_RULE = "protect_project_root"
NO_ACTIVE_MODE_RULE = "no_active_mode"
POLICY_HIERARCHY: tuple[str, ...] = ("block", "confirm", "warn", "info")


@dataclass(frozen=True)
class PolicyDecision:
    control_layer: str
    outcome: str
    block_rules: tuple[str, ...] = ()
    confirm_rules: tuple[str, ...] = ()
    warn_rules: tuple[str, ...] = ()
    info_rules: tuple[str, ...] = ()
    highest_tier: str = "info"
    hierarchy: tuple[str, ...] = POLICY_HIERARCHY


def resolve_policy_decision(
    *,
    control_layer: str = "runtime",
    block_rules: Iterable[str] = (),
    confirm_rules: Iterable[str] = (),
    warn_rules: Iterable[str] = (),
    info_rules: Iterable[str] = (),
) -> PolicyDecision:
    resolved_block_rules = _canonicalize_rule_ids(block_rules)
    resolved_confirm_rules = _canonicalize_rule_ids(confirm_rules)
    resolved_warn_rules = _canonicalize_rule_ids(warn_rules)
    resolved_info_rules = _canonicalize_rule_ids(info_rules)

    if resolved_block_rules:
        outcome = "block"
        highest_tier = "block"
    elif resolved_confirm_rules:
        outcome = "confirm"
        highest_tier = "confirm"
    elif resolved_warn_rules:
        outcome = "allow"
        highest_tier = "warn"
    else:
        outcome = "allow"
        highest_tier = "info"

    return PolicyDecision(
        control_layer=control_layer,
        outcome=outcome,
        block_rules=resolved_block_rules,
        confirm_rules=resolved_confirm_rules,
        warn_rules=resolved_warn_rules,
        info_rules=resolved_info_rules,
        highest_tier=highest_tier,
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
    protected_paths: Iterable[str] = (),
) -> tuple[PolicyDecision, str | None]:
    block_rules: list[str] = []
    confirm_rules: list[str] = []
    warn_rules: list[str] = []
    info_rules = [rule.identifier for rule in rule_registry.informational_rules]
    blocked_message: str | None = None

    if rule_registry.is_active(PROTECT_PROJECT_ROOT_RULE):
        blocked_message = _protect_project_root_message(
            plan=plan,
            cwd=cwd,
            workspace_root=workspace_root,
            configured_protected_paths=protected_paths,
        )
        if blocked_message is not None:
            block_rules.append(PROTECT_PROJECT_ROOT_RULE)

    if (plan.ops or blocked_message is not None) and rule_registry.is_active(REQUIRE_CONFIRM_RULE):
        confirm_rules.append(REQUIRE_CONFIRM_RULE)

    return (
        resolve_policy_decision(
            control_layer="filesystem_mutation",
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

    return resolve_policy_decision(control_layer="agent_mode", block_rules=block_rules, info_rules=info_rules)


def before_filesystem_mutation_plan_or_execute(
    *,
    plan: FsPlan,
    cwd: Path,
    workspace_root: Path,
    rule_registry: AgentRuleRegistry,
    protected_paths: Iterable[str] = (),
) -> FilesystemRuleDecision:
    policy_decision, blocked_message = evaluate_filesystem_policy(
        plan=plan,
        cwd=cwd,
        workspace_root=workspace_root,
        rule_registry=rule_registry,
        protected_paths=protected_paths,
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


def _protect_project_root_message(
    *,
    plan: FsPlan,
    cwd: Path,
    workspace_root: Path,
    configured_protected_paths: Iterable[str] = (),
) -> str | None:
    if any("Path escapes workspace root:" in warning for warning in plan.warnings):
        return (
            "Operation blocked by rule: protect_project_root\n\n"
            "The requested filesystem mutation targets a protected path."
        )

    protected_paths = _protected_paths(cwd=cwd, workspace_root=workspace_root, configured_protected_paths=configured_protected_paths)
    for op in plan.ops:
        for candidate in _relevant_op_paths(op=op, cwd=cwd):
            if candidate in protected_paths:
                return (
                    "Operation blocked by rule: protect_project_root\n\n"
                    "The requested filesystem mutation targets a protected path."
                )
    return None


def _protected_paths(*, cwd: Path, workspace_root: Path, configured_protected_paths: Iterable[str] = ()) -> set[Path]:
    protected = {workspace_root.resolve()}
    cwd_root = cwd.resolve().anchor or "/"
    protected.add(Path(cwd_root).resolve())
    protected.add(Path.home().resolve())
    for path_text in configured_protected_paths:
        candidate = Path(path_text)
        if candidate.is_absolute():
            protected.add(candidate.resolve())
        else:
            protected.add((workspace_root / candidate).resolve())
    return protected


def _relevant_op_paths(*, op, cwd: Path) -> list[Path]:
    candidates: list[Path] = []
    if op.src:
        candidates.append((cwd / op.src).resolve())
    if op.dst:
        candidates.append((cwd / op.dst).resolve())
    return candidates


def policy_tier_counts(policy_decision: PolicyDecision) -> dict[str, int]:
    return {
        "block": len(policy_decision.block_rules),
        "confirm": len(policy_decision.confirm_rules),
        "warn": len(policy_decision.warn_rules),
        "info": len(policy_decision.info_rules),
    }


def control_layer_summary(policy_decision: PolicyDecision) -> str:
    counts = policy_tier_counts(policy_decision)
    return (
        f"Control layer: {policy_decision.control_layer} "
        f"(hierarchy: {' > '.join(policy_decision.hierarchy)}; "
        f"effective tier: {policy_decision.highest_tier}; "
        f"outcome: {policy_decision.outcome}; "
        f"tiers: block={counts['block']}, confirm={counts['confirm']}, warn={counts['warn']}, info={counts['info']})"
    )


def _canonicalize_rule_ids(rule_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({rule_id for rule_id in rule_ids if rule_id}))
