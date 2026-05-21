# **M6.6 — Skill-Driven Task Routing**

## Goal

Implement skill-driven task routing so Snappy can choose the right skill for a user instruction without hardcoding skill-specific behaviour.

CodeGuardian should be used as a proof case, not as a special pathway.

The goal is not:

```text
User asks anything → run CodeGuardian
```

The goal is:

```text
User instruction
  → classify intent
  → discover matching skills
  → select best skill(s)
  → build grounded plan
  → route through existing safety/planning/confirmation layers
  → return useful result/report
```

M6.6 should make Snappy more generally capable across many skills:

- code review
- frontend design
- documentation
- testing
- Docker/deployment
- project extension
- project adaptation

No hidden ghosts. No haunted mansion pathways. No hardcoded CodeGuardian tunnels.

---

## Current Context

Snappy already has:

- M5 active planning foundation
- M6 modular skills:
-- .snappy/skills/<skill>/SKILL.md
-- skill validation
-- skill inspection
-- skill metadata

- M6.1 project relevance classification:
-- direct_project_work
-- project_extension
-- project_adaptation
-- unrelated

- M6.5 project configuration:
-- .snappy/snappy.yaml
-- enabled/disabled skills
-- planning defaults
-- safety-preserving config
-- effective config passed into planning/skills

M6.6 builds on these by adding an explicit task-routing layer.

---

## Core Principle
Skills are selected by meaning, not by hardcoded command names.

A skill may influence planning, but must not execute directly.

The routing stack should be:

```text
User request
  ↓
Project snapshot/context
  ↓
Effective config
  ↓
Available enabled skills
  ↓
Task intent classification
  ↓
Skill candidate scoring
  ↓
Best skill selection
  ↓
Project relevance/relationship classification
  ↓
Grounded plan/report generation
  ↓
Rules + confirmation + execution safety
```

Skills remain planning context only.

---

## Non-Negotiable Safety Rule

A selected skill must never:

- execute code directly
- bypass confirmation
- weaken rules
- override protected paths
- force active mode
- write files without approval
- call external services directly
- run shell commands directly

Existing safety layers remain authoritative.

---

## Required New Module

Add a module:

```python
src/snappy_putty/task_router.py
```

Suggested responsibilities:

- classify the user request into a task intent
- score enabled skills against that request
- choose the best matching skill(s)
- expose routing metadata for planner/history/CLI
- avoid routing unrelated requests into project skills

Suggested types:

```python
@dataclass
class TaskIntent:
    label: str
    confidence: float
    indicators: list[str]
    reason: str

@dataclass
class SkillRouteCandidate:
    skill_name: str
    score: float
    reasons: list[str]
    matched_terms: list[str]
    relationship_hints: list[str]

@dataclass
class SkillRouteResult:
    selected_skills: list[str]
    candidates: list[SkillRouteCandidate]
    task_intent: TaskIntent
    confidence: float
    reason: str
```

Exact names may be adjusted to match the codebase style.

---

## Supported Initial Task Intent Labels

Support these labels at minimum:

```text
code_review
frontend_build
documentation
testing
deployment
project_setup
project_extension
project_adaptation
general_project_help
unrelated
```

These are routing hints, not rigid product features.

Examples:

```text
code_review
```

User phrases:

```text
review my code
review latest changes
inspect the diff
give me PR feedback
give me MR feedback
code review
find risks in this change
```

Likely skill:

```text
codeguardian-review
```

frontend_build

User phrases:

```text
build a frontend
create a UI
make an interface
build a dashboard
create a landing page
style this page
```

Likely skill:

```text
frontend-design
```

documentation

User phrases:

```text
write docs
create README
document this API
improve docs
write usage guide
```

Likely skill:

```text
doc-coauthoring
```

testing

User phrases:

```text
write tests
add unit tests
add integration tests
test this feature
```

Likely skill:

```text
test-generation
```

deployment


User phrases:

```text
add Docker
create Dockerfile
add GitHub Actions
deployment setup
CI/CD
```

Likely skill:

```text
docker-support
deployment-helper
```


project_adaptation

User phrases:

```text
turn this into a Flask app
convert this to TypeScript
migrate this to React
make this a package
```

Likely skill depends on available enabled skills.

---

## Skill Matching Inputs

The router should score skills using:

- Skill name
- Skill description
- Skill body excerpt if already available safely
- x-snappy.indicators
- x-snappy.project_relationships
- x-snappy.extension_targets
- Effective config skill toggles
Project snapshot:
-- languages
-- package managers
-- frameworks/tools
-- source files
-- config files
-- entry points
- User request terms

The router should work even if ```x-snappy``` metadata is absent.

Do not require users to rewrite all existing skills.

---

## Optional Skill Metadata Enhancement

Support these optional fields in SKILL.md frontmatter:

