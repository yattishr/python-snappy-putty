You are implementing a **pre-M4 stabilization patch** for the `snappy_putty` codebase.

## Mission

Introduce a single typed `ActiveWorkflowSnapshot` model so the current in-flight workflow is no longer fragmented across scattered session fields and loose `pending_context` state.

This patch is a **foundation for M4 Workflow Memory + Continuation**.

It is **not** M4 itself.

---

## Scope

Implement the following:

1. Add a typed `ActiveWorkflowSnapshot` model
2. Add typed workflow context variants
3. Introduce `active_workflow` as the authoritative in-flight workflow object on session state
4. Populate and update the snapshot through active workflow states
5. Clear the snapshot on terminal cleanup back to `IDLE`
6. Update status/session reads to prefer snapshot-derived workflow data
7. Add tests for snapshot lifecycle and restoration primitives

---

## Non-Goals

Do **not** implement any of the following:

- disk persistence
- workflow resume across process restarts
- autonomous continuation
- multi-goal workflows
- skill routing
- major CLI UX redesign
- rule engine redesign
- broad refactor of unrelated modules

Do not drift into full M4.

---

## Problem Context

Right now active workflow state is fragmented across fields like:
- `active_goal`
- `pending_question`
- `pending_plan`
- `awaiting_confirmation`
- `pending_context`
- lifecycle/control state fields

This makes continuation and restoration risky.

The goal is to create **one structured in-memory snapshot** that can later be serialized safely.

---

## Required Models

Use typed dataclasses or the project’s equivalent strongly-typed pattern.

### Required snapshot model

Minimum shape:

```python
@dataclass
class ActiveWorkflowSnapshot:
    workflow_id: str
    state: str
    goal: str | None
    route: str | None
    pending_question: str | None
    pending_plan_summary: str | None
    awaiting_confirmation: bool
    control_state: str | None
    context: WorkflowContext | None
```

You may add fields only if clearly necessary.

Requirements:

- must be serializable in principle
- must not contain live handles or opaque runtime-only objects
- must represent exactly one active workflow

## Required context model

Do not keep using loose dict[str, Any] for workflow control context.

Introduce a typed workflow context family.

At minimum implement:
```
@dataclass
class ClarificationContext:
    kind: Literal["clarification"]
    source_path: str | None
    expected_input: str

@dataclass
class ConfirmationContext:
    kind: Literal["confirmation"]
    operation_count: int
    overwrite_detected: bool = False
```

Use a tagged union / shared base / type alias as appropriate.

Only add more context variants if clearly needed by the current code.

## Session integration
Session state should expose something like:
```
active_workflow: ActiveWorkflowSnapshot | None
```

Requirements:

- at most one active workflow snapshot exists at a time
- snapshot becomes the authoritative in-flight workflow model
- existing top-level fields may remain temporarily for compatibility, but should no longer be treated as the primary source of truth

Do not delete compatibility fields unless safe and low-risk in this patch.

## Lifecycle requirements
Populate snapshot during active workflow states

When the session is in states such as:

- CLARIFICATION
- PLANNING
- CONFIRMATION
- EXECUTING
- REFLECTING

the snapshot must reflect the current workflow.

## Clear snapshot on terminal cleanup
When the workflow reaches terminal handling and returns to IDLE, clear active_workflow.

Keep snapshot authoritative

Avoid scattered ad hoc mutation of:

- active goal
- pending question
- pending plan
- awaiting confirmation
- pending context

Prefer helper methods that update the snapshot coherently.

## Status integration

Update status/session reporting so that workflow-related fields are derived from the snapshot when present.

Examples:

- active goal
- pending question
- pending plan summary
- awaiting confirmation
- control state

Do not redesign all status UX. Just make snapshot-backed workflow reporting coherent.

## Compatibility / migration strategy

Implement this incrementally:

Phase 1
- add snapshot and typed context models
- populate snapshot during active flows
- keep compatibility fields in sync if needed

Phase 2
- migrate reads to snapshot-first
- reduce dependence on loose workflow fields

Do not attempt a full cleanup of all historical session fields in one patch.


## Restoration primitives

Even though this patch does not implement persistence, add tests that prove the snapshot is restoration-friendly.

At minimum cover scenarios like:

- construct a clarification snapshot
- construct a confirmation snapshot
- attach snapshot to session
- verify status/session logic can read it coherently
- verify terminal cleanup clears it cleanly

These are state restoration primitives, not full persistence flows.


## Implementation Guidance

Work in small, bounded changes.

Suggested order:

### Step 1

Identify where current in-flight workflow state lives today in:

- session model
- CLI lifecycle/orchestration
- status rendering

### Step 2

Add ActiveWorkflowSnapshot and typed context models.

### Step 3

Add active_workflow to session state.

### Step 4

Introduce small helper methods for workflow lifecycle mutation, for example:

- begin_workflow(...)
- update_active_workflow(...)
- set_workflow_context(...)
- clear_active_workflow()

Use names that fit the project style.

### Step 5

Wire clarification and confirmation paths to use typed context objects instead of loose pending_context.

### Step 6

Update status/session reads to prefer active_workflow.

### Step 7

Add tests.

## Required Tests

Add or update tests for at least:

1. snapshot creation
- active workflow snapshot can be created for clarification state
2. typed clarification context
- clarification path uses ClarificationContext, not loose dict state
3. typed confirmation context
- confirmation path uses ConfirmationContext
4. snapshot-backed status
- status/session reporting reflects active workflow fields from snapshot
5. single active workflow
- session cannot expose multiple active snapshots at once
6. terminal cleanup
- snapshot is cleared when workflow returns to IDLE
7. restoration-friendly primitives
- manually attach/construct snapshot and verify session logic reads it correctly

## Acceptance Criteria

Implementation is complete only if all of the following are true:

- ActiveWorkflowSnapshot exists as a typed model
- clarification/confirmation use typed context objects
- session exposes active_workflow
- active workflow state is represented coherently in one snapshot
- snapshot is populated during active workflow states
- snapshot is cleared on terminal cleanup
- status/session reads can derive workflow state from snapshot
- no persistence is introduced yet
- no broad unrelated refactor is introduced

## Code Quality Rules
- preserve project style and naming
- keep patch bounded
- avoid duplicate workflow state models
- prefer minimal invasive changes
- do not redesign unrelated parts of the CLI
- add comments only where they remove ambiguity


## Deliverables

Return:

1. code changes
2. tests
3. concise implementation summary including:
- files changed
- where snapshot model lives
- how workflow context is now typed
- what still remains for M4 proper


