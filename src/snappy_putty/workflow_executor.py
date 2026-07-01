from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from snappy_putty.skill_outputs import SkillOutput, SkillOutputRequest, SkillOutputSection, generate_skill_output
from snappy_putty.skills import Skill
from snappy_putty.workflow_models import WorkflowArtifact, WorkflowPlan, WorkflowStep


StepRunner = Callable[[WorkflowStep, list[WorkflowArtifact], SkillOutputRequest, list[Skill]], WorkflowArtifact]


@dataclass(frozen=True)
class WorkflowExecutionResult:
    workflow_plan: WorkflowPlan
    artifacts: list[WorkflowArtifact]
    final_output_kind: str
    summary: str
    success: bool
    final_output: SkillOutput | None = None


def execute_workflow_plan(
    workflow_plan: WorkflowPlan,
    output_context: SkillOutputRequest,
    skills: list[Skill] | None = None,
    *,
    step_runner: StepRunner | None = None,
) -> WorkflowExecutionResult:
    if not workflow_plan.workflow_required:
        output = generate_skill_output(output_context, skills)
        artifact = WorkflowArtifact(
            name=output.output_kind,
            kind=output.output_kind,
            data={"title": output.title, "summary": output.summary},
            summary=output.summary,
        )
        return WorkflowExecutionResult(
            workflow_plan=workflow_plan.with_status("completed"),
            artifacts=[artifact],
            final_output_kind=output.output_kind,
            summary=output.summary,
            success=True,
            final_output=output,
        )

    artifacts: list[WorkflowArtifact] = [artifact for artifact in workflow_plan.artifacts if artifact.producer_step_id is None]
    runner = step_runner or _default_step_runner
    completed_steps: list[WorkflowStep] = []
    for step in workflow_plan.steps:
        try:
            artifact = runner(step, artifacts, output_context, skills or [])
        except Exception as exc:
            failed_steps = [*completed_steps, replace(step, status="failed")]
            return WorkflowExecutionResult(
                workflow_plan=replace(workflow_plan, steps=failed_steps, status="failed"),
                artifacts=artifacts,
                final_output_kind=workflow_plan.final_output_kind,
                summary=f"Workflow failed at {step.skill_name}: {exc}",
                success=False,
                final_output=None,
            )
        artifacts.append(artifact)
        completed_steps.append(replace(step, status="completed"))

    final_artifact = artifacts[-1]
    final_output = _artifact_to_skill_output(workflow_plan, final_artifact, output_context)
    return WorkflowExecutionResult(
        workflow_plan=replace(workflow_plan, steps=completed_steps, artifacts=artifacts, status="completed"),
        artifacts=artifacts,
        final_output_kind=final_artifact.kind,
        summary=final_artifact.summary or f"Workflow produced {final_artifact.kind}.",
        success=True,
        final_output=final_output,
    )


def _default_step_runner(
    step: WorkflowStep,
    artifacts: list[WorkflowArtifact],
    output_context: SkillOutputRequest,
    skills: list[Skill],
) -> WorkflowArtifact:
    available = {artifact.name: artifact for artifact in artifacts}
    missing = [name for name in step.input_artifacts if name not in available]
    if missing:
        raise ValueError(f"missing input artifacts: {', '.join(missing)}")
    output_kind = step.output_artifact or "general_skill_report"
    return WorkflowArtifact(
        name=output_kind,
        kind=output_kind,
        producer_step_id=step.id,
        data={
            "skill": step.skill_name,
            "inputs": list(step.input_artifacts),
            "goal": output_context.goal,
            "files_referenced": list(output_context.files_considered),
        },
        summary=f"{step.skill_name} generated {output_kind}.",
    )


def _artifact_to_skill_output(
    workflow_plan: WorkflowPlan,
    artifact: WorkflowArtifact,
    output_context: SkillOutputRequest,
) -> SkillOutput:
    if artifact.kind == "pr_summary":
        title = "PR Summary"
        summary = f"Workflow output for: {output_context.goal}"
        sections = [
            SkillOutputSection("Summary", body=summary),
            SkillOutputSection(
                "Workflow Trace",
                items=[
                    f"{index}. {step.skill_name} produced {step.output_artifact or 'general_skill_report'}"
                    for index, step in enumerate(workflow_plan.steps, start=1)
                ],
            ),
            SkillOutputSection("Files Referenced", items=output_context.files_considered or ["No grounded file references were available."]),
            SkillOutputSection("Risks", items=["Generated from confirmed terminal-only workflow output; no files were changed."]),
        ]
    else:
        title = artifact.kind.replace("_", " ").title()
        summary = artifact.summary or f"Workflow output for: {output_context.goal}"
        sections = [
            SkillOutputSection("Summary", body=summary),
            SkillOutputSection(
                "Workflow Trace",
                items=[
                    f"{index}. {step.skill_name} produced {step.output_artifact or 'general_skill_report'}"
                    for index, step in enumerate(workflow_plan.steps, start=1)
                ],
            ),
        ]
    return SkillOutput(
        output_kind=artifact.kind,
        title=title,
        summary=summary,
        sections=sections,
        warnings=[],
        files_referenced=list(output_context.files_considered),
        mutations_applied=False,
    )
