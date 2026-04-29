# Snappy PuTTy — M5 Active Mode v1 Implementation Plan

## Milestone

```text
M5 — Active Mode v1
  - read-only project inspection / Basic Codebase Inspection
  - bounded planning from actual files
  - no unsupervised writes
  - cached ProjectSnapshot memory
  - session-bound grounded plans
  - append-only history.md trace log
```

## Purpose

M5 is the milestone where Snappy becomes meaningfully project-aware without becoming dangerously autonomous.

The goal is **not** to let Snappy freely edit code. The goal is to let Snappy inspect the real repository, understand the basic shape of the project, and generate plans that are grounded in actual files.

Think of this as:

```text
Snappy can look.
Snappy can reason.
Snappy can propose.
Snappy cannot write without supervision.
```

This milestone must preserve the existing control-layer guarantees:

```text
- one workflow at a time
- state machine remains authoritative
- strict confirmation remains mandatory for mutations
- no path bypasses the planner / confirmation / executor flow
- no unsupervised writes
```

---

# 1. High-Level Design

## Active Mode v1 Flow

```text
User Request
   ↓
Intent Router
   ↓
Active Mode Planner
   ↓
Project Inspector
   ↓
ProjectSnapshot
   ↓
Grounded Plan
   ↓
Session Memory
   ↓
History Log
   ↓
Confirmation Gate, only if mutation is ever proposed
```

## Core Rule

```text
Active Mode may inspect.
Active Mode may summarize.
Active Mode may create a grounded plan.
Active Mode may store that plan in session memory.
Active Mode may not write files without explicit user confirmation.
```

---

# 2. Required New Concepts

## 2.1 ProjectSnapshot

A `ProjectSnapshot` is a cached, read-only representation of the current project.

It should capture enough project context to support grounded planning, but it should not attempt deep static analysis yet.

### Suggested fields

```python
@dataclass
class ProjectSnapshot:
    snapshot_id: str
    root_path: str
    created_at: str
    root_hash: str | None
    git_branch: str | None
    git_status_summary: str | None
    languages: list[str]
    package_managers: list[str]
    frameworks: list[str]
    config_files: list[str]
    docs: list[str]
    test_files: list[str]
    source_files: list[str]
    entry_points: list[str]
    file_count: int
    sampled_files: list[str]
```

Keep the object simple. This is binoculars, not X-ray vision.

## 2.2 GroundedPlan

A `GroundedPlan` is a plan generated from actual inspected files.

It must be tied to the snapshot used to create it.

### Suggested fields

```python
@dataclass
class GroundedPlan:
    plan_id: str
    goal: str
    created_at: str
    based_on_snapshot_id: str
    inspected_files: list[str]
    referenced_files: list[str]
    steps: list[str]
    risks: list[str]
    status: str  # draft | awaiting_confirmation | rejected | completed | invalidated
```

## 2.3 Memory Files

M5 should introduce or extend the following files:

```text
.snappy/
  memory/
    session.json
    project_snapshot.json
    history.md
```

### Responsibility split

```text
session.json
  Active workflow state, active goal, pending question, current plan.

project_snapshot.json
  Cached inspection context. Short-lived. Must be invalidated aggressively.

history.md
  Append-only human-readable audit trail. Useful for traceability and observability.
```

Important:

```text
history.md is not source-of-truth.
history.md must never drive execution decisions.
```

History is the flight recorder, not the pilot.

---

# 3. ProjectSnapshot Memory Strategy

## Store snapshot here

```text
.snappy/memory/project_snapshot.json
```

## Snapshot should include metadata

