# Implement Chunk 3 for Snappy Agent Spec v1.

## Goal:
Add a `snappy init` command that scaffolds a minimal `.snappy/` directory.

Generate:
- `.snappy/snappy.yaml`
- `.snappy/skills/`
- `.snappy/rules/`
- `.snappy/memory/`

## Requirements:
- Do not overwrite existing files unless an explicit force option is provided
- Generate a minimal valid `snappy.yaml`
- Keep implementation simple and safe
- Do not connect this command to routing/execution logic yet

## Add tests for:
1. init in clean directory
2. init when `.snappy/` already exists
3. init with force

## Definition of done
- New project can run snappy init
- No existing workflows break
- User can inspect generated files manually