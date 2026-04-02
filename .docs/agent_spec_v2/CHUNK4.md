Implement Snappy Agent Spec V2 - Chunk 4.

Goal:
Add an agent diagnostics command that checks the `.snappy/` runtime surface and reports what loaded successfully.

Requirements:
- Add a diagnostic command available from the CLI and REPL
- Preferred UX:
  - top-level CLI: `snappy agent-doctor`
  - REPL exact-match: `agent doctor`
- Report on:
  - `.snappy/` presence
  - manifest presence and parse success
  - skills directory presence and number of successfully loaded skills
  - rules directory presence and number of successfully loaded rules
  - memory directory presence
  - session.json presence and parse success
- Surface warnings for malformed or skipped files when available
- Keep this read-only
- Do not alter routing or execution behavior

Add tests for:
1. no agent directory
2. valid full agent setup
3. malformed manifest
4. malformed memory file
5. malformed skill/rule files reflected in diagnostics