```json
{
  "snapshot_id": "snap_abc123",
  "created_at": "2026-04-29T15:42:00+02:00",
  "root_path": "/path/to/project",
  "root_hash": "...",
  "git_branch": "main",
  "git_status_summary": "clean",
  "languages": ["python"],
  "package_managers": ["pip"],
  "frameworks": ["typer", "rich", "pytest"],
  "config_files": ["pyproject.toml"],
  "docs": ["README.md"],
  "test_files": ["tests/test_state_machine.py"],
  "source_files": ["src/snappy_putty/cli.py"],
  "entry_points": ["src/snappy_putty/cli.py"],
  "file_count": 84,
  "sampled_files": ["README.md", "pyproject.toml", "src/snappy_putty/cli.py"]
}
```

## Invalidation rules

Recompute the snapshot when any of the following are true:

```text
- project_snapshot.json does not exist
- snapshot is malformed
- snapshot root_path differs from current project root
- git branch changed
- git status summary changed
- root hash changed
- snapshot is older than the configured TTL
- user explicitly runs inspect project
```

Suggested TTL for M5:

```text
10 minutes
```

Do not over-engineer file hashing. A cheap project fingerprint is good enough for M5.

Suggested `root_hash` inputs:

```text
- relative file paths
- file mtimes
- file sizes
- selected config file contents if safe and small
```

Ignore noisy folders:

```text
.git/
.venv/
venv/
node_modules/
__pycache__/
.pytest_cache/
.mypy_cache/
dist/
build/
.next/
.cache/
```

---

# 4. Plan Memory Strategy

Plans should be saved in `session.json`, not global memory.

## Example

```json
{
  "active_goal": "Add logging to the CLI",
  "state": "CONFIRMATION",
  "last_route": "active_plan",
  "current_plan": {
    "plan_id": "plan_123",
    "goal": "Add logging to the CLI",
    "created_at": "2026-04-29T15:45:00+02:00",
    "based_on_snapshot_id": "snap_abc123",
    "inspected_files": [
      "src/snappy_putty/cli.py",
      "src/snappy_putty/session.py"
    ],
    "referenced_files": [
      "tests/test_session_repl_subprocess.py"
    ],
    "steps": [
      "Inspect existing CLI output patterns.",
      "Identify where structured logging would fit.",
      "Propose minimal logging helper.",
      "Add tests after confirmation only."
    ],
    "risks": [
      "Logging could clutter current terminal UX if not gated."
    ],
    "status": "awaiting_confirmation"
  }
}
```

## Critical rule

```text
A plan is valid only if its based_on_snapshot_id matches the currently valid ProjectSnapshot.
```

If the snapshot is invalidated, the plan must be marked invalidated.

Expected UX:

```text
⚠️ Stored plan was based on an outdated project snapshot.
Re-run inspection before continuing.
```

---

# 5. history.md Trace Log

## Store here

```text
.snappy/memory/history.md
```

## Behavior

Append only.

Do not rewrite old history entries in M5.

## Events to log

```text
- project inspection started
- project inspection completed
- project snapshot created
- project snapshot reused
- project snapshot invalidated
- grounded plan created
- grounded plan shown
- grounded plan rejected
- grounded plan invalidated
- confirmation requested
- confirmation accepted
- confirmation rejected
- blocked write attempt
- workflow completed
- workflow cancelled
```

## Example entries

```md
## 2026-04-29 15:42:00 +02:00
Event: Project inspected
Mode: active
Result: success
Snapshot ID: snap_abc123
Files sampled:
- README.md
- pyproject.toml
- src/snappy_putty/cli.py
```

```md
## 2026-04-29 15:45:00 +02:00
Event: Grounded plan created
Goal: Add logging to CLI
Plan ID: plan_123
Based on snapshot: snap_abc123
Files referenced:
- src/snappy_putty/cli.py
- src/snappy_putty/session.py
Status: awaiting_confirmation
```

```md
## 2026-04-29 15:48:00 +02:00
Event: Plan invalidated
Plan ID: plan_123
Reason: Project snapshot changed
Action: Re-inspection required
```

## Guardrail

```text
history.md must not be parsed as execution state in M5.
```

---

# 6. CLI / REPL UX Requirements

## New commands or routes

