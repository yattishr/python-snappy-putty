# Snappy — M1: Workflow UX Tightening

## Goal

Tighten Snappy’s interactive workflow experience so that clarification, planning, confirmation, policy feedback, and recovery all feel consistent, readable, and deterministic.

This milestone is UX-focused.

It must **not** change the core execution model, state machine rules, or agent/rule semantics beyond presentation and interaction clarity.

---

## Why This Milestone Comes Next

Snappy already has:

* deterministic state machine
* clarification lock
* rule enforcement
* agent runtime inspection
* session mode control

But the workflow experience still has friction in places such as:

* prompt continuity
* confirmation wording
* policy vs plan display hierarchy
* zero-op/blocked plan feedback
* `after` vs `status` usefulness
* inconsistent mental model between clarification and confirmation

Before introducing multi-rule resolution or agent loops, the user interaction model must feel tight and predictable.

This milestone defines that interaction contract.

---

## GLOBAL RULES

* Do not rewrite the planner
* Do not rewrite the state machine
* Do not change rule enforcement behavior
* Do not change agent mode behavior
* Do not add new autonomous behavior
* Do not introduce skill-based routing
* Do not persist new session data
* All changes must be additive and low-risk
* Existing regression behavior must remain intact unless a UX change is explicitly intended in this milestone
* Prefer reuse of existing render helpers and panels where possible

---

## UX PRINCIPLES FOR M1

### 1. One interaction model

Clarification, confirmation, and blocked/policy feedback should feel like part of the same system.

### 2. Clear hierarchy

When Snappy responds, the user should easily understand:

* what the goal is
* what question is being asked
* what policy affected the request
* what plan exists
* what decision is required next

### 3. No dead-end states

If Snappy cannot proceed, the user should always know:

* why
* what to do next

### 4. No ambiguous transitions

The shift between:

* clarification
* planning
* confirmation
* blocked
* completed
  must feel deliberate and obvious

---

## M1 SCOPE

This milestone includes:

1. Clarification prompt tightening
2. Confirmation UX tightening
3. Policy / Plan / Warning display hierarchy
4. Better zero-op and blocked-plan feedback
5. `after` and `status` role clarification
6. Help text polish for workflow commands
7. UX-focused smoke/regression coverage

---

## CHUNK 1 — Clarification Prompt Tightening

### Goal

Make clarification prompts feel more continuous and intentional.

### Requirements

* Preserve the current inline clarification prompt model
* Ensure pending clarification always re-renders consistently after:

  * blocked input
  * help
  * status
* Clarification prompt should remain visually continuous and recognizable
* Keep wording concise
* Avoid duplicate or noisy prompt rendering

### Desired behavior

Example:

```text
snappy> copy README.md
destination path>
```

If blocked input is entered:

```text
destination path>show me all files

You have a pending question:

destination path>

Answer it, or type 'cancel' to abandon the current goal.
destination path>
```

This should feel intentional, not messy.

### Tests

1. blocked command during clarification re-renders prompt cleanly
2. `help` during clarification preserves prompt
3. `status` during clarification preserves prompt
4. prompt is not duplicated excessively

---

## CHUNK 2 — Confirmation UX Tightening

### Goal

Make confirmation feel like the natural twin of clarification.

### Requirements

* Preserve existing YES/NO confirmation behavior
* Standardize wording and layout of confirmation prompts
* Make overwrite confirmation and apply confirmation feel related
* Ensure confirmation prompt is always obvious after plan display
* Keep responses case-insensitive if already supported
* If invalid confirmation input is entered, show a clear retry prompt without destabilizing state

### Desired behavior

Examples:

```text
Type YES to apply, or NO to cancel.
```

and

```text
Destination exists. Type YES to overwrite, or NO to cancel.
```

These should feel like part of the same interaction family.

### Tests

1. apply confirmation still works
2. overwrite confirmation still works
3. invalid confirmation input re-prompts cleanly
4. cancel path still works

---

## CHUNK 3 — Policy / Plan / Warning Display Hierarchy

### Goal

Improve the visual and logical order of feedback shown before user confirmation.

### Requirements

Standardize pre-execution output hierarchy so the user can quickly parse:

1. Goal
2. Policy decisions or rule blocks, when relevant
3. Planned changes
4. Plan warnings
5. Confirmation prompt

For blocked cases, show:

1. Goal or rule block context
2. Policy message
3. Next-step hint if relevant

### Notes

* Do not redesign Rich panels completely unless needed
* Do not remove useful information
* Prioritize readability and consistent order
* If a rule blocks an operation, that block should visually dominate the response

### Tests

1. normal mutation flow shows plan and warnings in stable order
2. blocked-by-rule flow shows rule block prominently
3. zero-op plan feedback is clear and consistent

