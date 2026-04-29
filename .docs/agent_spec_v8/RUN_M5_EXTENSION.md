# Snappy PuTTy — M5 Extension: LLM-Assisted Grounded Planning

## Objective

Implement an M5 Extension that allows Snappy Active Mode to generate grounded, file-aware plans using an LLM **only when deterministic planning is insufficient**.

This extension must preserve Snappy’s existing safety model:

- No unsupervised writes
- No direct execution from LLM output
- No bypass around the confirmation gate
- No use of stale project context
- No hallucinated file paths accepted as executable truth

The LLM may assist with planning. It must not become the executor.

---

## Design Summary

M5 introduced Active Mode:

```text
read-only project inspection
bounded planning from actual files
no unsupervised writes
project snapshot memory
append-only history.md
```

This extension adds:

```text
LLM-assisted planning for ambiguous/high-level development goals
```

Examples:

```text
snappy ask "add logging to the CLI"
snappy ask "help me improve the test coverage"
snappy ask "refactor the session workflow code"
snappy ask "make the project easier to understand"
```

The LLM receives a bounded project snapshot and returns a structured plan. Snappy then validates that plan before saving or displaying it.

---

## Non-Negotiable Safety Invariants

These invariants must hold after this extension:

1. The LLM never executes actions.
2. The LLM never writes files.
3. The LLM never decides final file mutations.
4. The LLM plan must be validated before use.
5. Every LLM-generated plan must be bound to a valid `ProjectSnapshot`.
6. If the snapshot is stale, the plan is invalid.
7. Any referenced file path must exist or be explicitly marked as proposed/new.
8. The plan must be stored only as workflow state, not as permanent authority.
9. `history.md` is append-only and observational only.
10. The existing confirmation model remains mandatory before any write-capable workflow.

Think of the LLM as a navigator. Snappy remains the driver.

---

## Scope

### Include

- Add LLM-assisted planner route for high-level project goals.
- Add structured JSON plan schema.
- Add plan validator.
- Bind plans to `ProjectSnapshot.snapshot_id`.
- Save validated plans to `session.json`.
- Append plan events to `history.md`.
- Show plan provenance in `status`.
- Add tests for accepted, rejected, stale, and hallucinated plans.

### Exclude

Do not add:

- automatic code edits
- patch generation
- direct command execution from the LLM
- autonomous re-planning loops
- tool-calling execution
- dependency installation
- shell command execution
- GitHub/GitLab PR creation
- multi-plan orchestration

Those belong later, not here.

---

## Routing Behavior

The planner should choose between deterministic and LLM-assisted planning.

### Deterministic planner

Use deterministic planning for known, structured operations:

```text
copy file
move file
list files
inspect project
inspect files
git status
git branch
git diff summary
show commit
```

These should not call the LLM.

### LLM-assisted planner

Use the LLM only for ambiguous or high-level development goals:

```text
add logging
improve CLI UX
increase test coverage
refactor session flow
explain project architecture
make onboarding easier
help me implement feature X
```

The router should classify the request as one of:

```python
PlanningMode.DETERMINISTIC
PlanningMode.LLM_ASSISTED
```

A simple first-pass heuristic is acceptable for this extension.

Example heuristic:

```python
LLM_ASSISTED_TRIGGERS = [
    "add",
    "improve",
    "refactor",
    "design",
    "implement",
    "extend",
    "clean up",
    "make",
    "help me",
]
```

But do not route known filesystem commands through the LLM.

---

## Required Data Structures

### `GroundedPlan`

Create or extend a plan model.

Suggested shape:

```python
@dataclass
class GroundedPlan:
    plan_id: str
    goal: str
    mode: str  # "deterministic" | "llm_assisted"
    created_at: str
    based_on_snapshot_id: str
    files_inspected: list[str]
    steps: list[PlanStep]
    risks: list[str]
    assumptions: list[str]
    status: str  # "draft" | "awaiting_confirmation" | "invalidated" | "rejected"
```

### `PlanStep`

```python
@dataclass
class PlanStep:
    step_id: str
    description: str
    files: list[str]
    proposed_new_files: list[str]
    risk: str  # "LOW" | "MEDIUM" | "HIGH"
    requires_confirmation: bool
```

### `LLMPlanResponse`

This is the raw structured response expected from the LLM.

