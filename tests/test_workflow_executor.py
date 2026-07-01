from __future__ import annotations

from snappy_putty.skill_outputs import SkillOutputRequest
from snappy_putty.workflow_executor import execute_workflow_plan
from snappy_putty.workflow_models import WorkflowArtifact, WorkflowPlan, WorkflowStep


def _request() -> SkillOutputRequest:
    return SkillOutputRequest(
        goal="help me review this API and generate a PR summary",
        task_intent="code_review",
        selected_skills=["codeguardian-review", "doc-coauthoring"],
        project_relationship="direct_project_work",
        snapshot_id="snap_1",
        files_considered=["server.js"],
        context_summary="test context",
        plan_steps=[],
        skill_context="",
    )


def _workflow() -> WorkflowPlan:
    return WorkflowPlan(
        goal="help me review this API and generate a PR summary",
        workflow_required=True,
        reason="compatible_skill_handoff",
        status="awaiting_confirmation",
        final_output_kind="pr_summary",
        artifacts=[WorkflowArtifact(name="project_context", kind="project_context")],
        steps=[
            WorkflowStep(
                id="step_1",
                skill_name="codeguardian-review",
                purpose="Review API",
                input_artifacts=["project_context"],
                output_artifact="review_report",
            ),
            WorkflowStep(
                id="step_2",
                skill_name="doc-coauthoring",
                purpose="Draft PR summary",
                input_artifacts=["project_context", "review_report"],
                output_artifact="pr_summary",
                depends_on=["step_1"],
            ),
        ],
    )


def test_executes_steps_in_dependency_order_and_passes_artifacts() -> None:
    seen: list[tuple[str, list[str]]] = []

    def runner(step, artifacts, request, skills):
        seen.append((step.skill_name, [artifact.name for artifact in artifacts]))
        return WorkflowArtifact(name=step.output_artifact or "general", kind=step.output_artifact or "general", producer_step_id=step.id)

    result = execute_workflow_plan(_workflow(), _request(), step_runner=runner)

    assert result.success is True
    assert [name for name, _ in seen] == ["codeguardian-review", "doc-coauthoring"]
    assert "review_report" in seen[1][1]
    assert result.final_output_kind == "pr_summary"
    assert result.final_output is not None
    assert result.final_output.output_kind == "pr_summary"


def test_failed_step_halts_workflow() -> None:
    seen: list[str] = []

    def runner(step, artifacts, request, skills):
        seen.append(step.skill_name)
        if step.skill_name == "codeguardian-review":
            raise RuntimeError("review failed")
        return WorkflowArtifact(name=step.output_artifact or "general", kind=step.output_artifact or "general", producer_step_id=step.id)

    result = execute_workflow_plan(_workflow(), _request(), step_runner=runner)

    assert result.success is False
    assert seen == ["codeguardian-review"]
    assert result.workflow_plan.status == "failed"
    assert "review failed" in result.summary

