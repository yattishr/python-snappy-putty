from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from snappy_putty.fs_models import FsPlan
from snappy_putty.models import PlanStep

logger = logging.getLogger(__name__)

_SESSION_MEMORY_DIR = Path(".snappy") / "memory"
_SESSION_MEMORY_FILE = _SESSION_MEMORY_DIR / "session.json"


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
    pending_question_data: dict[str, Any] | str | None = None
    pending_plan_data: dict[str, Any] | list[dict[str, Any]] | None = None


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
            pending_question_data=_pending_question_data(self.pending_question),
            pending_plan_data=_pending_plan_data(self.pending_plan),
        )
        save_workflow_snapshot(self.active_workflow)

    def clear_active_workflow(self) -> None:
        self.active_workflow = None
        clear_workflow_snapshot()

    def restore_workflow(self, snapshot: ActiveWorkflowSnapshot) -> None:
        self.current_state = _lifecycle_state_from_workflow(snapshot.state)
        self.active_goal = snapshot.goal
        self.last_route = snapshot.route
        self.pending_question = _restore_pending_question(snapshot)
        self.pending_plan = _restore_pending_plan(snapshot)
        self.awaiting_confirmation = snapshot.awaiting_confirmation
        self.pending_context = snapshot.context
        self.error_message = None
        self.active_workflow = snapshot
        save_workflow_snapshot(snapshot)


def _pending_question_snapshot(question: Any | None) -> str | None:
    if question is None:
        return None
    if isinstance(question, dict):
        message = question.get("message") or question.get("prompt")
        return str(message) if message else str(question)
    return str(question)


def _pending_question_data(question: Any | None) -> dict[str, Any] | str | None:
    if question is None:
        return None
    if isinstance(question, dict):
        return dict(question)
    if isinstance(question, str):
        return question
    return None


def _pending_plan_summary(plan: Any | None) -> str | None:
    if plan is None:
        return None
    if hasattr(plan, "ops"):
        ops = getattr(plan, "ops", ())
        return f"filesystem plan with {len(ops)} op(s)"
    if isinstance(plan, list):
        return f"agent plan with {len(plan)} step(s)"
    return str(plan)


def _pending_plan_data(plan: Any | None) -> dict[str, Any] | list[dict[str, Any]] | None:
    if plan is None:
        return None
    if isinstance(plan, FsPlan):
        return plan.model_dump(mode="json")
    if isinstance(plan, list):
        serialized_steps: list[dict[str, Any]] = []
        for item in plan:
            if isinstance(item, PlanStep):
                serialized_steps.append(item.model_dump(mode="json"))
                continue
            if isinstance(item, dict):
                serialized_steps.append(dict(item))
        return serialized_steps
    return None


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


def _lifecycle_state_from_workflow(state: WorkflowState) -> LifecycleState:
    mapping: dict[WorkflowState, LifecycleState] = {
        "INTENT_RECEIVED": LifecycleState.INTENT_RECEIVED,
        "PLANNING": LifecycleState.PLANNING,
        "CLARIFICATION": LifecycleState.CLARIFICATION,
        "CONFIRMATION": LifecycleState.CONFIRMATION,
        "EXECUTING": LifecycleState.EXECUTING,
        "REFLECTING": LifecycleState.REFLECTING,
    }
    return mapping[state]


def _control_state_from_snapshot(state: SessionState) -> str:
    if state.awaiting_confirmation:
        return "awaiting_confirm"
    if state.current_state == LifecycleState.BLOCKED:
        return "blocked"
    if state.current_state == LifecycleState.FAILED and state.error_message and "Operation blocked by rule:" in state.error_message:
        return "blocked"
    return "allowed"


def _restore_pending_question(snapshot: ActiveWorkflowSnapshot) -> Any | None:
    if snapshot.pending_question_data is not None:
        return snapshot.pending_question_data
    return snapshot.pending_question


def _restore_pending_plan(snapshot: ActiveWorkflowSnapshot) -> Any | None:
    raw_plan = snapshot.pending_plan_data
    if raw_plan is None:
        return None
    if isinstance(raw_plan, dict):
        return FsPlan.model_validate(raw_plan)
    if isinstance(raw_plan, list):
        return [PlanStep.model_validate(item) for item in raw_plan]
    return None


def save_workflow_snapshot(snapshot: ActiveWorkflowSnapshot, cwd: Path | None = None) -> None:
    session_path = (cwd or Path.cwd()).resolve() / _SESSION_MEMORY_FILE
    payload = _read_session_payload(session_path)
    payload["workflow"] = _serialize_workflow_snapshot(snapshot)
    _write_session_payload(session_path, payload)


