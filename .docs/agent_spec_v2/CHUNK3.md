Implement Snappy Agent Spec V2 - Chunk 3.

Goal:
Improve discoverability of agent-related commands in help surfaces.

Requirements:
- Update the custom REPL help/cheat sheet to include:
  - agent
  - skills
  - rules
  - init
- Ensure descriptions are concise and accurate
- Confirm the top-level CLI help remains accurate for these commands
- Do not change routing or execution behavior
- Do not introduce natural-language variants; exact commands only

Add tests for:
1. REPL help includes agent, skills, rules, init
2. help formatting remains readable