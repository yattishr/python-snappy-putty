# Snappy — M2: Rule Priority + Multi-Rule Resolution

## Goal

Introduce a deterministic policy evaluation layer so that when multiple rules are loaded, Snappy resolves them in a consistent, inspectable order.

This milestone defines how rules combine.

It must answer:

* which rules win
* which rules block
* which rules require confirmation
* which rules only warn
* how combined policy decisions are displayed

This is the step that turns Snappy’s rule system from “individual safeguards” into a real policy engine.

---

## Why This Milestone Comes Now

Snappy already has:

* deterministic state machine
* clarification lock
* rule enforcement hooks
* agent runtime inspection
* policy block messaging
* workflow UX tightening

But right now, rules are enforced mostly one-at-a-time.

As Snappy grows, repos will load combinations like:

* `protect_project_root`
* `require_confirm`
* `no_active_mode`
* future rules like:

  * `readonly_workspace`
  * `protect_env_files`
  * `protect_git_history`
  * `warn_large_copy`

Without a deterministic resolution model, rule behavior will become inconsistent and hard to reason about.

M2 defines the order of authority.

---

## GLOBAL RULES

* Do not rewrite the planner
* Do not rewrite the state machine
* Do not remove existing supported rules
* Do not allow markdown rules to execute arbitrary logic
* Continue using internal predefined rule hooks only
* Keep all rule behavior deterministic and inspectable
* Keep existing single-rule behavior intact unless changed explicitly by priority resolution
* Preserve existing regression behavior unless this milestone intentionally changes output structure
* Prefer narrow, additive changes over broad refactors

---

## POLICY MODEL

Snappy must evaluate loaded rules into one or more policy decisions in the following priority order:

### 1. BLOCK

These rules stop the action entirely.

Examples:

* `protect_project_root`
* `readonly_workspace`
* `no_active_mode`

If any BLOCK rule triggers:

* operation is not executed
* no confirmation is shown
* block message is rendered
* lower-priority rules do not override the block

### 2. CONFIRM

These rules allow the action, but require explicit confirmation.

Examples:

* `require_confirm`
* future: `confirm_destructive_actions`

If no BLOCK rule triggers, and one or more CONFIRM rules trigger:

* confirmation is required
* policy summary may show why confirmation is being required
* execution only proceeds after YES

### 3. WARN

These rules do not block or require confirmation by themselves, but add warnings.

Examples:

* future: `warn_large_copy`
* future: `warn_many_files`

If no BLOCK rule triggers:

* warnings may be shown alongside plan output
* warnings do not prevent execution

### 4. INFO

These rules are informational only.

Examples:

* `custom_note`
* unknown/unsupported informational rules

These should be surfaced in inspection views, but not affect runtime behavior.

---

## CORE RESOLUTION LAW

Policy resolution order must be:

```text id="w7a5h9"
BLOCK > CONFIRM > WARN > INFO
```

This means:

* BLOCK wins over everything
* CONFIRM applies only if no BLOCK triggers
* WARN applies only if no BLOCK prevents the action
* INFO never changes runtime behavior

---

## M2 SCOPE

This milestone includes:

1. Rule priority model
2. Multi-rule evaluation result object
3. Combined policy display for workflows
4. Deterministic conflict resolution
5. Updated visibility in `rules`, `agent`, `status`, and `agent doctor`
6. Regression and smoke coverage for combined rules

---

## CHUNK 1 — Introduce Policy Decision Model

### Goal

Create a structured internal representation of policy outcomes.

### Requirements

Add an internal policy evaluation result object that can capture:

* triggered block rules
* triggered confirm rules
* triggered warn rules
* informational rules
* final effective outcome

Suggested shape:

```python id="gaax7z"
PolicyDecision(
    outcome="block" | "confirm" | "allow",
    block_rules=[...],
    confirm_rules=[...],
    warn_rules=[...],
    info_rules=[...],
)
```

The exact type can vary, but it must be explicit and testable.

### Notes

* Keep this internal
* Do not expose raw internals directly to users
* This object becomes the canonical output of policy evaluation

### Tests

1. no rules → allow
2. confirm rule only → confirm
3. block rule only → block
4. info rules only → allow + info only

---

## CHUNK 2 — Deterministic Rule Priority Resolution

### Goal

Implement the actual priority logic.

### Required order

```text id="bct7ar"
BLOCK > CONFIRM > WARN > INFO
```

### Requirements

When multiple rules are loaded:

* evaluate all relevant enforceable rules
* collect all triggered rule outcomes
* determine final effective outcome using the priority order above

### Examples

#### Example A

Loaded:

* `protect_project_root`
* `require_confirm`

Action:

* `copy README.md to /`

Result:

* final outcome = BLOCK
* confirmation is not shown

#### Example B

Loaded:

* `require_confirm`
* `custom_note`

Action:

* `copy README.md to tests/`

Result:

* final outcome = CONFIRM
* informational rule remains non-operative

#### Example C

Loaded:

* `custom_note`

Action:

* safe copy

Result:

* final outcome = ALLOW

### Tests

1. BLOCK outranks CONFIRM
2. CONFIRM applies when no BLOCK exists
3. INFO does not change outcome
4. future WARN category can coexist without affecting final outcome incorrectly

---

## CHUNK 3 — Combined Policy Rendering

### Goal

Show policy decisions cleanly when multiple rules are relevant.

### Requirements

For blocked flows:

* render a dominant policy block panel
* include primary blocking rule(s)
* optionally include additional relevant secondary policy context
* do not show confirmation when blocked

