# Implement Chunk 5 for Snappy Agent Spec v1.

## Goal:
Load `.snappy/rules/*.md` into a passive rule registry, without changing runtime behavior.

## Requirements:
- Parse simple markdown rule files with:
  - `# Rule: <name>`
  - remaining body as description/policy text
- Add a `rules` command to list loaded rules
- Surface loaded rule names in a status/debug-friendly way
- Do not enforce any rules yet

## Add tests for:
1. valid rules
2. empty rules directory
3. malformed markdown

## Definition of done
- Rules can be listed
- No existing behavior changes
- You now have a foundation for later enforcement