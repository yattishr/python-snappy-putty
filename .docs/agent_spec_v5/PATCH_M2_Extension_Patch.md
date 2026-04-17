# Snappy — M2 Extension Patch: Control Layer + Strict Confirmation Lock-In

## Goal

Extend the already-implemented M2 milestone to include the newer control-layer requirements that were added after the original M2 brief.

This is **not** a full reimplementation of M2.

It is a focused follow-up patch to add and lock in:

* control-layer framing
* explicit rule hierarchy behavior
* deterministic conflict resolution clarity
* strict confirmation model

---

## Context

### Original M2 already covered

* rule priority model
* multi-rule evaluation result object
* combined policy display for workflows
* deterministic conflict resolution
* updated visibility in `rules`, `agent`, `status`, and `agent doctor`
* regression and smoke coverage for combined rules

### New M2 additions that must now be locked in

* **Control Layer**
* **Rule hierarchy**
* **Conflict resolution**
* **Strict confirmation model**

This patch brings the implementation in line with the updated milestone definition.

---

## GLOBAL RULES

* Do not rewrite the existing M2 rule engine from scratch
* Do not remove current multi-rule evaluation behavior
* Do not weaken any existing block rules
* Do not change planner semantics outside confirmation/control behavior
* Do not change clarification lock behavior
* Do not introduce agent loop behavior
* Keep changes additive and narrow
* Preserve all already-passing M2 functionality

---

## PATCH SCOPE

This patch includes:

1. Formalize the Control Layer concept in runtime behavior and visibility
2. Lock in rule hierarchy semantics
3. Lock in deterministic conflict resolution semantics
4. Lock in a strict confirmation model
5. Update regression coverage for these additions

---

## PATCH 1 — Formalize the Control Layer

### Goal

Make it explicit in implementation and output that rule evaluation acts as a **control layer** between plan generation and execution.

### Required behavior

Snappy’s workflow should now be conceptually and operationally:

```text
intent
→ plan
→ control layer
→ block / confirm / warn / allow
→ execution
```

### Requirements

* Ensure policy evaluation happens as a distinct step before execution
* Ensure the control layer can be reasoned about independently from planning
* Keep current behavior intact, but tighten structure where needed
* Surfaces like `agent`, `status`, or `agent doctor` may reference “policy tiers” or “control layer” if helpful

### Acceptance

* control behavior is explicit in code structure and/or runtime summaries
* M2 no longer feels like “rules sprinkled around”
* rule handling is clearly centralized

---

## PATCH 2 — Lock in Rule Hierarchy

### Goal

Make the hierarchy an explicit contract, not just implied behavior.

### Hierarchy

```text
BLOCK > CONFIRM > WARN > INFO
```

### Requirements

* This ordering must be treated as a first-class runtime rule
* If a BLOCK decision exists, it must suppress confirmation and execution
* If no BLOCK exists and a CONFIRM decision exists, confirmation must be mandatory
* WARN must never bypass CONFIRM
* INFO must never affect runtime behavior

### Acceptance

* hierarchy is enforced deterministically
* hierarchy is visible in tests and, where useful, in diagnostic output
* no ambiguity about which tier wins

---

## PATCH 3 — Lock in Deterministic Conflict Resolution

### Goal

When multiple rules apply, Snappy must resolve them in a consistent and predictable way every time.

### Requirements

* Multi-rule evaluation must produce one final effective outcome
* If multiple rules in the same tier apply, behavior must still be deterministic
* If BLOCK and CONFIRM both apply, BLOCK wins
* If CONFIRM and WARN both apply, CONFIRM remains mandatory and WARN may still be shown
* INFO never changes the final outcome

### Desired examples

#### Example A

Rules:

* `protect_project_root`
* `require_confirm`

Command:

```text
copy README.md to /
```

Expected:

* BLOCK
* no confirmation prompt

#### Example B

Rules:

* `require_confirm`
* `custom_note`

Command:

```text
copy README.md to tests/
```

Expected:

