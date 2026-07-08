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
    if output_kind == "review_report":
        return _review_report_artifact(step, output_context)
    if output_kind == "pr_summary":
        return _pr_summary_artifact(step, available, output_context)
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


def _review_report_artifact(step: WorkflowStep, output_context: SkillOutputRequest) -> WorkflowArtifact:
    files = _dedupe(output_context.files_considered)
    findings = _review_findings(output_context)
    risks = output_context.plan_risks or [
        "No explicit diff was available, so review findings are grounded in the selected project context and plan only.",
        "Downstream summary quality depends on preserving structured review artifact fields.",
    ]
    plan_context = _plan_context_items(output_context)
    data = {
        "skill": step.skill_name,
        "inputs": list(step.input_artifacts),
        "goal": output_context.goal,
        "summary": output_context.plan_summary or f"Review findings for: {output_context.goal}",
        "findings": findings,
        "files_referenced": files,
        "risks": risks,
        "plan_context": plan_context,
        "test_notes": _test_notes(files),
        "assumptions": list(output_context.plan_assumptions),
    }
    return WorkflowArtifact(
        name="review_report",
        kind="review_report",
        producer_step_id=step.id,
        data=data,
        summary=data["summary"],
    )


def _pr_summary_artifact(
    step: WorkflowStep,
    available: dict[str, WorkflowArtifact],
    output_context: SkillOutputRequest,
) -> WorkflowArtifact:
    review = available.get("review_report")
    review_data = review.data if review is not None else {}
    findings = _string_list(review_data.get("findings")) or ["No concrete review findings were available from upstream artifacts."]
    files = _dedupe([*_string_list(review_data.get("files_referenced")), *output_context.files_considered])
    risks = _string_list(review_data.get("risks")) or ["Validate the generated summary against the actual PR diff before publishing."]
    plan_context = _string_list(review_data.get("plan_context")) or _plan_context_items(output_context)
    test_notes = _string_list(review_data.get("test_notes")) or _test_notes(files)
    summary = _pr_summary_text(output_context, findings, files)
    data = {
        "skill": step.skill_name,
        "inputs": list(step.input_artifacts),
        "goal": output_context.goal,
        "summary": summary,
        "findings": findings,
        "files_referenced": files,
        "risks": risks,
        "plan_context": plan_context,
        "test_notes": test_notes,
        "source_artifacts": [name for name in step.input_artifacts if name in available],
    }
    return WorkflowArtifact(
        name="pr_summary",
        kind="pr_summary",
        producer_step_id=step.id,
        data=data,
        summary=summary,
    )


def _artifact_to_skill_output(
    workflow_plan: WorkflowPlan,
    artifact: WorkflowArtifact,
    output_context: SkillOutputRequest,
) -> SkillOutput:
    if artifact.kind == "pr_summary":
        title = "PR Summary"
        summary = str(artifact.data.get("summary") or artifact.summary or f"PR summary for: {output_context.goal}")
        files = _dedupe([*_string_list(artifact.data.get("files_referenced")), *output_context.files_considered])
        sections = [
            SkillOutputSection("Review Findings", items=_string_list(artifact.data.get("findings")) or ["No concrete review findings were available from upstream artifacts."]),
            SkillOutputSection("Files Referenced", items=files or ["No grounded file references were available."]),
            SkillOutputSection("Risks", items=_string_list(artifact.data.get("risks")) or ["Validate the generated summary against the actual PR diff before publishing."]),
            SkillOutputSection("Testing Notes", items=_string_list(artifact.data.get("test_notes")) or _test_notes(files)),
            SkillOutputSection("Grounded Plan Context", items=_string_list(artifact.data.get("plan_context")) or _plan_context_items(output_context)),
            SkillOutputSection(
                "Workflow Trace",
                items=[
                    f"{index}. {step.skill_name} produced {step.output_artifact or 'general_skill_report'}"
                    for index, step in enumerate(workflow_plan.steps, start=1)
                ],
            ),
        ]
    else:
        title = artifact.kind.replace("_", " ").title()
        summary = artifact.summary or f"Workflow output for: {output_context.goal}"
        sections = [
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
        files_referenced=files if artifact.kind == "pr_summary" else list(output_context.files_considered),
        mutations_applied=False,
    )


def _pr_summary_text(output_context: SkillOutputRequest, findings: list[str], files: list[str]) -> str:
    file_text = ", ".join(f"`{path}`" for path in files[:3]) if files else "the grounded project context"
    subject = output_context.plan_summary or output_context.goal
    first_sentence = subject.rstrip(".")
    return f"{first_sentence}. Upstream review identified {len(findings)} finding(s) covering {file_text}. No files were changed by this workflow."


def _review_findings(output_context: SkillOutputRequest) -> list[str]:
    concrete_risks = [item for item in output_context.plan_risks if "confirm manually" not in item.lower()]
    if concrete_risks:
        return concrete_risks
    if output_context.plan_summary:
        return [output_context.plan_summary]
    return [
        "Review the confirmed workflow paths and artifact contracts before relying on generated output.",
        "Confirm behavior with focused tests around artifact handoff and final rendering.",
    ]


def _plan_context_items(output_context: SkillOutputRequest) -> list[str]:
    items = [_step_description(step) for step in output_context.plan_steps]
    if output_context.context_summary:
        items.append(output_context.context_summary)
    return _dedupe(items) or ["No grounded plan context was available."]


def _test_notes(files: list[str]) -> list[str]:
    referenced = ", ".join(files[:3]) if files else "the affected workflow paths"
    return [
        f"Run focused regression checks around {referenced}.",
        "Confirm the final terminal output contains artifact-derived content and no duplicate summary section.",
    ]


def _step_description(step: object) -> str:
    if isinstance(step, dict):
        return str(step.get("description") or step.get("action") or "Review the grounded workflow step.")
    return str(getattr(step, "description", None) or getattr(step, "action", None) or step)


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
