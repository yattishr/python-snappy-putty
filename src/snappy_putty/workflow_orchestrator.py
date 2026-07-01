from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from snappy_putty.skills import Skill, SkillMatch
from snappy_putty.workflow_models import WorkflowArtifact, WorkflowPlan, WorkflowStep


DEFAULT_ACCEPTS = ["project_context"]
DEFAULT_PRODUCES = ["general_skill_report"]
DEFAULT_POSITION = "general"
MAX_WORKFLOW_STEPS = 4
POSITION_ORDER = {
    "context": 0,
    "analysis": 1,
    "transformation": 2,
    "synthesis": 3,
    "finalization": 4,
    "general": 5,
}


@dataclass(frozen=True)
class WorkflowSkillMetadata:
    accepts: list[str]
    produces: list[str]
    preferred_position: str
    has_explicit_metadata: bool


def workflow_orchestration_enabled() -> bool:
    return os.getenv("SNAPPY_WORKFLOW_ORCHESTRATION", "").strip().lower() not in {"0", "false", "no", "off"}


def build_workflow_plan(
    goal: str,
    matched_skills: list[SkillMatch] | list[Skill],
    grounded_plan: Any | None = None,
    context: Any | None = None,
    *,
    max_steps: int = MAX_WORKFLOW_STEPS,
) -> WorkflowPlan:
    skills = _coerce_skills(matched_skills)
    if not workflow_orchestration_enabled():
        return _not_required(goal, "workflow_orchestration_disabled")
    if len(skills) < 2:
        return _not_required(goal, "single_or_no_skill")

    skills = skills[: max(1, max_steps)]
    metadata = {skill.metadata.name: skill_workflow_metadata(skill) for skill in skills}
    edges = _dependency_edges(skills, metadata)
    explicit_metadata = any(item.has_explicit_metadata for item in metadata.values())
    if not edges and not (_has_multi_action_goal(goal) and explicit_metadata):
        return _not_required(goal, "no_compatible_skill_handoff")

    ordered = _ordered_skills(skills, metadata, edges)
    if len(ordered) < 2:
        return _not_required(goal, "no_ordered_workflow")

    steps: list[WorkflowStep] = []
    artifacts: list[WorkflowArtifact] = [
        WorkflowArtifact(
            name="project_context",
            kind="project_context",
            summary="Grounded project context selected during planning.",
        ),
        WorkflowArtifact(
            name="source_files",
            kind="source_files",
            summary="Source files selected during bounded context discovery.",
        ),
    ]
    produced_by_step: dict[str, str] = {}
    for index, skill in enumerate(ordered, start=1):
        meta = metadata[skill.metadata.name]
        output_artifact = _select_output_artifact(goal, meta.produces)
        input_artifacts = _input_artifacts(meta.accepts, produced_by_step)
        depends_on = _depends_on(input_artifacts, produced_by_step)
        step_id = f"step_{index}"
        steps.append(
            WorkflowStep(
                id=step_id,
                skill_name=skill.metadata.name,
                purpose=_purpose_for_skill(skill, output_artifact),
                input_artifacts=input_artifacts,
                output_artifact=output_artifact,
                depends_on=depends_on,
                risk=str(skill.metadata.snappy.get("risk") or "LOW").upper(),
            )
        )
        if output_artifact:
            produced_by_step[output_artifact] = step_id
            artifacts.append(
                WorkflowArtifact(
                    name=output_artifact,
                    kind=output_artifact,
                    producer_step_id=step_id,
                    summary=f"Planned artifact from {skill.metadata.name}.",
                )
            )

    final_output_kind = steps[-1].output_artifact or "general_skill_report"
    return WorkflowPlan(
        goal=goal,
        workflow_required=True,
        reason="compatible_skill_handoff" if edges else "multi_action_skill_workflow",
        steps=steps,
        final_output_kind=final_output_kind,
        artifacts=artifacts,
        status="awaiting_confirmation",
    )


def skill_workflow_metadata(skill: Skill) -> WorkflowSkillMetadata:
    frontmatter = skill.metadata.frontmatter
    inferred = _inferred_skill_metadata(skill)
    accepts = _string_list(frontmatter.get("accepts") or skill.metadata.snappy.get("accepts")) or inferred.accepts or DEFAULT_ACCEPTS
    produces = _string_list(frontmatter.get("produces") or skill.metadata.snappy.get("produces")) or inferred.produces or DEFAULT_PRODUCES
    position = frontmatter.get("preferred_position") or skill.metadata.snappy.get("preferred_position") or inferred.preferred_position or DEFAULT_POSITION
    if not isinstance(position, str) or position not in POSITION_ORDER:
        position = DEFAULT_POSITION
    has_explicit = any(key in frontmatter for key in ("accepts", "produces", "preferred_position")) or any(
        key in skill.metadata.snappy for key in ("accepts", "produces", "preferred_position")
    ) or inferred.has_explicit_metadata
    return WorkflowSkillMetadata(
        accepts=accepts,
        produces=produces,
        preferred_position=position,
        has_explicit_metadata=has_explicit,
    )


