# Snappy M6.9 — Workflow Orchestration Codex Implementation Spec

## Status

**Milestone:** M6.9  
**Name:** Workflow Orchestration  
**Position:** After M6 Skills + M6.5 Config + M6.7 Skill Outputs, before M7 Execution Intelligence  
**Primary goal:** Convert multiple matched skills from a flat list into a supervised, ordered workflow where skill outputs can feed later skill steps.

---

## 1. Why This Milestone Exists

Snappy can already detect and display multiple matched skills for a single request. For example, a request such as:

```text
help me review this API and generate a PR summary
```

currently matches both:

```text
- doc-coauthoring
- codeguardian-review
```

But the current behavior treats multiple skills as co-selected contributors to one generic output. It does **not** yet understand that one skill may need to run before another.

The desired behavior is:

```text
User goal
  ↓
Skill matching
  ↓
Workflow orchestration
  ↓
Step 1: run codeguardian-review
  ↓
Artifact: review_report
  ↓
Step 2: run doc-coauthoring using review_report
  ↓
Artifact: pr_summary
  ↓
Final composed result
```

M6.9 introduces the missing layer: a **workflow orchestrator**.

This is not M7 yet. M7 evaluates and adapts execution. M6.9 simply creates the structured workflow that M7 can later evaluate.

---

## 2. Non-Negotiable Design Principle

M6.9 must remain **supervised and deterministic**.

Do not add:

- open-ended agent loops
- autonomous task discovery
- self-directed retries
- automatic mutation beyond current confirmation rules
- background execution
- plugin installation
- sandboxing

Those belong to later milestones.

M6.9 should only answer:

> Given a user goal and multiple matched skills, what ordered workflow should Snappy run, and how should outputs flow between steps?

---

## 3. Current Observed Problem

Current terminal behavior shows:

```text
Using: doc-coauthoring, codeguardian-review
Matched skills:
- doc-coauthoring
- codeguardian-review
```

But final output remains:

```text
Output kind: general_skill_report
```

This means Snappy recognizes multiple skills, but does not yet model:

- dependency order
- step-level inputs
- step-level outputs
- artifact handoff
- final result composition
- workflow trace

M6.9 fixes that.

---

## 4. Target Architecture

Add a new orchestration layer between planning and skill output generation.

```text
User Request
   ↓
Intent + Skill Matching
   ↓
Grounded Planner
   ↓
Workflow Orchestrator
   ↓
Workflow Plan
   ↓
Confirmation
   ↓
Workflow Executor
   ↓
Skill Step Outputs
   ↓
Composed Final Output
```

The orchestrator should not replace the planner. It should refine the planner result when multiple skills are matched.

---

## 5. Key Concepts

### 5.1 Workflow

A workflow is an ordered sequence of skill steps created for a single user goal.

```python
WorkflowPlan(
    goal="Review the API and generate a PR summary",
    steps=[...],
    final_output_kind="pr_summary",
    status="awaiting_confirmation"
)
```

### 5.2 Workflow Step

A workflow step represents one skill invocation.

```python
WorkflowStep(
    id="step_1",
    skill_name="codeguardian-review",
    purpose="Review API correctness, risks, and implementation gaps",
    input_artifacts=["project_context"],
    output_artifact="review_report",
    risk="LOW",
    depends_on=[]
)
```

### 5.3 Artifact

An artifact is a typed output produced by a workflow step.

Examples:

```text
project_context
review_report
pr_summary
markdown_document
general_skill_report
```

M6.9 does not need a full artifact store yet, but it should introduce a minimal in-memory and traceable artifact model.

---

## 6. Proposed Files To Add

Add these new modules if they do not already exist:

```text
src/snappy_putty/workflow_orchestrator.py
src/snappy_putty/workflow_models.py
src/snappy_putty/workflow_executor.py
```

Add or update tests:

```text
tests/test_workflow_orchestrator.py
tests/test_workflow_executor.py
tests/test_session_repl_subprocess.py
tests/test_state_machine.py
```

Only touch existing planner/router/skill-output modules as needed.

---

## 7. Data Models

Create `src/snappy_putty/workflow_models.py`.

Use dataclasses or Pydantic depending on existing project conventions. Prefer consistency with the existing codebase.

Suggested dataclasses:

```python
from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowStatus = Literal[
    "not_required",
    "awaiting_confirmation",
    "ready",
    "running",
    "completed",
    "failed",
]

@dataclass
class WorkflowArtifact:
    name: str
    kind: str
    producer_step_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None

@dataclass
class WorkflowStep:
    id: str
    skill_name: str
    purpose: str
    input_artifacts: list[str] = field(default_factory=list)
    output_artifact: str | None = None
    depends_on: list[str] = field(default_factory=list)
    risk: str = "LOW"
    status: str = "pending"

@dataclass
class WorkflowPlan:
    goal: str
    workflow_required: bool
    reason: str
    steps: list[WorkflowStep] = field(default_factory=list)
    final_output_kind: str = "general_skill_report"
    artifacts: list[WorkflowArtifact] = field(default_factory=list)
    status: WorkflowStatus = "not_required"
```

