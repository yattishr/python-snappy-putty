from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    IDLE = "IDLE"
    INTENT_RECEIVED = "INTENT_RECEIVED"
    PLANNING = "PLANNING"
    CLARIFICATION = "CLARIFICATION"
    CONFIRMATION = "CONFIRMATION"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class SessionState:
    current_state: LifecycleState = LifecycleState.IDLE
    active_goal: str | None = None
    last_route: str | None = None
    last_result: str | None = None
    pending_question: str | None = None
    pending_plan: Any | None = None
    awaiting_confirmation: bool = False
    last_completed_goal: str | None = None
    last_cancelled_goal: str | None = None
    last_failed_goal: str | None = None
    error_message: str | None = None
    pending_context: dict[str, Any] = field(default_factory=dict)

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
