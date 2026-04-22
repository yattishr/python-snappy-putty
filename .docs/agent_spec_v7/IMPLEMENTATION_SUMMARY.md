# M4 Implementation Summary

Files changed:
- `src/snappy_putty/session.py`
- `src/snappy_putty/cli.py`
- `tests/test_state_machine.py`
- `tests/test_session_repl_subprocess.py`

What changed:
- Added JSON-safe workflow persistence to `.snappy/memory/session.json` under a top-level `workflow` key.
- Persisted serialized clarification question data and confirmation plan data so CLARIFICATION and CONFIRMATION can resume safely.
- Added snapshot load/validation/clear helpers and restore logic for the interactive shell.
- Restored resumable workflows on shell startup without auto-planning or auto-execution.
- Marked restored `EXECUTING` and `REFLECTING` snapshots as failed interruptions and cleared them.

Clarification-input rejection:
- Data-only clarification prompts still reject command-shaped input through the existing control boundary.
- `fs_destination` and `guided_listing_custom_path` prompts only accept valid path-like clarification data.
- Guided listing choice prompts remain overrideable by a new routed command, and the abandoned listing workflow is reset before the new goal starts.

Trust and safety invariants now enforced:
- Only JSON-safe workflow state is persisted; no live objects or executable references are written to disk.
- Restore only accepts structurally valid snapshots with state/context compatibility checks.
- Restored CLARIFICATION workflows only re-display the pending question and wait.
- Restored CONFIRMATION workflows only re-display the confirmation prompt and wait.
- No restored workflow is executed automatically.
- Terminal cleanup clears persisted workflow snapshots so ghost workflows do not survive completion, cancellation, failure, or blocked outcomes.
- Existing M3.5 clarification lock semantics remain in place for data-only clarification channels.

Tests added or updated:
- Snapshot save/load/clear coverage in `tests/test_state_machine.py`
- Restore helper coverage for clarification and interrupted execution in `tests/test_state_machine.py`
- End-to-end restore coverage for clarification and confirmation in `tests/test_session_repl_subprocess.py`
- Compatibility fixes for guided listing and blocked-status assertions in `tests/test_session_repl_subprocess.py`

Verification:
- `PYTHONPATH=. pytest tests/test_state_machine.py tests/test_session_repl_subprocess.py -q`
- `PYTHONPATH=. pytest tests/test_agent_discovery.py -q`

Follow-up items to track separately:
- Snapshot persistence currently shares `.snappy/memory/session.json` with agent memory metadata; if those concerns need stronger separation, move workflow persistence to a dedicated file in a future change.
- There is still no persisted resume path for partially completed execution results beyond marking interrupted workflows failed on restore.
