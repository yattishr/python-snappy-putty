Implement an explicit single-goal lifecycle state machine for Snappy’s existing Python REPL workflow.

Work within the current architecture and existing files, especially:
- src/snappy_putty/session.py
- src/snappy_putty/cli.py

This is a formalization task, not a broad refactor.

Primary objective:
Introduce explicit lifecycle state tracking for one active goal at a time, while preserving current behavior and route-based flow.

Lifecycle states to support:
- IDLE
- INTENT_RECEIVED
- PLANNING
- CLARIFICATION
- CONFIRMATION
- EXECUTING
- COMPLETED
- FAILED
- CANCELLED

Constraints:
- Python only
- Keep the current router and route constants intact
- Do not redesign the router
- Do not implement Git yet
- Do not add multi-goal support
- Minimize disruption to existing REPL behavior
- Preserve current outputs unless changes are needed for lifecycle visibility

Current repo facts:
SessionState currently has:
- active_goal
- last_route
- last_result
- pending_question
- pending_plan
- awaiting_confirmation
- last_completed_goal
- last_cancelled_goal
- pending_context
- clear_pending()

cli.py already has implicit lifecycle points for:
- cancel
- ask/explain planning
- filesystem planning
- clarification prompts
- staged confirmation
- execution via apply_fs_plan(...)
- completion cleanup

Required changes:

1. Extend SessionState
Update src/snappy_putty/session.py to add:
- current_state
- last_failed_goal
- optionally error_message or equivalent structured failure field

Requirements:
- current_state defaults to IDLE
- clear_pending() should continue clearing only pending workflow fields
- do not make clear_pending() reset historical fields like last completed/cancelled/failed goal

2. Add a formal state type
Define the lifecycle states centrally in Python, preferably with Enum.
Avoid loose magic strings scattered through the code.

3. Map existing workflow branches to explicit lifecycle transitions
Update src/snappy_putty/cli.py so current_state is set intentionally at the existing workflow hotspots.

At minimum:

- When a new goal is accepted, set INTENT_RECEIVED
- When planning begins, set PLANNING
  Examples:
  - handle_ask(...)
  - handle_explain(...)
  - plan_fs_intent(...)
- When a follow-up question is required, set CLARIFICATION
  Examples:
  - result.output.question
  - filesystem destination prompt
- When confirmation is required, set CONFIRMATION
  Examples:
  - _set_fs_confirmation_state(...)
  - overwrite/limit/apply stages should remain within CONFIRMATION
- Immediately before apply_fs_plan(...), set EXECUTING
- On successful execution, set COMPLETED
- On user cancellation, set CANCELLED
  Examples:
  - cancel command
  - NO during confirmation
- On planning or execution failures, set FAILED
  Examples:
  - filesystem parse failure
  - missing actionable confirmation state
  - missing plan during confirmation
  - other precondition/execution failures
- After terminal states are handled and cleanup is complete, return to IDLE

4. Normalize cancellation bookkeeping
Cancellation via explicit cancel and via confirmation NO must behave consistently.
Requirements:
- both paths update last_cancelled_goal
- both paths clear active/pending state safely
- both paths end in IDLE

5. Make failure first-class
Failure should not be only a last_result string.
Requirements:
- set current_state = FAILED
- record last_failed_goal
- preserve a useful failure message in last_result and/or error_message
- cleanup after failure ends in IDLE

6. Update status visibility
Update the status output to include current_state.
Preserve existing status information:
- active goal
- last route
- pending question
- pending plan
- awaiting confirmation
- last completed goal
- last cancelled goal
Also include failed goal and/or error message if appropriate.

Canonical transition model:
- IDLE -> INTENT_RECEIVED
- INTENT_RECEIVED -> PLANNING | CANCELLED | FAILED
- PLANNING -> CLARIFICATION | CONFIRMATION | EXECUTING | FAILED | CANCELLED
- CLARIFICATION -> PLANNING | CANCELLED | FAILED
- CONFIRMATION -> CONFIRMATION | EXECUTING | CANCELLED | FAILED
- EXECUTING -> COMPLETED | FAILED | CANCELLED
- COMPLETED -> IDLE
- FAILED -> IDLE
- CANCELLED -> IDLE

Important note:
CONFIRMATION -> CONFIRMATION is valid because filesystem confirmation already has staged progression:
- overwrite
- limit
- apply

State invariants to preserve:
- IDLE:
  - active_goal is None
  - pending_question is None
  - awaiting_confirmation is False
- INTENT_RECEIVED:
  - active_goal is set
- PLANNING:
  - active_goal is set
- CLARIFICATION:
  - active_goal is set
  - pending_question is set
- CONFIRMATION:
  - active_goal is set
  - awaiting_confirmation is True
- EXECUTING:
  - active_goal is set
  - awaiting_confirmation is False
- COMPLETED:
  - last_completed_goal is updated before cleanup/reset
- FAILED:
  - last_failed_goal is updated
  - failure message is preserved
- CANCELLED:
  - last_cancelled_goal is updated before cleanup/reset

File guidance:
- session.py: add lifecycle state support and failed-goal tracking, keep the dataclass largely intact
- cli.py: wire explicit lifecycle transitions into existing branches, normalize cancellation/failure handling, update status output
- optional: add a very small helper/state module if useful, but keep it lightweight

Acceptance criteria:
- SessionState has explicit lifecycle state
- SessionState tracks failed goals
- status shows current lifecycle state
- incomplete FS intent sets CLARIFICATION
- answering a pending question returns flow to PLANNING
- FS confirmation sets CONFIRMATION
- overwrite/limit/apply progression remains inside CONFIRMATION
- final YES before apply moves to EXECUTING
- NO during confirmation results in CANCELLED with consistent bookkeeping
- apply_fs_plan(...) runs while state is EXECUTING
- successful apply records COMPLETED
- cleanup after terminal states returns to IDLE
- parse failures or invalid pending confirmation contexts produce FAILED
- current ask/explain/fs flows continue working
- router behavior remains intact
- current REPL usage remains recognizable

Non-goals:
- do not implement read-only Git
- do not add multi-goal support
- do not redesign the router
- do not introduce async/background orchestration
- do not refactor unrelated modules
- do not replace the current session model with a completely new architecture

Implementation mindset:
The repo already contains an implicit state machine. Make the lifecycle explicit with the smallest clean set of changes so Snappy becomes more observable, safer to extend, and ready for the next milestone.