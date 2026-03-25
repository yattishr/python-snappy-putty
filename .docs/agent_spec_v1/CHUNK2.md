# Implement Chunk 2 for Snappy Agent Spec v1.

## Goal:
Parse `.snappy/snappy.yaml` into a minimal validated manifest object, without changing runtime behavior.

## Schema for v1:
- name: string
- version: int
- mode: string
- confirmations: bool
- dry_run: bool
- skills: list[str]
- rules: list[str]
- memory: bool

## Requirements:
- Safely parse YAML
- Validate known fields
- Ignore unknown fields for forward compatibility
- If manifest is invalid, surface a clean warning and continue with normal Snappy behavior
- Update `status` to optionally display passive agent metadata
- Do not let the manifest alter routing or execution yet

## Add tests for:
1. valid manifest
2. missing optional fields
3. malformed YAML
4. wrong field types

## Definition of done
- status can show:
- Agent: Snappy Dev Agent
- Agent mode: supervised
- No command behavior changes yet.
- Invalid manifest gives a clean warning, not a crash.