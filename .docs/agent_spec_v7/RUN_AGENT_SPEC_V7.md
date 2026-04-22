# Snappy — M4 Workflow Memory + Continuation  
## Codex Implementation (Chunked)

---

## Overview

You are implementing **M4 — Workflow Memory + Continuation** for the `snappy_putty` codebase.

This milestone introduces:

- persistence of `ActiveWorkflowSnapshot`
- safe restoration of workflows
- continuation of CLARIFICATION and CONFIRMATION states

This must **preserve all guarantees from M3 and M3.5**.

---

## Global Rules (applies to all chunks)

- No automatic execution after restore
- No bypass of control layer
- No relaxation of confirmation rules
- No multi-goal support
- No persistence of unsafe/non-serializable data
- Keep implementation bounded and incremental

---

## Implementation Strategy
Run each chunk in the correct sequence: CHUNK 1, CHUNK 2, CHUNK 3, CHUNK 4

---

# CHUNK 1 — Persistence Layer (Save Snapshot)

## Goal
Persist `ActiveWorkflowSnapshot` to disk.

## Tasks

1. Create file:
```
.snappy/memory/session.json
```

2. Implement:

```python
def save_workflow_snapshot(snapshot: ActiveWorkflowSnapshot) -> None
```

Requirements:
- serialize snapshot to JSON
- include all safe fields
- ensure directory exists
- overwrite existing snapshot safely

3. Trigger save when:
- entering CLARIFICATION
- entering CONFIRMATION
- after planning completes

4. Do NOT:
- persist live objects
- persist executable references

---

## Tests

- snapshot saved on clarification
- snapshot saved on confirmation
- file exists and contains valid JSON

---

# CHUNK 2 — Restore Layer (Load Snapshot)

## Goal
Load snapshot safely on session start.

## Tasks

1. Implement:

```python
def load_workflow_snapshot() -> ActiveWorkflowSnapshot | None
```

2. On CLI startup:
- attempt to load snapshot
- validate structure
- restore into session

3. Validation rules:
- valid state
- valid fields
- context matches state

If invalid:
- discard snapshot
- log warning
- continue fresh

---

## Tests

- valid snapshot restores session
- invalid snapshot ignored
- missing file handled cleanly

---

# CHUNK 3 — Resume Logic

## Goal
Resume workflows safely.

## Behavior

### CLARIFICATION
- re-display pending question
- wait for input
- do not re-plan automatically

### CONFIRMATION
- re-display confirmation prompt
- wait for YES/NO
- do not execute automatically

### EXECUTING / REFLECTING
- mark workflow as FAILED or INTERRUPTED
- clear snapshot

---

## Tests

- clarification resumes correctly
- confirmation resumes correctly
- no execution occurs on restore
- invalid states handled safely

---

# CHUNK 4 — Integration + Status

## Goal
Integrate persistence with CLI and snapshot system.

## Tasks

- ensure `status` reflects restored workflow
- ensure snapshot cleared on:
  - completion
  - cancellation
  - failure
  - blocked

- ensure trust boundaries (M3.5) still enforced after restore

---

## Tests

- status after restore is accurate
- snapshot cleared after terminal states
- no ghost workflows remain

---

# Acceptance Criteria

M4 is complete when:

- workflows persist to disk
- workflows restore correctly
- clarification resumes correctly
- confirmation resumes correctly
- no automatic execution occurs
- invalid snapshots are ignored
- trust boundaries remain intact

---

# Design Insight

Persistent agents must store only **essential workflow state**, not everything, to avoid state drift and corruption across sessions. citeturn0search5

---

# Final Principle

Persistence must preserve behavior, not introduce new behavior.

---

# Deliverables

Return:

1. code changes
2. tests
3. concise implementation summary including:
   - files changed
   - how clarification-input rejection works
   - what trust/safety invariants are now enforced
   - any remaining follow-up items that should be tracked separately
   - save the results of this concise implementation to a file
