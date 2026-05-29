# Snappy M6.8 Codex Implementation Spec

## Milestone

**M6.8 — UX & Workflow Polish**

## Goal

Polish Snappy’s user experience now that the M6.x architecture is working:

- skill routing
- project relevance
- config
- structured skill outputs
- confirmation separation
- safe non-mutating report generation

This milestone should make Snappy feel clearer, smoother, and more intentional without changing its core architecture.

M6.8 is UX-only.

Do **not** add new autonomy.
Do **not** add new execution intelligence.
Do **not** add plugin/runtime features.
Do **not** change safety semantics.

---

## Core Principle

The user should always understand:

```text
What Snappy detected
What Snappy selected
What Snappy is about to do
Whether files will change
What happens after confirmation
```

The UX should feel like a competent supervised assistant, not a log stream wearing a trench coat.

---

## Current Context

Snappy currently supports:

- Project inspection and snapshots
- Active planning
- Skills
- Skill validation
- Skill-driven routing
- Project relevance classification
- Config-driven skill enablement
- Structured skill output generation
- Separate output-generation and filesystem-apply confirmation paths
- Non-mutating reports/artifacts after confirmation

Recent UX issues:

- Confirmation prompts are technically correct but too mechanical.
- Some output is redundant, for example:
  - `Selected skill: codeguardian-review`
  - `Matched skill: codeguardian-review`
- Reports are useful but can be rendered more professionally.
- Disabled-skill fallback needs clearer UX.
- YES/NO typing is friction-heavy.
- Debug/internal details should not dominate normal output.

---

## UX-1: Task-Aware Confirmation Prompts

Replace generic confirmation prompts with task-aware prompts.

### Current examples

```text
Status: awaiting_confirmation
confirm [YES/NO]>
```

```text
Type YES to generate the non-mutating skill output, or NO to cancel.
generate [YES/NO]>
```

### Desired examples

#### Code review report

```text
Ready to generate a CodeGuardian review report.

No files will be changed.

Continue?
> YES
  NO
```

#### Frontend design brief

```text
Ready to create a frontend design brief.

No files will be changed.

Continue?
> YES
  NO
```

#### Documentation draft

```text
Ready to generate documentation.

No files will be changed.

Continue?
> YES
  NO
```

#### Generic non-mutating output

```text
Ready to generate a structured report.

No files will be changed.

Continue?
> YES
  NO
```

#### Filesystem mutation

```text
Ready to apply changes to:

- src/app.py
- README.md

Files may be modified.

Continue?
> YES
  NO
```

### Requirements

- Use task intent, selected skill, and output kind to build prompt text.
- Clearly distinguish:
  - non-mutating output generation
  - filesystem mutation
  - generic fallback planning
- Always state whether files will be changed.
- Preserve typed YES/NO support.

---

## UX-2: Arrow-Key Selection for Choices

Add arrow-key selection for simple interactive choices.

Supported choice sets:

```text
YES / NO
YES / NO / CANCEL
CONTINUE / CANCEL
```

### Desired interaction

```text
Continue?

> YES
  NO
```

Arrow Down:

```text
Continue?

  YES
> NO
```

Enter confirms the selected option.

### Requirements

Add a reusable prompt helper, for example:

```python
prompt_choice(
    message: str,
    options: list[str],
    default: str | None = None,
    allow_typed: bool = True,
) -> str
```

The exact API may match project style.

### Required behavior

- Arrow Up/Down changes selected option.
- Enter confirms.
- Typed values still work:
  - `YES`
  - `NO`
  - `CANCEL`
  - lowercase variants should work too.
- Non-interactive environments must fall back gracefully to typed prompts.
- Tests must not hang in CI.
- Existing tests that send `YES`/`NO` should still pass.

### Constraints

- Do not add a heavy TUI framework.
- Avoid large dependencies.
- Prefer lightweight terminal handling.
- If robust arrow-key support is risky, implement a graceful helper that uses arrow selection only when TTY support is available and falls back otherwise.

---

## UX-3: Routing Transparency

Make routing output understandable without exposing raw internals by default.

### Current

```text
Matched task intent: code_review
Selected skill: codeguardian-review
Matched skill: codeguardian-review
```

### Desired

```text
Code review detected
Using: codeguardian-review
Reason: matched code review and MR feedback indicators
```

### For frontend

```text
Frontend build detected
Using: frontend-design
Reason: matched frontend and UI indicators
```

### For docs

```text
Documentation task detected
Using: doc-coauthoring
Reason: matched documentation and README indicators
```

### Requirements

- Avoid duplicate selected/matched skill messages.
- Show:
  - task intent label in friendly form
  - selected skill if any
  - short reason if available
