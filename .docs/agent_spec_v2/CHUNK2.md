Implement Snappy Agent Spec V2 - Chunk 2.

Goal:
Improve the agent section in `status` so it is more complete and easier to scan.

Requirements:
- Preserve the existing session state/status output exactly as-is
- Improve only the agent-related section
- Include, where available:
  - Agent feature mode
  - Agent name
  - Agent version
  - Agent mode
  - Loaded skills count
  - Loaded rules count
  - Agent memory present/absent
  - Agent memory session keys
- Keep formatting compact and readable
- Do not alter any routing, execution, or session state behavior

Add tests for:
1. status with no agent
2. status with valid agent and loaded skills/rules/memory
3. status with partial agent metadata