```json
{
  "goal": "Add logging to the CLI",
  "summary": "Introduce lightweight logging around command handling and workflow state transitions.",
  "files_inspected": [
    "src/snappy_putty/cli.py",
    "src/snappy_putty/session.py"
  ],
  "steps": [
    {
      "description": "Identify CLI entry points and workflow transitions where logging would be useful.",
      "files": ["src/snappy_putty/cli.py", "src/snappy_putty/session.py"],
      "proposed_new_files": [],
      "risk": "LOW",
      "requires_confirmation": true
    }
  ],
  "risks": [
    "Logging could alter visible CLI output if not kept separate from terminal rendering."
  ],
  "assumptions": [
    "The project prefers minimal dependencies."
  ]
}
```

---

## LLM Prompt Contract

The LLM must receive only bounded, relevant project context.

Do not dump entire files into the prompt by default.

Pass:

- user goal
- project root name
- detected languages
- detected frameworks/tools
- relevant file tree summary
- selected file summaries if available
- current snapshot id
- safety instructions
- required JSON schema

### Prompt Template

```text
You are assisting Snappy PuTTy, a supervised agentic CLI.

Your task is to create a grounded implementation plan based only on the provided project context.

You may suggest files to inspect or modify, but you must not invent files unless you mark them as proposed_new_files.

You must not output shell commands.
You must not output code patches.
You must not claim that changes have been made.
You must return valid JSON only.

User goal:
{goal}

Project snapshot id:
{snapshot_id}

Project summary:
{project_summary}

Relevant files:
{relevant_files}

Return JSON with this shape:
{
  "goal": string,
  "summary": string,
  "files_inspected": string[],
  "steps": [
    {
      "description": string,
      "files": string[],
      "proposed_new_files": string[],
      "risk": "LOW" | "MEDIUM" | "HIGH",
      "requires_confirmation": boolean
    }
  ],
  "risks": string[],
  "assumptions": string[]
}
```

---

## Validation Rules

Add a `validate_llm_plan(...)` function.

Suggested signature:

```python
def validate_llm_plan(
    raw_plan: dict,
    snapshot: ProjectSnapshot,
    project_root: Path,
) -> GroundedPlan:
    ...
```

Validation must check:

### Schema validation

- Required top-level keys exist.
- `steps` is a non-empty list.
- `risk` values are one of `LOW`, `MEDIUM`, `HIGH`.
- `requires_confirmation` is boolean.
- File fields are lists of strings.

### Path validation

For each path in `files`:

- Must be relative.
- Must not contain `..`.
- Must resolve inside project root.
- Must exist in current filesystem or snapshot.
- Must not be absolute.

For each path in `proposed_new_files`:

- Must be relative.
- Must not contain `..`.
- Must resolve inside project root.
- May not exist yet.

### Snapshot validation

- Plan must include or be wrapped with `based_on_snapshot_id`.
- Snapshot must still be valid.
- If snapshot is stale, reject the plan.

### Safety validation

Reject plan if any step includes:

```text
rm -rf
sudo
curl | sh
wget | sh
chmod -R
chown -R
format disk
install global dependency
delete project root
modify files outside project root
```

This does not need to be perfect. It needs to be conservative.

### Risk normalization

If any step references config files, dependency files, auth files, CI files, or `.snappy` files, upgrade risk to at least `MEDIUM`.

Examples:

```text
pyproject.toml
package.json
.env
.github/workflows/*
.snappy/rules/*
.snappy/memory/*
```

---

## Memory Behavior

### Save validated plan to `session.json`

Example:

```json
{
  "active_goal": "Add logging to the CLI",
  "state": "CONFIRMATION",
  "last_plan": {
    "plan_id": "plan_abc123",
    "mode": "llm_assisted",
    "goal": "Add logging to the CLI",
    "based_on_snapshot_id": "snapshot_123",
    "created_at": "2026-04-29T14:30:00+02:00",
    "status": "awaiting_confirmation",
    "files_inspected": [
      "src/snappy_putty/cli.py",
      "src/snappy_putty/session.py"
    ],
    "steps": [],
    "risks": [],
    "assumptions": []
  }
}
```

### Append to `history.md`

Example:

