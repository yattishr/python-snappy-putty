Implement REPL support for the `init` command.

Goal:
Allow `init` to work inside the interactive REPL exactly like `snappy init`.

Requirements:
- Add an exact-match REPL command: `init`
- When invoked, call the same scaffold logic used by the CLI `snappy init`
- Output should match CLI behavior:
  "Initialized agent scaffold at <path>"
- If `.snappy/` already exists, show the same message used by CLI init
- Do not duplicate scaffold logic — reuse the same function
- Keep this additive only
- Do not change routing, parsing, state machine, or execution logic

Behavior:
CLI:
    snappy init

REPL:
    snappy> init

Both must produce identical results.

Tests:
1. REPL `init` creates .snappy/
2. CLI `snappy init` still works
3. Running `init` twice does not crash
4. Help output remains unchanged