Add read-only inspection routes to the REPL if this matches the current architecture:

```text
snappy> inspect project
snappy> inspect files
snappy> inspect structure
snappy> inspect file src/snappy_putty/cli.py
snappy> show snapshot
snappy> show plan
snappy> refresh snapshot
```

If top-level Typer commands are more consistent for project-level commands, support:

```bash
snappy inspect project
snappy inspect files
snappy inspect structure
snappy inspect file src/snappy_putty/cli.py
```

Do not break existing commands.

## Example output: inspect project

```text
Project Inspection

Root: /path/to/snappy-putty
Git branch: main
Git status: clean
Languages: Python
Package managers: pip
Frameworks/tools detected: Typer, Rich, Pytest

Important files:
- README.md
- pyproject.toml
- src/snappy_putty/cli.py
- src/snappy_putty/session.py

Tests:
- tests/test_state_machine.py
- tests/test_session_repl_subprocess.py

Snapshot saved:
.snappy/memory/project_snapshot.json
```

## Example output: grounded planning

User:

```text
snappy> help me add logging to the CLI
```

Expected:

```text
Grounded Plan

Goal:
Add logging to the CLI

Files inspected:
- src/snappy_putty/cli.py
- src/snappy_putty/session.py
- tests/test_session_repl_subprocess.py

Suggested steps:
1. Identify existing user-facing output paths.
2. Add a minimal logging helper behind a quiet default.
3. Ensure logs do not pollute Rich UI output.
4. Add tests for log initialization and no-regression CLI output.

Risks:
- Logging could clutter the REPL if enabled by default.
- Tests may need stable output expectations.

Status:
Plan saved. No files were modified.
```

---

# 7. Safety Invariants

These are non-negotiable.

```text
1. Project inspection is read-only.
2. ProjectSnapshot creation is read-only except writing to .snappy/memory/project_snapshot.json.
3. Grounded planning is read-only except updating session.json and history.md.
4. No source file may be modified during inspect or plan.
5. No delete, move, copy, overwrite, patch, format, install, git commit, or shell execution may happen without explicit confirmation.
6. Existing strict confirmation model remains authoritative.
7. Existing rule priority / multi-rule resolution must not be bypassed.
8. Existing state machine remains authoritative.
9. Invalid snapshots must be ignored, not trusted.
10. Invalid plans must be marked invalidated, not executed.
```

Important nuance:

Writing to `.snappy/memory/project_snapshot.json`, `.snappy/memory/session.json`, and `.snappy/memory/history.md` is allowed as internal memory bookkeeping.

But this must be limited to `.snappy/memory/` only.

---

# 8. Suggested Implementation Steps for Codex

## Step 1 — Inspect current architecture

Before editing, inspect relevant files.

Likely files:

```text
src/snappy_putty/cli.py
src/snappy_putty/session.py
src/snappy_putty/state_machine.py
src/snappy_putty/agent.py
src/snappy_putty/rules.py
src/snappy_putty/memory.py
src/snappy_putty/planner.py
src/snappy_putty/executor.py
tests/test_state_machine.py
tests/test_session_repl_subprocess.py
```

Actual file names may differ. Inspect first. Do not guess.

## Step 2 — Add ProjectSnapshot model

Create a small module if appropriate:

```text
src/snappy_putty/project_inspector.py
```

Responsibilities:

```text
- find project root
- walk project tree safely
- ignore noisy folders
- detect languages
- detect package managers
- detect frameworks/tools from config files
- identify docs, tests, source files, entry points
- compute cheap root_hash
- return ProjectSnapshot
```

## Step 3 — Add snapshot persistence

Create or extend memory utilities.

Needed functions:

```python
def load_project_snapshot(root: Path) -> ProjectSnapshot | None: ...
def save_project_snapshot(root: Path, snapshot: ProjectSnapshot) -> None: ...
def is_project_snapshot_valid(root: Path, snapshot: ProjectSnapshot) -> bool: ...
def refresh_project_snapshot(root: Path) -> ProjectSnapshot: ...
```

