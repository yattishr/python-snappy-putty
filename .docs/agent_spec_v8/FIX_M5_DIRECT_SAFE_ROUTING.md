# Snappy M5 Final Patch — Direct Safe Operation Routing + Destructive Intent Preflight

## Goal

Stabilize M5 routing so Snappy does not accidentally turn safe inspection commands or destructive requests into project plans.

This is the final M5 stabilization patch.

Core principles:

```text
Safe inspection should execute directly.
Destructive intent should be intercepted early.
Planning should only happen for genuine developer goals.
```

---

## Problem 1 — Direct Safe Operations Enter Planning

Observed behavior:

```text
snappy> show file listing
```

After selecting current directory, Snappy creates a deterministic grounded plan:

```text
Goal: give me a file listing for "."
Mode: deterministic
Steps:
1. Inspect current implementation...
2. Apply the smallest project change...
3. Add or update tests...
```

This is wrong.

A file listing is a direct safe inspection operation, not a planning goal.

---

## Required Fix 1 — Direct Safe Operation Routing

Add a routing category:

```text
direct_safe_operation
```

or reuse/strengthen:

```text
safe_inspect
```

These routes must bypass planning entirely.

### Examples

The following should execute directly:

```text
show file listing
list files
show directory tree
show git status
git status
show current branch
inspect file
read README.md
show tests
inspect project
inspect files
```

### Required behavior

For direct safe operations:

```text
- do not create a plan
- do not persist last_plan
- do not enter PLANNING
- do not enter CONFIRMATION
- do not call the LLM
- execute bounded inspection directly
- return/remain IDLE
```

### Status after direct safe operation

Expected:

```text
Current state: IDLE
Active goal: (none)
Pending plan: (none)
Last route: safe_inspect
Grounded planning: no
```

Do not show a newly-created deterministic plan for safe inspection.

If a previous valid plan exists, it must not be overwritten by safe inspection output.

---

## Problem 2 — Destructive Requests Need Early Blocking

Snappy must not plan, inspect, or call the LLM for broad destructive commands.

Examples:

```text
help me delete all files on this filesystem
delete everything in this repo
wipe the filesystem
remove this project
rm -rf /
delete my home directory
erase .env
overwrite all files
drop the database
delete production data
force push over main
```

These must be intercepted before all other routing.

---

## Required Fix 2 — Destructive Intent Preflight Router

Add a top-level preflight classification before normal routing:

```text
destructive_or_high_risk_intent
```

This check must run before:

```text
direct_safe_operation
structured_project_inspection
plan_interaction
project_developer_goal
non_project_question
```

Recommended routing hierarchy:

```text
1. destructive_or_high_risk_intent
2. direct_safe_operation
3. structured_project_inspection
4. plan_interaction
5. project_developer_goal
6. non_project_question
```

---

## Broad Destructive Intent

Broad destructive requests must be blocked outright.

Example:

```text
help me delete all files on this filesystem
```

Expected response:

```text
I can’t help with deleting all files or wiping a filesystem.

That request is destructive and unsafe.

No action was taken.
```

State after:

```text
Current state: IDLE
Active goal: (none)
Pending plan: (none)
Last blocked goal: help me delete all files on this filesystem
Block reason: destructive_intent
```

Do not create a plan.

Do not call the LLM.

Do not prompt for confirmation.

---

## Scoped Destructive / High-Risk Operations

Some destructive requests may be legitimate if clearly scoped.

Examples:

```text
delete .pytest_cache
delete node_modules
remove build output
clean dist folder
delete temporary files
```

These should not be blocked outright if scoped safely.

They should route as:

```text
high_risk_scoped_operation
```

Expected behavior:

```text
- do not execute immediately
- require explicit confirmation
- use existing control/policy confirmation layer
- show clear target path and risk
```

Example response:

```text
This is a destructive scoped operation.

Target: .pytest_cache
Risk: deletes files from the project workspace

Confirm before proceeding: YES/NO
```

For M5, it is acceptable to conservatively block ambiguous destructive requests.

---

## Detection Rules

Implement conservative pattern matching first.

### Broad destructive patterns

Block if the request includes destructive verbs combined with broad targets.

Destructive verbs:

```text
delete
remove
wipe
erase
destroy
drop
purge
overwrite
reset hard
force push
rm -rf
```

Broad targets:

