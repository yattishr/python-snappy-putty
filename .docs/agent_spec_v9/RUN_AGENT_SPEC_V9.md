# Codex Implementation Prompt: Snappy M6 — Modular Skill System with Safe Execution Integration

## Context
You are working in the **Snappy PuTTy** repository.

Snappy is a supervised agentic CLI. It is intentionally safety-first. Its architecture already includes routing, rules, confirmation, workflow memory, active planning, bounded context discovery, and supervised execution behavior.

We are now implementing **M6: Modular Skill System with Safe Execution Integration**.

This milestone must align with the emerging **Agent Skills / Claude Skills** convention:

- A skill is a folder.
- Each skill folder contains a `SKILL.md` file.
- `SKILL.md` uses YAML frontmatter.
- Required metadata fields are:
  - `name`
  - `description`
- The markdown body contains instructions, workflows, references, and guidance.
- Additional files may exist beside `SKILL.md` for progressive disclosure, examples, references, or helper scripts.

However, Snappy must **not** blindly execute skill instructions or scripts. Snappy’s core rule remains:

> Skills inform planning. Skills do not execute directly.

Every skill-influenced operation must still pass through Snappy’s existing control layer:

```text
intent → skill discovery → skill match → plan → rules → confirmation → executor → verification/logging
```

Do not weaken safety, rule priority, confirmation, active-mode controls, context discovery, or workflow memory.

---

## Milestone Goal
Implement a standards-aligned skill system that lets Snappy discover, inspect, validate, and use local skills as planning context, while preserving Snappy’s supervised execution model.

This milestone should make it possible to place skills in:

```text
.snappy/skills/<skill-name>/SKILL.md
```

Example:

```text
.snappy/
  skills/
    git-commit-helper/
      SKILL.md
      examples.md
      reference.md
      scripts/
        validate_diff.py
```

Snappy should be able to:

1. Discover skills.
2. Validate skill structure.
3. List available skills.
4. Inspect a specific skill.
5. Match user intent to relevant skills.
6. Inject matched skill guidance into the planner/context bundle.
7. Preserve rule and confirmation enforcement.
8. Prevent direct execution of bundled scripts.
9. Persist skill-selection metadata in plan/session output where appropriate.

---

## Non-Negotiable Safety Rules

### 1. Skills are untrusted input
Treat every local skill as user-provided content. Never treat skill text as trusted executable authority.

### 2. Skills cannot bypass rules
A skill must not override or weaken existing Snappy rules, rule priority, deny rules, confirmation requirements, or active-mode controls.

### 3. Skills cannot execute directly
A skill may contain scripts, but the skill loader must never run them. Scripts may only be surfaced as resources or later routed through approved tool contracts in future milestones.

### 4. Skills inform planning only
The skill body may be used as contextual guidance for the planner. The final plan must still be produced and executed through Snappy’s normal supervised flow.

### 5. No remote installation in M6
Do not implement `snappy install <skill-pack>` yet. That belongs to a later milestone.

### 6. No autonomous skill chaining
Do not add unbounded loops or automatic multi-skill chaining. If multiple skills match, rank them and expose the match. Keep behavior bounded.

### 7. No M8 plugin system yet
Do not build a marketplace, version resolver, sandbox, package manager, trust registry, or remote dependency system.

---

## Desired File/Module Design

Prefer small, focused modules. Suggested implementation shape:

```text
src/snappy_putty/
  skills.py
  skill_registry.py          # optional if you prefer separation
  skill_matcher.py           # optional if you prefer separation
```

A compact single `skills.py` module is acceptable if it remains clean and testable.

Suggested core data types:

```python
@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
    frontmatter: dict[str, Any]
    snappy: dict[str, Any]

@dataclass(frozen=True)
class Skill:
    metadata: SkillMetadata
    body: str
    files: list[Path]
    scripts: list[Path]

@dataclass(frozen=True)
class SkillValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    message: str
    path: Path | None = None

@dataclass(frozen=True)
class SkillMatch:
    skill: Skill
    score: float
    reasons: list[str]
```

You may adjust names and shapes to match existing repo style.

---

## Skill Format

### Minimum valid skill

```markdown
---
name: git-commit-helper
description: Helps generate clear git commit messages from staged changes and git diffs. Use when the user asks to write, improve, or explain a commit message.
---

# Git Commit Helper

Use this skill when the user wants help creating a commit message from local repository changes.

## Workflow

1. Inspect the diff.
2. Identify the dominant change type.
3. Draft a concise commit message.
4. Ask for confirmation before committing.
```