---

## CHUNK 4 — Zero-Op and Blocked-Plan UX

### Goal

Prevent confusing states when planning results in no executable operations.

### Problem

Cases like:

* path escapes workspace
* same-file copy
* invalid target normalization
  can produce no-op plans or blocked plans

The user should clearly understand:

* what happened
* whether this was blocked
* whether there is anything to confirm
* what to do next

### Requirements

* If no operations are planned, Snappy must not leave the interaction in an ambiguous planning state
* Messaging must distinguish between:

  * blocked by rule
  * invalid request
  * no-op / same-file
* Avoid falling through into confusing confirmation or stale planning state
* Keep state transitions deterministic

### Desired behavior

Examples:

#### Same-file case

```text
No filesystem changes planned.

Reason: source and destination resolve to the same file.
```

#### Workspace escape / protected path case

```text
Operation blocked by rule: protect_project_root

The requested filesystem mutation targets a protected path.
```

### Tests

1. same-file copy gives clear no-op explanation
2. protected path gives clear blocked explanation
3. zero-op outcome does not leave stale pending plan
4. status reflects stable state afterward

---

## CHUNK 5 — `after` vs `status` Role Clarification

### Goal

Make `after` and `status` clearly distinct.

### Requirements

#### `status`

Must remain diagnostic:

* current state
* active goal
* pending question
* pending plan
* rule/agent status
* last completed/cancelled/failed goal

#### `after`

Must remain actionable:

* tell the user what the next expected input or step is
* especially useful in clarification or confirmation states

### Desired behavior

If clarification pending:

```text
snappy> after
Pending question: destination path>
```

If confirmation pending:

```text
snappy> after
Awaiting confirmation: Type YES to apply, or NO to cancel.
```

If idle:

```text
snappy> after
No pending next step.
```

### Tests

1. `after` during clarification is actionable
2. `after` during confirmation is actionable
3. `after` in IDLE is clean
4. `status` remains diagnostic and does not overlap too much with `after`

---

## CHUNK 6 — Help Text and Workflow Discoverability

### Goal

Polish help surfaces so the core workflow commands feel deliberate and discoverable.

### Requirements

* REPL help should clearly show:

  * help
  * status
  * after
  * cancel
  * agent
  * agent mode
  * init
  * skills
  * rules
  * agent doctor
* Workflow guidance should reflect the current UX
* Avoid vague or outdated examples
* Add one or two examples that demonstrate clarification-driven interaction

### Desired examples

```text
copy README.md
destination path> tests/
```

### Tests

1. help output includes workflow commands
2. examples remain readable and relevant
3. no stale references to unsupported behavior

---

## CHUNK 7 — UX Smoke Coverage

### Goal

Add a focused smoke pass for the tightened workflow UX.

### Requirements

Add or update tests covering:

* clarification prompt continuity
* confirmation re-prompt behavior
* same-file no-op message
* blocked-by-rule message prominence
* `after` behavior in clarification
* `after` behavior in confirmation
* `after` behavior in IDLE
* help text includes the intended workflow commands

### Important

This is additive coverage. Do not weaken existing regression tests.

---

## EXECUTION ORDER

Run chunks in this order:

1. Clarification Prompt Tightening
2. Confirmation UX Tightening
3. Policy / Plan / Warning Display Hierarchy
4. Zero-Op and Blocked-Plan UX
5. `after` vs `status` Role Clarification
6. Help Text and Workflow Discoverability
7. UX Smoke Coverage

Do not continue automatically between chunks.

After each chunk:

* stop
* summarize files changed
* summarize tests added or updated
* state any UX risks introduced
* confirm whether existing regression tests still pass

---

## ACCEPTANCE CRITERIA

M1 is complete when:

* clarification prompts feel continuous and stable
* confirmation prompts are consistent and easy to follow
* blocked/policy feedback is visually prominent and understandable
* zero-op plans do not leave stale or confusing state
* `after` is actionable and distinct from `status`
* help output reflects actual supported workflow UX
* regression tests still pass
* new UX smoke coverage passes

---

## OUT OF SCOPE

Do not implement in M1:

* multi-rule priority logic
* agent looping
* autonomous execution
* skill-aware routing fallback
* persistent workflow memory
* planner intelligence changes
* new filesystem actions
* new git write actions

Those belong to later milestones.

---

## MILESTONE CONTEXT

Completed before M1:

* Snappy Core
* Agent Spec V1
* Agent Spec V2
* Agent Spec V3
* Clarification Lock
* Agent Mode Control Surface
* Rule Enforcement Hooks

Current milestone:

* M1 — Workflow UX Tightening

Up next after M1:

* M2 — Rule Priority + Multi-Rule Resolution
* M3 — Snappy Agent Loop v1

```
```