- Hide raw scores in normal mode.
- Keep raw scores in debug/trace mode.

### Debug mode

If trace/debug is enabled, allow richer output:

```text
Task intent: code_review
Selected skill: codeguardian-review
Score: 1.51
Candidates:
- codeguardian-review: 1.51
- doc-coauthoring: 0.22
```

Normal mode should remain concise.

---

## UX-4: Disabled Skill Messaging

Integrate the M6.6.1 disabled skill fallback guard into polished UX.

### Desired output

```text
Code review detected.

Best matching skill is disabled:
codeguardian-review

No specialized skill will be used.

Continue with generic review planning?
> YES
  NO
```

### Requirements

- Do not silently continue when best matching skill is disabled.
- If user chooses YES:
  - continue with generic plan
  - clearly say:
    ```text
    Continuing without disabled skill: codeguardian-review
    ```
- If user chooses NO:
  - cancel cleanly
  - do not generate plan/output
  - do not mutate files
- Use arrow-key selector where supported.
- Preserve typed YES/NO fallback.

---

## UX-5: Report Rendering Polish

Improve readability of structured skill outputs.

### Desired report header

```text
══════════════════════════════════════
CodeGuardian Review Report
══════════════════════════════════════
```

or a Rich panel/table style if the project already uses Rich consistently.

### Requirements

Reports should have:

- clear title
- clean section headings
- consistent spacing
- consistent severity rendering
- explicit no-mutation statement
- no excessive decoration

Apply to:

- `code_review_report`
- `documentation_draft`
- `frontend_design_brief`
- `implementation_plan`
- `testing_plan`
- `deployment_plan`
- `general_skill_report`

### Code review report should render clearly

Sections:

```text
Summary
Findings
Suggested Fixes
Testing Notes
Limitations
No files were changed.
```

### Frontend design brief should render clearly

Sections:

```text
UI Direction
Screens / Components
API Integration Points
Suggested File Structure
Accessibility Notes
Implementation Sequence
No files were changed.
```

### Documentation draft should render clearly

Sections:

```text
Overview
Setup
Usage
Project Structure
Examples
Documentation Gaps
No files were changed.
```

---

## UX-6: Workflow Completion Summaries

When a workflow completes, show a short completion summary with next actions.

### Code review completion

```text
Review report generated successfully.

Suggested next actions:

1. Apply suggested fixes
2. Generate an implementation plan
3. Review another area
```

### Frontend brief completion

```text
Frontend design brief generated successfully.

Suggested next actions:

1. Generate an implementation plan
2. Apply design changes
3. Review API integration
```

### Documentation completion

```text
Documentation draft generated successfully.

Suggested next actions:

1. Save this draft to a file
2. Expand setup instructions
3. Review examples
```

### Requirements

- Max 3 suggestions.
- Suggestions should be contextual.
- Do not imply actions were taken.
- Do not auto-continue.
- Keep suggestions short.

---

## UX-7: Reduce Duplicate / Noisy Messages

Review normal CLI output and remove repeated messages.

### Remove or consolidate patterns like

```text
Selected skill: codeguardian-review
Matched skill: codeguardian-review
```

Use:

```text
Using: codeguardian-review
```

### Also reduce noise around

```text
Matched skills:
- codeguardian-review (score=1.51)
```

In normal mode, prefer:

```text
Using: codeguardian-review
```

In trace/debug mode, scores may remain visible.

### Requirements

- Normal output should be concise.
- Debug output should keep useful diagnostics.
- Existing metadata/history can keep detailed fields.

---

## UX-8: Consistent Status Messaging

Standardize common status messages.

Use consistent wording:

```text
Inspecting project...
Routing request...
Creating grounded plan...
Awaiting confirmation...
Generating report...
Applying changes...
Complete.
```

Avoid multiple variants for the same state.

### Requirements

- Do not remove useful progress messages entirely.
- Keep long-running operations visible.
- Avoid internal jargon in normal mode.

---

## UX-9: Confirmation Path Clarity

Snappy now has different confirmation paths:

1. non-mutating output generation
2. filesystem apply
3. generic fallback after disabled skill
4. cancel

Make the prompt text specific for each path.

### Non-mutating output

```text
No files will be changed.
```

### Filesystem apply

```text
Files may be modified.
```

### Generic fallback

```text
No specialized skill will be used.
```

### Cancel

```text
Cancelled. No changes were made.
```

---

## UX-10: Config-Aware Skill UX

When skills are disabled or not enabled, explain it clearly.

Examples:

```text
No skills are enabled in .snappy/snappy.yaml.
Run `snappy init` to detect and enable local skills.
```

