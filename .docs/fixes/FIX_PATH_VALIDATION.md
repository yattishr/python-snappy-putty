# 🧾 Fix Path Validation in CLARIFICATION State

## 🎯 Objective

Ensure that when Snappy is in CLARIFICATION state and expects a file path (e.g. "destination path>"):

- Valid path-like inputs (e.g. `tests/`, `./output`, `../dir`) are accepted
- They are treated as clarification responses (NOT new commands)
- The operation continues normally
- Unknown command guardrail is NOT triggered

---

## ❌ Current Problem

```text
snappy> copy README.md
destination path>

tests/
→ incorrectly treated as unknown command
→ flow breaks
```

---

## ✅ Expected Behavior

```text
snappy> copy README.md
destination path>

tests/
→ accepted as valid path
→ copy executes
→ state returns to IDLE
```

---

## 🔧 Implementation

### 1. Store structured clarification type

When asking for a path, replace string prompt with structured object:

```python
session.pending_question = {
    "type": "path",
    "prompt": "destination path>"
}
```

---

### 2. Update validation logic

Modify `is_valid_clarification_response`:

```python
def is_valid_clarification_response(user_input: str, session) -> bool:
    text = user_input.strip()

    # YES / NO always valid
    if text.lower() in ["yes", "no"]:
        return True

    # Structured validation
    if isinstance(session.pending_question, dict):
        qtype = session.pending_question.get("type")

        if qtype == "path":
            return looks_like_path(text)

        if qtype == "choice":
            return is_choice_input(text)

    return False
```

---

### 3. Implement `looks_like_path`

Keep validation simple and permissive:

```python
def looks_like_path(text: str) -> bool:
    return (
        len(text) > 0 and (
            "/" in text or
            text.startswith(".") or
            text.endswith("/") or
            text.isalnum()
        )
    )
```

IMPORTANT:
- Do NOT require path to exist
- Do NOT over-validate
- Only detect "path-like" input vs command-like input

---

### 4. Ensure override logic respects path inputs

In CLI loop:

```python
if session.state == "CLARIFICATION":
    if not is_valid_clarification_response(user_input, session):
        session.reset()
        route_new_command(user_input)
        return
```

Now:
- `tests/` → valid → continues flow
- `git status` → invalid → override triggered

---

## 🧪 Regression Tests

### Test 1 — Relative path

```text
copy README.md
tests/
```

Expected:
- File copied to `tests/`
- State returns to IDLE

---

### Test 2 — Dot path

```text
copy README.md
./backup
```

Expected:
- File copied to `./backup`

---

### Test 3 — Override still works

```text
copy README.md
git status
```

Expected:
- Copy flow cancelled
- `git status` executes
- No contamination

---

## 🚫 Constraints

- Do NOT break command override logic
- Do NOT route path input to unknown handler
- Do NOT require filesystem validation at this stage
- Keep logic lightweight and deterministic