```md
## 2026-04-29 14:30
Event: LLM-assisted plan created
Mode: active
Goal: Add logging to the CLI
Plan ID: plan_abc123
Based on snapshot: snapshot_123
Files referenced:
- src/snappy_putty/cli.py
- src/snappy_putty/session.py
Status: awaiting confirmation
```

If validation fails:

```md
## 2026-04-29 14:31
Event: LLM-assisted plan rejected
Goal: Add logging to the CLI
Reason: Referenced file path escaped project root
Status: rejected
```

---

## CLI / REPL UX

When a user asks a high-level goal:

```text
snappy [ask]> add logging to the CLI
```

Expected output:

```text
Inspecting project context...
Using snapshot: snapshot_123

Grounded Plan
Goal: Add logging to the CLI
Mode: LLM-assisted
Based on snapshot: snapshot_123

Files considered:
- src/snappy_putty/cli.py
- src/snappy_putty/session.py

Steps:
1. Identify CLI entry points and workflow transitions where logging is useful. [LOW]
2. Add a lightweight internal logging helper. [LOW]
3. Add tests to verify logging does not affect visible CLI output. [MEDIUM]

Risks:
- Logging must not pollute Rich-rendered terminal output.

Status: awaiting confirmation
No changes have been applied.
confirm [YES/NO]>
```

If the snapshot is stale:

```text
Project snapshot is stale. Re-inspection is required before planning.
No plan was created.
```

If the LLM returns an invalid plan:

```text
LLM-assisted plan was rejected by validation.
Reason: referenced file does not exist: src/fake.py
No changes have been applied.
```

---

## Status Output Update

Update `snappy status` to include plan provenance.

Example:

```text
Agent mode: active
Project snapshot: present
Snapshot ID: snapshot_123
Snapshot valid: yes
Grounded planning: yes
Last plan: present
Last plan mode: llm_assisted
Last plan status: awaiting_confirmation
Last plan based on snapshot: snapshot_123
Writes allowed: confirmation only
```

---

## Suggested Files to Inspect Before Editing

Codex should inspect the current repo and locate the actual files. Likely candidates based on current architecture:

```text
src/snappy_putty/cli.py
src/snappy_putty/session.py
src/snappy_putty/state.py
src/snappy_putty/agent.py
src/snappy_putty/memory.py
src/snappy_putty/planner.py
src/snappy_putty/inspection.py
src/snappy_putty/history.py
tests/test_state_machine.py
tests/test_session_repl_subprocess.py
tests/test_agent_runtime.py
tests/test_active_mode.py
```

Do not assume these exact files exist. Inspect first.

---

## Implementation Steps

### Step 1 — Locate current M5 implementation

Inspect the repo for:

- `ProjectSnapshot`
- Active Mode routing
- project inspection code
- session memory persistence
- history logging
- planner functions
- status output

Do not edit until the current structure is understood.

### Step 2 — Add planner mode classification

Introduce:

```python
class PlanningMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"
```

Add a classifier function:

```python
def classify_planning_mode(user_input: str) -> PlanningMode:
    ...
```

Known safe deterministic commands should remain deterministic.

### Step 3 — Add LLM planner adapter

Create a small adapter layer, for example:

```python
def create_llm_assisted_plan(goal: str, snapshot: ProjectSnapshot) -> dict:
    ...
```

For now, keep this adapter easy to mock in tests.

If the repo does not yet have OpenAI API wiring, implement an interface/stub rather than forcing full API integration.

Example:

```python
class LLMPlannerClient(Protocol):
    def create_plan(self, prompt: str) -> dict:
        ...
```

This allows tests to inject fake LLM responses.

### Step 4 — Add validation

Implement `validate_llm_plan(...)` with schema, path, snapshot, and safety checks.

Prefer conservative rejection over permissive acceptance.

### Step 5 — Save validated plan

Persist the validated `GroundedPlan` to session memory.

Do not persist invalid raw LLM responses as active plans.

### Step 6 — Append history events

Append one of:

```text
LLM-assisted plan created
LLM-assisted plan rejected
LLM-assisted plan invalidated
```

### Step 7 — Update status

Expose:

```text
Last plan mode
Last plan status
Last plan snapshot id
```

### Step 8 — Tests

Add tests for the extension.

---

## Required Tests

### 1. Deterministic commands do not call LLM

Input:

```text
copy README.md docs/README.md
```

Expected:

