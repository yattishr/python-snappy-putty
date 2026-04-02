Implement Snappy Agent Spec V2 - Chunk 6.

Goal:
Add smoke coverage for the new inspectable agent runtime surfaces and verify no regression to existing behavior.

Requirements:
- Keep the existing regression suite intact
- Add smoke tests for:
  - top-level `snappy agent`
  - REPL `agent`
  - `skills`
  - `rules`
  - `agent doctor`
  - `status` with agent metadata present
  - REPL `help` including agent-related commands
- Ensure these tests are additive and do not weaken existing regression coverage

Output:
- updated tests
- short summary of coverage added