Handle malformed JSON gracefully.

Expected warning:

```text
Stored project snapshot was invalid and was ignored.
```

## Step 4 — Add history logger

Create a simple append-only helper.

Suggested module:

```text
src/snappy_putty/history.py
```

Suggested function:

```python
def append_history_event(root: Path, event: str, details: dict[str, Any]) -> None:
    ...
```

It should:

```text
- ensure .snappy/memory exists
- append markdown
- never crash the main workflow if logging fails
- keep formatting deterministic enough for tests
```

## Step 5 — Add grounded plan model

Create or extend planner objects.

Suggested module:

```text
src/snappy_putty/active_planner.py
```

Responsibilities:

```text
- accept user goal + ProjectSnapshot
- select relevant files from snapshot
- generate a bounded plan
- save current_plan into session.json
- append history event
```

For M5, rule-based/simple heuristic planning is acceptable.

Do not require LLM integration for this milestone unless already present and feature-gated.

## Step 6 — Wire into REPL / CLI

Add routes:

```text
inspect project
inspect files
inspect structure
inspect file <path>
show snapshot
show plan
refresh snapshot
```

Also update natural-language `ask` behavior in active mode:

```text
snappy> help me improve the CLI
```

Should:

```text
1. load or refresh valid snapshot
2. inspect relevant files from snapshot
3. create grounded plan
4. save plan to session memory
5. append history event
6. show plan
7. avoid source mutations
```

## Step 7 — Update status output

`snappy status` should include Active Mode context when relevant:

```text
Agent mode: active
Project snapshot: present
Snapshot ID: snap_abc123
Snapshot age: 2m
Grounded planning: yes
Current plan: plan_123
Plan status: awaiting_confirmation
Writes allowed: confirmation only
History log: .snappy/memory/history.md
```

Keep output tidy. No terminal confetti cannon.

---

# 9. Tests to Add

## Snapshot tests

Add tests for:

```text
- inspect project creates project_snapshot.json
- snapshot includes expected files
- noisy folders are ignored
- malformed snapshot is ignored gracefully
- snapshot invalidates when root_hash changes
- refresh snapshot forces new snapshot
```

## Plan tests

Add tests for:

```text
- active planning creates current_plan in session.json
- plan references based_on_snapshot_id
- plan displays inspected files
- plan does not modify source files
- plan invalidates when snapshot changes
- show plan works after restart/resume
```

## History tests

Add tests for:

```text
- history.md is created
- project inspection is logged
- grounded plan creation is logged
- invalidation is logged
- history append does not overwrite existing content
```

## Safety regression tests

Add tests for:

```text
- inspect commands do not modify non-memory files
- planning commands do not modify non-memory files
- active mode cannot bypass confirmation
- existing copy/move confirmation tests still pass
- existing restore/memory tests still pass
```

---

# 10. Manual QA Checklist

Run the existing regression suite first.

```bash
pytest
```

Then run manual checks.

## 10.1 Inspect project

```bash
snappy
snappy> inspect project
```

Expected:

```text
- project summary appears
- snapshot saved under .snappy/memory/project_snapshot.json
- history.md created or appended
- no source files changed
```

Check git diff:

```bash
git diff -- . ':!.snappy/memory/project_snapshot.json' ':!.snappy/memory/session.json' ':!.snappy/memory/history.md'
```

Expected:

```text
No source file changes caused by inspection.
```

## 10.2 Show snapshot

```text
snappy> show snapshot
```

Expected:

```text
- snapshot ID visible
- root visible
- detected files/tools visible
```

## 10.3 Grounded plan

```text
snappy> help me add logging to the CLI
```

Expected:

```text
- plan references real project files
- plan says no files were modified
- current_plan saved to session.json
- history.md logs the plan
```

