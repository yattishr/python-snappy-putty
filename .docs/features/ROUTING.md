# Snappy PuTTy Routing Contract

`classify_input(text)` deterministically maps user input to one route. The router is heuristic-based and runs in strict precedence order.

## Routes

- `builtin_help`
  - For the exact `help` command.
  - Allowed behavior: show REPL cheat-sheet/help text only.
- `builtin_doctor`
  - For the exact `doctor` command.
  - Allowed behavior: run local context snapshot rendering.
- `builtin_exit`
  - For the exact `exit` or `quit` command.
  - Allowed behavior: exit REPL loop.
- `builtin_after`
  - For the exact `after` command.
  - Allowed behavior: continue/restate next pending step in session.
- `builtin_status`
  - For the exact `status` command.
  - Allowed behavior: show in-session goal/pending/route status.
- `builtin_cancel`
  - For the exact `cancel` command.
  - Allowed behavior: clear pending session state.
- `explain`
  - For inputs beginning with `explain` (for example `explain git worktree list`).
  - Allowed behavior: route to ExplainMode with parsed command payload.
- `fs_mutation`
  - For local filesystem mutation intents (`copy`, `move`, `rename`, `mkdir`, `make ... folder`, `create ... folder`).
  - Allowed behavior: use local filesystem planning/apply flow only; do not route to agent AskMode.
- `safe_inspect`
  - For read-only inspection intents (file/directory listing and git worktree listing).
  - Allowed behavior: route to AskMode safe inspection paths.
- `ask`
  - Default fallback for all other intents.
  - Allowed behavior: route to AskMode planning.

## Precedence Order

1. Built-ins: `help`, `doctor`, `after`, `status`, `cancel`, `exit`, `quit`
2. `explain <command>`
3. Filesystem mutation intents
4. Safe inspection intents
5. Fallback to `ask`

## Example Inputs

- `help` -> `builtin_help`
- `doctor` -> `builtin_doctor`
- `exit` -> `builtin_exit`
- `quit` -> `builtin_exit`
- `after` -> `builtin_after`
- `status` -> `builtin_status`
- `cancel` -> `builtin_cancel`
- `explain git worktree list` -> `explain`
- `copy README.md` -> `fs_mutation`
- `copy README.md file` -> `fs_mutation`
- `make a folder called sandbox` -> `fs_mutation`
- `give me a file listing` -> `safe_inspect`
- `give me a git worktree listing` -> `safe_inspect`
- `deploy this to google cloud` -> `ask`
