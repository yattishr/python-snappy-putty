---

# Chunk 3 — Bounded Single-Goal Loop Integration + Regression

M3.2 + M3.5 — Bounded Loop Integration and Regression Coverage (Final Integration Step)
Implement only this chunk. Do not add features outside scope, even if they seem adjacent.

## Mission

Wire the supervised single-goal loop together end-to-end so that one user goal flows through:

`INTENT_RECEIVED -> PLANNING -> [BLOCKED | CONFIRMATION] -> EXECUTING -> REFLECTING -> [COMPLETED | FAILED | CANCELLED | BLOCKED] -> IDLE`

This chunk is about:
- integrating the loop lifecycle end-to-end
- enforcing one active goal at a time
- ensuring no nested/recursive execution
- regression coverage for key scenarios

Do not add memory, autonomy, skills, retries, or custom rule DSL.

---

## Preconditions

Assume the codebase already has or now includes:
- explicit M3 states
- transition enforcement
- `ExecutionResult`
- reflection layer

If minor glue is missing, add only what is necessary for M3 loop integration.

---

## Required Behavioral Contract

Each loop must:
1. accept one user intent
2. create one plan
3. either get blocked or await confirmation
4. execute once if confirmed
5. reflect once
6. terminate cleanly
7. return to `IDLE`

Constraints:
- one active goal only
- no nested goals
- no recursive loop entry
- no implicit retries
- no auto-generated follow-up goals
- invalid confirmation input must preserve pending confirmation state

---

## Integration Focus

Audit and update the command lifecycle so that:
- new user input begins at `INTENT_RECEIVED`
- planning transitions to either `CONFIRMATION` or `BLOCKED`
- confirmation YES leads to `EXECUTING`
- confirmation NO leads to cancelled terminal handling
- invalid confirmation input keeps the session in `CONFIRMATION`
- execution moves to `REFLECTING`
- reflection sets terminal state
- terminal state returns to `IDLE`

Ensure there is no alternate path that bypasses the loop.

---

## Status / Session Expectations

After integration, session/status reporting should correctly reflect:
- current loop state
- active goal
- pending plan presence
- awaiting confirmation state
- terminal-state cleanup back to `IDLE`

Do not try to solve all historical UX polish in this chunk unless necessary for loop correctness.

---

## Required Tests

Add or update regression tests for:

1. **successful execution**
   - one goal
   - plan
   - YES
   - execute
   - reflect
   - terminal state = `COMPLETED`
   - return to `IDLE`

2. **cancel flow**
   - one goal
   - plan
   - NO
   - terminal state = `CANCELLED`
   - return to `IDLE`

3. **blocked flow**
   - one goal
   - blocked by policy
   - terminal state = `BLOCKED`
   - return to `IDLE`

4. **execution failure**
   - one goal
   - execution failure
   - terminal state = `FAILED`
   - return to `IDLE`

5. **invalid confirmation input**
   - remain in `CONFIRMATION`
   - active goal preserved
   - pending plan preserved
   - no execution occurs

6. **single-goal boundedness**
   - no nested or chained goal execution
   - no second goal begins while a confirmation is pending

7. **sequential loop integrity**
   - multiple runs in one session do not corrupt state

---

## Acceptance Criteria

- the loop is wired end-to-end
- exactly one goal is processed per loop
- no path bypasses terminal reflection
- invalid confirmation input does not corrupt state
- no nested or recursive loop execution occurs
- all required tests pass

---

## Deliverables

Return:
1. code changes
2. tests
3. concise summary of:
   - files changed
   - how the end-to-end loop is enforced
   - any remaining edge cases that should be tracked as follow-up issues