For confirmation flows:

* render a policy summary panel before the plan
* if multiple confirm-related rules apply, summarize them clearly
* keep the wording concise

For warning flows:

* warnings appear in the warning section, not as blocks

### Desired rendering patterns

#### Blocked case

```text id="a43hcu"
Policy Block
Operation blocked by rule: protect_project_root
```

If more than one blocking rule triggers in future, show a concise list.

#### Confirm case

```text id="83as4f"
Policy
• Loaded rules require confirmation before filesystem changes are applied.
```

#### Warning case

Warnings remain under warnings, not policy block.

### Tests

1. block case renders block panel only
2. block case suppresses confirmation prompt
3. confirm case renders policy summary before plan
4. combined rules do not create cluttered duplicate messages

---

## CHUNK 4 — Rule Classification by Priority Tier

### Goal

Expose each rule’s tier cleanly in runtime inspection surfaces.

### Requirements

Extend rule metadata/classification so rules can be tagged internally as:

* block
* confirm
* warn
* info

Examples for current rules:

* `protect_project_root` → block
* `no_active_mode` → block
* `require_confirm` → confirm
* `custom_note` → info

### Surfaces to update

* `rules`
* `agent`
* `agent doctor`

### Example `rules` output

```text id="ox635a"
Loaded rules:
- protect_project_root [protect_project_root] (enforceable:block)
- require_confirm [require_confirm] (enforceable:confirm)
- custom_note [custom_note] (informational)
```

Exact formatting can vary, but the tier should be visible.

### Tests

1. block-tier rule classified correctly
2. confirm-tier rule classified correctly
3. info-tier rule still listed properly

---

## CHUNK 5 — Status and Agent Visibility for Effective Policy

### Goal

Make current policy posture inspectable.

### Requirements

Update status/agent surfaces so users can understand both:

* loaded rules
* effective enforced categories

### `status`

Keep concise. Example:

```text id="4g2q5i"
Loaded rules: 3
Policy tiers: block=2, confirm=1, warn=0, info=1
```

### `agent`

Can be richer, for example:

* block rules: protect_project_root, no_active_mode
* confirm rules: require_confirm
* informational rules: custom_note

### `agent doctor`

Should report:

* loaded rules
* enforceable rules
* tier counts
* malformed or unsupported rules

### Tests

1. status shows tier summary
2. agent shows grouped rules
3. doctor shows tier counts

---

## CHUNK 6 — Multi-Rule Conflict Scenarios

### Goal

Add explicit test coverage for realistic rule combinations.

### Required scenarios

#### Scenario 1

Loaded:

* `protect_project_root`
* `require_confirm`

Command:

```text id="w8d1ju"
copy README.md to /
```

Expected:

* block
* no confirmation
* block message shown

#### Scenario 2

Loaded:

* `require_confirm`
* `custom_note`

Command:

```text id="ax3v0f"
copy README.md to tests/
```

Expected:

* confirmation required
* no block
* informational rule does not change behavior

#### Scenario 3

Loaded:

* `no_active_mode`
* `custom_note`

Command:

```text id="9n8nmp"
agent mode active
```

Expected:

* block
* current mode unchanged

#### Scenario 4

Loaded:

* info rules only

Command:
safe copy

Expected:

* normal flow
* no policy enforcement side effect

### Tests

Add explicit tests for all four.

---

## CHUNK 7 — Regression and Smoke Coverage

### Goal

Ensure M2 does not destabilize the existing runtime.

### Requirements

Re-run and/or extend coverage for:

* baseline no-agent flow
* clarification lock
* clarification answer flow
* cancel during clarification
* require_confirm
* protect_project_root
* no_active_mode
* agent mode control
* informational rules
* no-agent regression behavior

Add smoke coverage for:

* combined block + confirm rules
* combined confirm + info rules
* grouped visibility output

### Important

Do not weaken existing regression coverage.

---

## EXECUTION ORDER

Run chunks in this order:

1. Policy Decision Model
2. Deterministic Rule Priority Resolution
3. Combined Policy Rendering
4. Rule Classification by Priority Tier
5. Status and Agent Visibility for Effective Policy
6. Multi-Rule Conflict Scenarios
7. Regression and Smoke Coverage

Do not continue automatically between chunks.

After each chunk:

* stop
* summarize files changed
* summarize tests added or updated
* state any risks introduced
* confirm whether regression tests still pass

---

## ACCEPTANCE CRITERIA

M2 is complete when:

* multiple rules are evaluated into a single deterministic policy outcome
* BLOCK rules always outrank CONFIRM, WARN, and INFO
* CONFIRM applies only when no BLOCK rule triggers
* INFO rules never affect runtime behavior
* rule tiers are visible in inspection surfaces
* combined rule scenarios behave predictably
* existing regressions still pass
* new multi-rule regression coverage passes

---

## OUT OF SCOPE

Do not implement in M2:

* agent looping
* autonomous execution
* planner intelligence changes
* skill-aware routing fallback
* persistent workflow memory
* free-form rule DSL
* arbitrary markdown-defined rule behavior
* agent-generated policy

Those belong to later milestones.

---

## MILESTONE CONTEXT

Completed before M2:

* Snappy Core
* Agent Spec V1
* Agent Spec V2
* Agent Spec V3
* Clarification Lock
* Agent Mode Control Surface
* Rule Enforcement Hooks
* Workflow UX Tightening

Current milestone:

* M2 — Rule Priority + Multi-Rule Resolution

Up next after M2:

* M3 — Snappy Agent Loop v1
