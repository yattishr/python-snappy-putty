# Snappy M5.7.x Patch — Plan State, Skip Cleanup, Context Selection

## Problem 1 — Successful plan leaves state as PLANNING

After LLM plan generation succeeds, status shows:

Current state: PLANNING

But the plan exists and is awaiting user review.

## Fix

After successful plan creation:

state = CONFIRMATION

Not PLANNING.

A valid stored plan means planning has completed and Snappy is now waiting for user review/refinement/confirmation.

---

## Problem 2 — Stale skip metadata remains after successful plan

Status still shows:

Last skipped goal: help me improve this cli
Last skip reason: llm_required_but_unavailable

Even though LLM planning succeeded.

## Fix

After successful plan creation, clear:

last_skipped_goal
last_skip_reason

Do not show stale skip metadata after a valid plan exists.

---

## Problem 3 — Context selector misses actual CLI entrypoint

For:

help me improve this CLI

Snappy selected:

pyproject.toml
README.md
docs/ROADMAP.md
tests/*
src/taskcli/__init__.py

But it missed:

src/taskcli/main.py

That is the actual CLI entrypoint.

## Fix

Improve context selection for CLI-related goals.

For goals containing:

cli
command
commands
terminal
arg
args
input validation

Prioritize files named:

main.py
cli.py
app.py
commands.py

Also boost files containing:

sys.argv
argparse
typer
click
def main(
if __name__ == "__main__"

Expected selected context for the test project:

src/taskcli/main.py
src/taskcli/tasks.py
src/taskcli/storage.py
tests/test_tasks.py
tests/test_storage.py
README.md

Docs/config may be included, but must not crowd out implementation files.

---

## Tests Required

1. Successful LLM plan sets state to CONFIRMATION.

2. Successful LLM plan clears stale skip metadata.

3. CLI-related goal includes src/taskcli/main.py in selected context.

4. Generated plan for “help me improve this CLI” references src/taskcli/main.py.

5. show plan displays state/status consistently:
   - Current state: CONFIRMATION
   - Last plan status: awaiting_confirmation
   - Pending plan: llm_assisted plan with N step(s)

---

## Verification

Run:

python -m py_compile src/snappy_putty/*.py
python -m pytest

Manual:

snappy
agent mode active
help me improve this CLI
status
show plan

Expected:

- state = CONFIRMATION
- no stale last_skipped_goal
- plan includes src/taskcli/main.py
- no deterministic fallback
