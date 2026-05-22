# Snappy M6.7 Codex Implementation Prompt

## Milestone

**M6.7 — Structured Skill Output Generation**

## Goal

Implement structured, non-mutating skill output generation.

M6.6 taught Snappy how to choose the right skill for a user instruction.

M6.7 should let Snappy use the selected skill to produce a useful final output/report/artifact after the plan is confirmed, without applying file changes or running unsafe actions.

This milestone is about:

```text
selected skill
  → grounded context
  → confirmed non-mutating task
  → structured output
```

It is **not** about autonomous execution, file mutation, external API posting, shell execution, or plugin systems.

---

## Current Context

Snappy already has:

- Project inspection and snapshots
- Active planning
- Rules and confirmation
- Context discovery
- M6 modular skills:
  - `.snappy/skills/<skill>/SKILL.md`
  - skill metadata
  - skill validation
  - skill inspection
- M6.1 project relevance classification:
  - `direct_project_work`
  - `project_extension`
  - `project_adaptation`
  - `unrelated`
- M6.5 project config:
  - `.snappy/snappy.yaml`
  - enabled/disabled skills
  - planning preferences
- M6.6 skill-driven task routing:
  - task intent classification
  - generic skill selection
  - selected skill metadata in planning/history
  - selected skill context passed to planning

M6.7 should build on these foundations.

---

## Core Principle

A skill may generate structured output.

A skill must not directly execute.

The selected skill can be used to produce:

- review reports
- implementation proposals
- documentation drafts
- testing plans
- design briefs
- migration notes
- risk assessments
- checklists
- recommended next steps

But it must not:

- write files
- modify files
- run commands
- call external APIs
- post comments to GitLab/GitHub
- bypass confirmation
- weaken rules
- continue autonomously without user approval

---

## Desired Behaviour

### Example 1: CodeGuardian Review

User:

```text
Review my latest changes and give me MR-style feedback.
```

Current M6.6 behaviour:

```text
Matched task intent: code_review
Selected skill: codeguardian-review
Grounded plan created
Status: awaiting_confirmation
```

Desired M6.7 behaviour after user confirms:

```text
CodeGuardian Review Report

Summary:
...

Findings:
1. [High] ...
2. [Medium] ...
3. [Low] ...

Suggested Fixes:
...

Testing Notes:
...

No files changed.
```

### Example 2: Documentation

User:

```text
Write README documentation for this project.
```

After confirmation, Snappy should generate a structured README draft or documentation report, but should not write `README.md` unless the user explicitly approves a file-writing plan.

### Example 3: Frontend Design

User:

```text
Design a frontend interface for this API.
```

After confirmation, Snappy may produce:

- UI concept
- file structure proposal
- endpoint integration map
- component outline
- implementation plan

It should not create files unless the user confirms a mutation plan.

---

## Required New Concept

Introduce a **skill output generation phase**.

Suggested lifecycle:

```text
request
  → route skill
  → classify project relationship
  → build grounded plan
  → await confirmation
  → generate structured skill output
  → return report/artifact
  → no mutation unless separately confirmed
```

This should reuse existing confirmation state where possible.

---

## Required New Module

Add a module:

```text
src/snappy_putty/skill_outputs.py
```

Suggested responsibilities:

- define output schemas/types
- map task intent + selected skill to output kind
- build skill output prompts/context
- validate generated output shape
- produce display-ready report text
- record output metadata in history

Suggested types:

```python
@dataclass
class SkillOutputRequest:
    goal: str
    task_intent: str
    selected_skills: list[str]
    project_relationship: str
    snapshot_id: str | None
    files_considered: list[str]
    context_summary: str
    plan_steps: list[Any]
    skill_context: str
    config: Any

@dataclass
class SkillOutput:
    output_kind: str
    title: str
    summary: str
    sections: list[SkillOutputSection]
    warnings: list[str]
    files_referenced: list[str]
    mutations_applied: bool = False

@dataclass
class SkillOutputSection:
    heading: str
    items: list[str] | None = None
    body: str | None = None
    severity: str | None = None
```

Exact names may be adjusted to match project conventions.

---

## Supported Output Kinds

Support at least:

```text
code_review_report
documentation_draft
frontend_design_brief
implementation_plan
testing_plan
deployment_plan
general_skill_report
```

Mapping examples:

```text
task_intent=code_review + codeguardian-review
  → code_review_report

task_intent=documentation + doc-coauthoring
  → documentation_draft

task_intent=frontend_build + frontend-design
  → frontend_design_brief

task_intent=testing
  → testing_plan

task_intent=deployment
  → deployment_plan

fallback
  → general_skill_report
```

Do not hardcode full CodeGuardian behaviour. It is acceptable to map `code_review` to `code_review_report` generically.

