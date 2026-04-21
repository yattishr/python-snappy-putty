# Snappy UI-Only Implementation Plan

## Goal

Improve Snappy's interactive user experience without changing:

- control logic
- route classification
- lifecycle/state-machine behavior
- workflow/memory handling
- policy enforcement
- execution semantics

This plan is restricted to presentation-layer changes in the existing CLI and render surface.

## Guardrails

The implementation must not:

- change `SessionState` transitions
- change confirmation or clarification acceptance rules
- change control-layer decisions
- add persistence or memory features
- add autonomous continuation
- reinterpret invalid input as valid input

The implementation may:

- change prompt text
- add panels, tables, and banners
- reorder status output for readability
- add helper functions that format existing state
- standardize message wording

## Current UI Surface

The main presentation hooks already exist in:

- [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py)
- [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py)
- [src/snappy_putty/status.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/status.py)

Relevant current entry points:

- `render_prompt(...)`
- `_render_clarification_followup(...)`
- `_render_confirmation_prompt(...)`
- `_handle_status(...)`
- `_handle_after(...)`
- `render_fs_plan(...)`
- `render_fs_rule_block(...)`
- `render_fs_cannot_proceed(...)`
- `render_fs_apply_result(...)`
- `render_agent_output(...)`

## Implementation Phases

### Phase 1: Stateful Prompt

#### Objective

Make the prompt itself communicate the current interaction mode so users do not need to infer context from previous output.

#### Changes

Update `render_prompt(state)` in [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py) so the prompt reflects the active UI state.

Suggested prompt mapping:

- `IDLE` -> `snappy> `
- `CLARIFICATION` -> `snappy [clarification]> `
- `CONFIRMATION` -> `snappy [confirm]> `
- `BLOCKED` -> `snappy [blocked]> `
- `FAILED` -> `snappy [failed]> `

For path-style clarifications, keep the inline prompt text, but prepend a compact state cue before it when appropriate.

Example:

- current: `destination path>`
- target: `snappy [clarification:path]> `

#### Notes

This is strictly a formatting change. Do not alter prompt routing or input handling.

### Phase 2: Active Workflow Banner

#### Objective

Surface the current in-flight task before each prompt during non-idle states.

#### Changes

Add a new UI helper in [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py), for example:

- `render_active_workflow_banner(...)`

Inputs should be derived from existing state only:

- active goal
- lifecycle state
- pending question summary
- pending plan summary
- awaiting confirmation flag
- control state
- next valid actions

Suggested display:

- Title: `Current Task`
- Goal: current active goal
- State: `Awaiting clarification`, `Awaiting confirmation`, `Planning`, `Blocked`, etc.
- Expected input: `Path answer only`, `YES/NO only`, `Answer only`
- Actions: `status`, `help`, `cancel`

#### Integration points

Render this banner in the main shell loop before prompt collection when:

- `state.current_state != IDLE`
- `state.active_goal` exists

Do not render it repeatedly if a larger panel for the same state was just shown in the same branch. Keep it compact.

### Phase 3: Clarification UI

#### Objective

Make clarification screens explicit about what kind of answer Snappy expects.

#### Changes

Replace or augment `_render_clarification_followup(...)` in [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py) with a structured panel rendered via `render.py`.

Add a helper such as:

- `render_clarification_state(...)`

Suggested content:

- Title: `Clarification`
- Goal: active goal
- Need: pending question
- Expected input:
  - `destination path`
  - `choice selection`
  - `free-text answer`
- Rules:
  - `Answer the pending question`
  - `Type cancel to abandon the current goal`

When the clarification lock rejects command-shaped input, render:

- a short reason line
- the pending question again
- the allowed next actions again

Suggested wording:

- `Input ignored because Snappy is waiting for clarification data, not a new command.`
- `Answer the pending question, or type cancel.`

#### Integration points

- `_render_clarification_lock_message(...)`
- `_render_clarification_followup(...)`
- any place the shell re-prompts after `help` during clarification

### Phase 4: Confirmation Staging View

#### Objective

Turn confirmation into a deliberate review step rather than a bare yes/no instruction.

#### Changes

Add a dedicated confirmation renderer in [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py), for example:

- `render_confirmation_stage(...)`

Use existing state and `FsPlan` details only:

- goal
- operation count
- first few planned targets
- stage:
  - overwrite
  - limit
  - apply
- policy notes from existing decision path if already available to the caller

Suggested sections:

- `Goal`
- `Pending Apply`
- `Operations`
- `Special Conditions`
- `Required Input`

Suggested `Required Input` lines:

- `Type YES to apply, or NO to cancel.`
- `Destination exists. Type YES to overwrite, or NO to cancel.`
- `Plan exceeds N operations. Type YES to continue, or NO to cancel.`

#### Integration points

Replace direct text output in `_render_confirmation_prompt(...)` with a structured confirmation panel while preserving the same exact confirmation wording.

### Phase 5: Status Screen Redesign

#### Objective

Make `status` prioritize the active workflow over historical fields.

#### Changes

Refactor `_handle_status(...)` in [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py) to render a multi-section status view instead of one long flat block.

Recommended sections:

1. `Current Workflow`
2. `Control State`
3. `Recent Outcomes`
4. `Agent Mode`

Suggested `Current Workflow` fields:

- Current state
- Active goal
- Last route
- Pending question
- Pending plan
- Awaiting confirmation

Suggested `Recent Outcomes` fields:

- Last completed goal
- Last cancelled goal
- Last failed goal
- Last blocked goal
- Error message

#### Rendering approach

Use either:

- one parent `Panel` with grouped subsections
- or multiple compact `Panel.fit(...)` calls in sequence

