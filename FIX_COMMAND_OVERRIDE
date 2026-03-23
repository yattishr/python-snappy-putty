# 🧾 Fix Command Override in CLARIFICATION State

## 🎯 Objective

Ensure that when Snappy is in `CLARIFICATION` state:

- Valid answers (e.g. "yes", "no", simple responses) → continue flow  
- New commands → reset state and execute as a new goal  

---

## ✅ Required Behavior

### Continue flow
```text
copy a.txt
→ destination path>

b.txt
→ continues execution
```

### Override flow (NEW)
```text
git push
→ enters CLARIFICATION

give me a file listing for the current directory
→ previous goal is discarded
→ new command executes
→ state returns to IDLE after execution
```

---

## 🔧 Implementation

### 1. Add override check in CLI loop (before routing input)

```python
if session.state == "CLARIFICATION":
    if not is_valid_clarification_response(user_input, session):
        session.reset()
```

---

### 2. Add helper: is_valid_clarification_response

```python
def is_valid_clarification_response(user_input: str, session) -> bool:
    text = user_input.strip().lower()

    if text in ["yes", "no"]:
        return True

    if session.pending_question:
        if not looks_like_new_command(text):
            return True

    return False
```

---

### 3. Add helper: looks_like_new_command

```python
def looks_like_new_command(text: str) -> bool:
    command_prefixes = [
        "git",
        "copy",
        "move",
        "delete",
        "remove",
        "list",
        "show",
        "status",
        "give me",
        "create",
        "make",
    ]

    return any(text.startswith(cmd) for cmd in command_prefixes)
```

---

### 4. Ensure session.reset() clears all state

```python
def reset(self):
    self.state = "IDLE"
    self.active_goal = None
    self.pending_question = None
    self.pending_plan = None
    self.awaiting_confirmation = False
```

---

### 5. After reset, process input normally

```python
route = router.route(user_input)
```

Do NOT reuse previous goal or context.

---

## 🧪 Regression Test

```text
git push
give me a file listing for the current directory
status
```

### Expected Output

```text
Directory listing displayed

Current state: IDLE
Last route: safe_inspect
Last completed goal: give me a file listing for the current directory
Active goal: (none)
Pending question: (none)
Pending plan: (none)
```

---

## 🚫 Constraints

- Do NOT modify routing logic
- Do NOT introduce async behavior
- Do NOT change agent planning
- Keep solution minimal and deterministic