```text
Skill exists but is disabled by config: codeguardian-review
Enable it in .snappy/snappy.yaml to use specialized CodeGuardian review.
```

```text
No specialized skill found for this request.
Continuing with generic grounded planning.
```

Important distinction:

```text
missing skill = generic fallback allowed
disabled skill = ask before fallback
```

---

## UX-11: Non-Interactive Safety

Ensure new UX does not break CI, scripting, or test automation.

Requirements:

- If stdin is not a TTY, use typed prompt mode.
- Existing input patterns like `YES\n` and `NO\n` must still work.
- Arrow selector must not run in non-interactive test contexts unless explicitly tested.
- Provide a small abstraction so tests can inject choices.

---

## Suggested Implementation Areas

Likely files:

```text
src/snappy_putty/cli.py
src/snappy_putty/session.py
src/snappy_putty/skill_outputs.py
src/snappy_putty/task_router.py
src/snappy_putty/config.py
```

Suggested new or refactored module:

```text
src/snappy_putty/prompts.py
```

Possible helpers:

```python
prompt_choice(...)
render_confirmation_prompt(...)
render_routing_summary(...)
render_completion_summary(...)
```

Keep helpers small.

Do not create a large UI framework.

---

## Tests Required

Add or update tests in:

```text
tests/test_cli.py
tests/test_active_mode_v1.py
tests/test_skill_outputs.py
tests/test_task_router.py
tests/test_config.py
```

### Confirmation tests

Cover:

1. Code review confirmation says report will be generated.
2. Non-mutating output confirmation says no files will be changed.
3. Filesystem apply confirmation says files may be modified.
4. Typed YES still works.
5. Typed NO still works.
6. CANCEL works where available.

### Arrow-key selection tests

Cover:

1. Default option selected.
2. Arrow Down changes selection.
3. Arrow Up changes selection.
4. Enter confirms selected option.
5. Non-interactive fallback works.
6. Tests do not hang.

If terminal arrow-key testing is difficult, isolate the selection state machine and unit-test it separately.

### Routing output tests

Cover:

1. Enabled CodeGuardian request shows concise routing summary.
2. Frontend request shows frontend routing summary.
3. Raw scores hidden in normal mode.
4. Raw scores visible in trace/debug mode if supported.
5. Duplicate selected/matched messages removed.

### Disabled skill UX tests

Cover:

1. Disabled best-match skill shows clear warning.
2. Prompt asks whether to continue generically.
3. YES continues with generic planning.
4. NO cancels cleanly.
5. Disabled skill is not selected.

### Report rendering tests

Cover:

1. Code review report has polished title/header.
2. Report includes no-files-changed statement.
3. Documentation draft renders clean sections.
4. Frontend brief renders clean sections.
5. No excessive duplicate output.

### Completion summary tests

Cover:

1. Review report completion suggests relevant next actions.
2. Frontend brief completion suggests relevant next actions.
3. Documentation draft completion suggests relevant next actions.
4. Max 3 suggestions.
5. Does not imply actions were executed.

### Regression tests

Cover:

1. Existing REPL confirmation flow still works.
2. Existing skill routing still works.
3. Existing non-mutating output generation still works.
4. Existing filesystem apply confirmation still works.
5. Existing tests using typed input still pass.

---

## Acceptance Criteria

M6.8 is complete when:

- Confirmation prompts are task-aware.
- Arrow-key selection works where terminal supports it.
- Typed YES/NO remains supported.
- Non-interactive fallback is safe.
- Routing output is concise and understandable.
- Disabled skill fallback UX is explicit.
- Reports render cleanly.
- Workflow completion summaries are shown.
- Duplicate skill messages are removed.
- Debug/trace output still exposes details.
- Existing behavior is preserved.
- Full test suite passes.

---

## Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
git diff --check
```

Manual smoke tests:

```text
1. Review my latest changes and give me MR-style feedback
2. YES
3. Build a frontend interface for this application
4. YES
5. Disable codeguardian-review and repeat review request
6. Choose YES generic fallback
7. Repeat and choose NO
```

Expected:

- prompts are clear
- arrow keys work in interactive terminal
- typed YES/NO works
- no files changed during report generation
- disabled skill fallback is explicit

---

## Non-Goals

Do not implement:

- M7 execution intelligence
- bounded retry loops
- autonomous continuation
- plugin system
- skill marketplace
- file mutation from reports
- shell command execution
- external API posting
- GitHub/GitLab integration
- background execution
- GUI app
- large TUI framework

This is polish, not power creep.

---

## Final Note

M6.8 should make Snappy feel calmer, clearer, and more deliberate.

The system already has the right bones.

This milestone gives it a better voice, cleaner posture, and fewer haunted hallway noises.