def load_workflow_snapshot(cwd: Path | None = None) -> ActiveWorkflowSnapshot | None:
    session_path = (cwd or Path.cwd()).resolve() / _SESSION_MEMORY_FILE
    if not session_path.is_file():
        return None

    payload = _read_session_payload(session_path, log_errors=True)
    raw_snapshot: Any = payload.get("workflow")
    if raw_snapshot is None and _looks_like_workflow_snapshot(payload):
        raw_snapshot = payload
    if raw_snapshot is None:
        return None

    try:
        return _deserialize_workflow_snapshot(raw_snapshot)
    except ValueError as exc:
        logger.warning("Invalid workflow snapshot: %s", exc)
        clear_workflow_snapshot(cwd)
        return None


def clear_workflow_snapshot(cwd: Path | None = None) -> None:
    session_path = (cwd or Path.cwd()).resolve() / _SESSION_MEMORY_FILE
    if not session_path.exists():
        return

    payload = _read_session_payload(session_path)
    if "workflow" not in payload and not _looks_like_workflow_snapshot(payload):
        return

    if "workflow" in payload:
        payload.pop("workflow", None)
    else:
        payload = {}

    if payload:
        _write_session_payload(session_path, payload)
        return

    try:
        session_path.unlink()
    except FileNotFoundError:
        return


def _serialize_workflow_snapshot(snapshot: ActiveWorkflowSnapshot) -> dict[str, Any]:
    payload = {
        "workflow_id": snapshot.workflow_id,
        "state": snapshot.state,
        "goal": snapshot.goal,
        "route": snapshot.route,
        "pending_question": snapshot.pending_question,
        "pending_plan_summary": snapshot.pending_plan_summary,
        "awaiting_confirmation": snapshot.awaiting_confirmation,
        "control_state": snapshot.control_state,
        "context": asdict(snapshot.context) if snapshot.context is not None else None,
        "pending_question_data": snapshot.pending_question_data,
        "pending_plan_data": snapshot.pending_plan_data,
    }
    return payload


def _deserialize_workflow_snapshot(raw_snapshot: Any) -> ActiveWorkflowSnapshot:
    if not isinstance(raw_snapshot, dict):
        raise ValueError("workflow snapshot must be a JSON object")

    state = raw_snapshot.get("state")
    if state not in {"INTENT_RECEIVED", "PLANNING", "CLARIFICATION", "CONFIRMATION", "EXECUTING", "REFLECTING"}:
        raise ValueError(f"unsupported workflow state: {state!r}")

    workflow_id = raw_snapshot.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("workflow_id must be a non-empty string")

    pending_question = raw_snapshot.get("pending_question")
    if pending_question is not None and not isinstance(pending_question, str):
        raise ValueError("pending_question must be a string when present")

    pending_plan_summary = raw_snapshot.get("pending_plan_summary")
    if pending_plan_summary is not None and not isinstance(pending_plan_summary, str):
        raise ValueError("pending_plan_summary must be a string when present")

    awaiting_confirmation = raw_snapshot.get("awaiting_confirmation")
    if not isinstance(awaiting_confirmation, bool):
        raise ValueError("awaiting_confirmation must be a boolean")

    context = _deserialize_workflow_context(raw_snapshot.get("context"))
    question_data = _deserialize_question_data(raw_snapshot.get("pending_question_data"))
    plan_data = _deserialize_plan_data(raw_snapshot.get("pending_plan_data"))

    snapshot = ActiveWorkflowSnapshot(
        workflow_id=workflow_id,
        state=state,
        goal=_coerce_optional_string(raw_snapshot.get("goal"), field_name="goal"),
        route=_coerce_optional_string(raw_snapshot.get("route"), field_name="route"),
        pending_question=pending_question,
        pending_plan_summary=pending_plan_summary,
        awaiting_confirmation=awaiting_confirmation,
        control_state=_coerce_optional_string(raw_snapshot.get("control_state"), field_name="control_state"),
        context=context,
        pending_question_data=question_data,
        pending_plan_data=plan_data,
    )
    _validate_workflow_snapshot(snapshot)
    return snapshot


