# Implement Chunk 1 for Snappy Agent Spec v1.

## Goal:
Add non-invasive discovery for a project-local `.snappy/` folder and `.snappy/snappy.yaml`, without changing any existing CLI behavior.

Requirements:
- Create a new module for agent discovery/loading.
- Add a function that checks the current working directory for:
  - `.snappy/`
  - `.snappy/snappy.yaml`
- Return a small structured result such as:
  - agent_found: bool
  - agent_root: optional path
  - manifest_path: optional path
- Do not modify routing, parsing, execution, prompts, pending-question handling, or confirmation flow.
- If `.snappy/` is absent, Snappy must behave exactly as before.

## Output:
- Clean implementation
- Minimal tests for:
  1. no `.snappy/` present
  2. `.snappy/` present, no manifest
  3. `.snappy/snappy.yaml` present

## Definition of done
- status still works exactly the same.
- copy, cancel, after, pending-question flows all still work exactly the same.
- There is no new behavior except internal discovery.  