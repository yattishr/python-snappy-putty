# Snappy Patch — Fix `protect_project_root` Rule Messaging

## Problem

When `protect_project_root` is loaded and a user targets a protected path (`/`, `~`, outside workspace), Snappy currently shows:

* `No filesystem changes planned`
* `Path escapes workspace root`

This is safe, but the rule is not surfaced.

Regression expects:

```
Operation blocked by rule: protect_project_root
```

---

## Goal

When `protect_project_root` is active and a protected path is requested:

1. Operation remains blocked
2. Rule-specific message is shown
3. No execution occurs
4. No success state recorded

---

## Required Behavior

Input:

```
copy README.md to /
```

Output:

```
Operation blocked by rule: protect_project_root
The requested filesystem mutation targets a protected path.
```

Optional additional detail:

```
Path: /
```

---

## Implementation

Where filesystem planning currently detects:

* workspace escape
* protected root
* invalid mutation target

Add:

```
if rule_active("protect_project_root"):
    render_rule_block("protect_project_root")
    abort_plan()
    return
```

Do NOT:

* change existing safety logic
* change planner behavior
* change state machine
* allow execution

Only change the **user-visible message**.

---

## Acceptable Locations

Patch may be applied in:

* filesystem planner
* path validation layer
* rule enforcement hook
* plan rendering stage

Use the smallest, safest interception point.

---

## Tests

### Test 1 — Root target blocked

```
copy README.md to /
```

Expected:

```
Operation blocked by rule: protect_project_root
```

No execution.

---

### Test 2 — Home path blocked

```
copy README.md to ~
```

Expected:

```
Operation blocked by rule: protect_project_root
```

No execution.

---

### Test 3 — Rule not loaded

Remove rule.

```
copy README.md to /
```

Expected:

Old behavior remains:

```
No filesystem changes planned
Path escapes workspace root
```

---

### Test 4 — No false completion

After blocked operation:

```
status
```

Expected:

* no completed goal
* no pending plan
* state stable

---

## Acceptance Criteria

Patch is complete when:

* rule message appears when rule active
* operation still blocked
* no regressions
* regression suite passes
* behavior unchanged when rule absent

---

## Output Required

Codex should report:

* files modified
* where rule interception added
* regression now passing
* confirmation safety unchanged
