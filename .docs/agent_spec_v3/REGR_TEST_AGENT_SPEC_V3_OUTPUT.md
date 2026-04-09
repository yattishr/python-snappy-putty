# Agent Spec V3 Regression Test Output

Date: 2026-04-09

## Scope

Regression testing was rerun against the current workspace implementation using the checklist in `.docs/agent_spec_v3/RUN_REGR_TEST_AGENT_SPEC_V3.md`.

Local command used for the runs:

```bash
/home/yattishr/Projects/snappy-putty/src/.venv/bin/snappy_putty
```

Test fixtures:

- Baseline no-agent runs: fresh temporary git repos under `/tmp/snappy-v3-regr-postfix2/t1_git` and `/tmp/snappy-v3-regr-postfix2/t14_git`
- Agent-enabled runs: fresh temporary repos built from the local `.snappy` fixture plus a clean `README.md`

Important note:

- Agent and rule loading only occur when agent feature mode is not `off`.
- For agent-specific REPL tests, the session was switched to `passive` with `agent mode passive`.
- For top-level CLI agent surfaces outside the REPL, `SNAPPY_AGENT_MODE=passive` was used where needed.

## Summary

- Passed: 14
- Failed: 0
- Overall result: `PASS`

All regression checks in the V3 smoke test document passed on this run. The previously failing `protect_project_root` case now emits the required deterministic rule block message and leaves the session in a stable idle state with no pending plan.

## Results

| Test | Result | Notes |
| --- | --- | --- |
| 1. Baseline (No Agent Loaded) | PASS | `status` showed agent mode `off` and no agent loaded. Directory listing worked. `git status` worked in a fresh temporary git repo. |
| 2. Agent Runtime Loads | PASS | In `passive` mode, `status`, `agent`, `skills`, `rules`, and `agent doctor` all showed the loaded agent, 4 loaded rules, 3 enforceable rules, and 1 informational rule. |
| 3. Clarification Lock | PASS | After `copy README.md`, entering `show me all files` was blocked with the pending question message. State stayed `CLARIFICATION`, active goal stayed `copy README.md`, and pending question stayed `destination path>`. |
| 4. Clarification Accepts Answer | PASS | After `copy README.md`, answering `tests/` continued normally into a planned mkdir+copy flow and confirmation prompt. |
| 5. Cancel Works During Clarification | PASS | `cancel` cleared the pending clarification, returned state to `IDLE`, and set `Last cancelled goal: copy README.md`. |
| 6. `require_confirm` Rule | PASS | `copy README.md to README-copy.md` showed a planned change and required confirmation. Entering `NO` cancelled apply. `README-copy.md` was not created. |
| 7. `protect_project_root` Rule | PASS | `copy README.md to /` printed `Operation blocked by rule: protect_project_root` and `The requested filesystem mutation targets a protected path.` No execution occurred. `status` then showed `Current state: IDLE`, `Pending plan: (none)`, and `Last failed goal: copy README.md to /`. |
| 8. `no_active_mode` Rule | PASS | `agent mode active` printed `Active mode is disabled by the loaded agent rules.` A follow-up `agent mode` prompt confirmed the session remained `passive`. |
| 9. Informational Rule | PASS | `custom_note` appeared in `rules` as `informational`, and `agent` / `agent doctor` reflected `Informational rules: 1` with no behavior change. |
| 10. Agent Mode Control | PASS | `agent mode` prompt worked, switching to `passive` worked, `agent mode active` was blocked by rule, `agent mode off` worked, and `status` reflected the final mode correctly. |
| 11. Clarification + Rules Together | PASS | Clarification lock still blocked a new intent while rules were loaded, and `cancel` still cleared the pending state. |
| 12. Status Integrity | PASS | `status` included all expected fields and showed no missing values or crash behavior. |
| 13. CLI Commands Still Work | PASS | `--help`, `init`, `skills`, `rules`, and `agent` all executed successfully. After `init`, `agent` showed a valid scaffolded agent summary. |
| 14. No Agent Mode Regression | PASS | In a repo without `.snappy`, core REPL behavior still worked, no rule enforcement appeared, and there were no agent errors. |

## Key Observations

- Agent/rule visibility is working as intended once feature mode is enabled.
- Clarification lock behavior remained intact with rules loaded.
- `require_confirm`, `protect_project_root`, and `no_active_mode` all behaved as specified.
- The `protect_project_root` fix now takes precedence over the generic workspace-escape rendering for the `/` target case.
- Core non-agent REPL behavior remains unchanged when `.snappy` is absent or the session mode is `off`.

## Representative Outputs

### Test 3

```text
You have a pending question:

destination path>

Answer it, or type 'cancel' to abandon the current goal.
```

### Test 6

```text
Type YES to apply, or NO to cancel.
```

```text
Cancelled. No pending action was applied.
```

### Test 7

```text
Operation blocked by rule: protect_project_root

The requested filesystem mutation targets a protected path.
```

### Test 8

```text
Active mode is disabled by the loaded agent rules.
```

## Conclusion

The full Agent Spec V3 regression checklist passed. Agent loading, inspectable runtime, clarification lock, rule enforcement, and agent mode control all behaved as documented, and no core Snappy regressions were observed in the manual smoke run.
