# 🧪 Snappy — M2 Rule Priority Regression Tests

## Purpose

This suite validates **Rule Priority + Multi-Rule Resolution**.

It ensures that when multiple rules are loaded, Snappy:

* resolves them deterministically
* applies correct priority
* surfaces correct UX
* does not break existing behavior

---

## Priority Model Being Tested

```text
BLOCK > CONFIRM > WARN > INFO
```

---

# ✅ Test 1 — BLOCK overrides CONFIRM

## Setup

Ensure rules exist:

```text
.snappy/rules/protect_project_root.md
.snappy/rules/require_confirm.md
```

## Command

```text
copy README.md to /
```

## Expected

* Operation is blocked
* No confirmation prompt shown
* Output contains:

```text
Operation blocked by rule: protect_project_root
```

## Verify

```text
status
```

Expected:

* Last failed goal set
* No pending plan
* No awaiting confirmation

---

# ✅ Test 2 — CONFIRM applies when no BLOCK

## Setup

Rules:

```text
require_confirm
custom_note (optional)
```

## Command

```text
copy README.md to tests/
```

## Expected

* Plan is shown
* Confirmation required:

```text
Type YES to apply, or NO to cancel.
```

## Continue

```text
NO
```

## Expected

* Operation cancelled
* No file created
* State returns to IDLE

---

# ✅ Test 3 — INFO does not affect behavior

## Setup

Only rule:

```text
custom_note
```

## Command

```text
copy README.md to tests/
```

## Expected

* Normal flow
* No block
* No forced confirmation
* Behavior identical to no-rule scenario

---

# ✅ Test 4 — BLOCK overrides everything

## Setup

Rules:

```text
protect_project_root
require_confirm
custom_note
```

## Command

```text
copy README.md to /
```

## Expected

* BLOCK occurs
* No confirmation
* INFO ignored
* Output shows block message

---

# ✅ Test 5 — no_active_mode overrides mode change

## Setup

Rules:

```text
no_active_mode
custom_note
```

## Command

```text
agent mode active
```

## Expected

```text
Active mode is disabled by the loaded agent rules.
```

## Verify

```text
agent mode
```

Expected:

* Mode unchanged

---

# ✅ Test 6 — Mixed CONFIRM + INFO

## Setup

Rules:

```text
require_confirm
custom_note
```

## Command

```text
copy README.md to tests/
```

## Expected

* Confirmation required
* INFO does not change behavior

---

# ✅ Test 7 — Multiple BLOCK rules (future-proof)

## Setup

Simulate or include:

```text
protect_project_root
no_active_mode
```

## Commands

```text
copy README.md to /
agent mode active
```

## Expected

* Each action blocked by its relevant rule
* No conflicts or crashes
* Correct message per action

---

# ✅ Test 8 — Rule tier visibility

## Command

```text
rules
```

## Expected

Output includes classification:

```text
protect_project_root (block)
require_confirm (confirm)
custom_note (info)
```

---

## Command

```text
agent
```

## Expected

Grouped rules visible:

* Block rules
* Confirm rules
* Informational rules

---

## Command

```text
agent doctor
```

## Expected

* Tier counts visible
* No malformed rules
* Correct classification

---

# ✅ Test 9 — Status reflects policy cleanly

## Command

```text
status
```

## Expected

* Loaded rules count
* Policy tier summary (if implemented)
* No inconsistent state

---

# ✅ Test 10 — Safe path still works under rules

## Setup

Rules:

```text
protect_project_root
require_confirm
```

## Command

```text
copy README.md to tests/
```

## Expected

* Not blocked
* Confirmation required
* Operation proceeds only after YES

---

# PASS CRITERIA

M2 is successful when:

* BLOCK rules always override everything
* CONFIRM rules apply only when no BLOCK
* INFO rules do not affect behavior
* No conflicting outputs appear
* UX remains clean and readable
* No regressions from core behavior
* No broken state transitions
* No orphaned plans or pending states

---

# TEST EXECUTION STRATEGY

Run in this order:

1. Core regression suite
2. M2 rule priority suite (this file)

---

# NOTES

* This suite validates **combinations**, not individual rules
* This is the first milestone where behavior depends on rule interaction
* Any inconsistency here must be fixed before moving to Agent Loop

---
