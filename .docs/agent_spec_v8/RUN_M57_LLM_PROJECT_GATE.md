# Snappy M5.7 — LLM-First Planning Gate + Clean Non-Project State Handling

## Purpose

M5.7 fixes a critical planning-quality issue discovered during manual testing.

The current deterministic planner can produce safe-looking but unusable generic plans for broad developer goals, such as:

```text
help me improve this CLI
```

This is not acceptable.

Snappy must never pretend to have a useful implementation plan when LLM-assisted planning is unavailable.

Core principle:

```text
Smart or honest.
Never fake smart.
```

---

## Problem

Current behavior:

```text
LLM-assisted planning is unavailable.
Deterministic planning and inspection remain available.
```

Then Snappy creates a generic deterministic plan anyway.

Example bad plan:

```text
1. Inspect pyproject.toml, README.md, docs/ROADMAP.md.
2. Apply the smallest project change that addresses: help me improve this CLI.
3. Add or update tests.
```

This is too generic to be useful to a developer.

For broad developer work, deterministic planning is not reliable.

---

## M5.7 Goal

Change Plan Mode so that broad contextual developer plans require LLM-assisted planning.

If LLM-assisted planning is unavailable:

- inspect project context if appropriate
- inform the user clearly
- do not create a plan
- do not persist a plan
- do not enter confirmation
- return to `IDLE`

---

## High-Level Routing Model

Add or update intent classification so Snappy separates requests into:

```text
structured_project_intent
project_developer_goal
project_inspection
general_knowledge_question
current_info_question
unrelated_non_project_request
unsupported_external_tool_request
```

Only this category may enter implementation planning:

```text
project_developer_goal
```

But it requires LLM-assisted planning.

---

## Planning Rules

### 1. Structured project intents may remain deterministic

These are allowed without LLM:

```text
inspect project
inspect files
show plan
why this plan
explain step 1
summarize README.md
explain file src/taskcli/main.py
copy README.md to docs/
git status
list tests
```

These are narrow, bounded, and structured.

---

### 2. Broad developer goals require LLM-assisted planning

These must NOT use deterministic planning fallback:

```text
help me improve this CLI
add logging
refactor auth flow
build payment integration
add PayFast support
fix webhook flow
improve error handling
implement user onboarding
review this codebase
make the app production-ready
```

If LLM is available, use the LLM-assisted planning pipeline.

If LLM is unavailable, do not create a plan.

---

### 3. Non-project/general/current-info questions must not enter project planning

Examples:

```text
what is the weather in San Francisco today?
what is the price of bitcoin?
who is playing in this weekend's NBA finals?
what is the movie Interstellar about?
help me create a fitness routine
plan my holiday
write me a poem
```

These must not create grounded project plans.

They should terminate cleanly as non-project outcomes.

---

## Agent Mode and LLM Behavior

When agent mode is `active` or `passive`:

```text
Snappy should attempt LLM-assisted planning by default for project_developer_goal requests.
```

But:

```text
If LLM-assisted planning is unavailable, Snappy must NOT fallback to deterministic implementation planning.
```

Expected behavior:

```text
LLM-assisted planning is unavailable.

I inspected the project, but I did not create a plan because this request requires contextual developer planning.

You can still use inspection commands such as:
- inspect project
- inspect files
- show plan
```

---

## State Machine Handling

Use the minimal state outcome preferred for M5.7:

```text
IDLE
→ PLANNING_SKIPPED
→ IDLE
```

This outcome should be used for:

```text
llm_required_but_unavailable
non_project_question
unsupported_current_info_question
goal_not_project_related
```

Important:

`PLANNING_SKIPPED` is not a failure state.

It is a terminal non-plan outcome.

---

## Required State Cleanup

For any skipped planning path, clear:

```text
active_goal
pending_question
pending_plan
awaiting_confirmation
current_plan
```

Do not persist a new `last_plan`.

Do not overwrite a previous valid `last_plan` unless the existing design already requires clearing it for safety.

Recommended behavior:

- preserve previous valid `last_plan` only if it remains explicitly visible as previous/history
- do not make it appear pending for the new skipped request

---

## Status Fields

Add or update status fields so skipped outcomes are visible without being treated as crashes/errors.

Recommended fields:

```text
Last skipped goal: <goal>
Last skip reason: <reason>
```

Examples:

```text
Last skipped goal: what is the weather in San Francisco today?
Last skip reason: non_project_question
```

or:

