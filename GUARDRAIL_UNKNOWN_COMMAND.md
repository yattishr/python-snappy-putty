# 🧾 Add Guardrail for Unknown / Unsupported Commands

## 🎯 Objective

Ensure that when Snappy encounters an unrecognized or unsupported command, it:

1. Responds with a clear, local message (no agent/LLM call)
2. Does NOT attempt to route to `ask`
3. Resets session state to `IDLE`
4. Leaves no residual state (no goal, no pending question, no plan)

---

## ✅ Required Behavior

### Example

```text
snappy> do something random and undefined

I don’t recognize that command. Try 'help' to see what I can do.

snappy> status

Current state: IDLE
Active goal: (none)
Pending question: (none)
Pending plan: (none)
```

---

## 🔧 Implementation

### 1. Add new route type

```python
ROUTE_UNKNOWN = "unknown"
```

---

### 2. Update router fallback logic

At the END of the routing function:

```python
if no_route_matched:
    return ROUTE_UNKNOWN
```

IMPORTANT:
- This must be reached BEFORE falling back to any agent/ask route
- Unknown commands must NOT go to `ROUTE_ASK`

---

### 3. Handle unknown route in CLI

In the CLI execution handler:

```python
if route == ROUTE_UNKNOWN:
    print("I don’t recognize that command. Try 'help' to see what I can do.")
    session.reset()
    return
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

## 🧪 Regression Test

```text
do something undefined
status
```

### Expected Output

```text
I don’t recognize that command. Try 'help' to see what I can do.

Current state: IDLE
Active goal: (none)
Pending question: (none)
Pending plan: (none)
```

---

## 🚫 Constraints

- Do NOT route unknown commands to `ask`
- Do NOT invoke agent/LLM
- Do NOT modify existing valid routes
- Keep behavior deterministic and local