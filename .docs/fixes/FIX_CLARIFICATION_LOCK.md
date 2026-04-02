# Snappy — State Machine Hardening: Clarification Lock

## Goal
Prevent Snappy from silently abandoning a pending clarification flow when the user types a new goal.

If Snappy is waiting for an answer to a pending question, it must not accept a new intent unless the current flow is explicitly cancelled.

This is a **state machine integrity fix**, not a copy-specific fix.

---

## Problem Being Solved

Current unsafe behavior:

1. User starts a goal that requires clarification:
   - `copy README.md`
   - Snappy asks: `destination path>`

2. Instead of answering, the user types a brand new goal:
   - `give me a file listing for the current directory`

3. Snappy executes the new goal and silently discards the old clarification state.

This is unsafe because it:
- breaks deterministic state handling
- allows silent goal replacement
- creates future risk for multi-step workflows
- weakens trust in the pending-question flow

---

## Desired Behavior

When Snappy is in a pending-question state, only a limited set of inputs should be allowed.

### Allowed while clarification is pending
- direct answer to the pending question
- `cancel`
- `status`
- `help`

### Blocked while clarification is pending
Any new intent or unrelated command, including examples like:
- `give me a file listing for the current directory`
- `git status`
- `copy a.txt to b.txt`
- `agent`
- `skills`
- `rules`
- `agent mode`
- any other new request that is not the pending answer and not in the allowlist above

---

## Required UX

If the user enters a blocked command while a pending question exists, Snappy should respond with a clear message like:

You have a pending question:

destination path>

Answer it, or type 'cancel' to abandon the current goal.

Do not execute the new command.  
Do not replace the active goal.  
Do not clear the pending question.

---

## State Machine Rule

If:
- `pending_question` is not empty
- current state is `CLARIFICATION`

Then:
- only allow answer input
- only allow `cancel`, `status`, `help`
- block all other commands
- preserve the current active goal and pending question

---

## Implementation Requirements

- Keep this additive and low-risk
- Do not rewrite the entire parser/router
- Apply the lock centrally so it protects all current and future clarification flows
- Reuse existing state/session fields where possible
- Do not change successful confirmation/execution behavior
- Do not change existing non-clarification behavior
- Do not allow blocked commands to mutate state
- Do not allow blocked commands to replace the active goal

---

## Allowed Input Handling

### 1. Answer input
If the user provides the expected answer to the pending question, continue the clarification flow normally.

Example:
- pending question: `destination path>`
- user types: `tests/`
- Snappy continues copy planning as it does today

### 2. cancel
Allowed exactly as today.

Example:
- `cancel`
- clears pending question/plan state
- returns to IDLE

### 3. status
Allowed while clarification is pending.

Should show:
- current state: CLARIFICATION
- active goal still present
- pending question still present

### 4. help
Allowed while clarification is pending.

Should show help without clearing or replacing the current clarification flow.

---

## Blocked Input Handling

If the user types a new goal while clarification is pending, Snappy must:

- show pending-question reminder message
- remain in `CLARIFICATION`
- keep `active_goal`
- keep `pending_question`
- keep `pending_plan` unchanged
- not update `last_route`
- not update `last_completed_goal`
- not update `last_failed_goal`
- not update `last_cancelled_goal`

Blocked commands must be treated as rejected input, not as new intents.

---

## Suggested Message

Use a short, clear message such as:

You have a pending question:

destination path>

Answer it, or type 'cancel' to abandon the current goal.

This message should be deterministic and easy to test.

---

## Scope Boundaries

This task is only about clarification-state hardening.

Do not:
- redesign copy UX
- add override confirmation for new goals
- introduce queueing
- introduce goal suspension/resume
- change confirmation logic
- change agent mode behavior
- change rules/skills behavior
- change safe inspect behavior outside clarification state

---

## Tests To Add

### 1. Clarification blocks new safe-inspect goal
Commands:
- `copy README.md`
- `give me a file listing for the current directory`
- `status`

Expected:
- listing is not executed
- state remains `CLARIFICATION`
- active goal remains `copy README.md`
- pending question remains `destination path>`
- reminder message shown

### 2. Clarification blocks git-read goal
Commands:
- `copy README.md`
- `git status`
- `status`

Expected:
- git status is not executed
- state remains `CLARIFICATION`
- active goal unchanged
- pending question unchanged

### 3. Clarification allows answer input
Commands:
- `copy README.md`
- `tests/`

Expected:
- clarification flow continues normally
- no blocking message
- existing copy behavior preserved

### 4. Clarification allows cancel
Commands:
- `copy README.md`
- `cancel`
- `status`

Expected:
- returns to IDLE
- pending question cleared
- last cancelled goal set correctly

### 5. Clarification allows status
Commands:
- `copy README.md`
- `status`

Expected:
- state still `CLARIFICATION`
- active goal still present
- pending question still present

### 6. Clarification allows help
Commands:
- `copy README.md`
- `help`
- `status`

Expected:
- help shown
- state still `CLARIFICATION`
- pending question preserved

### 7. Blocked command does not mutate completion/failure fields
Commands:
- `copy README.md`
- `git status`
- `status`

Expected:
- no new completed goal
- no failed goal from blocked command
- no route change caused by blocked command

---

## Acceptance Criteria

This task is complete when:

- pending-question state is protected by a clarification lock
- new goals cannot silently override a pending clarification flow
- `cancel`, `status`, `help`, and direct answer input still work
- blocked commands do not alter session state
- regression behavior outside clarification state remains unchanged
- new tests pass
- existing regression tests still pass

---

## Output Requirements

After implementation, provide:
- summary of files changed
- summary of logic added
- summary of tests added/updated
- any risks or edge cases observed
- confirmation that existing regression tests still pass