### Optional Snappy metadata

Support an optional `x-snappy` frontmatter block:

```yaml
---
name: git-commit-helper
description: Helps generate clear git commit messages from staged changes and git diffs. Use when the user asks to write, improve, or explain a commit message.
x-snappy:
  risk: low
  tools:
    - git.diff
    - git.status
  requires_confirmation: false
  tags:
    - git
    - commit
---
```

Rules:

- `x-snappy` is optional.
- Unknown frontmatter fields should not fail validation.
- Unknown `x-snappy` keys should warn, not fail.
- Invalid required fields should fail validation.
- `name` should be kebab-case or at least stable CLI-friendly text.
- `description` should be non-empty and must explain when to use the skill.

---

## Progressive Disclosure

Skills may include extra files:

```text
reference.md
examples.md
templates/*.md
scripts/*.py
```

For M6:

- Discover these files.
- Show them in `inspect` output.
- Do not automatically load all files into planner context.
- Load only `SKILL.md` by default.
- Optionally include names/paths of adjacent files as available references.
- Do not execute scripts.

This keeps context bounded and prevents token bloat.

---

## CLI Requirements

Add skill-related commands to the CLI. Match existing CLI style and Rich formatting if present.

### `snappy skills`

Lists discovered skills.

Expected behavior:

- Search default project path: `.snappy/skills/`
- If no skills exist, show a friendly empty state.
- Display:
  - name
  - short description
  - path
  - validation status
  - optional risk if present

Example output:

```text
Available Skills

name                risk    status   description
git-commit-helper   low     valid    Helps generate clear git commit messages...
code-reviewer       medium  valid    Helps review code changes...
```

### `snappy skills inspect <name>`

Shows detailed skill info.

Expected behavior:

- Find skill by `name`.
- Display:
  - name
  - path
  - description
  - frontmatter
  - optional `x-snappy` metadata
  - body preview or full body depending existing output conventions
  - adjacent files
  - scripts listed as non-executable resources

Do not run scripts.

### `snappy skills validate [path]`

Validates one skill or all skills.

Expected behavior:

- If `path` points to a skill folder, validate that folder.
- If no path is provided, validate `.snappy/skills/`.
- Report warnings and errors.
- Exit non-zero only when validation errors exist, if the existing CLI style supports exit codes.

Validation should catch:

- missing `SKILL.md`
- malformed YAML frontmatter
- missing `name`
- missing `description`
- empty body warning
- duplicate skill names
- scripts present warning: “scripts are listed but not executable by the skill loader”

---

## Planner / Active Mode Integration

Add skill-aware planning without breaking existing planning behavior.

### Required behavior

When the user asks for a task:

1. Discover available skills.
2. Match user intent against skill `name`, `description`, and optionally body headings.
3. Select at most a small bounded number of skills, preferably top 1 to 3.
4. Inject selected skill summaries into the planner/context bundle.
5. Persist skill-selection metadata in the plan result where appropriate.
6. Ensure all actions still go through existing rules and confirmation.

Suggested metadata:

```json
{
  "skill_selection": {
    "enabled": true,
    "matched": [
      {
        "name": "git-commit-helper",
        "score": 0.86,
        "reasons": [
          "description matched: commit message",
          "name matched: git"
        ],
        "path": ".snappy/skills/git-commit-helper/SKILL.md"
      }
    ]
  }
}
```

If no skills match, planning should continue normally.

### Do not do this

Do not let a skill call tools directly.
Do not let a skill decide confirmation policy.
Do not let a skill override risk classification.
Do not let a skill mutate the plan after confirmation.

---

## Matching Algorithm

Keep M6 simple and deterministic.

Implement a lightweight matcher using keyword overlap and phrase matching.

Inputs:

- user goal / prompt
- active plan goal if available
- skill name
- skill description
- selected headings from skill body, if easy

Output:

- ranked `SkillMatch` list
- score
- reasons

No embeddings required.
No external API calls.
No network dependency.

Suggested scoring:

- exact phrase match in description: strong boost
- keyword overlap with description: medium boost
- keyword overlap with name: medium boost
- keyword overlap with headings: small boost
- ignore common stopwords

The matcher must be deterministic and easy to test.

---

## Project Configuration

For M6, keep configuration minimal.

Default skill path:

```text
.snappy/skills/
```

