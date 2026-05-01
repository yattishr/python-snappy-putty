from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.agent_discovery import AgentRule, AgentRuleRegistry
from snappy_putty.fs_models import FsPlan, PlannedOp
from snappy_putty.rule_hooks import (
    control_layer_summary,
    evaluate_agent_mode_policy,
    evaluate_filesystem_policy,
    policy_tier_counts,
    resolve_policy_decision,
)


def _rule(identifier: str, *, enforceable: bool = True) -> AgentRule:
    return AgentRule(
        name=identifier.replace("_", " ").title(),
        identifier=identifier,
        body=f"Rule body for {identifier}.",
        supported_for_enforcement=enforceable,
    )


def _copy_plan(dst: str) -> FsPlan:
    return FsPlan(
        goal=f"copy README.md to {dst}",
        cwd=".",
        ops=[PlannedOp(op_id="op1", action="copy", src="README.md", dst=dst, notes=[], risk="low")],
        warnings=[],
        requires_confirmation=False,
    )


def test_policy_decision_defaults_to_allow_when_no_rules_trigger() -> None:
    decision = resolve_policy_decision()

    assert decision.outcome == "allow"
    assert decision.control_layer == "runtime"
    assert decision.highest_tier == "info"
    assert decision.block_rules == ()
    assert decision.confirm_rules == ()
    assert decision.warn_rules == ()
    assert decision.info_rules == ()


def test_policy_decision_confirm_rule_only_requires_confirmation() -> None:
    decision = resolve_policy_decision(confirm_rules=["require_confirm"])

    assert decision.outcome == "confirm"
    assert decision.highest_tier == "confirm"
    assert decision.confirm_rules == ("require_confirm",)
    assert decision.block_rules == ()


def test_policy_decision_block_rule_only_wins() -> None:
    decision = resolve_policy_decision(block_rules=["protect_project_root"])

    assert decision.outcome == "block"
    assert decision.highest_tier == "block"
    assert decision.block_rules == ("protect_project_root",)
    assert decision.confirm_rules == ()


def test_policy_decision_info_rules_only_still_allows() -> None:
    decision = resolve_policy_decision(info_rules=["custom_note"])

    assert decision.outcome == "allow"
    assert decision.highest_tier == "info"
    assert decision.info_rules == ("custom_note",)
    assert decision.block_rules == ()
    assert decision.confirm_rules == ()


def test_filesystem_policy_block_outranks_confirm() -> None:
    registry = AgentRuleRegistry(
        rules=[
            _rule("protect_project_root"),
            _rule("require_confirm"),
            _rule("custom_note", enforceable=False),
        ]
    )

    decision, blocked_message = evaluate_filesystem_policy(
        plan=_copy_plan("/"),
        cwd=Path.cwd(),
        workspace_root=Path.cwd(),
        rule_registry=registry,
    )

    assert decision.outcome == "block"
    assert decision.control_layer == "filesystem_mutation"
    assert decision.highest_tier == "block"
    assert decision.block_rules == ("protect_project_root",)
    assert decision.confirm_rules == ("require_confirm",)
    assert decision.info_rules == ("custom_note",)
    assert blocked_message is not None


def test_filesystem_policy_confirm_applies_when_no_block_exists() -> None:
    registry = AgentRuleRegistry(rules=[_rule("require_confirm"), _rule("custom_note", enforceable=False)])

    decision, blocked_message = evaluate_filesystem_policy(
        plan=_copy_plan("tests/README.md"),
        cwd=Path.cwd(),
        workspace_root=Path.cwd(),
        rule_registry=registry,
    )

    assert decision.outcome == "confirm"
    assert decision.control_layer == "filesystem_mutation"
    assert decision.highest_tier == "confirm"
    assert decision.block_rules == ()
    assert decision.confirm_rules == ("require_confirm",)
    assert decision.info_rules == ("custom_note",)
    assert blocked_message is None


def test_agent_mode_policy_info_does_not_change_outcome() -> None:
    registry = AgentRuleRegistry(rules=[_rule("custom_note", enforceable=False)])

    decision = evaluate_agent_mode_policy(target_mode="active", rule_registry=registry)

    assert decision.outcome == "allow"
    assert decision.control_layer == "agent_mode"
    assert decision.block_rules == ()
    assert decision.info_rules == ("custom_note",)


def test_policy_decision_warn_rules_do_not_override_confirm() -> None:
    decision = resolve_policy_decision(confirm_rules=["require_confirm"], warn_rules=["warn_large_copy"])

    assert decision.outcome == "confirm"
    assert decision.confirm_rules == ("require_confirm",)
    assert decision.warn_rules == ("warn_large_copy",)
    assert decision.highest_tier == "confirm"


def test_policy_decision_same_tier_rules_are_canonicalized_deterministically() -> None:
    decision = resolve_policy_decision(confirm_rules=["z_rule", "a_rule", "z_rule"])

    assert decision.outcome == "confirm"
    assert decision.confirm_rules == ("a_rule", "z_rule")


def test_policy_tier_counts_and_control_layer_summary_capture_effective_outcome() -> None:
    decision = resolve_policy_decision(
        control_layer="filesystem_mutation",
        confirm_rules=["require_confirm"],
        warn_rules=["warn_large_copy"],
        info_rules=["custom_note"],
    )

    assert policy_tier_counts(decision) == {"block": 0, "confirm": 1, "warn": 1, "info": 1}
    assert (
        control_layer_summary(decision)
        == "Control layer: filesystem_mutation (hierarchy: block > confirm > warn > info; effective tier: confirm; outcome: confirm; tiers: block=0, confirm=1, warn=1, info=1)"
    )
