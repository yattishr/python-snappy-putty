from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    current_goal: str | None = None
    last_route: str | None = None
    last_result: str | None = None
    pending_question: str | None = None
    pending_plan: Any | None = None
    awaiting_confirmation: bool = False
    pending_context: dict[str, Any] = field(default_factory=dict)

    def clear_pending(self) -> None:
        self.pending_question = None
        self.pending_plan = None
        self.awaiting_confirmation = False
        self.pending_context = {}
