# Snappy M5.5 — Plan Interaction Layer (Codex Implementation)

## Goal

Enable users to inspect, understand, and refine plans before execution.

This layer introduces interaction, not execution.

---

## Features

### 1. show plan

Command:
snappy> show plan

Displays:
- Goal
- Mode (deterministic / llm_assisted)
- Snapshot ID
- Steps
- Files per step
- Risks
- Assumptions
- Status

Edge case:
No plan → "No active plan to display."

---

### 2. why this plan

Command:
snappy> why this plan

Explains:
- Why files were selected
- Why steps exist
- Assumptions
- Planning mode

Must use stored plan data. No new LLM calls.

---

### 3. explain step <n>

Command:
snappy> explain step 1

Explains:
- What the step does
- Why it exists
- Files touched
- Risk level

---

### 4. refine plan / refine step

Commands:
snappy> refine plan
snappy> refine step 2

Flow:
User input → validate → update plan → persist → log history

Examples:
- refine step 2 → "focus only on CLI logging"
- refine plan → "limit changes to README"

---

## Guardrails

- No execution allowed
- No new files outside snapshot
- No implicit confirmation
- No LLM re-planning (modify existing plan only)

---

## Data Model

Update session.json:

{
  "last_plan": {
    "id": "...",
    "mode": "deterministic",
    "goal": "...",
    "steps": [...],
    "files": [...],
    "snapshot_id": "...",
    "status": "awaiting_confirmation",
    "refinements": [
      {
        "timestamp": "...",
        "change": "step 2 refined"
      }
    ]
  }
}

---

## History Logging

Append:

## <timestamp>
Event: Plan displayed

## <timestamp>
Event: Step explained

## <timestamp>
Event: Plan refined
Change: <description>

---

## CLI Routes

show_plan
explain_step
refine_plan

---

## Tests

1. show plan works / no plan case
2. explain step valid/invalid
3. refine step updates plan
4. refine does NOT execute
5. session.json updated
6. history.md updated

---

## Acceptance Criteria

User can:
- view plan
- understand plan
- refine plan

Without:
- execution
- breaking snapshot
- losing control

---

## Verification

python -m py_compile src/snappy_putty/*.py
python -m pytest tests/

Manual:

snappy> show plan
snappy> explain step 1
snappy> refine step 2
snappy> status


---

# Deliverables

Return:

1. code changes
2. tests
3. concise implementation summary including:
   - files changed
   - any remaining follow-up items that should be tracked separately
   - save the results of this concise implementation into a file on this filesystem
