from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


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
    pending_context: dict[str, Any] = field(default_factory=dict)
    last_execution_result: ExecutionResult | None = None

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

    def start_goal(self, *, goal: str, route: str) -> None:
        if self.has_active_goal or self.current_state != LifecycleState.IDLE:
            raise ActiveGoalConflictError(
                f"Cannot start goal {goal!r} while state={self.current_state.value} active_goal={self.active_goal!r}"
            )
        self.active_goal = goal
        self.last_route = route
        self.error_message = None
        self.transition_to(LifecycleState.INTENT_RECEIVED)

    def finish_cycle(self) -> None:
        self.active_goal = None
        self.clear_pending()
        self.transition_to(LifecycleState.IDLE)

    def clear_pending(self) -> None:
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.pending_context = {}

    def reset(self) -> None:
        self.current_state = LifecycleState.IDLE
        self.active_goal = None
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.error_message = None
        self.pending_context = {}

    def reset_to_idle_preserving_history(self) -> None:
        self.current_state = LifecycleState.IDLE
        self.active_goal = None
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.pending_context = {}
