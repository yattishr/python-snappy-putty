Implement Snappy Agent Spec V2 - Chunk 5.

Goal:
Add reusable test fixtures for agent runtime inspection and diagnostics.

Requirements:
- Create fixture directories for:
  - valid agent
  - missing manifest
  - malformed manifest
  - malformed memory
  - malformed skill
- Keep fixture contents small and readable
- Update or add tests to use these fixtures where appropriate
- Do not change runtime behavior

Output:
- clear fixture structure
- tests referencing fixtures cleanly