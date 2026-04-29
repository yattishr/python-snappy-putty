# Snappy M5 Guardrails Follow-up Patch — Rejected Planning Must Reset Workflow State

## Context

After adding the M5 grounded-planning relevance gate, a rejected non-project request can leave Snappy in a dirty workflow state.

Observed error:

```text
ActiveGoalConflictError: Cannot start goal 'help me create a fitness routine' while state=PLANNING active_goal='help me build a rocketship'
```

Result:

```text
terminal crash + burn
```

Banana rocketship confirmed.

---

## Root Cause

The relevance gate rejects or skips grounded planning, but the workflow/session state is not reset after rejection.

The rejected goal remains active:

```text
state=PLANNING
active_goal='help me build a rocketship'
```

So the next request hits the single-goal guard and raises `ActiveGoalConflictError`.

---

## Required Behavior

When grounded planning is skipped because the goal is not project-related:

- Do not create a `GroundedPlan`.
- Do not persist `last_plan`.
- Do not move to confirmation.
- Do not leave state as `PLANNING`.
- Do not leave `active_goal` populated.
- Do not raise `ActiveGoalConflictError` on the next request.
- Do append a history event.
- Do return cleanly to `IDLE`.

A rejected or skipped plan must be treated as a completed workflow outcome, not a half-open workflow.

---

## Required State After Rejection

After this input:

```text
help me build a rocketship
```

Expected state:

```text
Current state: IDLE
Active goal: (none)
Pending plan: (none)
Awaiting confirmation: no
Last blocked goal: help me build a rocketship
Last route: ask
Error message: goal_not_project_related
```

If `error_message` is too noisy in normal status, it may be cleared after display, but the workflow must not remain active.

---

## Expected Output Behavior

For input:

```text
help me build a rocketship
```

Expected output:

```text
This request does not appear to be related to the current project.

I did not create a grounded project plan because there is no clear connection between the request and the inspected workspace.
```

Then the next input should work normally:

```text
help me create a fitness routine
```

That second request should either:

- be rejected cleanly as unrelated, or
- be handled as a non-project/general request if such a path exists.

It must not crash.

---

## Implementation Notes

Find the code path where the grounded-planning relevance gate rejects a request.

That branch must explicitly reset/complete the workflow state.

Suggested behavior:

```text
on relevance rejection:
  record blocked/skipped goal
  clear active goal
  clear pending plan
  keep last_plan unchanged
  set state to IDLE
  append history event
  return user-facing rejection message
```

Do not route this through normal plan persistence.

Do not set `awaiting_confirmation`.

Do not leave any pending confirmation context.

---

## History Log Entry

Append a history event similar to:

```md
## <timestamp>
Event: Grounded planning skipped
Goal: help me build a rocketship
Reason: goal_not_project_related
Snapshot ID: snap_xxx
Result: no_plan_created
Workflow state: reset_to_idle
```

---

## Tests Required

Add coverage in:

```text
tests/test_active_mode_v1.py
```

### Test 1 — Rejected grounded planning resets state

Steps:

1. Start active mode.
2. Ensure a project snapshot exists.
3. Send:

```text
help me build a rocketship
```

Expected:

- Output contains the project relevance rejection.
- Session state is `IDLE`.
- `active_goal` is `None` or absent.
- Pending/current plan is `None` or absent.
- `last_plan` is unchanged or absent.
- `last_blocked_goal` is set to the rejected goal.
- No confirmation is pending.

---

### Test 2 — Second rejected request does not crash

Steps:

1. Send:

```text
help me build a rocketship
```

2. Then send:

```text
help me create a fitness routine
```

Expected:

- No `ActiveGoalConflictError`.
- No terminal crash.
- Second request is handled or rejected cleanly.
- State remains `IDLE` afterward.

---

### Test 3 — Valid project request still works after rejection

Steps:

1. Send unrelated request:

```text
help me build a rocketship
```

2. Then send valid project request:

```text
help me improve this CLI
```

Expected:

- First request creates no plan.
- First request resets workflow state.
- Second request creates a grounded plan normally.
- Plan is bound to the current snapshot.
- State transitions are correct.

---

## Verification Commands

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest tests/test_active_mode_v1.py
python -m pytest
```

Manual verification inside Snappy:

```text
agent mode active
help me build a rocketship
status
help me create a fitness routine
status
help me improve this CLI
status
```

Expected manual result:

- Rocketship request is rejected cleanly.
- Fitness routine request does not crash the terminal.
- Valid CLI improvement request still creates a grounded project plan.
- Status does not show stale `PLANNING` state after rejected requests.

---

## Non-Negotiable Guardrail

A rejected or skipped grounded plan must not leave Snappy in a half-open workflow state.

Rejected planning should behave like a controlled block, not a crash.

Core principle:

```text
Reject cleanly.
Reset state.
Keep the terminal alive.
No banana rocketships.
```
