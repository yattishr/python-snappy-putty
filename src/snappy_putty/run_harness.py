from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal


RunResult = Literal["success", "failed", "cancelled", "skipped"]
StepStatus = Literal["pending", "running", "success", "failed", "skipped", "cancelled"]
Risk = Literal["LOW", "MEDIUM", "HIGH", "DESTRUCTIVE"]
Scope = Literal["project_only", "read_only", "filesystem", "git", "network", "external"]

RUNNING = "RUNNING"
RUNS_DIR = Path(".snappy") / "runs"


@dataclass(frozen=True)
class ActionEnvelope:
    action_id: str
    tool: str
    risk: Risk
    scope: Scope
    target: str | None = None
    requires_confirmation: bool = False


@dataclass(frozen=True)
class StepResult:
    step_number: int
    description: str
    action: str
    status: StepStatus
    started_at: str
    completed_at: str | None = None
    files_touched: list[str] = field(default_factory=list)
    summary: str | None = None
    error: str | None = None
    action_id: str | None = None


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    goal: str
    mode: str
    state: str
    plan_id: str | None
    snapshot_id: str | None
    started_at: str
    completed_at: str | None = None
    result: RunResult | None = None
    steps: list[StepResult] = field(default_factory=list)
    summary: str | None = None
    actions: list[ActionEnvelope] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def runs_dir(root: Path) -> Path:
    return root / RUNS_DIR


def run_path(root: Path, run_id: str) -> Path:
    return runs_dir(root) / f"{run_id}.json"


def _run_id_prefix() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("run_%Y%m%d")


def next_run_id(root: Path) -> str:
    directory = runs_dir(root)
    prefix = _run_id_prefix()
    if not directory.exists():
        return f"{prefix}_001"
    highest = 0
    for path in directory.glob(f"{prefix}_*.json"):
        suffix = path.stem.removeprefix(f"{prefix}_")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}_{highest + 1:03d}"


def start_run(
    root: Path,
    *,
    goal: str,
    mode: str,
    plan_id: str | None = None,
    snapshot_id: str | None = None,
) -> RunRecord:
    record = RunRecord(
        run_id=next_run_id(root),
        goal=goal,
        mode=mode,
        state=RUNNING,
        plan_id=plan_id,
        snapshot_id=snapshot_id,
        started_at=now_iso(),
    )
    save_run(root, record)
    return record


def save_run(root: Path, record: RunRecord) -> None:
    directory = runs_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    run_path(root, record.run_id).write_text(json.dumps(run_to_payload(record), indent=2) + "\n", encoding="utf-8")


def load_run(root: Path, run_id: str) -> RunRecord:
    return run_from_payload(json.loads(run_path(root, run_id).read_text(encoding="utf-8")))


def list_runs(root: Path, *, limit: int | None = None) -> list[RunRecord]:
    directory = runs_dir(root)
    if not directory.exists():
        return []
    records: list[RunRecord] = []
    for path in sorted(directory.glob("run_*.json"), reverse=True):
        try:
            records.append(run_from_payload(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if limit is not None and len(records) >= limit:
            break
    return records


def load_last_run(root: Path) -> RunRecord | None:
    records = list_runs(root, limit=1)
    return records[0] if records else None


def add_action(root: Path, record: RunRecord, action: ActionEnvelope) -> RunRecord:
    updated = replace(record, actions=[*record.actions, action])
    save_run(root, updated)
    return updated


def record_step(root: Path, record: RunRecord, step: StepResult) -> RunRecord:
    updated = replace(record, steps=[*record.steps, step])
    save_run(root, updated)
    return updated


def complete_run(root: Path, record: RunRecord, *, result: RunResult, summary: str | None = None) -> RunRecord:
    updated = replace(
        record,
        state=result.upper(),
        completed_at=now_iso(),
        result=result,
        summary=summary or _summary_for(record, result=result),
    )
    save_run(root, updated)
    return updated


def run_to_payload(record: RunRecord) -> dict[str, Any]:
    return asdict(record)


def run_from_payload(payload: dict[str, Any]) -> RunRecord:
    steps = [StepResult(**item) for item in payload.get("steps", [])]
    actions = [ActionEnvelope(**item) for item in payload.get("actions", [])]
    return RunRecord(
        run_id=str(payload["run_id"]),
        goal=str(payload["goal"]),
        mode=str(payload["mode"]),
        state=str(payload["state"]),
        plan_id=payload.get("plan_id"),
        snapshot_id=payload.get("snapshot_id"),
        started_at=str(payload["started_at"]),
        completed_at=payload.get("completed_at"),
        result=payload.get("result"),
        steps=steps,
        summary=payload.get("summary"),
        actions=actions,
    )


def _summary_for(record: RunRecord, *, result: RunResult) -> str:
    return f"Run {result}: {len(record.steps)} step(s) recorded."