Keep the model intentionally small. M7 can add evaluation fields later.

---

## 8. Skill Metadata Extension

Extend skill metadata so each skill can optionally declare what it accepts and produces.

Existing `SKILL.md` files should continue to work without modification.

Add optional frontmatter support if frontmatter already exists. If not, use the current skill metadata parser pattern.

Suggested metadata shape:

```yaml
---
name: codeguardian-review
accepts:
  - project_context
  - source_files
produces:
  - review_report
preferred_position: analysis
---
```

```yaml
---
name: doc-coauthoring
accepts:
  - project_context
  - review_report
  - outline
produces:
  - markdown_document
  - pr_summary
preferred_position: synthesis
---
```

### Backward Compatibility Rule

If a skill has no `accepts` or `produces`, assign defaults:

```python
accepts = ["project_context"]
produces = ["general_skill_report"]
preferred_position = "general"
```

No existing skills should break.

---

## 9. Orchestration Rules

Create `src/snappy_putty/workflow_orchestrator.py`.

### 9.1 When Workflow Is Required

Workflow orchestration should be triggered when:

1. Two or more enabled skills are matched, and
2. The goal appears to contain multiple actions or deliverables, or
3. The matched skills have compatible output/input types.

Examples that should trigger workflow:

```text
help me review this API and generate a PR summary
```

```text
analyze this repo and draft release notes
```

```text
inspect these changes and write a migration guide
```

Examples that should not trigger workflow:

```text
review this API
```

```text
write a PR summary
```

unless multiple skills are clearly required.

### 9.2 Ordering Heuristic

Use deterministic ordering. Do not ask the LLM to invent workflows in M6.9 unless an existing planner already returns enough structured information.

Recommended ordering by `preferred_position`:

```text
context
analysis
transformation
synthesis
finalization
general
```

If no `preferred_position` exists, preserve matched skill order.

### 9.3 Artifact Handoff

If skill A produces something skill B accepts, create dependency:

```text
A → B
```

Example:

```text
codeguardian-review produces review_report

doc-coauthoring accepts review_report

Therefore:
codeguardian-review runs before doc-coauthoring
```

### 9.4 Fallback Behavior

If no dependency graph can be inferred:

- preserve current behavior
- use `general_skill_report`
- do not fail
- optionally show: `Workflow orchestration not required; using flat multi-skill report.`

---

## 10. Workflow Orchestrator API

Suggested function:

```python
def build_workflow_plan(
    goal: str,
    matched_skills: list[MatchedSkill],
    grounded_plan: GroundedPlan,
    context: OutputGenerationContext | None = None,
) -> WorkflowPlan:
    ...
```

The function should:

1. inspect matched skills
2. load skill metadata
3. determine whether workflow is required
4. order workflow steps
5. infer artifact handoffs
6. return a `WorkflowPlan`

Do not execute anything in this function.

---

## 11. Workflow Executor

Create `src/snappy_putty/workflow_executor.py`.

M6.9 executor should be lightweight.

Suggested function:

```python
def execute_workflow_plan(
    workflow_plan: WorkflowPlan,
    output_context: OutputGenerationContext,
) -> WorkflowExecutionResult:
    ...
```

Suggested result:

```python
@dataclass
class WorkflowExecutionResult:
    workflow_plan: WorkflowPlan
    artifacts: list[WorkflowArtifact]
    final_output_kind: str
    summary: str
    success: bool
```

### Important

The workflow executor should not bypass existing confirmation or safety behavior.

It should only run after the user confirms the grounded plan, using the same confirmation gate already used by skill output generation.

---

## 12. Output Behavior

When workflow orchestration is active, terminal output should show:

```text
Workflow orchestration enabled.

Workflow:
1. codeguardian-review
   Produces: review_report
2. doc-coauthoring
   Consumes: review_report
   Produces: pr_summary
```

Then after confirmation:

```text
Running workflow...

Step 1/2: codeguardian-review
Generated artifact: review_report

Step 2/2: doc-coauthoring
Using artifact: review_report
Generated artifact: pr_summary

Workflow completed successfully.
```

Final output should be typed:

```text
Output kind: pr_summary
```

not merely:

```text
Output kind: general_skill_report
```

---

## 13. Example Target Behavior

### Input

```text
snappy> help me review this API and generate a PR summary
```

### Expected Planning Output

