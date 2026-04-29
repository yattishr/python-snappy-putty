# Snappy M5 Patch — Grounded Planning Guardrails

## Context

M5 Active Mode is working, but quick manual testing exposed two issues:

1. Snappy creates grounded repo plans for unrelated requests.
2. Status labels deterministic plans as “agent plan,” which is misleading.

Example problematic input:

help me build a rocketship

Current behavior:

Grounded Plan
Goal: help me build a rocketship
Mode: deterministic
Files considered: README.md, README_done.md, README_final.md
Steps:
1. Inspect current implementation...
2. Apply the smallest project change...

This is incorrect. Non-project requests should not be forced into a repository plan.

---

## Required Fix 1 — Add Project Relevance Gate

Before creating a grounded plan, Snappy must decide whether the user goal is plausibly related to the inspected project.

### Desired Flow

User goal  
↓  
Project snapshot available?  
↓  
Is goal project-related?  
→ YES: create grounded plan  
→ NO: reject/clarify (no plan)

---

## Relevance Rules

### Project-related if:

- Mentions code/project terms:
  code, file, folder, directory, test, bug, fix, refactor, function, class, module, CLI, command, route, package, dependency, README, docs, logging, config, implementation, project

- References existing file or directory in ProjectSnapshot

- Asks to inspect, explain, improve, update, or modify repo content

- Matches deterministic routes

### Not project-related if:

- General or unrelated to repo
- No grounding in files, tests, docs, or config

Examples to reject:
- help me build a rocketship
- write a poem
- plan my holiday
- what should I cook
- explain quantum physics
- what is the price of bitcoin
- give me the price of bitcoin today
- hack this
- give me the weather
- what is the weather in

Examples to allow:
- improve this CLI
- add logging
- summarize README
- refactor module
- fix routing logic

---

## Expected Behavior (Irrelevant Goal)

Output:

This request does not appear to be related to the current project.

No grounded plan was created.

Do not:
- create a plan
- update session.json
- set awaiting_confirmation

### History Log Entry

## <timestamp>
Event: Grounded planning skipped
Goal: help me build a rocketship
Reason: goal_not_project_related
Snapshot ID: snap_xxx
Result: no_plan_created

---

## Required Fix 2 — Correct Status Plan Label

Replace:

Pending plan: agent plan with X steps

With:

Pending plan: deterministic plan with X steps
OR
Pending plan: llm_assisted plan with X steps

---

## Required Fix 3 — Tests

Add tests:

### Test 1: Irrelevant request rejected
- No plan created
- Output contains rejection message
- History logs skip
- No confirmation state

### Test 2: Relevant request works
- Plan created
- Bound to snapshot

### Test 3: File reference allowed
Input: summarize README.md → valid

### Test 4: Status label correct
Ensure no "agent plan" wording

---

## Non-Negotiable Guardrail

Snappy must NEVER invent a project connection.

If not grounded → do not plan.

Core principle:

Understand first.
Ground only when justified.
Never hallucinate intent into action.

---

## Verification

Run:

python -m py_compile src/snappy_putty/*.py
python -m pytest tests/test_active_mode_v1.py
python -m pytest

Manual:

snappy inspect project
snappy

agent mode active
help me build a rocketship
status
help me improve this CLI
status