```text
Last skipped goal: help me improve this CLI
Last skip reason: llm_required_but_unavailable
```

Avoid using `last_blocked_goal` for ordinary non-project/general questions.

Reserve `last_blocked_goal` for policy/safety blocks.

---

## Expected Behavior Examples

### Example 1 — Broad developer goal, LLM unavailable

Input:

```text
help me improve this CLI
```

Expected:

```text
Inspecting project context...
Using snapshot: snap_xxx

LLM-assisted planning is unavailable.

I inspected the project, but I did not create a plan because this request requires contextual developer planning.

You can still use inspection commands such as:
- inspect project
- inspect files
- show plan
```

State after:

```text
Current state: IDLE
Active goal: (none)
Pending plan: (none)
Awaiting confirmation: no
Grounded planning: no
Last plan: absent or unchanged
Last skipped goal: help me improve this CLI
Last skip reason: llm_required_but_unavailable
```

---

### Example 2 — Broad developer goal, LLM available

Input:

```text
help me improve this CLI
```

Expected:

```text
Inspecting project context...
Using snapshot: snap_xxx
Generating LLM-assisted grounded plan...
```

Then create a developer-usable plan.

The plan must be:

- specific
- grounded in selected files
- bound to snapshot
- validated before persistence

---

### Example 3 — General question

Input:

```text
what is the movie Interstellar about?
```

Expected:

```text
This looks like a general question, not a project task.

No project plan was created.
```

Optional if general LLM response path exists:

```text
Interstellar is a science-fiction film about...
```

But it must not create a project plan.

State after:

```text
Current state: IDLE
Active goal: (none)
Pending plan: (none)
Last skipped goal: what is the movie Interstellar about?
Last skip reason: non_project_question
```

---

### Example 4 — Current-info question

Input:

```text
what is the price of bitcoin?
```

Expected:

```text
This looks like a current information request, not a project task.

Snappy cannot answer live market data unless current-info tools are enabled.

No project plan was created.
```

State:

```text
IDLE
```

No plan, no confirmation, no active goal.

---

## LLM-Assisted Planning Pipeline

When LLM planning is available and the request is a `project_developer_goal`, use this pipeline:

```text
User goal
↓
Relevance check
↓
ProjectSnapshot
↓
Context selector
↓
Context compressor
↓
LLM-assisted planning
↓
Plan validator
↓
Session memory
↓
History log
↓
User interaction layer
```

---

## Context Selector

Do not send the entire repository to the LLM.

Select relevant files from `ProjectSnapshot`.

Use deterministic heuristics first.

Examples:

### If goal includes CLI

Prefer files named:

```text
main.py
cli.py
app.py
commands.py
```

Also include:

```text
tests/
README.md
```

### If goal includes payment/billing

Prefer files or paths containing:

```text
payment
payments
billing
checkout
subscription
payfast
stripe
webhook
```

### If goal includes auth

Prefer files or paths containing:

```text
auth
login
session
middleware
clerk
user
```

### If goal includes database/storage

Prefer files or paths containing:

```text
storage
db
database
model
schema
repository
```

### If goal includes tests

Prefer:

```text
tests/
test_*.py
*_test.py
```

---

## Context Compressor

For selected files, avoid dumping full large files.

Include compact information such as:

```text
file path
file purpose
functions/classes found
imports
important snippets
first 20–40 lines if small enough
```

For small files, full content may be acceptable.

The LLM should receive enough context to reason, not the whole repo as a haystack.

---

## LLM Prompt Requirements

The LLM prompt must instruct the model to:

- generate a grounded implementation plan
- only reference provided files
- not invent files
- produce concrete developer-actionable steps
- include risk levels
- include assumptions
- output strict JSON matching the existing `GroundedPlan` schema or compatible internal schema

Example instruction:

```text
You are generating a grounded implementation plan for a developer.

Only use the files provided in the project context.
Do not invent files, modules, directories, commands, or dependencies.
If the provided context is insufficient, say so in the plan assumptions or return a no-plan result.
```

---

## Plan Validation

After LLM output, validate before storing.

Reject if:

```text
references files not in ProjectSnapshot
contains empty steps
contains vague steps
contains invalid risk values
introduces unsafe paths
violates existing policy/rules
```

Plan validation should reuse or extend the M5.6 integrity validator where appropriate.

---

## History Logging

Append history events for skipped planning:

