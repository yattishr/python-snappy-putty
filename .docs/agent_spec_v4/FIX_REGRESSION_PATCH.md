# Snappy — M1 Regression Patch

## Goal

Fix the remaining M1 regressions without changing Snappy’s core execution, planner, policy enforcement, or state machine semantics.

This patch is intentionally narrow.

---

## Problem Summary

M1 introduced 3 regressions:

1. `agent mode active` correctly blocks under `no_active_mode`, but then appears to fall through into the mode selector UI.
2. `agent mode` now opens an interactive selector in a way that breaks the non-interactive regression flow.
3. The "No Agent Mode Regression" failure appears to be an expectation mismatch rather than a real runtime break, because clarification + cancel still behaves correctly.

---

## GLOBAL RULES

* Keep this patch additive and low-risk
* Do not rewrite the state machine
* Do not change planner behavior
* Do not change rule semantics
* Do not weaken `no_active_mode`
* Do not weaken clarification lock
* Do not remove the session-only agent mode control feature
* Preserve the improved M1 workflow UX where it is already correct

---

## PATCH 1 — Stop fallthrough after `no_active_mode` block

### Problem

When the user runs:

```text
agent mode active
```

and `no_active_mode` is loaded, Snappy correctly prints:

```text
Active mode is disabled by the loaded agent rules.
```

But then the flow appears to continue into the selector UI, which is wrong.

### Required fix

When `agent mode active` is blocked by rule:

* show the block message
* keep the current mode unchanged
* return immediately
* do not open the selector UI
* do not emit any invalid-mode retry text

### Acceptance

This sequence:

```text
agent mode active
agent mode
```

should result in:

* blocked message on first command
* current mode unchanged on second command

---

## PATCH 2 — Split inspect vs selector behavior for `agent mode`

### Problem

`agent mode` currently opens an interactive selector, which is awkward for regression harnesses and line-based REPL automation. The current failure shows the selector prompting for choice and then treating the next scripted line as invalid selector input. 

### Required fix

Make `agent mode` deterministic and non-interactive by default.

#### New behavior

```text
agent mode
```

should display only:

* current mode
* source

Example:

```text
Agent Mode

Current: passive
Source: environment
```

#### Selector behavior

Move the menu-style selector behind an explicit command, for example:

```text
agent mode select
```

This command may open the selector UI.

### Notes

* Keep existing direct set commands:

  * `agent mode off`
  * `agent mode passive`
  * `agent mode active`
* Keep session-only behavior
* Keep environment/default precedence behavior
* Keep the selector feature, but make it opt-in

### Acceptance

* `agent mode` is safe for automated regression and REPL scripting
* `agent mode select` opens the menu UI
* direct set commands still work

---

## PATCH 3 — Reconcile Test 14 expectation with actual behavior

### Problem

The “No Agent Mode Regression” failure appears to show correct behavior:

* `copy README.md` enters clarification
* `cancel` clears state
* `status` returns to IDLE cleanly 

This suggests the regression may be failing because the expected output no longer matches the tightened M1 workflow UX, rather than because runtime behavior is broken.

### Required fix

Inspect the failing regression assertion for Test 14.

If runtime behavior is already correct, update the test expectation to reflect the current intended UX.

Do not change runtime code unless there is a real behavior bug.

### Acceptance

Test 14 should pass if:

* clarification still appears
* cancel still clears state
* no-agent mode remains stable
* state returns to IDLE correctly

---

## Tests To Add / Update

### Test A — `no_active_mode` block does not fall through

Setup:

* `no_active_mode` loaded
* current mode passive

Commands:

```text
agent mode active
agent mode
```

Expected:

* block message shown
* no selector UI shown after the blocked command
* mode remains passive

---

### Test B — `agent mode` is display-only

Commands:

```text
agent mode
```

Expected:

* current mode shown
* source shown
* no selector prompt
* no “Enter choice >”

---

### Test C — `agent mode select` opens selector

Commands:

```text
agent mode select
```

Expected:

* selector UI appears
* selection works as intended

---

### Test D — direct mode set still works

Commands:

```text
agent mode passive
status
agent mode off
status
```

Expected:

* session mode changes correctly
* status reflects new mode and source=session

---

### Test E — no-agent clarification + cancel remains valid

Commands:

```text
copy README.md
cancel
status
```

Expected:

* clarification prompt appears
* cancel clears pending state
* final status is IDLE
* this test should pass under the new intended UX

---

## Acceptance Criteria

This patch is complete when:

* `agent mode active` blocked by `no_active_mode` does not fall through into selector UI
* `agent mode` becomes deterministic, display-only, and regression-safe
* optional selector UI remains available through an explicit command such as `agent mode select`
* direct mode-set commands still work
* Test 14 either passes through corrected runtime behavior or corrected expectation, whichever is appropriate
* existing regression tests still pass
* no new changes are introduced to planner, rules, or clarification lock semantics

---

## Output Required From Codex

After implementation, provide:

* summary of files changed
* summary of `agent mode` control-flow changes
* summary of tests added or updated
* confirmation that the previously failing regressions now pass
* note whether Test 14 required code changes or only expectation updates