def render_workflow_plan_text(plan: WorkflowPlan) -> str:
    if not plan.workflow_required:
        return "Workflow orchestration not required; using flat multi-skill report."
    lines = ["Workflow orchestration enabled.", "", "Workflow Plan:"]
    for index, step in enumerate(plan.steps, start=1):
        inputs = ", ".join(step.input_artifacts) if step.input_artifacts else "(none)"
        produces = step.output_artifact or "general_skill_report"
        lines.extend(
            [
                f"{index}. {step.skill_name} -> {produces}",
                f"   Purpose: {step.purpose}",
                f"   Inputs: {inputs}",
                f"   Produces: {produces}",
            ]
        )
    lines.append(f"Final output: {plan.final_output_kind}")
    return "\n".join(lines)


def _not_required(goal: str, reason: str) -> WorkflowPlan:
    return WorkflowPlan(goal=goal, workflow_required=False, reason=reason, status="not_required")


def _coerce_skills(items: list[SkillMatch] | list[Skill]) -> list[Skill]:
    skills: list[Skill] = []
    for item in items:
        skill = getattr(item, "skill", item)
        if isinstance(skill, Skill):
            skills.append(skill)
    return skills


def _dependency_edges(skills: list[Skill], metadata: dict[str, WorkflowSkillMetadata]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for producer in skills:
        producer_meta = metadata[producer.metadata.name]
        producer_outputs = set(producer_meta.produces)
        for consumer in skills:
            if producer.metadata.name == consumer.metadata.name:
                continue
            consumer_inputs = set(metadata[consumer.metadata.name].accepts) - {"project_context", "source_files"}
            if producer_outputs & consumer_inputs:
                edges.add((producer.metadata.name, consumer.metadata.name))
    return edges


def _ordered_skills(
    skills: list[Skill],
    metadata: dict[str, WorkflowSkillMetadata],
    edges: set[tuple[str, str]],
) -> list[Skill]:
    by_name = {skill.metadata.name: skill for skill in skills}
    remaining = {skill.metadata.name for skill in skills}
    ordered: list[Skill] = []
    while remaining:
        ready = [
            name
            for name in remaining
            if all(consumer != name or producer not in remaining for producer, consumer in edges)
        ]
        if not ready:
            ready = list(remaining)
        ready.sort(key=lambda name: (POSITION_ORDER[metadata[name].preferred_position], skills.index(by_name[name])))
        selected = ready[0]
        ordered.append(by_name[selected])
        remaining.remove(selected)
    return ordered


def _select_output_artifact(goal: str, produces: list[str]) -> str:
    lowered = goal.lower()
    if "pr summary" in lowered or "pull request summary" in lowered or "merge request summary" in lowered:
        if "pr_summary" in produces:
            return "pr_summary"
    if "release notes" in lowered and "release_notes" in produces:
        return "release_notes"
    if "review" in lowered and "review_report" in produces:
        return "review_report"
    return produces[0] if produces else "general_skill_report"


def _input_artifacts(accepts: list[str], produced_by_step: dict[str, str]) -> list[str]:
    accepted = accepts or DEFAULT_ACCEPTS
    inputs = [artifact for artifact in ("project_context", "source_files") if artifact in accepted]
    for artifact in produced_by_step:
        if artifact in accepts and artifact not in inputs:
            inputs.append(artifact)
    return _dedupe(inputs or ["project_context"])


def _depends_on(input_artifacts: list[str], produced_by_step: dict[str, str]) -> list[str]:
    return _dedupe([produced_by_step[item] for item in input_artifacts if item in produced_by_step])


def _purpose_for_skill(skill: Skill, output_artifact: str) -> str:
    description = skill.metadata.description.strip().rstrip(".")
    if output_artifact and output_artifact != "general_skill_report":
        return f"{description}; produce {output_artifact}."
    return f"{description}."


def _inferred_skill_metadata(skill: Skill) -> WorkflowSkillMetadata:
    name = skill.metadata.name.lower()
    text = " ".join([skill.metadata.name, skill.metadata.description, skill.body]).lower()
    output_kinds = _string_list(skill.metadata.snappy.get("output_kinds"))
    if name == "codeguardian-review" or ("codeguardian" in name and "review" in text):
        return WorkflowSkillMetadata(
            accepts=["project_context", "source_files"],
            produces=["review_report"],
            preferred_position="analysis",
            has_explicit_metadata=True,
        )
    if name == "doc-coauthoring" or ("doc" in name and ("summary" in text or "documentation" in text)):
        produces = ["markdown_document", "pr_summary"] if "pr_summary" not in output_kinds else output_kinds
        return WorkflowSkillMetadata(
            accepts=["project_context", "review_report", "outline"],
            produces=produces,
            preferred_position="synthesis",
            has_explicit_metadata=True,
        )
    return WorkflowSkillMetadata([], [], "", False)


def _has_multi_action_goal(goal: str) -> bool:
    lowered = goal.lower()
    return bool(
        re.search(r"\b(and|then|after|using)\b", lowered)
        and re.search(r"\b(review|analyze|inspect|generate|draft|write|summarize|summary|notes|guide)\b", lowered)
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
