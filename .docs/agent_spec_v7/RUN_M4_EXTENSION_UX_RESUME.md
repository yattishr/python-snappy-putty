# Snappy — M4 Extension 1  
## Restore UX + Resume Safety Hardening  
### Codex-Ready Implementation Spec

---

## Status

Post-M4 hardening layer

---

## 1. Mission

Implement a narrow hardening layer on top of **M4 — Workflow Memory + Continuation** so that restored workflows are:

- explicit to the user
- easy to inspect
- safe to resume
- hard to misinterpret

This is a **UX + safety hardening pass**, not a new memory model.

---

## 2. Scope

### Included

- explicit restored-workflow notice on shell startup
- status visibility for restored workflows
- invalid/corrupt snapshot warning on startup
- prompt restoration consistency after allowed control commands
- cleanup of restore-state ambiguity

### Excluded

- decision memory
- multi-workflow history
- auto-resume execution
- workflow replay
- autonomous continuation
- new memory stores
- broad CLI redesign

---

## 3. Problem

M4 gives Snappy the ability to persist and restore workflows, but the user experience can still feel ghostly if:

- a workflow resumes without clearly saying so
- `status` does not reveal restored origin
- invalid snapshots are silently ignored
- active pending prompts are not re-presented consistently after `status`, `help`, or similar allowed control commands

This patch makes restored state visible and trustworthy.

---

## 4. Required Behaviors

### 4.1 Restore Notice on Startup

If a valid workflow snapshot is restored on shell startup, Snappy must display a concise resume notice before returning control to the user.

#### Example: restored clarification
```text
Restored pending workflow: copy README.md
State: clarification
Awaiting: destination path
```

#### Example: restored confirmation
```text
Restored pending workflow: copy README.md to out.md
State: confirmation
Awaiting: YES/NO
```

Requirements:
- must appear only when a workflow was actually restored
- must not imply execution has occurred
- must be concise and consistent

---

### 4.2 Invalid Snapshot Warning

If a stored workflow snapshot is invalid, malformed, or incompatible, Snappy must surface a warning and continue with a clean session.

#### Example
```text
Stored workflow snapshot was invalid and was ignored.
```

Requirements:
- do not silently swallow invalid restore state
- do not crash
- do not partially restore malformed workflow data

---

### 4.3 Status Visibility for Restored Workflows

When a workflow has been restored, `status` must make that explicit.

Minimum requirement:
- add a field indicating whether the current active workflow was restored from persisted memory

Suggested field:
```text
Workflow restored from memory: yes
```

Optional:
```text
Restore source: .snappy/memory/session.json
```

Requirements:
- only shown when relevant
- derived from actual restored workflow state, not inferred vaguely

---

### 4.4 Prompt Restoration After Allowed Control Commands

When a workflow is pending in:
- `CLARIFICATION`
- `CONFIRMATION`

and the user enters an allowed control command such as:
- `status`
- `help`

Snappy must, after rendering that control output, restore the correct pending prompt rather than falling back to generic shell prompt presentation.

#### Clarification example
```text
destination path>
```

#### Confirmation example
The user should be returned to the active confirmation context, not left visually at a plain `snappy>` prompt with hidden pending state.

Requirements:
- workflow state must remain intact
- prompt restoration must match the active pending state
- no execution occurs
- no new goal begins

---

### 4.5 Resume-State Symmetry

Restored workflows should feel operationally equivalent to live pending workflows.

This means:
- restored clarification behaves like normal clarification
- restored confirmation behaves like normal confirmation
- restored pending state survives inspection commands cleanly
- no special-case confusion after restore

---

## 5. Safety Rules

This extension must preserve all existing guarantees from M3.5 and M4:

- no automatic execution after restore
- command-shaped clarification input remains rejected
- confirmation remains strict
- no new goal while clarification or confirmation is pending
- control layer remains mandatory before execution
- invalid restore state never enters active workflow

---

## 6. Likely Integration Areas

Use actual project structure rather than inventing parallel infrastructure.

Likely files may include:
- `src/snappy_putty/cli.py`
- `src/snappy_putty/session.py`
- related tests

Do not introduce a large abstraction layer just for messaging.

---

## 7. Implementation Guidance

### Step 1
Identify where restored workflow state is loaded on shell startup.

### Step 2
Add a small startup resume-notice path for successfully restored workflows.

### Step 3
Add an explicit invalid-snapshot warning path when restoration fails validation.

### Step 4
Add a minimal restored-origin indicator to the active workflow snapshot or session state if not already present.

Suggested examples:
- `restored_from_memory: bool`
- `restore_source: str | None`

Keep it small and typed.

### Step 5
Update `status` to surface restored origin when relevant.

### Step 6
Tighten prompt rendering so allowed control commands re-present the correct pending prompt after output.

### Step 7
Add tests.

---

## 8. Required Tests

Add or update tests for at least:

### 8.1 Restored clarification notice
- persist a clarification workflow
- restart shell
- expect explicit restored-workflow notice
- expect clarification prompt to remain active

### 8.2 Restored confirmation notice
- persist a confirmation workflow
- restart shell
- expect explicit restored-workflow notice
- expect confirmation prompt to remain active
- expect no auto-execution

### 8.3 Invalid snapshot warning
- create malformed snapshot
- start shell
- expect warning
- expect clean session

### 8.4 Status shows restored origin
- restore workflow
- run `status`
- expect restored-memory indicator

### 8.5 Prompt restoration after `status` during clarification
- restored or live clarification pending
- run `status`
- expect clarification prompt re-presented correctly

### 8.6 Prompt restoration after `status` during confirmation
- restored or live confirmation pending
- run `status`
- expect confirmation context still visually active

### 8.7 No trust-boundary regression
- restored clarification still rejects command-shaped input
- restored confirmation still rejects invalid confirmation input

---

## 9. Acceptance Criteria

Implementation is complete only if all of the following are true:

- restored workflows announce themselves clearly on startup
- invalid snapshots produce a visible warning
- `status` explicitly indicates restored active workflows
- pending clarification/confirmation prompts are restored after allowed control commands
- restored workflows remain subject to existing trust boundaries
- no automatic execution is introduced
- no new memory subsystem is added

---

## 10. Non-Goals Reminder

Do **not** add:
- decision memory
- memory history timeline
- workflow replay
- multi-session merge logic
- auto-discard commands unless strictly necessary
- broad redesign of shell rendering

This patch is about making existing restore behavior clearer and safer, not expanding capability.

---

## 11. Deliverables

Return:

1. code changes
2. tests
3. concise implementation summary including:
   - files changed
   - how restored workflows are surfaced
   - how invalid snapshots are reported
   - how prompt restoration now behaves
   - any follow-up items that should be tracked separately

---

## 12. Final Principle

**Restored state must be visible, honest, and safe.**

Persistence should never feel magical.
It should feel explicit and trustworthy.
