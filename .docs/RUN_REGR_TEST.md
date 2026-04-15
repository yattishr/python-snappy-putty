# 🧪 Snappy Agent V3 Smoke Tests

This document validates:

* Agent Spec V1 (agent loading)
* Agent Spec V2 (inspectable runtime)
* Agent Spec V3 (rule enforcement)
* Clarification lock
* Agent mode control surface
* No regressions in core Snappy behavior

Run these tests manually in a test repository.

---

# ✅ Test 1 — Baseline (No Agent Loaded)

Start Snappy in a directory with **no `.snappy/` folder**

### Command

```
snappy shell
```

### Test

```
status
give me a file listing for the current directory
git status
```

### Expected

* No crashes
* Directory listing works
* git status works
* No agent loaded
* No rule enforcement

---

# ✅ Test 2 — Agent Runtime Loads

Run in directory **with `.snappy/` folder**

### Test

```
status
agent
skills
rules
agent doctor
```

### Expected

status shows:

* Agent feature mode
* Agent loaded
* Rules loaded (if present)

agent shows:

* Agent name
* mode
* skills
* rules

skills shows:

* Loaded skills list

rules shows:

* enforceable rules
* informational rules

agent doctor shows:

* .snappy found
* skills parsed
* rules parsed
* memory status

---

# ✅ Test 3 — Clarification Lock

### Test

```
copy README.md
show me all files
```

### Expected

Snappy blocks the new intent:

```
You have a pending question:

destination path>

Answer it, or type 'cancel' to abandon the current goal.
```

State must remain:

* Current state: CLARIFICATION
* Active goal: copy README.md
* Pending question: destination path>

---

# ✅ Test 4 — Clarification Accepts Answer

### Test

```
copy README.md
tests/
```

### Expected

* Flow continues normally
* Copy planning appears
* No lock message shown

---

# ✅ Test 5 — Cancel Works During Clarification

### Test

```
copy README.md
cancel
status
```

### Expected

* Flow cancelled
* State returns to IDLE
* No pending question
* Last cancelled goal set correctly

---

# ✅ Test 6 — require_confirm Rule

Ensure rule exists:

```
.snappy/rules/require_confirm.md
```

### Test

```
copy README.md to README-copy.md
```

### Expected

* Planned change shown
* Confirmation required

### Continue

```
NO
```

### Expected

* No file created
* State returns to IDLE

---

# ✅ Test 7 — protect_project_root Rule

Ensure rule exists:

```
.snappy/rules/protect_project_root.md
```

### Test

```
copy README.md to /
```

### Expected

Operation blocked:

```
Operation blocked by rule: protect_project_root
```

Expected behavior:

* No execution
* No file created
* State preserved
* No false completion

---

# ✅ Test 8 — no_active_mode Rule

Ensure rule exists:

```
.snappy/rules/no_active_mode.md
```

### Test

```
agent mode active
```

### Expected

Blocked:

```
Active mode is disabled by the loaded agent rules.
```

### Verify

```
agent mode
```

Expected:

* Mode unchanged
* Still passive or off

---

# ✅ Test 9 — Informational Rule

Create rule:

```
.snappy/rules/custom_note.md
```

Contents:

```
# Rule: custom_note

This is informational only.
```

### Test

```
rules
agent
agent doctor
```

### Expected

* Rule listed
* Marked informational
* No behavior change

---

# ✅ Test 10 — Agent Mode Control

### Test

```
agent mode
agent mode passive
agent mode active
agent mode off
```

### Expected

* Mode switches correctly
* Session-only behavior
* Status reflects changes

---

# ✅ Test 11 — Clarification + Rules Together

### Test

```
copy README.md
show me all files
cancel
```

### Expected

* Lock still enforced
* Rules do not break clarification
* cancel still works

---

# ✅ Test 12 — Status Integrity

### Test

```
status
```

### Expected Fields

* Current state
* Active goal
* Pending question
* Last route
* Last completed goal
* Agent feature mode
* Loaded rules
* Agent loaded

No missing values
No crashes

---

# ✅ Test 13 — CLI Commands Still Work

Outside REPL:

```
snappy --help
snappy init
snappy skills
snappy rules
snappy agent
```

### Expected

* Commands work
* No regressions
* No crashes

---

# ✅ Test 14 — No Agent Mode Regression

Run without `.snappy/`

### Test

```
snappy shell
status
copy README.md
cancel
```

### Expected

* Core Snappy works
* No rule enforcement
* No agent errors

---

# PASS CRITERIA

All tests must:

* run without crashes
* preserve state machine integrity
* enforce rules deterministically
* maintain clarification lock
* not regress core Snappy behavior
* keep REPL responsive
* maintain session mode control

If all tests pass, Agent Spec V3 is considered stable.
