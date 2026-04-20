You are implementing **M3.1 — Agent Loop State Machine Formalization** for the `snappy_putty` codebase.
Implement only this chunk. Do not add features outside scope, even if they seem adjacent.

## Mission

Introduce explicit M3 loop states and enforce valid state transitions for the supervised single-goal loop.

This chunk is only about:
- state definitions
- transition rules
- transition helpers
- wiring current lifecycle/state handling into a single authoritative model

Do not implement execution result reflection yet.
Do not implement memory, autonomy, skills, or custom rule DSL.

---

## Required States

Ensure the system has explicit support for these states:

- `IDLE`
- `INTENT_RECEIVED`
- `PLANNING`
- `CONFIRMATION`
- `EXECUTING`
- `REFLECTING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`
- `BLOCKED`

If equivalent states already exist, normalize or extend carefully instead of duplicating.

---

## Required Allowed Transitions

Allowed transitions:

- `IDLE -> INTENT_RECEIVED`
- `INTENT_RECEIVED -> PLANNING`
- `PLANNING -> CONFIRMATION`
- `PLANNING -> BLOCKED`
- `CONFIRMATION -> EXECUTING`
- `CONFIRMATION -> CANCELLED`
- `EXECUTING -> REFLECTING`
- `REFLECTING -> COMPLETED`
- `REFLECTING -> FAILED`
- `REFLECTING -> CANCELLED`
- `REFLECTING -> BLOCKED`
- terminal state -> `IDLE`

Examples of invalid transitions:
- `CONFIRMATION -> PLANNING`
- `EXECUTING -> CONFIRMATION`
- `COMPLETED -> EXECUTING`

Invalid transitions must be prevented.

---

## Behavioral Constraints

- one active goal at a time
- no recursive loop entry
- no nested goals
- no auto-generated subgoals
- no replanning
- no retries

This chunk only establishes the loop skeleton and transition enforcement.

---

## Implementation Guidance

1. Identify existing lifecycle/session state model
2. Add or normalize M3 state constants / enum
3. Introduce transition enforcement helpers, such as:
   - `can_transition(from_state, to_state)`
   - `transition_to(new_state)`
4. Refactor lifecycle mutation points to use the new transition helper
5. Ensure terminal states can return to `IDLE`

Do not create a parallel lifecycle model if one already exists.

---

## Required Tests

Add or update tests to cover:

1. valid transitions succeed
2. invalid transitions are rejected or prevented
3. terminal states can return to `IDLE`
4. single-goal lifecycle does not allow nested active goals

---

## Acceptance Criteria

- explicit M3 states exist
- transition rules are enforced
- invalid transitions are blocked
- state handling uses one authoritative transition path
- implementation remains strictly within state-machine scope

---

## Deliverables

Return:
1. code changes
2. tests
3. concise summary of:
   - files changed
   - state model changes
   - any lifecycle assumptions still left for later chunks