```text
PlanningMode.DETERMINISTIC
LLM client not called
```

### 2. High-level goal calls LLM planner

Input:

```text
add logging to the CLI
```

Expected:

```text
PlanningMode.LLM_ASSISTED
LLM client called with project snapshot context
Validated GroundedPlan saved to session
history.md appended
```

### 3. Hallucinated file is rejected

Fake LLM returns:

```json
{
  "files": ["src/does_not_exist.py"]
}
```

Expected:

```text
plan rejected
no active plan saved
history rejection event appended
```

### 4. Path escape is rejected

Fake LLM returns:

```json
{
  "files": ["../outside.py"]
}
```

Expected:

```text
plan rejected
no active plan saved
```

### 5. Proposed new file is allowed if safe

Fake LLM returns:

```json
{
  "files": ["src/snappy_putty/cli.py"],
  "proposed_new_files": ["src/snappy_putty/logging.py"]
}
```

Expected:

```text
plan accepted
new file marked as proposed only
requires confirmation remains true
```

### 6. Stale snapshot invalidates plan

Given:

```text
snapshot is stale before validation
```

Expected:

```text
plan rejected or invalidated
no confirmation prompt for stale plan
```

### 7. Status displays plan provenance

Expected status includes:

```text
Last plan mode: llm_assisted
Last plan status: awaiting_confirmation
Last plan based on snapshot: snapshot_...
```

### 8. LLM output cannot bypass confirmation

Even if fake LLM returns:

```json
{
  "requires_confirmation": false
}
```

Expected:

```text
Snappy normalizes confirmation requirement to true for write-capable plans
```

---

## Manual Smoke Checklist

Run after implementation:

```bash
pytest
```

Then manually test:

```bash
snappy
```

Inside REPL:

```text
inspect project
status
ask add logging to the CLI
status
NO
status
```

Expected:

- project inspection succeeds
- snapshot is created
- LLM-assisted plan is created or mocked depending on environment
- no files are changed
- plan is stored in session memory
- history.md includes plan event
- rejecting the plan does not mutate files

Also test deterministic route:

```text
ask copy README.md docs/README.md
```

Expected:

- no LLM call
- existing deterministic planner behavior preserved

---

## Failure Modes to Guard Against

### Failure: LLM invents files

Response:

```text
Reject unless files are explicitly proposed_new_files.
```

### Failure: LLM references outside path

Response:

```text
Reject immediately.
```

### Failure: LLM returns prose instead of JSON

Response:

```text
Reject and show validation failure.
```

### Failure: snapshot changed after plan

Response:

```text
Invalidate plan and require re-inspection.
```

### Failure: LLM says confirmation not required

Response:

```text
Override. Confirmation is required for all write-capable plans.
```

### Failure: no LLM API key available

Response:

```text
Show graceful message:
LLM-assisted planning is unavailable. Deterministic planning and inspection remain available.
```

Do not crash.

---

## Acceptance Criteria

This extension is complete when:

1. High-level development goals can trigger LLM-assisted planning.
2. The LLM receives project snapshot context.
3. The LLM must return structured JSON.
4. Invalid LLM plans are rejected.
5. Hallucinated existing files are rejected.
6. Safe proposed new files are allowed as proposed only.
7. Plans are bound to snapshot IDs.
8. Stale snapshots invalidate plans.
9. Valid plans are saved to `session.json`.
10. Plan events are appended to `history.md`.
11. `status` shows last plan provenance.
12. No LLM-generated plan can mutate files without confirmation.
13. Existing deterministic routes still work without LLM calls.
14. Full regression suite passes.

---

## Codex Execution Instructions

1. Start by inspecting the current M5 implementation.
2. Do not assume file names. Locate the actual modules.
3. Preserve existing behavior and tests.
4. Add the smallest cohesive implementation.
5. Prefer dependency injection for the LLM client so tests can use fake responses.
6. Keep validation conservative.
7. Do not add autonomous execution.
8. Do not weaken confirmation logic.
9. Add tests before or alongside implementation.
10. Run the full test suite.
11. Provide a concise summary of changed files, tests added, and remaining limitations.

---

## Final Principle

M5 Extension gives Snappy a planning brain, not a pair of unsupervised hands.

The LLM may suggest.
Snappy must verify.
The user must confirm.