* CONFIRM
* info remains informational

#### Example C

Rules:

* future warning rule
* `require_confirm`

Expected:

* CONFIRM plus warning
* no ambiguity

### Acceptance

* same inputs always produce same outcome
* ordering is stable
* outputs are not contradictory

---

## PATCH 4 — Strict Confirmation Model (Lock This In)

### Goal

Formalize confirmation as a strict control-layer requirement, not just a nice-to-have UX step.

### Meaning

If the resolved policy outcome is CONFIRM, then:

* execution must not proceed without explicit confirmation
* warnings must not bypass confirmation
* planner output alone must not imply execution readiness
* invalid confirmation input must not degrade state
* block rules must suppress confirmation entirely

### Required rules

If final effective outcome is:

#### BLOCK

* no YES/NO prompt
* show block message only
* no execution

#### CONFIRM

* YES/NO confirmation is mandatory
* execution cannot proceed until YES
* NO cancels cleanly
* invalid input re-prompts or preserves pending confirmation state safely

#### ALLOW

* normal allowed behavior proceeds according to existing Snappy model

### Important

This patch is about locking in confirmation as a **hard control contract**.

Not optional.
Not best-effort.
Not bypassable by warnings or mixed rule states.

### Acceptance

* strict confirmation behavior is explicit
* mixed-rule outcomes never weaken confirmation
* blocked flows never fall through into confirmation
* confirmation state remains deterministic

---

## PATCH 5 — Visibility and Diagnostics Update

### Goal

Reflect the updated control-layer semantics in the inspectable runtime surfaces.

### Requirements

Update as needed:

#### `rules`

Show tier clearly where useful

#### `agent`

May show grouped policy tiers and effective control-layer concepts

#### `status`

Should remain concise, but may summarize:

* loaded rules
* tier counts
* whether current flow is blocked / awaiting confirm / allowed

#### `agent doctor`

May include:

* policy tier counts
* control-layer readiness
* confirmation-capable rule presence

### Acceptance

* visibility reflects the new locked-in semantics
* output remains readable
* diagnostics help explain why behavior happened

---

## PATCH 6 — Regression and Smoke Coverage

### Goal

Add coverage specifically for the new M2 extension behavior.

### Required tests

#### Test 1 — BLOCK suppresses confirmation

Rules:

* `protect_project_root`
* `require_confirm`

Command:

```text
copy README.md to /
```

Expected:

* block message shown
* no YES/NO prompt

#### Test 2 — CONFIRM remains mandatory with mixed rules

Rules:

* `require_confirm`
* `custom_note`

Command:

```text
copy README.md to tests/
```

Expected:

* YES/NO prompt required
* info does not weaken confirmation

#### Test 3 — WARN cannot bypass confirmation

If warning-tier rules exist or are stubbed:

* confirm remains mandatory when confirm-tier rule exists

#### Test 4 — Invalid confirmation input is safe

When awaiting confirmation:

* invalid input does not execute
* state remains deterministic

#### Test 5 — Multiple same-tier rules remain deterministic

If multiple informational or confirm-tier rules exist:

* output and outcome remain stable and non-contradictory

---

## Acceptance Criteria

This patch is complete when:

* control-layer behavior is explicit and centralized
* hierarchy is locked in as a runtime contract
* conflict resolution is deterministic and stable
* strict confirmation model is formalized and enforced
* diagnostics reflect the updated semantics
* regression coverage includes these additions
* all original M2 behavior still passes

---

## Output Required From Codex

After implementation, provide:

* summary of files changed
* summary of control-layer changes added
* summary of strict confirmation changes added
* summary of tests added or updated
* confirmation that original M2 behavior still passes
* confirmation that the new M2 extension tests pass

---

## Milestone Context

Completed before this patch:

* Snappy Core
* Agent Spec V1
* Agent Spec V2
* Agent Spec V3
* Workflow UX Tightening
* M2 core implementation

Current work:

* M2 Extension Patch — Control Layer + Strict Confirmation Lock-In