---

## Output Shape Requirements

### `code_review_report`

Must include:

- Summary
- Findings
- Severity labels where possible:
  - Critical
  - High
  - Medium
  - Low
  - Info
- File references where grounded
- Suggested fixes
- Testing recommendations
- Assumptions / limitations
- Explicit statement that no files were changed

Example:

```markdown
# Code Review Report

## Summary

...

## Findings

### 1. [High] Route accepts numeric IDs but data uses UUIDs
Files: `server.js`, `data/products.json`

...

## Suggested Fixes

...

## Testing Notes

...

## Limitations

...

_No files were changed._
```

### `documentation_draft`

Must include:

- Proposed title
- Overview
- Installation/setup
- Usage
- Project structure if known
- API/CLI examples if known
- Next documentation gaps
- Explicit statement that no files were changed

### `frontend_design_brief`

Must include:

- UI direction
- User flows
- Screens/components
- API integration points
- Suggested file structure
- Styling approach
- Accessibility considerations
- Implementation sequence
- Explicit statement that no files were changed

### `implementation_plan`

Must include:

- Goal
- Steps
- Files likely involved
- Risks
- Acceptance checks
- Explicit statement that no files were changed

### `testing_plan`

Must include:

- Test scope
- Suggested test files
- Unit tests
- Integration tests
- Edge cases
- Commands to run as suggestions only
- Explicit statement that no commands were run

### `deployment_plan`

Must include:

- Deployment target assumptions
- Config files likely involved
- Environment variables
- Build steps as suggestions only
- Risks
- Verification checklist
- Explicit statement that no files were changed and no commands were run

---

## Planner / Confirmation Integration

Currently, Snappy creates a grounded plan and waits for confirmation.

M6.7 should support confirmation leading to non-mutating output generation.

Example flow:

```text
snappy> Review my latest changes and give me MR-style feedback
...
Status: awaiting_confirmation
No changes have been applied.

snappy> yes
Generating skill output using codeguardian-review...
[structured report]
No files changed.
```

Requirements:

- The existing confirmation flow should be reused where possible.
- Non-mutating output generation should still require confirmation if the current plan is awaiting confirmation.
- Output generation must not be treated as file execution.
- After output generation, workflow state should be marked completed or output_generated.
- History should record:
  - selected skill
  - task intent
  - output kind
  - files referenced
  - snapshot id
  - mutations_applied=false

If existing confirmation handling is tightly coupled to execution, add a clean branch for `output_generation` or `report_generation`.

Do not create a brittle workaround.

---

## Skill Metadata Extension

Support optional output metadata in `SKILL.md`:

```yaml
x-snappy:
  task_intents:
    - code_review
  output_kinds:
    - code_review_report
```

Rules:

- `output_kinds` is optional.
- If present, it helps choose output shape.
- If absent, infer from task intent and selected skill.
- Unknown output kind should produce validation warning, not crash.
- Basic skills without this metadata remain valid.

Update `snappy skills validate` accordingly.

---

## Prompt Construction

The skill output prompt should include:

- user goal
- selected skill name(s)
- selected skill instructions/summary
- task intent
- project relationship
- snapshot metadata
- files considered
- relevant context excerpts
- grounded plan steps
- risks and assumptions from plan
- output kind requirements
- safety instruction:
  - do not claim files were changed
  - do not claim commands were run
  - do not invent unavailable diff data
  - distinguish observed facts from assumptions
  - cite/mention file paths where grounded

Do not dump the entire repo if context discovery already selected relevant files.

Use existing prompt caching/context caching patterns where applicable, but do not overbuild.

---

## Grounding Rules

Generated output must be grounded in available context.

The output should:

- reference only files that were considered or known from snapshot
- clearly say when exact diff data is unavailable
- avoid pretending to know hidden files/tests
- avoid claiming command results unless commands were actually run
- avoid claiming successful fixes unless mutations occurred

For CodeGuardian specifically:

If no diff is available:

```text
Limitations: I reviewed the current workspace snapshot, not a line-by-line MR diff.
```

If dirty git status is known but changed files are not available:

```text
Limitations: The project is dirty, but changed-file diff context was not available in the snapshot.
```

---

## CLI Output

When output generation begins, show concise status:

```text
Generating skill output...
Using skill: codeguardian-review
Output kind: code_review_report
```

Then show the structured report.

Avoid noisy internal details.

---

## History / Metadata

Record structured metadata for generated outputs.

Suggested metadata:

```json
{
  "event": "skill_output_generated",
  "task_intent": "code_review",
  "selected_skills": ["codeguardian-review"],
  "output_kind": "code_review_report",
  "snapshot_id": "snap_...",
  "files_referenced": ["server.js", "models/productModel.js"],
  "mutations_applied": false
}
```

