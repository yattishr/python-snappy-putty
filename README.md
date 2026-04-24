# Snappy PuTTy

Snappy PuTTy is a suggestion-first terminal assistant for planning and explaining shell workflows.
It is designed to help you reason about commands safely before you run anything yourself.

## Recent Changes

- interactive workflows can now be restored after a shell restart
- restored clarification and confirmation states are shown explicitly at startup
- `status` now reports whether the active workflow came from memory
- invalid restore snapshots are warned about and ignored instead of being silently dropped

## Purpose

This repository provides a Python CLI that:

- plans task-oriented command sequences (`ask` mode)
- explains individual commands (`explain` mode)
- reports local environment context (`doctor` mode)
- offers an interactive REPL (`shell` mode or default when no subcommand is provided)

The project emphasizes safety and clarity:

- risk tags (`low`, `med`, `high`) on suggested commands
- warnings and safer alternatives for higher-risk actions
- strict separation between planning vs explaining behavior
- read-only local inspection tools only (no state-changing execution by the app)

## Core Behavior

### AskMode (`ask`)

Use AskMode when you want a plan for an intent.

- can use context snapshot information (OS/cwd/tools/git/project markers)
- can use read-only helpers when needed (for example directory listing)
- can ask at most one clarifying question if request is ambiguous
- returns structured output rendered with Rich panels/tables

### ExplainMode (`explain`)

Use ExplainMode when you want command understanding.

- explains meaning, syntax, and typical usage
- references prerequisites generically (for example “must run in a git repo”)
- does not claim current machine state unless you explicitly provide that info
- does not do troubleshooting unless you ask about a failure/provide an error

### Doctor (`doctor`)

Shows a local context report including:

- OS and platform
- current working directory
- git branch/state (if inside a git repo)
- tool detection (`git`, `docker`, `gcloud`, `kubectl`, `terraform`)
- project type markers (`Dockerfile`, `package.json`, `pyproject.toml`)

## Project Structure

- `src/snappy_putty/cli.py`: Typer CLI entrypoints and REPL routing
- `src/snappy_putty/agent.py`: Ask/Explain orchestration, parsing, mode instructions
- `src/snappy_putty/models.py`: Pydantic schema for agent output
- `src/snappy_putty/render.py`: Rich rendering helpers (panels/tables/snippets)
- `src/snappy_putty/context.py`: local environment snapshot collection
- `src/snappy_putty/safety.py`: regex-based risk scoring and tagging
- `src/snappy_putty/tools_safe.py`: read-only terminal helpers
- `tests/`: smoke and unit tests
- `SKILLS.md`: product behavior contract and safety constraints
- `TASKS.md`: delivery phase checklist

## Requirements

- Python 3.10+
- Unix-like shell (for examples below)

## Installation

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If you only want runtime dependencies:

```bash
pip install -e .
```

## Running Snappy PuTTy

### 1. Interactive mode (default)

Start REPL by running without subcommand:

```bash
snappy
```

Or explicitly:

```bash
snappy shell
```

Prompt:

```text
snappy [ask]>
```

REPL commands:

- `help` -> prints the cheat-sheet
- `doctor` -> runs doctor report
- `status` -> shows the current session state, including any restored workflow
- `after` -> shows the next expected input or step
- `explain <command>` -> explain route
- any other non-empty line -> ask route
- `exit` / `quit` -> exit REPL

History is stored at:

- `~/.snappy_putty_history`

### Workflow restore and resume safety

Snappy PuTTy persists pending workflow state in `.snappy/memory/session.json` so clarification and confirmation flows can survive shell restarts.

- restored clarification prompts remain active and show the pending question again
- restored confirmation prompts still require an explicit `YES` or `NO`
- `status` shows whether the active workflow was restored from memory
- invalid or incompatible snapshots are ignored with a warning instead of silently failing
- `help` and `status` preserve the pending workflow instead of clearing it

### 2. Non-interactive commands

```bash
snappy ask "give me a file listing"
snappy ask "deploy this to google cloud"
snappy explain "git worktree list"
snappy doctor --verbose
```

## Special Ask Behaviors

### Directory listing intents

If intent looks like file/folder listing:

- defaults to current directory when path is omitted
- uses requested path when present (for example `for src`)
- asks one follow-up question when directory is ambiguous

Output includes a `Directory Listing` panel and still provides plan/notes.

### Google Cloud deploy intent

For CLI-like projects (`pyproject.toml` present and no web framework markers), the tool:

- asks one clarifying question between web service vs CLI distribution
- provides two branches:
  - Branch A: Cloud Run Job workflow (container build/push/create/execute)
  - Branch B: package/publish workflow (build/twine/TestPyPI-first)

## Environment Configuration

Copy and configure:

```bash
cp .env.example .env
```

Typical variable:

- `OPENAI_API_KEY` for SDK-backed responses

When API key is missing/unavailable, Snappy PuTTy falls back to safe structured output.

## Safety Model

Snappy PuTTy does not execute user commands. It only suggests commands.

Risk scoring:

- `high`: destructive/irreversible patterns (for example `rm -rf`, `terraform apply`)
- `med`: potentially state-changing commands (for example `gcloud run deploy`, `docker system prune`)
- `low`: read-only/safe operations

For medium/high risk suggestions, warnings and tool-specific guidance are added.

## Testing

Run all tests:

```bash
pytest -q
```

Tests cover:

- CLI smoke behavior (`ask`/`explain`/`doctor`/`shell`)
- schema parsing robustness (including fenced JSON extraction)
- risk scoring logic
- rendering behavior (including snippet panels and command normalization)

## Troubleshooting

### `snappy` command not found

Ensure editable install is active in your current virtualenv:

```bash
pip install -e .
```

### Missing dependencies in tests/runtime

Install dev dependencies:

```bash
pip install -e .[dev]
```

### API key warnings

Set `OPENAI_API_KEY` in environment or `.env` to enable live SDK calls.
Fallback behavior is expected without a key.

## Development Notes

- Keep AskMode and ExplainMode behavior separated.
- Prefer read-only inspection; never add state-changing execution paths.
- Maintain structured output contract in `models.py`.
- If modifying intent routing, update smoke tests accordingly.
