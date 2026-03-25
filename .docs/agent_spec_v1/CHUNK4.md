# Implement Chunk 4 for Snappy Agent Spec v1.

## Goal:
Load `.snappy/skills/*.md` as a read-only skill registry, without affecting current routing.

## Requirements:
- Scan the skills directory for markdown files
- Parse a simple structure:
  - heading `# Skill: <name>`
  - `Description:`
  - `Intent examples:`
  - `Risk:`
- Build an in-memory registry
- Add a simple command like `skills` to display loaded skills
- Invalid skill files should be skipped with a warning, not crash Snappy

Do not:
- modify intent parsing
- modify regex routes
- auto-execute skills
- change execution flow

Add tests for valid and invalid skill files

## Definition of done
- snappy skills shows parsed skill names
- Existing parser/router untouched
- Bad skill file does not crash app