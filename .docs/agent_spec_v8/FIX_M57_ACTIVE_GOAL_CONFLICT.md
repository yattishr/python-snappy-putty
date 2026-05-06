# Snappy M5.7.x — Active Goal Conflict Handling + Single Pending Goal Buffer

## Goal

Prevent crashes when the user sends a new goal while another goal is still active.

Core rule:

```text
One active goal.
One parked goal.
Zero crashes.
```

## Problem

Currently, if Snappy is in PLANNING, CONFIRMATION, or EXECUTING and the user enters a new goal, Snappy can raise:
```text
ActiveGoalConflictError
```

and crash. This must never happen.

## Required Fix 1 — Catch Active Goal Conflicts

When a new goal arrives while another goal is active:

``text
Required Fix 1 — Catch Active Goal Conflicts

When a new goal arrives while another goal is active:
```

Do not start the new goal.

Do not crash.

Show:
```text
A goal is already active:

<active_goal>

I can’t start a second goal yet.

You can:
- finish the current goal
- cancel it
- park this new request for later
```

State must remain unchanged.

---

## Required Fix 2 — Add Single Pending Goal Buffer

Support one parked request.

Persist in session.json:

```json
{
  "pending_goal": {
    "text": "help me add logging",
    "created_at": "...",
    "reason": "active_goal_in_progress"
  }
}
```

Only one pending goal is allowed.

If a pending goal already exists and user tries to park another:

```text
A pending goal already exists:

<pending_goal>

Replace it? [yes/no]
```

---

## Required Commands

Add REPL routes:

``text
show pending
resume pending
clear pending
```

show pending

If pending exists:

```text
Pending goal:
<goal>
Reason: active_goal_in_progress
Created: <timestamp>
```

If none:

```text
No pending goal.
```

resume pending

Only allowed when current state is IDLE.

If not IDLE:

```text
Cannot resume pending goal while another goal is active.
```


If IDLE:

move pending goal into normal goal handling
clear pending_goal
process it as if user typed it fresh
clear pending

Deletes pending goal.

Output:
```text
Pending goal cleared.
```

---


## Required Fix 3 — Optional Park Prompt

When conflict happens, user may type:

```text
park
```

or:

```text
park this
```

Expected:

store the conflicting goal as pending_goal
keep current active workflow unchanged

If implementing prompt state is too invasive, skip interactive prompt and just add:

```text
Use: park this
```

to the conflict message.

---

## State Machine Rules

Do not add multi-goal execution.

Do not auto-run pending goal.

Do not queue multiple goals.

Do not mutate current plan.

Do not change current active workflow state.

Pending goal is storage only.

---

## History Logging

Append events:

```text
Event: Goal conflict detected
Active goal: <active_goal>
Incoming goal: <new_goal>
Result: not_started
```

```text
Event: Goal parked
Goal: <pending_goal>
Reason: active_goal_in_progress
```

```text
Event: Pending goal resumed
Goal: <pending_goal>
```

```text
Event: Pending goal cleared
Goal: <pending_goal>
```

---

## Tests Required
New goal during PLANNING does not crash.
New goal during CONFIRMATION does not crash.
Current active goal/state remains unchanged after conflict.
show pending works with and without pending goal.
resume pending only works from IDLE.
clear pending removes pending goal.
Existing pending goal is not silently overwritten.

---

## Verification

Run:

``` python
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Manual:

```text
agent mode active
help me improve this CLI
help me add logging
show pending
park this
show pending
cancel
resume pending
status
```

---

## Non-Negotiable

A second goal must never crash Snappy.

No hidden queue.
No automatic execution.
No surprise goal switching.


This keeps it tight: conflict handling first, one parked goal only, no multi-lane traffic chaos.