## 10.4 Restart and show plan

Exit and restart Snappy.

```text
snappy> show plan
```

Expected:

```text
- stored plan appears
- plan is still tied to snapshot ID
```

## 10.5 Invalidate snapshot

Touch or edit a source file manually.

```bash
touch src/snappy_putty/cli.py
```

Then:

```text
snappy> show plan
```

Expected:

```text
- Snappy detects stale snapshot/plan
- plan is marked invalidated
- user is told to re-run inspection/planning
```

## 10.6 Confirm no unsupervised writes

Try a request that sounds like a mutation:

```text
snappy> update the CLI logging now
```

Expected:

```text
- Snappy creates or shows a plan
- Snappy does not edit files directly
- Snappy requires explicit confirmation before any write path
```

---

# 11. Expected User-Facing Messages

## Snapshot invalid

```text
Stored project snapshot was invalid and was ignored.
```

## Snapshot stale

```text
Project snapshot is stale. Re-inspection is required before continuing.
```

## Plan invalidated

```text
Stored plan was based on an outdated project snapshot and was invalidated.
```

## Read-only guarantee

```text
No files were modified. Active Mode only inspected the project and created a plan.
```

## Blocked write attempt

```text
Write blocked: Active Mode cannot modify project files without explicit confirmation.
```

---

# 12. Definition of Done

M5 is complete when:

```text
1. Snappy can inspect the current project.
2. Snappy can save a valid ProjectSnapshot.
3. Snappy can reuse a fresh ProjectSnapshot.
4. Snappy invalidates stale/malformed snapshots.
5. Snappy can generate a grounded plan from actual project files.
6. Snappy saves the current plan to session memory.
7. Snappy ties plans to snapshot IDs.
8. Snappy invalidates plans when snapshots become stale.
9. Snappy appends trace events to history.md.
10. Snappy status exposes active-mode context.
11. Existing M1–M4 tests still pass.
12. New M5 tests pass.
13. No source file writes happen during inspection/planning.
14. All mutation paths still require explicit confirmation.
```

---

# 13. Non-Goals for M5

Do not implement these yet:

```text
- automatic patch generation
- automatic code editing
- multi-file refactoring
- AST-level symbol intelligence
- dependency installation
- arbitrary shell execution
- GitHub/GitLab PR creation
- tool marketplace
- modular skill execution
- autonomous background loops
- multi-plan management
- long-term learning from history.md
```

These belong to later milestones.

Especially do not sneak M6 into M5. That is how projects grow tentacles and start charging rent.

---

# 14. Codex Execution Instructions

Use this plan as the implementation contract.

## Work style

```text
- Inspect files before changing them.
- Keep changes minimal and milestone-scoped.
- Preserve existing behavior.
- Do not rewrite large modules unnecessarily.
- Add tests alongside implementation.
- Prefer small helper modules over bloating cli.py/session.py.
- Make all new behavior deterministic enough for tests.
```

## Safety priority

```text
Safety > UX polish > feature completeness
```

## Implementation order

```text
1. Inspect current architecture.
2. Add ProjectSnapshot and project_inspector module.
3. Add snapshot persistence and validation.
4. Add history append logger.
5. Add GroundedPlan/session memory support.
6. Add inspect/show routes.
7. Add active planning route.
8. Update status output.
9. Add tests.
10. Run full regression suite.
11. Report exactly what changed and what remains out of scope.
```

## Required final report from Codex

After implementation, report:

```text
- Files changed
- New modules added
- New commands/routes added
- Tests added
- Full test command run
- Test results
- Manual QA checklist status
- Any known limitations
```

Save the above report into a file on the local filesystem.

---

# 15. Final Reminder

M5 is the first truly useful Active Mode milestone.

But useful does not mean reckless.

The correct behavior is:

```text
Inspect first.
Plan from reality.
Remember carefully.
Log everything important.
Never write without confirmation.
```

That is the spine of Snappy.
