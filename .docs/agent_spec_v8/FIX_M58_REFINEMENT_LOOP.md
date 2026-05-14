# Snappy M5.8.x Final Polish — Refinement Loop + LLM Plan Rationale

## Goal

Fix two remaining M5 polish issues before locking M5:

1. Refinement prompt exits too early after rejected input.
2. `why this plan` is too similar to `show plan` and should provide real rationale.

---

## Change 1 — Refinement Loop Consistency

### Problem

Current behavior:

```text
snappy> refine step 2
refinement> help me build a starship
That looks like a new request, not a refinement instruction.
The current plan was not changed.
snappy>
```

After rejection, Snappy exits refinement mode.

Then this valid refinement:

```text
focus only on task validation and bad input handling
```

is treated as a normal command and fails.

### Required Behavior

After rejecting invalid refinement input, stay in refinement mode.

Expected:

```text
refinement> help me build a starship

That looks like a new request, not a refinement instruction.

Refinement should modify the current step.
Examples:
- focus on validation
- split this into two steps
- reduce scope to storage only

The current plan was not changed.

refinement>
```

The user should remain in refinement mode until:

- valid refinement is accepted
- user types `cancel`
- user types `exit`
- user types `back`

### Required Rules

- Rejected refinement must not modify the plan.
- Rejected refinement must not become `last_failed_goal`.
- Rejected refinement may be recorded as `last_rejected_refinement` or only logged in history.
- Valid refinement should exit refinement mode after success.
- `cancel`, `exit`, or `back` inside refinement mode should return to the normal REPL without cancelling the whole active workflow unless explicitly using the normal top-level `cancel`.

---

## Change 2 — LLM-Backed `why this plan`

### Problem

`show plan` and `why this plan` currently produce very similar output.

### Required Behavior

Keep both commands, but make their roles distinct:

```text
show plan
```

Answers:

```text
What is the plan?
```

It should display:

- goal
- steps
- files
- risks
- assumptions
- status

```text
why this plan
```

Answers:

```text
Why did Snappy choose this plan?
```

It should explain:

- why these files were selected
- why the steps are ordered this way
- what trade-offs were made
- why broader/riskier alternatives were avoided
- what project evidence influenced the plan
- what uncertainty remains

### LLM Usage

When agent mode is `active` and LLM is available:

- route `why this plan` to the LLM
- pass only:
  - stored plan
  - selected files
  - snapshot summary
  - user goal
  - assumptions/risks
- do not regenerate the plan
- do not refine the plan
- do not mutate session state
- do not create a new plan
- do not execute anything

### If LLM unavailable

Return:

```text
LLM-backed plan rationale is unavailable.

I can show the stored plan metadata, but I can’t provide a deeper rationale right now.
```

Then optionally show the existing lightweight metadata explanation.

---

## State/Mutation Guardrails

`why this plan` must be read-only.

It must not change:

- active_goal
- current_plan
- last_plan
- plan status
- workflow state
- snapshot
- pending goal
- run state

It may append a history event:

```text
Event: Plan rationale requested
Mode: llm_assisted | metadata_fallback
```

---

## Tests Required

### Refinement loop tests

1. Invalid refinement stays inside refinement mode.
2. Valid refinement after a rejected refinement succeeds.
3. Rejected refinement does not update plan.
4. Rejected refinement does not set `last_failed_goal`.
5. `back`/`exit` leaves refinement mode but preserves active workflow.

### Why-this-plan tests

6. `show plan` remains structural.
7. `why this plan` uses LLM when active mode + LLM available.
8. `why this plan` does not mutate plan/session state.
9. `why this plan` falls back honestly when LLM unavailable.
10. `why this plan` output is not just a duplicate of `show plan`.

---

## Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Manual REPL:

```text
agent mode active
help me improve this CLI
show plan
why this plan
refine step 2
help me build a starship
focus only on task validation and bad input handling
show plan
status
```

Expected:

- invalid refinement rejected and remains in refinement prompt
- valid follow-up refinement succeeds
- `why this plan` provides actual rationale, not a duplicate plan display
- no state corruption
- full test suite passes
