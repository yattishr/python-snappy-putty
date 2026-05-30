# Snappy UX-12 Codex Implementation Spec

## Patch

**UX-12 — Home Screen Redesign**

## Goal

Replace Snappy’s current command-heavy startup/help screen with a compact, project-aware home screen.

The current screen overwhelms users with too many commands and workflow details. The new screen should quickly answer:

```text
Where am I?
What is Snappy’s current state?
What did I do recently?
What can I ask next?
Which core commands matter right now?
```

This is UX polish only.

Do not change routing, planning, skill execution, config semantics, or workflow state behavior.

---

## Desired Home Screen

Use this as the target style:

```text
╭──────────────────────────────────────────────╮
│               Snappy PuTTy                   │
│        Project-Aware AI Co-Pilot             │
╰──────────────────────────────────────────────╯

Project
  vanilla-nodejs-rest-api

Status
  ✓ Active
  ✓ Snapshot ready
  ✓ 4 skills enabled

Last Activity
  Review my latest changes and give me MR-style feedback

Try asking:
  • Build a frontend for this API
  • Generate project documentation
  • Explain this codebase

Commands:
  help • skills • inspect • status • exit

snappy>
```

---

## Requirements

### 1. Replace command wall on startup

On REPL start, do not print the long full command list by default.

Show the compact home screen instead.

The full help/command reference should remain available via:

```text
help
```

or another existing help command.

---

### 2. Project section

Show current project name.

Suggested source order:

1. `.snappy/snappy.yaml` agent/project name if available
2. current folder name
3. fallback: `(unknown project)`

Example:

```text
Project
  vanilla-nodejs-rest-api
```

Optional extra metadata if already available cheaply:

```text
  JavaScript • npm • Git repository
```

Keep it short. Do not turn this into `inspect project`.

---

### 3. Status section

Show concise status lines.

Examples:

```text
Status
  ✓ Active
  ✓ Snapshot ready
  ✓ 4 skills enabled
```

Status items should include where available:

- agent mode:
  - `Active`
  - `Off`
- snapshot status:
  - `Snapshot ready`
  - `No snapshot yet`
  - `Snapshot stale` if already detectable
- enabled skill count:
  - `0 skills enabled`
  - `1 skill enabled`
  - `4 skills enabled`

Do **not** list all skills on the home screen.

If no config exists:

```text
  ! Config not initialized
```

If no skills enabled:

```text
  ! 0 skills enabled
```

Use existing Rich styling if available.

---

### 4. Last Activity section

Show recent user command if available.

Example:

```text
Last Activity
  Review my latest changes and give me MR-style feedback
```

If no recent activity:

```text
Last Activity
  No recent command yet
```

Source can be:

- session history
- last workflow metadata
- recent run history
- safe fallback

Do not overbuild history storage.

---

### 5. Try asking section

Show 3 contextual prompt suggestions.

Default suggestions:

```text
Try asking:
  • Review my latest changes
  • Build a frontend for this API
  • Generate project documentation
```

If project snapshot indicates language/framework, suggestions may be lightly tailored.

Examples:

Node/API project:

```text
  • Review my latest changes
  • Build a frontend for this API
  • Explain the API structure
```

Python project:

```text
  • Review my latest changes
  • Create a Streamlit dashboard
  • Generate project documentation
```

No snapshot:

```text
  • Inspect this project
  • Explain this codebase
  • Show available skills
```

Keep to 3 suggestions.

---

### 6. Commands section

Show only core commands:

```text
Commands:
  help • skills • inspect • status • exit
```

Do not show the full command catalog here.

The full catalog remains available via `help`.

---

### 7. Visual style

Use a clean Rich panel or simple terminal layout.

Requirements:

- compact
- readable
- no dense command tables
- no excessive decoration
- works on narrow terminals reasonably
- avoids giant blank sections
- avoids large diagnostics on startup

The screen should fit comfortably in a typical terminal without scrolling.

---

### 8. Preserve help behavior

The existing detailed help screen should still be accessible.

If current startup screen is reused from `help`, split them:

- startup: compact home screen
- `help`: detailed command reference
- optional future: `home` command to re-render compact home screen

If easy, add:

```text
home
```

as an alias to render the home screen again.

---

### 9. Config awareness

Use `.snappy/snappy.yaml` where available.

The home screen should reflect:

- agent mode
- enabled skill count
- config missing/valid status if already available
- no full config dump

Do not crash if config is malformed. Show a concise warning:

```text
  ! Config warning: run `snappy config validate`
```

---

### 10. Tests required

Add/update tests for:

1. REPL startup shows compact home screen.
2. Startup does not show full command wall.
3. Project name appears.
4. Agent mode appears.
5. Skill count appears.
6. Skills are not individually listed.
7. Last activity appears when available.
8. Fallback last activity appears when no history exists.
9. Suggestions appear.
10. Help command still shows detailed help.
11. Malformed/missing config does not crash home screen.
12. Narrow/no snapshot case still renders cleanly.

Likely files:

```text
tests/test_session_repl_subprocess.py
tests/test_cli.py
tests/test_config.py
```

Use existing test structure.

---

## Acceptance Criteria

Done when:

- Startup screen is compact and project-aware.
- Full command wall no longer appears on startup.
- Full help remains available.
- Home screen shows:
  - project
  - status
  - last activity
  - 3 suggestions
  - core commands
- Skill count is shown, but skills are not listed.
- Invalid/missing config is handled gracefully.
- Tests pass.

---

## Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
git diff --check
```

Manual smoke test:

```bash
snappy
```

Expected:

- compact home screen
- no huge command list
- prompt returns normally

Then:

```text
help
```

Expected:

- detailed help still available

---

## Non-Goals

Do not implement:

- new routing behavior
- new planning behavior
- new config semantics
- new skill execution
- M7 execution intelligence
- plugin system
- GUI/TUI framework
- listing all skills on startup

This is a focused home screen polish patch.
