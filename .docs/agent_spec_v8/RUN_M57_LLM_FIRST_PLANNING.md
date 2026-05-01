# Snappy — Agent Mode Simplification + LLM-First Planning Rule

## Goal

Eliminate ambiguous planning behavior and remove deterministic fallback for broad developer goals.

Snappy must never generate low-quality “generic” plans.

---

## Agent Mode Model

Agent mode has only two states:

- off
- active

Passive mode is removed.

---

## When Agent Mode = active

### Planning behavior

- LLM-assisted planning is REQUIRED for all `project_developer_goal` requests
- Deterministic planning MUST NOT be used for broad implementation goals

### Execution rules

- Snappy must internally attempt to use the LLM planner
- `SNAPPY_PUTTY_ENABLE_SDK` must NOT be used as the decision-maker
- LLM usage is controlled by Snappy logic, not environment variables

### If LLM is available

- Run full LLM-assisted planning pipeline:
  - inspect project
  - select context
  - compress context
  - call LLM
  - validate plan
  - persist plan
  - enter interaction flow

### If LLM is unavailable

- Do NOT fallback to deterministic planning
- Do NOT create a plan
- Perform project inspection only (optional but recommended)
- Inform the user clearly:

  Active planning requires LLM support, but the LLM planner is unavailable.

  I inspected the project, but I did not create a plan.

- Reset state cleanly to IDLE
- Record:
  - last_skipped_goal
  - last_skip_reason = llm_required_but_unavailable

---

## When Agent Mode = off

- LLM-assisted planning must NOT be used
- Structured deterministic commands remain available:

  inspect project
  inspect files
  show plan
  explain step
  file operations
  git operations

- Broad developer goals must NOT trigger planning

---

## Non-Negotiable Rules

No LLM.
No real developer plan.
No pretending.

Active mode = real planning or no planning.
Never fake planning.

Deterministic planning must NOT be used for:
- help me improve this CLI
- add logging
- refactor auth flow
- build payment integration

---

## State Machine Behavior

Minimal flow:

IDLE → INTENT_RECEIVED → PLANNING → (SUCCESS or PLANNING_SKIPPED) → IDLE

If LLM unavailable:

PLANNING → PLANNING_SKIPPED → IDLE

Must clear:

active_goal
pending_plan
awaiting_confirmation
pending_question

---

## Expected Outcome

Snappy becomes:

- intelligent when capable
- honest when not
- never misleading

No more generic plans.
No more silent fallbacks.
No more confusion.