```md
## <timestamp>
Event: Planning skipped
Goal: help me improve this CLI
Reason: llm_required_but_unavailable
Snapshot ID: snap_xxx
Result: no_plan_created
Workflow state: reset_to_idle
```

For non-project questions:

```md
## <timestamp>
Event: Planning skipped
Goal: what is the price of bitcoin?
Reason: non_project_question
Result: no_plan_created
Workflow state: reset_to_idle
```

For successful LLM planning:

```md
## <timestamp>
Event: LLM-assisted plan created
Goal: help me improve this CLI
Snapshot ID: snap_xxx
Files provided:
- src/taskcli/main.py
- src/taskcli/tasks.py
- tests/test_tasks.py
Result: plan_created
```

---

## Tests Required

Add or update tests in:

```text
tests/test_active_mode_v1.py
```

Add subprocess tests if that is where CLI/REPL behavior is currently covered.

---

### Test 1 — Broad developer goal with LLM unavailable does not create deterministic plan

Setup:

```text
agent mode active
LLM unavailable / SDK disabled
```

Input:

```text
help me improve this CLI
```

Expected:

- project inspection may run
- output says LLM-assisted planning is unavailable
- output says no plan was created
- no deterministic plan is displayed
- no `last_plan` is created for this request
- state returns to IDLE
- `last_skipped_goal` is set
- `last_skip_reason = llm_required_but_unavailable`

---

### Test 2 — Non-project general question exits cleanly

Input:

```text
what is the movie Interstellar about?
```

Expected:

- no project plan created
- no active goal left behind
- no pending plan
- state is IDLE
- `last_skip_reason = non_project_question`

---

### Test 3 — Current-info question exits cleanly

Input:

```text
what is the price of bitcoin?
```

Expected:

- no project plan created
- no active goal
- no pending plan
- state is IDLE
- user is informed current-info tools are not available, if applicable

---

### Test 4 — Existing structured project intents still work without LLM

Inputs:

```text
inspect project
inspect files
show plan
explain step 1
```

Expected:

- these routes still work as before where applicable
- no LLM required for inspection/display commands

---

### Test 5 — LLM available creates LLM-assisted plan

Setup:

```text
SNAPPY_PUTTY_ENABLE_SDK=1
mock SDK response
agent mode active
```

Input:

```text
help me improve this CLI
```

Expected:

- LLM-assisted planning route used
- plan mode is `llm_assisted`
- plan is specific and uses selected context files
- plan is validated
- plan is persisted
- state transitions correctly

---

### Test 6 — No fallback after LLM failure

Setup:

```text
agent mode active
LLM enabled but SDK call fails
```

Input:

```text
help me improve this CLI
```

Expected:

- no deterministic implementation fallback
- clear LLM unavailable/failure message
- no plan created
- state returns to IDLE
- history logs skipped planning

---

### Test 7 — Previous valid plan is not confused with skipped request

Setup:

1. Create a valid LLM-assisted plan.
2. Then ask a non-project question:

```text
what is the weather in San Francisco today?
```

Expected:

- no new plan created
- status does not show the weather question as pending plan
- previous plan is not silently overwritten as if it belongs to the weather question
- state remains IDLE

---

## Manual Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest tests/test_active_mode_v1.py
python -m pytest
```

Manual REPL checks:

```text
agent mode active
help me improve this CLI
status
what is the movie Interstellar about?
status
what is the price of bitcoin?
status
inspect project
inspect files
```

With SDK disabled, broad developer goals should not produce deterministic implementation plans.

With SDK enabled and mocked/working, broad developer goals should produce LLM-assisted plans.

---

## Non-Negotiable Invariants

```text
No LLM.
No real developer plan.
No pretending.
```

```text
Only project_developer_goal enters planning.
```

```text
Non-project questions must terminate cleanly in IDLE.
```

```text
Skipped planning is not failure.
It is a controlled non-plan outcome.
```

```text
Snappy may inspect when unsure.
Snappy may refuse to plan when incapable.
Snappy must never fake a developer plan.
```

---

## Acceptance Criteria

M5.7 is complete when:

- deterministic generic implementation planning is removed
- broad developer goals require LLM-assisted planning
- LLM unavailable leads to inspection-only plus clear user message
- general/current-info questions do not enter project planning
- skipped planning paths reset to IDLE
- status clearly shows skipped goal/reason
- structured deterministic commands still work
- full test suite passes

---

## Final Product Principle

Snappy should be:

```text
useful when capable
honest when not
safe always
```