Use the existing history/session mechanism.

---

## Config Integration

Respect `.snappy/snappy.yaml`.

Potential optional config:

```yaml
outputs:
  require_confirmation: true
  default_format: markdown
```

This is optional. Do not overbuild.

At minimum:

- disabled skills cannot generate output
- enabled allowlist is respected
- project extensions setting remains respected
- config cannot allow unsafe mutation

If adding `outputs` config creates too much scope, defer it.

---

## Safety Requirements

M6.7 must guarantee:

- No file writes during output generation
- No shell command execution during output generation
- No external API calls during output generation
- No GitLab/GitHub posting
- No confirmation bypass for mutations
- No pretending mutations happened
- No pretending tests were run
- No auto-continuation into implementation after report generation

If user wants to apply fixes after the report:

```text
User: apply the suggested fixes
```

That should become a new grounded plan requiring confirmation.

---

## Tests Required

Add/update tests in:

```text
tests/test_skill_outputs.py
tests/test_active_mode_v1.py
tests/test_task_router.py
tests/test_skills.py
```

### Unit tests

Cover:

1. `code_review` maps to `code_review_report`.
2. `documentation` maps to `documentation_draft`.
3. `frontend_build` maps to `frontend_design_brief`.
4. Unknown task intent maps to `general_skill_report`.
5. `x-snappy.output_kinds` is parsed.
6. Invalid `output_kinds` produces validation warning.
7. Basic skills without `output_kinds` remain valid.

### Integration tests

Cover:

1. CodeGuardian request creates grounded plan, then confirmation generates code review report.
2. Generated code review report includes:
   - summary
   - findings
   - severity labels
   - suggested fixes
   - limitations
   - no files changed statement
3. Frontend request generates frontend design brief after confirmation.
4. Documentation request generates documentation draft after confirmation.
5. Disabled skill cannot generate output.
6. Unrelated request does not generate project skill output.
7. Generated output records metadata/history.
8. After output generation, workflow state is completed/output_generated.

### Safety tests

Cover:

1. Output generation does not write files.
2. Output generation does not run shell commands.
3. Output generation does not call external APIs.
4. Output generation does not bypass mutation confirmation.
5. Output does not claim tests ran when they did not.
6. Output does not claim files were changed when they were not.

### Grounding tests

Cover:

1. Report only references known/considered files.
2. If diff is unavailable, limitations mention snapshot-only review.
3. If changed-file context is unavailable, output does not invent exact diff.
4. Missing tests/docs are phrased as observed absence only when snapshot supports it.

---

## Acceptance Criteria

M6.7 is complete when:

- Selected skills can generate structured non-mutating outputs after confirmation.
- CodeGuardian can produce an MR-style review report.
- Frontend skill can produce a frontend design brief.
- Documentation skill can produce a documentation draft.
- Output kind selection is generic and task-intent driven.
- Optional `x-snappy.output_kinds` metadata is supported and validated.
- Output generation is grounded in selected context.
- Output generation records history/metadata.
- No files are changed during output generation.
- No shell commands are run during output generation.
- No external APIs are called during output generation.
- Mutation remains a separate confirmed workflow.
- Full test suite passes.

---

## Explicit Non-Goals

Do not implement:

- file writing from skill outputs
- automatic patch generation
- automatic fix application
- shell command execution
- running tests
- GitLab API posting
- GitHub API posting
- PR/MR inline comments
- remote skill installation
- plugin runtime
- sandbox execution
- autonomous multi-step loops
- self-healing retries
- background execution

Those belong to later milestones.

---

## Suggested Implementation Order

1. Add `skill_outputs.py` with output kind mapping and schemas.
2. Add unit tests for output kind mapping.
3. Extend skill metadata parsing for `x-snappy.output_kinds`.
4. Add validation tests for output metadata.
5. Wire skill output generation into confirmation flow.
6. Build output prompt/context construction.
7. Add CodeGuardian report generation integration test.
8. Add frontend/design/doc output integration tests.
9. Add history metadata recording.
10. Add safety/grounding tests.
11. Run full verification.

---

## Verification Commands

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Expected:

- Existing tests remain green.
- New M6.7 tests pass.
- No regression in M6/M6.1/M6.5/M6.6.
- No mutation or command execution occurs during output generation.

---

## Final Note

M6.7 is the point where Snappy starts delivering useful work products from selected skills.

But keep the boundary clean:

```text
Reports are allowed.
Recommendations are allowed.
Drafts are allowed.
Plans are allowed.

Silent mutation is not allowed.
Shell execution is not allowed.
External posting is not allowed.
```


Write a summary of all changes and testing to an output file: "OUTPUT_RUN_M67.md" on this filesystem.
