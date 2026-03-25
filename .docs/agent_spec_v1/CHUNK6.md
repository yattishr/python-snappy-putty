# Implement Chunk 6 for Snappy Agent Spec v1.

## Goal:
Add read-only support for `.snappy/memory/` and optional `.snappy/memory/session.json`.

## Requirements:
- Detect whether memory folder exists
- Safely parse `session.json` if present
- Expose this as passive agent memory metadata
- Do not overwrite or replace Snappy’s current in-memory session/state machine behavior
- Invalid JSON should warn and continue safely

## Add tests for:
1. no memory folder
2. valid session.json
3. malformed session.json

## Definition of done
- No change to active goal logic
- No resuming behavior yet
- Just safe visibility