```yaml
x-snappy:
  task_intents:
    - code_review
  project_relationships:
    - direct_project_work
  extension_targets:
    - javascript
    - python
  indicators:
    - code review
    - review changes
    - merge request
    - pull request
    - MR feedback
    - PR feedback
    - inspect diff
```

Rules:

- task_intents should be optional.
- If present, it strongly influences routing.
- If absent, infer from name, description, and indicators.
- Invalid task intent values should produce warnings during skill validation, not crash.
- Disabled skills must not be routed.
- Missing skills must not be routed.

---


## CodeGuardian as Proof Case, Not Special Case

Add or document a sample skill:

```text
.snappy/skills/codeguardian-review/SKILL.md
```

Example:

```markdown

---
name: codeguardian-review
description: Use this skill when the user asks to review code changes, inspect diffs, generate merge request feedback, identify risks, or produce structured PR/MR-style code review notes.
x-snappy:
  task_intents:
    - code_review
  project_relationships:
    - direct_project_work
  indicators:
    - code review
    - review changes
    - inspect diff
    - merge request
    - pull request
    - MR feedback
    - PR feedback
---


# CodeGuardian Review

Use this skill to produce structured code review feedback.

## Instructions

- Inspect the project snapshot and changed files where available.
- Identify correctness risks, security risks, missing tests, fragile logic, and maintainability concerns.
- Produce clear merge-request style review notes.
- Separate blocking issues from suggestions.
- Do not modify files directly.
- Do not execute tests or shell commands directly.
- Ask for confirmation before any mutation or external action.

```

Important:

Do not add special code like:

```python

if skill_name == "codeguardian-review":
    …
```

The router must pick it through generic scoring.

---

## Routing Behaviour Requirements

1. Explicit skill request

If the user says:

```text
Use CodeGuardian to review this repo.
```

Expected:

- route to codeguardian-review if enabled and valid
- relationship should usually be direct_project_work
- plan/report should be grounded in current project context
- no execution without confirmation

If the skill is disabled:

- do not route it
- explain that the skill is disabled by config
- suggest enabling it if appropriate

2. Implicit skill request

If the user says:

```text
Review my latest changes and give me MR-style feedback.
```

Expected:

- route to codeguardian-review if available
- task intent: code_review
- selected skill metadata included in planning/history
- generate review-oriented plan/report

3. Different skill request

If the user says:

```text
Build a frontend interface for this application.
```

Expected:

- route to frontend-design
- not codeguardian-review
- relationship likely project_extension
- plan should inspect relevant project files first

4. Documentation request

If the user says:

```text
Write README documentation for this project.
```

Expected:

- route to doc-coauthoring if available
- not codeguardian-review
- relationship likely direct_project_work or project_extension

5. Unrelated request

If the user says:

```text
Design a Batman poster.
```

Expected:

- do not route to project skills unless user explicitly connects it to the project
- unrelated/project rejection behaviour should remain intact

6. Ambiguous request

If two skills score closely:

```text
Improve this app interface and write docs for it.
```

Expected:

- either choose multiple selected skills if architecture supports it
- or choose the strongest skill and include secondary candidates in metadata
- avoid silently picking a wrong skill with high confidence
- if needed, produce a clarification instead of pretending certainty

---

## Planner Integration

Update active planner so routing happens before final planning prompt construction.

Planning metadata should include:

```json
{
  "task_intent": "code_review",
  "selected_skills": ["codeguardian-review"],
  "skill_route_confidence": 0.86,
  "skill_route_reason": "...",
  "skill_candidates": [
    {
      "skill_name": "codeguardian-review",
      "score": 0.86,
      "reasons": ["matched task_intent code_review", "matched indicator MR feedback"]
    }
  ]
}
```

Exact structure may follow current metadata style.

Planner prompt should receive:

- selected skill summaries
- only enabled/allowed skills
- routing reason
- project relationship classification
- project snapshot context

Do not dump every skill into the prompt if a small selected set is enough.

---

## CLI / History Output

When routing occurs, CLI/history should make it visible.

Example output:

```text
Matched task intent: code_review
Selected skill: codeguardian-review
Relationship: direct_project_work
```

Or concise:

```text
Using skill: codeguardian-review (code_review)
```


If no skill is selected:

```text
No matching skill selected.
```

Warnings should be understandable:

```text
Skill codeguardian-review matched the request but is disabled by config.
```

Do not spam large skill bodies in CLI output.

---

## Project Snapshot / Changed Files

For code review routing, Snappy should prefer changed-file/diff context if already available through existing project inspection/history mechanisms.

Do not implement full GitLab or GitHub integration in M6.6.

Acceptable local behaviour:

- inspect project snapshot
- identify dirty git status if current inspector exposes it
- prefer changed files if available
- otherwise review the project structure and ask for diff/context if needed
- generate a review plan/report without external posting

Do not add shell execution unless it already exists safely through approved pathways.

---

