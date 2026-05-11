# Snappy M5.7.x — Refinement Prompt UX + Input Guard

## Goal

Make `refine step N` clear to the user and prevent unrelated/new-goal input from being accepted as a refinement.

---

## Problem

Current behavior:

```text
snappy> refine step 2
refinement>
```

The prompt appears without explanation. Users may not know what to enter.

Also, unrelated input can be accepted:

```text
refinement> help me build a starship
Plan refined: step 2 refined.
```

This must not happen.

---

## Required UX Change

When user runs:

```text
refine step 2
```

Display:

```text
Refining step 2.

Describe how you want this step adjusted.
The refinement should stay related to the current goal.

Examples:
- focus more on validation
- split this into two smaller steps
- reduce scope to storage only
- include edge-case testing

refinement>
```

If refinement is provided inline:

```text
refine step 2 focus more on validation
```

Do not show the prompt. Process the inline refinement directly.

---

## Required Input Guard

Before applying refinement, classify the refinement input:

```text
valid_refinement
new_goal_attempt
unrelated_request
```

Reject `new_goal_attempt` and `unrelated_request`.

Examples to reject:

```text
help me build a starship
what is bitcoin price?
write me a poem
plan my holiday
```

Expected response:

```text
That looks like a new request, not a refinement instruction.

Refinement should modify the current step.
Examples:
- focus on validation
- split this into two steps
- reduce scope to storage only

The current plan was not changed.
```

---

## Refinement Flow

Correct flow:

```text
refine step N
→ collect user refinement instruction
→ classify instruction
→ reject if unrelated/new goal
→ use LLM to rewrite/refine that step if available
→ validate refined step/plan
→ persist only if safe
```

The LLM must not invent a refinement without user instruction.

---

## Tests

Add tests for:

1. `refine step N` shows explanatory refinement prompt.
2. Inline refinement still works.
3. `help me build a starship` inside refinement prompt is rejected.
4. Rejected refinement leaves plan unchanged.
5. Valid refinement still updates plan.
6. History logs rejected refinement.

---

## Non-Negotiable

A refinement prompt is not a new goal prompt.

Refinement must stay scoped to the current plan/step.

No hidden planning backdoor.
