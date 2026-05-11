# Snappy M5.8 — Minimal Harness Foundation

## Goal

Add a thin execution harness foundation before M6 Skills.

This is NOT the full verification harness.

M5.8 should give Snappy enough structure to safely record future executions without adding autonomy, retries, skill plugins, or complex evaluation.

Core principle:

```text
Plan interaction is not enough.
M6 skills need a minimal run/step/action structure to stand on.
```

---

## Scope

Implement only:

```text
1. Structured Run Object
2. Step Result Recording
3. Tool/Action Envelope
4. Execution Lifecycle States
5. Completion Summary
```

Do not build the full M7 verification harness yet.

---

## Non-Goals

Do NOT implement:

```text
replay engine
parallel execution
graph execution
autonomous retry loops
semantic diffing
benchmark harness
artifact lineage DAGs
sandbox orchestration
skill installation
plugin system
multi-agent coordination
```

Those belong later.

---

## 1. Structured Run Object

Add a run record for any workflow that reaches execution or simulated execution.

Recommended storage:

```text
.snappy/runs/
```

Example file:

```text
.snappy/runs/run_20260511_001.json
```

Schema:

```json
{
  "run_id": "run_20260511_001",
  "goal": "help me improve this CLI",
  "mode": "active",
  "state": "RUNNING",
  "plan_id": "plan_llm-assisted-improve-the",
  "snapshot_id": "snap_abc123",
  "started_at": "2026-05-11T18:20:00+02:00",
  "completed_at": null,
  "result": null,
  "steps": [],
  "summary": null
}
```

Valid run result values:

```text
success
failed
cancelled
skipped
```

---

## 2. Step Result Recording

Add a lightweight structure for recording step outcomes.

Schema:

```json
{
  "step_number": 1,
  "description": "Inspect CLI entrypoint",
  "action": "read_file",
  "status": "success",
  "started_at": "2026-05-11T18:20:03+02:00",
  "completed_at": "2026-05-11T18:20:04+02:00",
  "files_touched": ["src/taskcli/main.py"],
  "summary": "Read CLI entrypoint successfully.",
  "error": null
}
```

Valid step status values:

```text
pending
running
success
failed
skipped
cancelled
```

For M5.8, step recording may be used by direct safe operations and future execution stubs.

---

## 3. Tool / Action Envelope

Add a minimal action envelope used before any tool/action is executed or simulated.

Schema:

```json
{
  "action_id": "action_001",
  "tool": "read_file",
  "risk": "LOW",
  "scope": "project_only",
  "target": "src/taskcli/main.py",
  "requires_confirmation": false
}
```

Risk values:

```text
LOW
MEDIUM
HIGH
DESTRUCTIVE
```

Scope values:

```text
project_only
read_only
filesystem
git
network
external
```

Initial tool/action examples:

```text
read_file
list_files
inspect_project
inspect_files
git_status
```

This is the seed for M6 Skills.

Do not build a full tool abstraction yet.

---

## 4. Execution Lifecycle States

Add or formalize execution lifecycle states.

Recommended states:

```text
IDLE
PLANNING
PLANNING_SKIPPED
CONFIRMATION
RUNNING
COMPLETED
FAILED
CANCELLED
BLOCKED
```

State semantics:

- `IDLE`: no active workflow.
- `PLANNING`: Snappy is actively generating or validating a plan.
- `PLANNING_SKIPPED`: planning did not occur because unsupported, unsafe, unrelated, or unavailable. Terminal; return to IDLE.
- `CONFIRMATION`: valid plan/action awaits human review or confirmation.
- `RUNNING`: confirmed run/action is executing.
- `COMPLETED`: run/action finished successfully; record outcome then return to IDLE.
- `FAILED`: run/action failed; record outcome then return to IDLE.
- `CANCELLED`: user cancelled workflow; record outcome then return to IDLE.
- `BLOCKED`: policy/risk/destructive intent blocked request; record then return to IDLE.

---

## 5. Completion Summary

At the end of any run, display a concise completion summary.

Example success:

```text
Run completed.

Goal: help me improve this CLI
Result: success
Steps executed: 3
Files inspected: 2
Files modified: 0
Run log: .snappy/runs/run_20260511_001.json
```

Example failure:

```text
Run failed.

Goal: help me improve this CLI
Failed step: 2
Reason: file not found
Run log: .snappy/runs/run_20260511_001.json
```

Example cancellation:

```text
Run cancelled.

Goal: help me improve this CLI
Steps completed before cancellation: 0
Run log: .snappy/runs/run_20260511_001.json
```

---

## History Integration

Append history events for run lifecycle.

### Run started

```md
## <timestamp>
Event: Run started
Run ID: run_20260511_001
Goal: help me improve this CLI
Plan ID: plan_llm-assisted-improve-the
Snapshot ID: snap_abc123
```

### Step recorded

```md
## <timestamp>
Event: Step recorded
Run ID: run_20260511_001
Step: 1
Action: read_file
Status: success
```

### Run completed

```md
## <timestamp>
Event: Run completed
Run ID: run_20260511_001
Result: success
```

---

## CLI / REPL Commands

Add minimal inspection commands for run records:

```text
show last run
show runs
```

### show last run

Displays:

```text
Run ID
Goal
Result
Started
Completed
Steps
Run log path
```

### show runs

Displays last N run records, default 5.

Example:

```text
Run ID                Result      Goal
run_20260511_001      success     help me improve this CLI
run_20260511_002      cancelled   add logging
```

Do not build replay or resume from run logs yet.

---

## Integration Rules

### Planning

Creating a plan does not automatically create a run.

A run starts only when:

```text
- an action is confirmed
- a future execution step begins
- a direct safe operation is explicitly wrapped as a run
```

### Direct Safe Operations

If safe operations create runs:

```text
show file listing
```

should produce:

```text
Run result: success
Action: list_files
Risk: LOW
Files modified: 0
```

But must still not create a plan.

### Destructive Blocks

Blocked destructive requests may log history but do not need a run record unless implementation already has a clean pattern for blocked runs.

If a run is created for a blocked operation:

```text
result = skipped
```

and no action is executed.

---

## Tests Required

Add tests for:

### Test 1 — Run object creation

When a run is started:

```text
- run_id is generated
- run file is created in .snappy/runs/
- goal, mode, snapshot_id, plan_id are recorded
```

### Test 2 — Step result recording

Record a step result and verify:

```text
- status stored
- files_touched stored
- summary stored
- run file updated
```

### Test 3 — Completion summary

Complete a run and verify:

```text
- completed_at set
- result set
- summary generated
- state returns to IDLE
```

### Test 4 — Cancelled run

Cancel active workflow/run and verify:

```text
- result = cancelled
- completed_at set
- state returns to IDLE
```

### Test 5 — show last run

Verify:

```text
show last run
```

prints latest run record.

### Test 6 — show runs

Verify:

```text
show runs
```

prints recent run records.

### Test 7 — Safe operation does not create plan

If safe operations are wrapped as runs, verify:

```text
show file listing
```

creates no plan and does not overwrite last_plan.

---

## Manual Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Manual REPL checks:

```text
show file listing
show last run
show runs
agent mode active
help me improve this CLI
show plan
cancel
show last run
status
```

Expected:

```text
- run logs exist under .snappy/runs/ where appropriate
- safe operations do not create plans
- cancellation is recorded cleanly if a run/workflow exists
- status returns cleanly to IDLE after terminal run outcomes
```

---

## Non-Negotiable Rules

```text
M5.8 must not add autonomy.
M5.8 must not execute unconfirmed writes.
M5.8 must not introduce skill loading.
M5.8 must not create multi-step autonomous loops.
M5.8 is a harness foundation, not the full harness.
```

---

## Acceptance Criteria

M5.8 is complete when:

```text
- Snappy can create structured run records
- Snappy can record step outcomes
- Snappy has a minimal action envelope
- Snappy has explicit execution lifecycle states
- Snappy can show recent run records
- terminal outcomes return cleanly to IDLE
- full test suite passes
```

After M5.8, Snappy may move to M6 Modular Skills System.
