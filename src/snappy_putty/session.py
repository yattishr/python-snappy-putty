from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class LifecycleState(str, Enum):
    IDLE = "IDLE"
    INTENT_RECEIVED = "INTENT_RECEIVED"
    PLANNING = "PLANNING"
    CLARIFICATION = "CLARIFICATION"
    CONFIRMATION = "CONFIRMATION"
    EXECUTING = "EXECUTING"
    REFLECTING = "REFLECTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


TERMINAL_LIFECYCLE_STATES = {
    LifecycleState.COMPLETED,
    LifecycleState.FAILED,
    LifecycleState.CANCELLED,
    LifecycleState.BLOCKED,
}

_ALLOWED_LIFECYCLE_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.IDLE: {LifecycleState.INTENT_RECEIVED},
    LifecycleState.INTENT_RECEIVED: {
        LifecycleState.PLANNING,
        LifecycleState.REFLECTING,
        LifecycleState.CANCELLED,
        LifecycleState.FAILED,
        LifecycleState.BLOCKED,
    },
    LifecycleState.PLANNING: {
        LifecycleState.CLARIFICATION,
        LifecycleState.CONFIRMATION,
        LifecycleState.EXECUTING,
        LifecycleState.REFLECTING,
        LifecycleState.FAILED,
        LifecycleState.BLOCKED,
    },
    LifecycleState.CLARIFICATION: {
        LifecycleState.PLANNING,
        LifecycleState.REFLECTING,
        LifecycleState.CANCELLED,
        LifecycleState.FAILED,
    },
    LifecycleState.CONFIRMATION: {
        LifecycleState.EXECUTING,
        LifecycleState.REFLECTING,
        LifecycleState.CANCELLED,
        LifecycleState.FAILED,
        LifecycleState.BLOCKED,
    },
    LifecycleState.EXECUTING: {LifecycleState.REFLECTING, LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.CANCELLED, LifecycleState.BLOCKED},
    LifecycleState.REFLECTING: {
        LifecycleState.COMPLETED,
        LifecycleState.FAILED,
        LifecycleState.CANCELLED,
        LifecycleState.BLOCKED,
    },
    LifecycleState.COMPLETED: {LifecycleState.IDLE},
    LifecycleState.FAILED: {LifecycleState.IDLE},
    LifecycleState.CANCELLED: {LifecycleState.IDLE},
    LifecycleState.BLOCKED: {LifecycleState.IDLE},
}


class InvalidLifecycleTransition(ValueError):
    """Raised when session lifecycle moves through an unsupported edge."""


class ActiveGoalConflictError(RuntimeError):
    """Raised when a new goal is started while another goal is still active."""


OperationExecutionStatus = Literal["applied", "skipped", "failed"]
ExecutionStatus = Literal["completed", "failed", "cancelled", "blocked"]
WorkflowState = Literal["INTENT_RECEIVED", "PLANNING", "CLARIFICATION", "CONFIRMATION", "EXECUTING", "REFLECTING"]
ClarificationInputKind = Literal["path", "choice", "answer"]
ConfirmationStage = Literal["apply", "overwrite", "limit"]


@dataclass(frozen=True)
class ExecutionOperation:
    action: str
    status: OperationExecutionStatus
    message: str


@dataclass(frozen=True)
class ExecutionResult:
    goal: str
    status: ExecutionStatus
    summary: str
    operations: tuple[ExecutionOperation, ...] = ()
    error: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClarificationContext:
    kind: Literal["clarification"] = "clarification"
    source_path: str | None = None
    expected_input: ClarificationInputKind = "answer"
    action: str | None = None
    base_intent: str | None = None
    workspace_root: str | None = None
    prompt_kind: str | None = None


@dataclass(frozen=True)
class ConfirmationContext:
    kind: Literal["confirmation"] = "confirmation"
    operation_count: int = 0
    overwrite_detected: bool = False
    stage: ConfirmationStage = "apply"
    workspace_root: str | None = None
    allow_overwrite: bool = False
    allow_excess_ops: bool = False
    excess_ops: bool = False


WorkflowContext = ClarificationContext | ConfirmationContext


@dataclass(frozen=True)
class ActiveWorkflowSnapshot:
    workflow_id: str
    state: WorkflowState
    goal: str | None
    route: str | None
    pending_question: str | None
    pending_plan_summary: str | None
    awaiting_confirmation: bool
    control_state: str | None
    context: WorkflowContext | None


