from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal


WorkflowStatus = Literal[
    "not_required",
    "awaiting_confirmation",
    "ready",
    "running",
    "completed",
    "failed",
]


@dataclass(frozen=True)
class WorkflowArtifact:
    name: str
    kind: str
    producer_step_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    skill_name: str
    purpose: str
    input_artifacts: list[str] = field(default_factory=list)
    output_artifact: str | None = None
    depends_on: list[str] = field(default_factory=list)
    risk: str = "LOW"
    status: str = "pending"


@dataclass(frozen=True)
class WorkflowPlan:
    goal: str
    workflow_required: bool
    reason: str
    steps: list[WorkflowStep] = field(default_factory=list)
    final_output_kind: str = "general_skill_report"
    artifacts: list[WorkflowArtifact] = field(default_factory=list)
    status: WorkflowStatus = "not_required"

    def with_status(self, status: WorkflowStatus) -> WorkflowPlan:
        return replace(self, status=status)