```text
all files
everything
filesystem
root
/
home directory
repo
repository
project
production
database
.env
secrets
credentials
```

### Scoped destructive patterns

Require confirmation if destructive verb targets a specific safe project-relative path.

Examples:

```text
delete .pytest_cache
remove dist
clean build
delete node_modules
```

Reject if the resolved path is outside the project root.

Reject if the path is:

```text
/
~
$HOME
..
.env
.git
```

unless future explicit rules allow it.

---

## State Machine Rules

### Direct safe operation

```text
IDLE → SAFE_INSPECT → IDLE
```

or if using existing routes:

```text
IDLE → direct_safe_operation → IDLE
```

Do not produce plan state.

### Broad destructive block

```text
IDLE → BLOCKED → IDLE
```

Preserve:

```text
last_blocked_goal
block_reason = destructive_intent
```

Clear:

```text
active_goal
pending_plan
pending_question
awaiting_confirmation
```

### Scoped destructive operation

```text
IDLE → CONFIRMATION
```

Only if the operation is clearly scoped and allowed by policy.

---

## History Logging

Append history events.

### Direct safe operation

```md
## <timestamp>
Event: Direct safe operation
Command: show file listing
Route: safe_inspect
Result: completed
Workflow state: reset_to_idle
```

### Broad destructive block

```md
## <timestamp>
Event: Destructive intent blocked
Goal: help me delete all files on this filesystem
Reason: destructive_intent
Result: no_action_taken
Workflow state: reset_to_idle
```

### Scoped destructive confirmation

```md
## <timestamp>
Event: Scoped destructive operation requires confirmation
Goal: delete .pytest_cache
Target: .pytest_cache
Reason: destructive_scoped_operation
Result: awaiting_confirmation
```

---

## Tests Required

Add or update tests in the existing active-mode/state-machine test files.

### Test 1 — File listing bypasses planning

Input:

```text
show file listing
```

Expected:

```text
- route is safe_inspect/direct_safe_operation
- no plan created
- no last_plan overwritten
- state returns to IDLE
```

### Test 2 — Safe inspection does not overwrite existing plan

Setup:

1. Create a valid LLM-assisted plan.
2. Run:

```text
show file listing
```

Expected:

```text
- previous plan is not overwritten by a deterministic file-listing plan
- safe inspection output completes
- state remains/returns IDLE if no active workflow is expected
```

If active plan should block safe operation under current single-goal rules, then the operation should be rejected cleanly without creating a plan.

### Test 3 — Broad destructive intent blocked

Input:

```text
help me delete all files on this filesystem
```

Expected:

```text
- no plan created
- no LLM call
- no inspection required
- state IDLE
- last_blocked_goal set
- block_reason = destructive_intent
```

### Test 4 — rm -rf root blocked

Input:

```text
rm -rf /
```

Expected:

```text
- blocked immediately
- no action taken
- state IDLE
```

### Test 5 — Scoped destructive request requires confirmation

Input:

```text
delete .pytest_cache
```

Expected:

```text
- not executed immediately
- confirmation required
- target shown
- state CONFIRMATION
```

If scoped destructive support is too large for this patch, then conservatively block it with a clear message.

### Test 6 — Destructive intent checked before planning

Input:

```text
help me delete everything then improve this CLI
```

Expected:

```text
- destructive block wins
- no planning
- no LLM call
```

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
status
help me delete all files on this filesystem
status
rm -rf /
status
delete .pytest_cache
status
```

Expected:

```text
- file listing does not create a plan
- broad destructive request is blocked
- rm -rf / is blocked
- scoped destructive request requires confirmation or is conservatively blocked
- state always lands cleanly
```

---

## Non-Negotiable Rules

```text
Direct safe operations must not become plans.
```

```text
Broad destructive requests must never reach planning.
```

```text
Destructive intent is checked before all other routes.
```

```text
No LLM call is required to identify obvious destructive intent.
```

```text
No hidden execution.
No surprise deletion.
No digital bonfires.
```

---

## Acceptance Criteria

This patch is complete when:

```text
- show file listing executes as inspection only
- no deterministic plan is created for safe inspection commands
- destructive broad intent is blocked before planning
- scoped destructive requests require confirmation or are conservatively blocked
- state returns/remains clean
- full test suite passes
```

After this patch, M5 can be locked if the full regression and manual smoke tests pass.
