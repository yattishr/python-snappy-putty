# Snappy Bugfix — Remove Legacy SNAPPY_PUTTY_ENABLE_SDK Gate

## Problem

Runtime still checks `SNAPPY_PUTTY_ENABLE_SDK` in `src/snappy_putty/agent.py`.

Observed:

```
src/snappy_putty/agent.py:535: return os.getenv("SNAPPY_PUTTY_ENABLE_SDK") == "1"
```

This causes active-mode LLM planning and SDK-backed routes (e.g. `explain git diff`) to report unavailable even when:

- OPENAI_API_KEY is visible
- openai imports correctly
- agents imports correctly
- agent mode active is enabled

This is why you see:

```
OpenAI Agents SDK could not be reached; using local fallback output.
```

---

## Root Cause

Legacy gating logic is still controlling SDK availability:

```
SNAPPY_PUTTY_ENABLE_SDK == "1"
```

Even though M5.7 introduced:

```
agent mode active → use LLM
```

So the system is internally contradicting itself.

---

## Required Fix

### 1. Remove Env-Var Gate

Remove or refactor ALL logic that uses:

```
SNAPPY_PUTTY_ENABLE_SDK
```

as the decision-maker for LLM availability.

This includes:

- `_is_sdk_enabled()` or equivalent helper
- any direct env var checks in agent/planner/explain routes

---

### 2. Replace with Runtime Capability Check

LLM availability should be determined by:

```
agent mode == active
AND
OPENAI_API_KEY exists
AND
agents import succeeds
AND
OpenAI client/runner initializes successfully
```

Pseudo:

```python
def is_llm_available():
    if agent_mode != "active":
        return False

    if not os.getenv("OPENAI_API_KEY"):
        return False

    try:
        import agents
        return True
    except Exception:
        return False
```

---

### 3. Apply to ALL LLM-Backed Routes

This must affect:

- planning (M5.7)
- explain commands (e.g. `explain git diff`)
- any other SDK-backed features

---

## Why `explain git diff` is failing

It uses the same SDK gate.

So even though:

- your API key is correct
- imports succeed

The route still checks:

```
SNAPPY_PUTTY_ENABLE_SDK != "1"
→ fallback mode
```

So it never attempts LLM usage.

This is the SAME bug.

---

### 4. Correct Behavior

When agent mode = active:

#### If LLM available

- use LLM for:
  - planning
  - explain commands
  - analysis routes

#### If LLM unavailable

Return:

```
This command requires LLM support, but the LLM is unavailable.

No explanation was generated.
```

---

### 5. Update Tests

Replace all uses of:

```
SNAPPY_PUTTY_ENABLE_SDK
```

in tests:

```
tests/test_active_mode_v1.py
tests/test_security.py
tests/test_smoke.py
```

Instead:

- mock LLM availability
- mock SDK client
- simulate success/failure

---

## Verification

Run:

```bash
grep -R "SNAPPY_PUTTY_ENABLE_SDK" -n src tests
```

Expected:

```
No functional logic depends on SNAPPY_PUTTY_ENABLE_SDK
```

Then:

```bash
python -m pytest
```

---

## Expected Result After Fix

```text
agent mode active
OPENAI_API_KEY present

help me improve this CLI
→ LLM plan generated

explain git diff
→ LLM explanation generated
```

---

## Non-Negotiable Rule

```
Agent mode controls LLM usage.
Environment variables do not control behavior.
```
