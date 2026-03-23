# 🧾 Implement State-Aware Prompt Rendering + Inline Clarification + Arrow Navigation

## 🎯 Objective

Improve Snappy CLI UX by:

1. Making prompt rendering **state-aware**
2. Removing `snappy [ask]>` during CLARIFICATION
3. Using **inline prompts** (the question becomes the input line)
4. Supporting **arrow-key navigation (↑/↓ + ENTER)** for guided choices
5. Eliminating ambiguity between command input and clarification input

---

## ✅ Target UX

### File copy example

```text
snappy> copy ROUTING.md

destination path>
tests/

Planned Changes:
...
```

---

### Guided option example (arrow navigation)

```text
snappy> give me a file listing

Where would you like the file listing from?

> Current directory (.)
  Root directory (/)
  Specify a custom path

(Use ↑/↓ to navigate, ENTER to select)
```

---

## 🔧 Implementation

## 1. Make prompt rendering state-aware

Replace static prompt rendering with:

```python
def render_prompt(session):
    if session.state == "CLARIFICATION":
        if isinstance(session.pending_question, dict):
            return session.pending_question.get("prompt", "> ")
        else:
            return session.pending_question  # e.g. "destination path>"
    else:
        return "snappy> "
```

IMPORTANT:
- Do NOT print both question and `snappy [ask]>`
- The clarification question IS the prompt

---

## 2. Remove `snappy [ask]>` from CLARIFICATION state

Ensure main REPL loop does:

```python
prompt = render_prompt(session)
user_input = input(prompt)
```

NOT:

```python
print("destination path>")
print("snappy [ask]> ")  # ❌ remove this
```

---

## 3. Inline clarification behavior

When entering CLARIFICATION:

```python
session.state = "CLARIFICATION"
session.pending_question = {
    "type": "path",
    "prompt": "destination path>"
}
```

User input is captured directly via that prompt.

---

## 4. Add arrow-key navigation for choice prompts

If:

```python
session.pending_question["type"] == "choice"
```

Then use interactive selector:

```python
def select_with_arrows(question):
    index = 0
    options = question["options"]

    while True:
        clear_screen()

        print(question["message"])
        print()

        for i, opt in enumerate(options):
            prefix = ">" if i == index else " "
            print(f"{prefix} {opt['label']}")

        print("\n(Use ↑/↓ to navigate, ENTER to select)")

        key = read_key()

        if key == "UP":
            index = (index - 1) % len(options)
        elif key == "DOWN":
            index = (index + 1) % len(options)
        elif key == "ENTER":
            return options[index]["value"]
```

---

## 5. Integrate selection into flow

```python
if session.state == "CLARIFICATION":
    if session.pending_question["type"] == "choice":
        selected = select_with_arrows(session.pending_question)

        if selected == "custom":
            session.pending_question = {
                "type": "path",
                "prompt": "Enter custom path:"
            }
        else:
            handle_selection(selected)
            session.reset()
```

---

## 6. Preserve override behavior (CRITICAL)

Before handling clarification:

```python
if session.state == "CLARIFICATION":
    if not is_valid_clarification_response(user_input, session):
        session.reset()
        route_new_command(user_input)
        return
```

This ensures:

- User can break out anytime
- No stuck flows

---

## 7. Support direct input alongside arrow UI

Even when menu is shown:

- Allow user to type:
  - a path (`./test`)
  - a command (`git status` → triggers override)

---

## 🧪 Regression Tests

### Test 1 — Inline prompt

```text
copy ROUTING.md
tests/
```

Expected:
- No `snappy [ask]>`
- Path accepted
- Copy executes

---

### Test 2 — Arrow selection

```text
give me a file listing
↓ ENTER
```

Expected:
- Executes correct option
- Returns to IDLE

---

### Test 3 — Override

```text
give me a file listing
git status
```

Expected:
- Menu cancelled
- `git status` runs
- Clean state

---

## 🚫 Constraints

- Do NOT break state machine
- Do NOT block REPL loop
- Do NOT remove free-text input support
- Keep behavior deterministic
- Keep CLI responsive and interruptible