Avoid a single long newline-delimited blob if possible.

### Phase 6: Standardized Next-Actions Footer

#### Objective

Reduce invalid input by always telling the user what inputs are valid in the current state.

#### Changes

Add a formatter in [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py), for example:

- `render_next_actions_footer(...)`

Suggested mappings:

- Clarification/path:
  - `Next: enter a path, status, help, cancel`
- Clarification/choice:
  - `Next: choose an option, status, help, cancel`
- Confirmation:
  - `Next: YES, NO, status, cancel`
- Idle:
  - no footer by default

#### Integration points

Render this footer:

- after clarification lock rejections
- after invalid confirmation input
- optionally after initial clarification and confirmation panels

### Phase 7: Microcopy Cleanup

#### Objective

Make the CLI sound consistent and predictable.

#### Changes

Normalize wording across [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py) and [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py).

Recommended phrasing set:

- `Awaiting clarification.`
- `Awaiting destination path.`
- `Awaiting confirmation.`
- `Input ignored because confirmation is still pending.`
- `Input ignored because clarification is still pending.`
- `Cancelled pending action.`
- `Operation blocked by rule.`
- `No pending next step.`

Avoid mixing styles like:

- conversational explanation in one place
- terse system wording in another

#### Constraint

Do not change semantic wording that tests rely on until tests are updated intentionally.

### Phase 8: Planned Changes Presentation Tightening

#### Objective

Improve the readability of plan output without changing planning behavior.

#### Changes

Refine `render_fs_plan(...)` in [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py).

Recommended adjustments:

- add a compact summary line above the table:
  - `2 planned filesystem operations`
- move policy notes into a lighter advisory panel
- keep warnings panel only when warnings exist, otherwise omit it
- cap visible rows if very large and show:
  - `Showing first N operations`

Do not change the underlying `FsPlan`.

### Phase 9: Blocked and Cannot-Proceed Views

#### Objective

Make blocked and invalid outcomes clearer and more actionable.

#### Changes

Refine:

- `render_fs_rule_block(...)`
- `render_fs_cannot_proceed(...)`

Recommended structure:

- Goal
- Outcome type
- Why this happened
- Next valid action

Suggested improvement:

Use more explicit titles:

- `Blocked by Policy`
- `Request Cannot Proceed`
- `No Filesystem Changes Planned`

Keep the existing message body from the control layer intact. Only change the framing.

### Phase 10: `after` Command Presentation

#### Objective

Make `after` read like a crisp next-step inspector rather than a thin debug helper.

#### Changes

Refine `_handle_after(...)` in [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py) to use consistent panelized output.

Suggested behavior:

- if clarification pending:
  - `Next Step`
  - `Answer pending question: ...`
- if confirmation pending:
  - `Next Step`
  - `Respond with YES or NO`
- if agent plan pending:
  - `Next Suggested Step`
  - first plan action
- if filesystem plan pending:
  - `Next Filesystem Step`
  - first op action and target

## Concrete Work Breakdown

### Work Item 1

Create new render helpers in [src/snappy_putty/render.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/render.py):

- `render_active_workflow_banner(...)`
- `render_clarification_state(...)`
- `render_confirmation_stage(...)`
- `render_next_actions_footer(...)`
- optional compact status section helpers

### Work Item 2

Update [src/snappy_putty/cli.py](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py):

- `render_prompt(...)`
- `_render_clarification_lock_message(...)`
- `_render_clarification_followup(...)`
- `_render_confirmation_prompt(...)`
- `_handle_status(...)`
- `_handle_after(...)`

### Work Item 3

Keep existing renderers, but tighten layout:

- `render_fs_plan(...)`
- `render_fs_rule_block(...)`
- `render_fs_cannot_proceed(...)`
- `render_fs_apply_result(...)`

### Work Item 4

Add or update UI-focused tests:

- prompt string changes
- clarification panel copy
- confirmation panel copy
- status output ordering/content
- `after` output
- blocked view titles

## Suggested Test Plan

Update tests that assert on shell copy or prompt text in:

- [tests/test_state_machine.py](/home/yattishr/Projects/snappy-putty/tests/test_state_machine.py)
- [tests/test_session_repl_subprocess.py](/home/yattishr/Projects/snappy-putty/tests/test_session_repl_subprocess.py)
- [tests/test_smoke.py](/home/yattishr/Projects/snappy-putty/tests/test_smoke.py)
- [tests/test_render.py](/home/yattishr/Projects/snappy-putty/tests/test_render.py)

Recommended test additions:

1. Prompt reflects clarification state.
2. Prompt reflects confirmation state.
3. Clarification rejection shows expected-input guidance.
4. Invalid confirmation input shows next valid actions.
5. Status output places current workflow section before history.
6. Blocked panel title and next-step hint remain visible.

## Rollout Order

Recommended implementation order:

1. Stateful prompt
2. Clarification and confirmation panels
3. Next-actions footer
4. Status redesign
5. Planned changes and blocked-view tightening
6. `after` polish

This order gives the fastest UX improvement with the lowest risk of test churn.

## Definition of Done

The UI-only refresh is complete when:

- prompt reflects workflow state
- active non-idle workflows are visually obvious
- clarification screens explicitly state expected input type
- confirmation screens show a staged summary plus exact required input
- status emphasizes the active workflow first
- blocked and invalid outcomes are more legible
- no control logic or state-machine behavior changed
- tests validate the new copy/layout behavior

## Non-Goals for This Plan

The following are intentionally out of scope:

- TUI conversion
- mouse interaction
- fuzzy input acceptance
- command palette
- multiline compose UI
- background progress tracking
- persistent session dashboard
- changes to lifecycle semantics
