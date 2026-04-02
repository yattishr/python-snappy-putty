Implement Snappy Agent Spec V2 - Chunk 1.

Goal:
Add an inspectable `agent` summary command for both the top-level CLI and the interactive REPL.

Requirements:
- Add a top-level CLI command: `snappy agent`
- Add exact-match REPL support for: `agent`
- Display a clean summary of the currently loaded agent, including:
  - feature mode
  - whether manifest is present
  - agent name
  - version
  - agent mode
  - number of loaded skills
  - number of loaded rules
  - whether memory is present
  - session memory keys if available
- If no `.snappy/` agent is present, show a friendly summary stating that no agent is loaded
- Keep this read-only and additive only
- Do not change routing, execution, planning, confirmation, or existing command behavior

Add tests for:
1. no agent present
2. valid agent present
3. REPL `agent` command works
4. top-level `snappy agent` command works