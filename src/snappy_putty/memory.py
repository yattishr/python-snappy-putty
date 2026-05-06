from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from snappy_putty.history import append_history_event
from snappy_putty.project_inspector import ProjectSnapshot, inspect_project, is_project_snapshot_valid, snapshot_from_payload, snapshot_to_payload
from snappy_putty.active_planner import GroundedPlan, invalidate_plan, plan_from_payload, plan_to_payload


logger = logging.getLogger(__name__)


def memory_dir(root: Path) -> Path:
    return root.resolve() / ".snappy" / "memory"


def session_path(root: Path) -> Path:
    return memory_dir(root) / "session.json"


def project_snapshot_path(root: Path) -> Path:
    return memory_dir(root) / "project_snapshot.json"


def history_path(root: Path) -> Path:
    return memory_dir(root) / "history.md"


def load_project_snapshot(root: Path) -> ProjectSnapshot | None:
    path = project_snapshot_path(root)
    if not path.is_file():
        return None
    payload = _read_json(path)
    if payload is None:
        logger.warning("Stored project snapshot was invalid and was ignored.")
        return None
    try:
        snapshot = snapshot_from_payload(payload)
    except ValueError as exc:
        logger.warning("Stored project snapshot was invalid and was ignored: %s", exc)
        return None
    if not is_project_snapshot_valid(root, snapshot):
        logger.warning("Stored project snapshot was invalid and was ignored.")
        return None
    return snapshot


def save_project_snapshot(root: Path, snapshot: ProjectSnapshot) -> None:
    payload = snapshot_to_payload(snapshot)
    _write_json(project_snapshot_path(root), payload)


def refresh_project_snapshot(root: Path) -> ProjectSnapshot:
    append_history_event(root, "project inspection started", {"Mode": "active"})
    snapshot = inspect_project(root)
    save_project_snapshot(root, snapshot)
    append_history_event(
        root,
        "project snapshot created",
        {
            "Snapshot ID": snapshot.snapshot_id,
            "Root": snapshot.root_path,
            "Files sampled": snapshot.sampled_files,
        },
    )
    append_history_event(root, "project inspection completed", {"Snapshot ID": snapshot.snapshot_id})
    return snapshot


def ensure_project_snapshot(root: Path, *, force_refresh: bool = False) -> ProjectSnapshot:
    if force_refresh:
        return refresh_project_snapshot(root)

    snapshot = load_project_snapshot(root)
    if snapshot is not None:
        append_history_event(root, "project snapshot reused", {"Snapshot ID": snapshot.snapshot_id})
        return snapshot
    if project_snapshot_path(root).is_file():
        append_history_event(root, "project snapshot invalidated", {"Reason": "Stored snapshot was stale or malformed"})
    return refresh_project_snapshot(root)


def load_grounded_plan(root: Path) -> GroundedPlan | None:
    payload = _session_payload(root)
    raw_plan = payload.get("last_plan") or payload.get("current_plan")
    if raw_plan is None:
        return None
    try:
        return plan_from_payload(raw_plan)
    except ValueError as exc:
        logger.warning("Stored grounded plan was invalid and was ignored: %s", exc)
        return None


def save_grounded_plan(root: Path, plan: GroundedPlan, snapshot: ProjectSnapshot | None = None) -> None:
    payload = _session_payload(root)
    payload["current_plan"] = plan_to_payload(plan)
    payload["last_plan"] = plan_to_payload(plan)
    payload.pop("last_skipped_goal", None)
    payload.pop("last_skip_reason", None)
    if snapshot is not None:
        payload["project_snapshot"] = snapshot_to_payload(snapshot)
    _write_json(session_path(root), payload)


def invalidate_grounded_plan(root: Path, plan: GroundedPlan, reason: str) -> GroundedPlan:
    updated = invalidate_plan(plan, reason=reason)
    save_grounded_plan(root, updated)
    append_history_event(
        root,
        "grounded plan invalidated",
        {
            "Plan ID": plan.plan_id,
            "Reason": reason,
        },
    )
    return updated


def load_current_snapshot_metadata(root: Path) -> ProjectSnapshot | None:
    snapshot = load_project_snapshot(root)
    if snapshot is not None:
        return snapshot
    payload = _session_payload(root)
    raw = payload.get("project_snapshot")
    if raw is None:
        return None
    try:
        snapshot = snapshot_from_payload(raw)
    except ValueError:
        return None
    if not is_project_snapshot_valid(root, snapshot):
        return None
    return snapshot


def load_or_refresh_snapshot(root: Path) -> ProjectSnapshot:
    snapshot = load_project_snapshot(root)
    if snapshot is not None:
        return snapshot
    return refresh_project_snapshot(root)


def snapshot_is_stale(root: Path, snapshot: ProjectSnapshot) -> bool:
    return not is_project_snapshot_valid(root, snapshot)


def save_session_payload(root: Path, updates: dict[str, Any]) -> None:
    payload = _session_payload(root)
    payload.update(updates)
    _write_json(session_path(root), payload)


def load_session_payload(root: Path) -> dict[str, Any]:
    return _session_payload(root)


def save_planning_skipped(
    root: Path,
    *,
    goal: str,
    reason: str,
    snapshot: ProjectSnapshot | None = None,
) -> None:
    payload = _session_payload(root)
    payload.pop("current_plan", None)
    payload["last_skipped_goal"] = goal
    payload["last_skip_reason"] = reason
    if snapshot is not None:
        payload["project_snapshot"] = snapshot_to_payload(snapshot)
    _write_json(session_path(root), payload)


def _session_payload(root: Path) -> dict[str, Any]:
    path = session_path(root)
    if not path.is_file():
        return {}
    payload = _read_json(path)
    return payload or {}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)