## Config Integration

Respect M6.5 config:

```yaml
skills:
  enabled:
    - codeguardian-review
  disabled:
    - frontend-design
```

Rules:

- Only enabled/allowed skills may be routed.
- Disabled skills must not be selected.
- If enabled allowlist is non-empty, skills outside the list are unavailable.
- Config can disable project extensions, which should influence relationship classification.
- Config cannot force unsafe execution.

---

## Validation Updates
Update snappy skills validate to validate optional M6.6 metadata:

```yaml
x-snappy:
  task_intents:
    - code_review
```

Validation should warn for:

- unknown task intent
- non-list task_intents
- unknown relationship values
- invalid indicator types
- invalid extension target types

Do not hard-fail valid basic skills that omit x-snappy.

---

## Tests Required

Add tests, likely in:

```text
tests/test_task_router.py
tests/test_active_mode_v1.py
tests/test_skills.py
tests/test_config.py
```

### Router unit tests

Cover:

- Code review request routes to codeguardian-review.
- Frontend request routes to frontend-design, not CodeGuardian.
- Documentation request routes to doc-coauthoring, not CodeGuardian.
- Docker/deployment request routes to deployment skill if present.
- Unknown/unrelated request selects no project skill.
- Explicit skill name request routes to that skill if enabled.
- Disabled skill is not selected.
- Enabled allowlist blocks skills outside the allowlist.
- x-snappy.task_intents boosts correct skill.
- Description-only skills still work without x-snappy.

### Integration tests

Cover:

- In active planning, “Review my latest changes and give me MR-style feedback” selects CodeGuardian.
- In active planning, “Build a frontend interface for this application” selects frontend-design.
- Project relevance remains unrelated for poster-style requests not tied to the project.
- Skill routing metadata appears in plan/history.
- Selected skill context appears in planner prompt context.
- Disabled skill does not appear in planner prompt context.
- Ambiguous request either selects multiple skills or records candidate ambiguity safely.
- No mutation occurs without confirmation.

### Validation tests

Cover:

- Valid task_intents accepted.
- Unknown task_intents warning.
- Non-list task_intents warning.
- Basic skill without x-snappy remains valid.


### Safety tests

Cover:

- Selected skill cannot bypass confirmation.
- Selected skill cannot execute directly.
- Selected skill cannot force active mode.
- Selected skill cannot override protected paths.
- CodeGuardian routing does not call GitLab/GitHub APIs.

---

## Acceptance Criteria

M6.6 is complete when:

- task_router.py or equivalent exists.
- User instructions are classified into task intents.
- Enabled skills are scored against user request and project context.
- Best matching skill(s) are selected generically.
- CodeGuardian is selected for code review/MR/PR feedback requests without hardcoding.
- Frontend requests select frontend skill, not CodeGuardian.
- Documentation requests select documentation skill, not CodeGuardian.
- Disabled skills are never selected.
- Enabled allowlist is respected.
- Routing metadata is available in active planning/history.
- Planner receives only selected/allowed skill context.
- Unrelated requests remain unrelated.
- Ambiguous routing is handled safely.
- Full test suite passes.
- No safety bypass is introduced.

---

## Explicit Non-Goals

Do not implement:

- GitLab API integration
- GitHub API integration
- posting MR/PR comments
- remote skill installation
- skill marketplace
- plugin runtime
- sandbox execution
- formal tool abstraction
- autonomous multi-step agent loops
- test command execution
- shell command execution
- hidden CodeGuardian special cases

These belong later.

---

## Suggested Implementation Order

- Add task_router.py with task intent labels and scoring.
- Add unit tests for routing against mock skills.
- Extend skill metadata parsing for x-snappy.task_intents.
- Update skill validation warnings for M6.6 metadata.
- Wire router into active planner before prompt construction.
- Add routing metadata to planner/history output.
- Ensure config skill toggles are respected.
- Add integration tests for CodeGuardian, frontend, docs, unrelated, disabled skill.
- Add safety regression tests.
- Run full verification.

---


## Verification Commands

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Expected:

- Existing M6/M6.1/M6.5 behaviour remains green.
- New M6.6 routing tests pass.
- No skill bypasses confirmation.
- No hardcoded CodeGuardian execution path exists.

---

## Final Note

M6.6 is not a CodeGuardian milestone.

M6.6 is the milestone where Snappy learns to choose the right skill for the job.

CodeGuardian is only the first serious proof that the routing architecture works.

The desired future behaviour:

```text
User: Review my latest changes and give me MR-style feedback.
Snappy: Uses codeguardian-review.

User: Build a frontend interface for this app.
Snappy: Uses frontend-design.

User: Write docs for this package.
Snappy: Uses doc-coauthoring.

User: Design a Batman poster.
Snappy: Does not pretend this belongs to the repo.
```

Build the general router. Let CodeGuardian be just one creature in the zoo.
