# Snappy PuTTy – Agent Spec V2: Inspectable Agent Runtime

## GLOBAL RULES
- Do not replace, rewrite, or remove any existing routing, parsing, prompting, state machine, planning, execution, or confirmation behavior.
- Add Agent Spec V2 support incrementally and non-destructively.
- All new behavior must be additive only.
- Existing commands and flows must continue to work exactly as before unless a chunk explicitly states otherwise.
- Do not allow agent metadata to influence routing or execution decisions in V2.

## EXECUTION ORDER
- Run the chunks in exact order from Chunk 1 to Chunk 6.
- Do not begin the next chunk until the current chunk is implemented and complete.
- After each chunk, verify that existing behavior still works before continuing.

## CHUNK COMPLETION RULE
After completing each chunk:
- stop
- summarize files changed
- summarize tests added or updated
- state any risks introduced
- do not continue automatically

## Chunk 1
Goal: Add an `agent` summary command.
RUN: CHUNK1.md

## Chunk 2
Goal: Improve the `status` agent section.
RUN: CHUNK2.md

## Chunk 3
Goal: Improve REPL and CLI help discoverability.
RUN: CHUNK3.md

## Chunk 4
Goal: Add `agent doctor` diagnostics.
RUN: CHUNK4.md

## Chunk 5
Goal: Add reusable agent fixture test sets.
RUN: CHUNK5.md

## Chunk 6
Goal: Run regression plus V2 smoke coverage.
RUN: CHUNK6.md