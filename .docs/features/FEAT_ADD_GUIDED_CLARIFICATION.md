# 🧾 Add Guided Clarification with Arrow-Key Selection (CLI UX Upgrade)

## 🎯 Objective

Enhance Snappy’s clarification flow to support **guided options with keyboard navigation**:

- Use ↑ / ↓ arrow keys to move through options
- Press ENTER to select
- Maintain compatibility with existing state machine
- Preserve command override behavior

---

## ✅ Target Behavior

### Example Flow

```text
snappy> give me a file listing

Where would you like the file listing from?

> Current directory (.)
  Root directory (/)
  Specify a custom path

(Use ↑/↓ to navigate, ENTER to select)
```

User presses ↓ ↓ ENTER:

```text
Enter custom path:
```

OR presses ENTER on first option:

```text
→ Executes listing for "."
→ Returns to IDLE
```

---

## 🔧 Implementation

### 1. Introduce structured clarification type

Replace simple string `pending_question` with structured object when needed:

```python
session.pending_question = {
    "type": "choice",
    "message": "Where would you like the file listing from?",
    "options": [
        {"label": "Current directory (.)", "value": "."},
        {"label": "Root directory (/)", "value": "/"},
        {"label": "Specify a custom path", "value": "custom"}
    ],
    "selected_index": 0
}
```

---

### 2. Detect when to trigger guided clarification

In intent parsing:

```python
if intent == "list_files" and not target_path:
    return CLARIFICATION_REQUIRED
```

---

### 3. Render interactive menu (arrow key navigation)

Use a lightweight CLI input handler (e.g. `readchar`, `curses`, or similar).

Example behavior:

```python
def render_choice_menu(question):
    index = question["selected_index"]

    while True:
        clear_screen()

        print(question["message"])
        print()

        for i, option in enumerate(question["options"]):
            prefix = ">" if i == index else " "
            print(f"{prefix} {option['label']}")

        print("\n(Use ↑/↓ to navigate, ENTER to select)")

        key = read_key()

        if key == "UP":
            index = (index - 1) % len(question["options"])
        elif key == "DOWN":
            index = (index + 1) % len(question["options"])
        elif key == "ENTER":
            return question["options"][index]["value"]
```

---

### 4. Handle selection result

```python
selected = render_choice_menu(session.pending_question)

if selected == "custom":
    session.pending_question = "Enter custom path:"
    session.state = "CLARIFICATION"
else:
    execute_file_listing(selected)
    session.reset()
```

---

### 5. Preserve override behavior (CRITICAL)

Before handling menu input:

```python
if session.state == "CLARIFICATION":
    if not is_valid_clarification_response(user_input, session):
        session.reset()
        route_new_command(user_input)
        return
```

Arrow navigation must NOT block command override.

---

### 6. Ensure non-interactive fallback (important)

If arrow key handling fails (e.g. unsupported terminal):

Fallback to:

```text
1. Current directory (.)
2. Root directory (/)
3. Specify a custom path

Enter 1, 2, or a path:
```

---

## 🧪 Regression Tests

### Test 1 — Arrow selection

```text
give me a file listing
↓
ENTER
```

Expected:
- Executes correct option
- Returns to IDLE

---

### Test 2 — Override during menu

```text
give me a file listing
git status
```

Expected:
- Menu is cancelled
- `git status` executes
- No contamination from previous state

---

### Test 3 — Custom path

```text
give me a file listing
↓ ↓ ENTER
/home/user
```

Expected:
- Executes listing for provided path
- Returns to IDLE

---

## 🚫 Constraints

- Do NOT break existing state machine
- Do NOT block REPL input loop
- Do NOT introduce async complexity
- Keep implementation lightweight and deterministic