@dataclass
class SessionState:
    agent_mode: str | None = None
    current_state: LifecycleState = LifecycleState.IDLE
    active_goal: str | None = None
    last_route: str | None = None
    last_result: str | None = None
    pending_question: Any | None = None
    pending_plan: Any | None = None
    awaiting_confirmation: bool = False
    last_completed_goal: str | None = None
    last_cancelled_goal: str | None = None
    last_failed_goal: str | None = None
    last_blocked_goal: str | None = None
    error_message: str | None = None
    pending_context: WorkflowContext | None = None
    last_execution_result: ExecutionResult | None = None
    active_workflow: ActiveWorkflowSnapshot | None = None

    @property
    def has_active_goal(self) -> bool:
        return bool(self.active_goal)

    def is_terminal_state(self) -> bool:
        return self.current_state in TERMINAL_LIFECYCLE_STATES

    def can_transition(self, new_state: LifecycleState) -> bool:
        return new_state in _ALLOWED_LIFECYCLE_TRANSITIONS.get(self.current_state, set())

    def transition_to(self, new_state: LifecycleState) -> None:
        if self.current_state == new_state:
            return
        if not self.can_transition(new_state):
            raise InvalidLifecycleTransition(f"Invalid lifecycle transition: {self.current_state.value} -> {new_state.value}")
        self.current_state = new_state
        self.sync_active_workflow()

    def start_goal(self, *, goal: str, route: str) -> None:
        if self.has_active_goal or self.current_state != LifecycleState.IDLE:
            raise ActiveGoalConflictError(
                f"Cannot start goal {goal!r} while state={self.current_state.value} active_goal={self.active_goal!r}"
            )
        self.active_goal = goal
        self.last_route = route
        self.error_message = None
        self.begin_workflow(goal=goal, route=route)
        self.transition_to(LifecycleState.INTENT_RECEIVED)

    def finish_cycle(self) -> None:
        self.active_goal = None
        self.clear_pending()
        self.transition_to(LifecycleState.IDLE)
        self.clear_active_workflow()

    def clear_pending(self) -> None:
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.pending_context = None
        self.sync_active_workflow()

    def reset(self) -> None:
        self.current_state = LifecycleState.IDLE
        self.active_goal = None
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.error_message = None
        self.pending_context = None
        self.clear_active_workflow()

    def reset_to_idle_preserving_history(self) -> None:
        self.current_state = LifecycleState.IDLE
        self.active_goal = None
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.pending_context = None
        self.clear_active_workflow()

    def begin_workflow(self, *, goal: str, route: str) -> None:
        self.active_workflow = ActiveWorkflowSnapshot(
            workflow_id=uuid4().hex,
            state="INTENT_RECEIVED",
            goal=goal,
            route=route,
            pending_question=None,
            pending_plan_summary=None,
            awaiting_confirmation=False,
            control_state="allowed",
            context=None,
        )

    def update_workflow_context(self, context: WorkflowContext | None) -> None:
        self.pending_context = context
        self.sync_active_workflow()

    def sync_active_workflow(self) -> None:
        if self.current_state == LifecycleState.IDLE or not self.active_goal:
            return
        if self.active_workflow is None:
            self.begin_workflow(goal=self.active_goal, route=self.last_route or "")
        workflow_state = _workflow_state_from_lifecycle(self.current_state)
        if workflow_state is None:
            return
        self.active_workflow = ActiveWorkflowSnapshot(
            workflow_id=self.active_workflow.workflow_id,
            state=workflow_state,
            goal=self.active_goal,
            route=self.last_route,
            pending_question=_pending_question_snapshot(self.pending_question),
            pending_plan_summary=_pending_plan_summary(self.pending_plan),
            awaiting_confirmation=self.awaiting_confirmation,
            control_state=_control_state_from_snapshot(self),
            context=self.pending_context,
        )

    def clear_active_workflow(self) -> None:
        self.active_workflow = None


def _pending_question_snapshot(question: Any | None) -> str | None:
    if question is None:
        return None
    if isinstance(question, dict):
        message = question.get("message") or question.get("prompt")
        return str(message) if message else str(question)
    return str(question)


def _pending_plan_summary(plan: Any | None) -> str | None:
    if plan is None:
        return None
    if hasattr(plan, "ops"):
        ops = getattr(plan, "ops", ())
        return f"filesystem plan with {len(ops)} op(s)"
    if isinstance(plan, list):
        return f"agent plan with {len(plan)} step(s)"
    return str(plan)


def _workflow_state_from_lifecycle(state: LifecycleState) -> WorkflowState | None:
    mapping: dict[LifecycleState, WorkflowState] = {
        LifecycleState.INTENT_RECEIVED: "INTENT_RECEIVED",
        LifecycleState.PLANNING: "PLANNING",
        LifecycleState.CLARIFICATION: "CLARIFICATION",
        LifecycleState.CONFIRMATION: "CONFIRMATION",
        LifecycleState.EXECUTING: "EXECUTING",
        LifecycleState.REFLECTING: "REFLECTING",
    }
    return mapping.get(state)


def _control_state_from_snapshot(state: SessionState) -> str:
    if state.awaiting_confirmation:
        return "awaiting_confirm"
    if state.current_state == LifecycleState.BLOCKED:
        return "blocked"
    if state.current_state == LifecycleState.FAILED and state.error_message and "Operation blocked by rule:" in state.error_message:
        return "blocked"
    return "allowed"