```text
Using: codeguardian-review, doc-coauthoring
Workflow orchestration enabled.

Workflow Plan:
1. codeguardian-review
   Purpose: Review API correctness, risks, and implementation gaps.
   Inputs: project_context
   Produces: review_report

2. doc-coauthoring
   Purpose: Draft a concise PR summary using the review findings.
   Inputs: project_context, review_report
   Produces: pr_summary

Final output: pr_summary
```

### Expected Execution Output

```text
Generating workflow output...

Running step 1/2: codeguardian-review
Artifact generated: review_report

Running step 2/2: doc-coauthoring
Artifact generated: pr_summary

═══════════════════════════
PR Summary
═══════════════════════════

...

No files were changed.
_Displayed in the terminal only. No files were created or changed._
Workflow completed successfully.
```

---

## 14. Minimal Artifact Shapes

M6.9 does not need perfect schemas, but it should introduce useful conventions.

### 14.1 Review Report Artifact

```json
{
  "kind": "review_report",
  "summary": "Short review summary",
  "findings": [
    {
      "title": "Sparse error handling",
      "severity": "medium",
      "files": ["controllers/productControllers.js"],
      "detail": "Some catch blocks may not return user-facing errors."
    }
  ],
  "files_referenced": [
    "server.js",
    "controllers/productControllers.js"
  ]
}
```

### 14.2 PR Summary Artifact

```json
{
  "kind": "pr_summary",
  "title": "Review product CRUD API",
  "summary": "This PR reviews the product API request flow and JSON-backed persistence behavior.",
  "bullets": [
    "Reviewed route handling and controller flow.",
    "Checked product persistence behavior.",
    "Flagged validation and error-handling gaps."
  ],
  "risks": [
    "No automated tests were found."
  ]
}
```

Keep these as conventions, not strict global contracts, unless the current output system already supports strict schema validation.

---

## 15. Integration Points

Codex should inspect and integrate with these likely modules:

```text
src/snappy_putty/task_router.py
src/snappy_putty/active_planner.py
src/snappy_putty/context_discovery.py
src/snappy_putty/skill_registry.py
src/snappy_putty/skill_outputs.py
src/snappy_putty/state_machine.py
src/snappy_putty/cli.py
```

Do not assume names blindly. Search the repo first.

Integration should happen around the point where Snappy already knows:

- user goal
- matched skills
- grounded plan
- output generation context
- confirmation status

---

## 16. CLI / UX Requirements

### 16.1 Planning Stage

If workflow orchestration is active, display the workflow before confirmation.

Example:

```text
Workflow orchestration enabled.

1. codeguardian-review → review_report
2. doc-coauthoring → pr_summary
```

### 16.2 Confirmation Stage

Keep the existing confirmation prompt.

```text
No files will be changed.

Continue?
```

Do not add another confirmation prompt unless the workflow includes mutating steps.

### 16.3 Execution Stage

Show step-level progress.

```text
Running workflow step 1/2: codeguardian-review
Running workflow step 2/2: doc-coauthoring
```

### 16.4 Final Stage

Show final output kind and terminal-only/file-change status.

---

## 17. Configuration

Add a feature flag in `.snappy/snappy.yaml` if config architecture supports it.

Suggested config:

```yaml
workflow_orchestration:
  enabled: true
  max_steps: 4
```

Default should be enabled if safe, or enabled only when tests confirm no regressions.

Environment override:

```bash
SNAPPY_WORKFLOW_ORCHESTRATION=off
```

Optional, but useful for debugging.

---

## 18. Limits

M6.9 workflows should have a hard maximum step count.

Recommended:

```text
max_steps = 4
```

If more than four skills match:

- choose the best chain
- drop unrelated/general skills
- explain that lower-confidence skills were omitted

Do not run large workflows yet.

---

## 19. Tests

### 19.1 Unit Tests: Orchestrator

Create `tests/test_workflow_orchestrator.py`.

Test cases:

#### Test: single skill does not require workflow

Input:

```text
matched_skills = [doc-coauthoring]
```

Expected:

```text
workflow_required = False
status = not_required
```

#### Test: review then PR summary creates workflow

Input:

```text
matched_skills = [doc-coauthoring, codeguardian-review]
goal = "help me review this API and generate a PR summary"
```

Expected:

```text
workflow_required = True
steps[0].skill_name == "codeguardian-review"
steps[1].skill_name == "doc-coauthoring"
final_output_kind == "pr_summary"
```

#### Test: disabled skills are not included

If `codeguardian-review` is disabled, expected workflow should not include it.

#### Test: unknown metadata falls back safely

If skills have no accepts/produces metadata, orchestration should not crash.

#### Test: preserves current behavior when dependency cannot be inferred

Multiple unrelated skills should fall back to flat report.

---

### 19.2 Unit Tests: Executor

Create `tests/test_workflow_executor.py`.

Test cases:

#### Test: executes steps in dependency order

Assert step order:

```text
codeguardian-review before doc-coauthoring
```

#### Test: passes prior artifact into dependent step

Assert `review_report` is available to `doc-coauthoring`.

#### Test: final output kind uses last artifact

Expected:

```text
pr_summary
```

#### Test: failed step halts workflow

If step 1 fails, step 2 should not run.

No repair loop in M6.9.

---

### 19.3 Subprocess / CLI Regression Tests

Update `tests/test_session_repl_subprocess.py`.

Add a test around:

```text
help me review this API and generate a PR summary
```

Expected output contains:

```text
Workflow orchestration enabled
codeguardian-review
review_report
doc-coauthoring
pr_summary
```

After confirmation, expected output contains:

```text
Running workflow step 1/2
Running workflow step 2/2
Workflow completed successfully
```

---

### 19.4 State Machine Tests

Update `tests/test_state_machine.py` if needed.

Ensure workflow states do not break existing states:

```text
awaiting_confirmation
output_generated
failed
```

If adding new state is unavoidable, use:

```text
workflow_ready
workflow_running
workflow_completed
```

But prefer not to expand state machine unless necessary.

---

## 20. Acceptance Criteria

M6.9 is complete when all are true:

- Snappy can detect when multiple matched skills form a workflow.
- Snappy can order compatible skills deterministically.
- Snappy can represent step-level inputs and outputs.
- Snappy can pass a produced artifact from one skill step to another.
- Snappy displays the workflow before confirmation.
- Snappy executes workflow steps after confirmation.
- Snappy produces a typed final output such as `pr_summary` instead of always `general_skill_report`.
- Single-skill behavior remains unchanged.
- Disabled skills are never used in workflows.
- Existing tests pass.
- New workflow tests pass.
- No files are changed unless the underlying skill/output flow already allowed that and confirmation rules permit it.

---

## 21. Explicit Non-Goals

Do not implement in M6.9:

- autonomous retries
- result scoring
- confidence scoring
- self-evaluation
- sandbox execution
- plugin installation
- remote skill packs
- GitHub PR creation
- background execution
- multi-agent identity/persona system
- long-running workflows
- automatic file mutation from report-only workflows

These belong to M7 or M8.

---

## 22. Suggested Implementation Sequence For Codex

### Step 1: Inspect Existing Skill Output Flow

Find where Snappy currently displays:

```text
Using skill: doc-coauthoring, codeguardian-review
Output kind: general_skill_report
```

Identify the function responsible for generating skill output.

### Step 2: Add Workflow Models

Create `workflow_models.py`.

Add tests for model creation if the project usually tests models.

### Step 3: Extend Skill Metadata

Add optional metadata fields:

```text
accepts
produces
preferred_position
```

Ensure old skills still load.

### Step 4: Add Workflow Orchestrator

Create `build_workflow_plan(...)`.

Start deterministic and simple.

### Step 5: Integrate Into Planner Display

When multiple skills match, build workflow plan and display it before confirmation.

### Step 6: Add Workflow Executor

Execute ordered steps using existing output generation functions.

Do not duplicate skill execution logic unnecessarily.

### Step 7: Compose Final Output

Use the last meaningful artifact as the final output.

For review + doc generation workflow, final output should be:

```text
pr_summary
```

### Step 8: Add CLI Regression Tests

Protect the terminal UX.

### Step 9: Run Full Test Suite

Run:

```bash
pytest
```

Also run any existing smoke command used by the project.

---

## 23. Example Skill Metadata Updates

Update the local sample skills as follows if they exist.

### codeguardian-review

```yaml
---
name: codeguardian-review
accepts:
  - project_context
  - source_files
produces:
  - review_report
preferred_position: analysis
---
```

### doc-coauthoring

```yaml
---
name: doc-coauthoring
accepts:
  - project_context
  - review_report
  - outline
produces:
  - markdown_document
  - pr_summary
preferred_position: synthesis
---
```

If existing skill docs do not use YAML frontmatter, adapt to the current parser style.

---

## 24. Guardrail Behavior

If a workflow includes any mutating skill:

- surface that risk in the plan
- preserve confirmation
- do not silently apply changes

If all workflow steps are report-only:

```text
No files will be changed.
```

must remain true.

---

## 25. Good First Test Scenario

Use this exact prompt in tests where possible:

```text
help me review this API and generate a PR summary
```

Expected matched skills:

```text
codeguardian-review
doc-coauthoring
```

Expected workflow:

```text
codeguardian-review → review_report → doc-coauthoring → pr_summary
```

This scenario captures the whole point of M6.9.

---

## 26. Final Codex Instruction

Implement M6.9 as a small, safe architectural layer.

The goal is not to make Snappy more autonomous.

The goal is to make Snappy more compositional.

At the end of this patch, Snappy should understand that multiple skills are not merely a list.

They can be a workflow.
