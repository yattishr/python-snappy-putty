# Snappy PuTTy – SKILLS

## Product Rule (A-mode only)
Snappy PuTTy is suggestion-only.
- It NEVER executes shell commands.
- It returns a plan + suggested commands + risk tags + assumptions.
- It may ask at most 1 clarifying question if needed.

## CLI Commands
- `snappy_putty ask "<intent>"`
- `snappy_putty explain "<command>"`
- `snappy_putty doctor`

## Output Contract (Structured)
All agent responses must map to this schema:

- goal: string
- assumptions: list[string]
- question: string | null
- plan: list[{ step: int, action: string, why: string }]
- commands: list[{ cmd: string, explain: string, risk: "low"|"med"|"high" }]
- warnings: list[string]

## Safety Policy
Risk tags:
- high: destructive/irreversible or broad-impact commands
- med: changes system/services/cloud resources
- low: read-only and safe operations

High-risk patterns include:
- rm -rf, mkfs, dd, iptables, chmod -R, chown -R
- kubectl delete, terraform apply, gcloud sql *patch*, etc.

For med/high:
- always include safer alternative (dry run/plan/diff)
- always include a warning line

## Context Snapshot Rules
Collect and pass to the agent:
- OS, cwd
- git status (if repo)
- detected tools (git/docker/gcloud/kubectl/terraform)
- project type detection (Dockerfile/package.json/pyproject.toml)

## Coding Conventions
- Python 3.10+
- Typer for CLI
- Rich for UI rendering
- No network calls in MVP
- Tests: simple smoke tests in `tests/`

## Definition of Done for v0.1
- `snappy_putty --help` works
- `ask/explain/doctor` commands work
- Agent returns structured output
- Render shows Rich panels + commands table
- Safety risk tagging works
