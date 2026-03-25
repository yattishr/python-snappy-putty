# 🧾 Fix Unknown Command History Recording

## 🎯 Objective

When Snappy handles an unknown/unrecognized command:

- It must:
  1. Display the unknown command message
  2. Reset the session to IDLE
  3. BUT still record what happened in session history

Currently:
- The system resets state correctly
- BUT `Last route`, `Last failed goal`, and `Error message` are lost

---

## ❌ Current Behavior

```text
snappy> git push
I don't recognize that command. Try 'help' to see what I can do.

snappy> status

Current state: IDLE
Last route: (none)
```

---

## ✅ Expected Behavior

```text
snappy> git push
I don't recognize that command. Try 'help' to see what I can do.

snappy> status

Current state: IDLE
Last route: unknown
Last failed goal: git push
Error message: Unrecognized command
```

---

## 🔧 Implementation

### 1. DO NOT call full `session.reset()` directly in unknown handler

Current (problematic):

```python
if route == ROUTE_UNKNOWN:
    print("I don't recognize that command. Try 'help' to see what I can do.")
    session.reset()
    return
```

This wipes history before it is recorded.

---

### 2. Record history BEFORE resetting state

Update to:

```python
if route == ROUTE_UNKNOWN:
    session.last_route = "unknown"
    session.last_failed_goal = user_input
    session.error_message = "Unrecognized command"

    print("I don't recognize that command. Try 'help' to see what I can do.")

    session.reset_to_idle_preserving_history()
    return
```

---

### 3. Implement `reset_to_idle_preserving_history`

```python
def reset_to_idle_preserving_history(self):
    self.state = "IDLE"
    self.active_goal = None
    self.pending_question = None
    self.pending_plan = None
    self.awaiting_confirmation = False
```

IMPORTANT:
- Do NOT clear:
  - last_route
  - last_failed_goal
  - error_message

---

### 4. Ensure status command displays these fields

`status` output must include:

- Last route
- Last failed goal
- Error message

---

## 🧪 Regression Test

```text
git push
status
```

Expected:

```text
I don't recognize that command. Try 'help' to see what I can do.

Current state: IDLE
Last route: unknown
Last failed goal: git push
Error message: Unrecognized command
```

---

## 🚫 Constraints

- Do NOT modify routing logic
- Do NOT introduce async behavior
- Do NOT change existing success/failure flows
- Only fix history preservation for unknown commands