Optional future config can live in M6.5. Do not overbuild configuration now.

If existing project config already exists, add a small optional setting only if it naturally fits:

```yaml
skills:
  enabled: true
  path: .snappy/skills
```

But do not create a full agent configuration layer unless it already exists. That belongs to M6.5.

---

## Tests Required

Add regression tests. Prefer test files like:

```text
tests/test_skills.py
tests/test_skill_registry.py
tests/test_skill_matching.py
tests/test_cli_skills.py
```

Match existing test style.

### Unit tests

Test validation:

- valid skill loads successfully
- missing `SKILL.md` fails
- malformed frontmatter fails
- missing `name` fails
- missing `description` fails
- duplicate names are detected
- optional `x-snappy` metadata is preserved
- unknown fields do not fail validation
- scripts are listed but not executed

Test discovery:

- discovers skills under `.snappy/skills`
- ignores non-directories or invalid folders gracefully
- deterministic ordering by name

Test matching:

- matching skill selected for relevant prompt
- irrelevant skill not selected
- top results are bounded
- reasons are included
- deterministic ranking

### CLI tests

Test:

- `snappy skills` with no skills
- `snappy skills` with one or more skills
- `snappy skills inspect <name>`
- `snappy skills inspect <missing>`
- `snappy skills validate`
- `snappy skills validate <path>`

### Planner integration tests

Test:

- matching skill metadata appears in plan/context metadata
- no match does not break planning
- skill instructions do not bypass confirmation
- existing active/passive/off mode behavior remains unchanged

---

## Manual Smoke Checklist

After implementation, run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Create a temporary test project:

```bash
mkdir -p .snappy/skills/git-commit-helper
cat > .snappy/skills/git-commit-helper/SKILL.md <<'SKILL'
---
name: git-commit-helper
description: Helps generate clear git commit messages from staged changes and git diffs. Use when the user asks to write, improve, or explain a commit message.
x-snappy:
  risk: low
  tools:
    - git.diff
    - git.status
  requires_confirmation: false
---

# Git Commit Helper

Use this skill when the user wants help creating or improving a git commit message.

## Workflow

1. Inspect the diff.
2. Identify the dominant change type.
3. Draft a concise commit message.
4. Ask for confirmation before committing.
SKILL
```

Then run:

```bash
snappy skills
snappy skills inspect git-commit-helper
snappy skills validate
```

Then test a skill-relevant planning prompt:

```bash
snappy "help me write a commit message for my staged changes"
```

Expected:

- skill is discovered
- planner metadata mentions `git-commit-helper`
- no direct script execution occurs
- normal confirmation/rule behavior remains intact

---

## Acceptance Criteria

M6 is complete when:

1. Skills can be discovered from `.snappy/skills/<name>/SKILL.md`.
2. `SKILL.md` supports Claude/Agent Skills-compatible frontmatter with required `name` and `description`.
3. Optional `x-snappy` metadata is parsed and preserved.
4. `snappy skills` lists available skills.
5. `snappy skills inspect <name>` shows detailed skill information.
6. `snappy skills validate [path]` validates skills and reports issues.
7. Skill matching is deterministic and tested.
8. Matched skills can influence planning context.
9. Skill-selection metadata is visible/persisted where plan metadata is already shown.
10. Skills cannot execute scripts directly.
11. Skills cannot bypass rules or confirmations.
12. Existing M1-M5 behavior remains green.
13. All tests pass.

---

## Out of Scope

Do not implement:

- remote skill installation
- marketplace
- package manager
- trust registry
- semantic embeddings
- MCP integration
- tool contract redesign
- sandbox execution
- autonomous skill chaining
- remote GitHub skill packs
- full `.snappy/snappy.yaml` agent config layer unless a minimal existing config hook already exists

Those belong to later milestones.

---

## Suggested Implementation Order

1. Add skill data models and parser.
2. Add frontmatter parsing and validation.
3. Add skill discovery from `.snappy/skills`.
4. Add deterministic matcher.
5. Add CLI commands: list, inspect, validate.
6. Integrate matched skill summaries into active planner/context selection.
7. Add plan/session metadata for skill selection.
8. Add regression tests.
9. Run full test suite.
10. Update README or developer notes with a short M6 usage example.

---

## Important Design Note

Snappy’s differentiator is not that it can load skills.

Many agents will do that.

Snappy’s differentiator is that it can load skills **without surrendering control**.

The skill system should make Snappy more capable, not less governable.