def _deserialize_workflow_context(raw_context: Any) -> WorkflowContext | None:
    if raw_context is None:
        return None
    if not isinstance(raw_context, dict):
        raise ValueError("context must be an object when present")

    kind = raw_context.get("kind")
    if kind == "clarification":
        return ClarificationContext(
            source_path=_coerce_optional_string(raw_context.get("source_path"), field_name="context.source_path"),
            expected_input=_coerce_literal(
                raw_context.get("expected_input"),
                {"path", "choice", "answer"},
                field_name="context.expected_input",
            ),
            action=_coerce_optional_string(raw_context.get("action"), field_name="context.action"),
            base_intent=_coerce_optional_string(raw_context.get("base_intent"), field_name="context.base_intent"),
            workspace_root=_coerce_optional_string(raw_context.get("workspace_root"), field_name="context.workspace_root"),
            prompt_kind=_coerce_optional_string(raw_context.get("prompt_kind"), field_name="context.prompt_kind"),
        )
    if kind == "confirmation":
        return ConfirmationContext(
            operation_count=_coerce_int(raw_context.get("operation_count"), field_name="context.operation_count"),
            overwrite_detected=_coerce_bool(raw_context.get("overwrite_detected"), field_name="context.overwrite_detected"),
            stage=_coerce_literal(raw_context.get("stage"), {"apply", "overwrite", "limit"}, field_name="context.stage"),
            workspace_root=_coerce_optional_string(raw_context.get("workspace_root"), field_name="context.workspace_root"),
            allow_overwrite=_coerce_bool(raw_context.get("allow_overwrite"), field_name="context.allow_overwrite"),
            allow_excess_ops=_coerce_bool(raw_context.get("allow_excess_ops"), field_name="context.allow_excess_ops"),
            excess_ops=_coerce_bool(raw_context.get("excess_ops"), field_name="context.excess_ops"),
        )
    raise ValueError(f"unsupported workflow context kind: {kind!r}")


def _deserialize_question_data(raw_question: Any) -> dict[str, Any] | str | None:
    if raw_question is None or isinstance(raw_question, str):
        return raw_question
    if isinstance(raw_question, dict):
        return dict(raw_question)
    raise ValueError("pending_question_data must be a string, object, or null")


def _deserialize_plan_data(raw_plan: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
    if raw_plan is None:
        return None
    if isinstance(raw_plan, dict):
        FsPlan.model_validate(raw_plan)
        return dict(raw_plan)
    if isinstance(raw_plan, list):
        validated_steps: list[dict[str, Any]] = []
        for item in raw_plan:
            if not isinstance(item, dict):
                raise ValueError("pending_plan_data list items must be objects")
            validated_steps.append(PlanStep.model_validate(item).model_dump(mode="json"))
        return validated_steps
    raise ValueError("pending_plan_data must be an object, list, or null")


def _validate_workflow_snapshot(snapshot: ActiveWorkflowSnapshot) -> None:
    if snapshot.goal is None or not snapshot.goal.strip():
        raise ValueError("goal must be present")
    if snapshot.route is None or not snapshot.route.strip():
        raise ValueError("route must be present")

    if snapshot.state == "CLARIFICATION":
        if not snapshot.pending_question:
            raise ValueError("clarification workflow is missing pending_question")
        if not isinstance(snapshot.context, ClarificationContext):
            raise ValueError("clarification workflow requires ClarificationContext")
        if snapshot.awaiting_confirmation:
            raise ValueError("clarification workflow must not await confirmation")
        return

    if snapshot.state == "CONFIRMATION":
        if not snapshot.awaiting_confirmation:
            raise ValueError("confirmation workflow must await confirmation")
        if not isinstance(snapshot.context, ConfirmationContext):
            raise ValueError("confirmation workflow requires ConfirmationContext")
        if snapshot.pending_plan_data is None:
            raise ValueError("confirmation workflow requires pending_plan_data")
        if not isinstance(snapshot.pending_plan_data, dict):
            raise ValueError("confirmation workflow requires filesystem plan data")
        return

    if snapshot.context is not None:
        raise ValueError("workflow context only persists for clarification or confirmation states")


def _coerce_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when present")
    return value


def _coerce_literal(value: Any, allowed: set[str], *, field_name: str) -> Any:
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}")
    return value


def _coerce_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _coerce_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _read_session_payload(session_path: Path, *, log_errors: bool = False) -> dict[str, Any]:
    if not session_path.is_file():
        return {}
    try:
        raw_payload = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if log_errors:
            logger.warning("Invalid workflow session file: %s", exc)
        return {}
    if not isinstance(raw_payload, dict):
        if log_errors:
            logger.warning("Invalid workflow session file: top-level JSON must be an object")
        return {}
    return raw_payload


def _write_session_payload(session_path: Path, payload: dict[str, Any]) -> None:
    session_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = session_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(session_path)


def _looks_like_workflow_snapshot(payload: dict[str, Any]) -> bool:
    return "workflow_id" in payload and "state" in payload
