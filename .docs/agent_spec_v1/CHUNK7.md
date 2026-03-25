# Implement Chunk 7 for Snappy Agent Spec v1.

# Goal:
Introduce a feature gate for agent loading.

# Requirements:
- Add a config/flag with possible values:
  - off
  - passive
  - active
- For now, only implement behavior for:
  - off: ignore `.snappy/`
  - passive: load and surface agent metadata only
- Do not implement active mode behavior yet
- Ensure existing behavior remains default-safe

Add tests for feature gate behavior