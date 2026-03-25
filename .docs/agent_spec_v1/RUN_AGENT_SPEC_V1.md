# Snappy PuTTy – Agent Spec V1

## GLOBAL RULES
- Do not replace, rewrite, or remove any existing routing, parsing, prompting, state machine, planning, execution, or confirmation behavior.
- Add Agent Spec V1 support incrementally and non-destructively.
- All new agent-loading behavior must be additive only.
- Existing commands and flows must continue to work exactly as before unless a chunk explicitly states otherwise.
- If a chunk introduces risk to existing behavior, stop and preserve the current implementation approach.

## EXECUTION ORDER
- Run the chunks in exact order from Chunk 1 to Chunk 7.
- Do not begin the next chunk until the current chunk is implemented and complete.
- After each chunk, verify that existing behavior still works before continuing.

## CHUNK COMPLETION RULE
After completing each chunk:
- stop
- summarize files changed
- summarize tests added or updated
- state any risks introduced
- do not continue to the next chunk automatically

## SCOPE CONTROL
Implement only the chunk currently being executed.
Do not partially implement future chunks unless the current chunk explicitly requires a tiny shared utility.
Do not wire passive metadata into runtime decision-making until instructed by a later chunk.

## Chunk 1
Goal: Teach Snappy to detect whether a project contains a .snappy/ directory, without changing how any command behaves.
RUN: CHUNK1.md

## Chunk 2
Goal: Parse a minimal manifest, but do not let it control anything yet.
RUN: CHUNK2.md

## Chunk 3
Goal: Create a command that scaffolds a starter .snappy/ folder.
RUN: CHUNK3.md

## Chunk 4
Goal: Allow Snappy to read .snappy/skills/*.md and build a registry, but do not use it for routing yet.
RUN: CHUNK4.md

## Chunk 5
Goal: Load .snappy/rules/*.md, display them, but do not enforce them yet.
RUN: CHUNK5.md

## Chunk 6
Goal: Support .snappy/memory/ existence and optionally read a session.json, without replacing your current session state.
RUN: CHUNK6.md

## Chunk 7
Goal: Create a feature flag like:
- `SNAPPY_AGENT_MODE=off|passive|active`
RUN: CHUNK7.md

## TESTING RULE
After each completed chunk, run the regression checklist before proceeding.

Goal:
Ensure that existing routing, prompting, state handling, pending-question flows, confirmation flows, and execution behavior remain unchanged.

RUN: RUN_REGRESSION_TEST.md