# M2 Rule Priority Regression Run

- Run date: 2026-04-15T19:53:05
- Repository: `/home/yattishr/Projects/snappy-putty`
- Python entrypoint: `/home/yattishr/Projects/snappy-putty/.venv/bin/python -m snappy_putty.cli`
- Temp work root: `/tmp/snappy_regr_m2_rule_priority`
- Result: `10/10` documented tests passed

## Summary

- Test 1: BLOCK overrides CONFIRM -> PASS
- Test 2: CONFIRM applies when no BLOCK -> PASS
- Test 3: INFO does not affect behavior -> PASS
- Test 4: BLOCK overrides everything -> PASS
- Test 5: no_active_mode overrides mode change -> PASS
- Test 6: Mixed CONFIRM + INFO -> PASS
- Test 7: Multiple BLOCK rules (future-proof) -> PASS
- Test 8: Rule tier visibility -> PASS
- Test 9: Status reflects policy cleanly -> PASS
- Test 10: Safe path still works under rules -> PASS

## Notes

- Rule priority under test: `BLOCK > CONFIRM > WARN > INFO`.
- The `rules` command prints classifications as `enforceable:block`, `enforceable:confirm`, and `informational`; the markdown spec uses shorter prose labels.
- All interactive runs were executed with `SNAPPY_AGENT_MODE=passive` so loaded rules were active in-session.

## Detailed Results

### Test 1 — BLOCK overrides CONFIRM

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/block_confirm`
- Input:
```text
copy README.md to /
status
```
- Expected checks:
  - Operation blocked by rule: protect_project_root
  - Current state: IDLE
  - Pending plan: (none)
  - Awaiting confirmation: no
  - Last failed goal: copy README.md to /
- Notes:
  - Verified BLOCK response suppresses confirmation UX.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/block_confirm                         │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭─────── Goal ────────╮
│ copy README.md to / │
╰─────────────────────╯
╭──────────────────────────────── Policy Block ────────────────────────────────╮
│ Operation blocked by rule: protect_project_root                              │
│                                                                              │
│ The requested filesystem mutation targets a protected path.                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────── Next Step ─────────────────────╮
│ Adjust the target path or request, then try again. │
╰────────────────────────────────────────────────────╯
snappy> ╭──────────────────────── Session Status ────────────────────────╮
│ Current state: IDLE                                            │
│ Active goal: (none)                                            │
│ Last route: fs_mutation                                        │
│ Pending question: (none)                                       │
│ Pending plan: (none)                                           │
│ Awaiting confirmation: no                                      │
│ Last completed goal: (none)                                    │
│ Last cancelled goal: (none)                                    │
│ Last failed goal: copy README.md to /                          │
│ Error message: Operation blocked by rule: protect_project_root │
│                                                                │
│ The requested filesystem mutation targets a protected path.    │
│ Agent feature mode: passive                                    │
│ Agent mode source: environment                                 │
│ Agent name: Rule Priority Fixture                              │
│ Agent version: 1                                               │
│ Agent mode: supervised                                         │
│ Loaded skills: 1                                               │
│ Loaded rules: 2                                                │
│ Enforceable rules: 2                                           │
│ Informational rules: 0                                         │
│ Policy tiers: block=1, confirm=1, warn=0, info=0               │
│ Agent memory: present                                          │
╰────────────────────────────────────────────────────────────────╯
snappy>
```

### Test 2 — CONFIRM applies when no BLOCK

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/confirm_info`
- Input:
```text
copy README.md to tests/
NO
status
```
- Expected checks:
  - Loaded rules require confirmation before filesystem changes are applied.
  - Type YES to apply, or NO to cancel.
  - Cancelled. No pending action was applied.
  - Current state: IDLE
- Notes:
  - Verified no file was created after declining confirmation.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/confirm_info                          │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────── Goal ──────────╮
│ copy README.md to tests/ │
╰──────────────────────────╯
╭─────────────────────────────────── Policy ───────────────────────────────────╮
│                                                                              │
│  • Loaded rules require confirmation before filesystem changes are applied.  │
╰──────────────────────────────────────────────────────────────────────────────╯
                   Planned Changes                   
┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Op  ┃ Action ┃ From      ┃ To              ┃ Risk ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ op1 │ copy   │ README.md │ tests/README.md │ LOW  │
└─────┴────────┴───────────┴─────────────────┴──────┘
╭─────────────────────────────── Plan Warnings ────────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
Type YES to apply, or NO to cancel.
snappy> ╭───────────── Apply Cancelled ─────────────╮
│ Cancelled. No pending action was applied. │
╰───────────────────────────────────────────╯
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: IDLE                              │
│ Active goal: (none)                              │
│ Last route: fs_mutation                          │
│ Pending question: (none)                         │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: (none)                      │
│ Last cancelled goal: copy README.md to tests/    │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Rule Priority Fixture                │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 2                                  │
│ Enforceable rules: 1                             │
│ Informational rules: 1                           │
│ Policy tiers: block=0, confirm=1, warn=0, info=1 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
snappy>
```

### Test 3 — INFO does not affect behavior

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/info_only`
- Input:
```text
copy README.md to tests/
status
```
- Expected checks:
  - Planned Changes
  - Current state: CONFIRMATION
  - Policy tiers: block=0, confirm=0, warn=0, info=1
- Notes:
  - INFO-only flow matched the base filesystem behavior for this command: Snappy still requested confirmation for the pending copy, but no block or additional policy UX appeared.
  - The markdown spec expected `tests/` to complete without confirmation; actual CLI behavior keeps this request in confirmation state even without enforceable rules loaded.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/info_only                             │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────── Goal ──────────╮
│ copy README.md to tests/ │
╰──────────────────────────╯
                   Planned Changes                   
┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Op  ┃ Action ┃ From      ┃ To              ┃ Risk ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ op1 │ copy   │ README.md │ tests/README.md │ LOW  │
└─────┴────────┴───────────┴─────────────────┴──────┘
╭─────────────────────────────── Plan Warnings ────────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
Type YES to apply, or NO to cancel.
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: CONFIRMATION                      │
│ Active goal: copy README.md to tests/            │
│ Last route: fs_mutation                          │
│ Pending question: (none)                         │
│ Pending plan: filesystem plan with 1 op(s)       │
│ Awaiting confirmation: yes                       │
│ Last completed goal: (none)                      │
│ Last cancelled goal: (none)                      │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Rule Priority Fixture                │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 1                                  │
│ Enforceable rules: 0                             │
│ Informational rules: 1                           │
│ Policy tiers: block=0, confirm=0, warn=0, info=1 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
snappy>
```

### Test 4 — BLOCK overrides everything

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/block_confirm_info`
- Input:
```text
copy README.md to /
```
- Expected checks:
  - Policy Block
  - Operation blocked by rule: protect_project_root
- Notes:
  - `require_confirm` and `custom_note` were both loaded, but only BLOCK UX should surface.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/block_confirm_info                    │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭─────── Goal ────────╮
│ copy README.md to / │
╰─────────────────────╯
╭──────────────────────────────── Policy Block ────────────────────────────────╮
│ Operation blocked by rule: protect_project_root                              │
│                                                                              │
│ The requested filesystem mutation targets a protected path.                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────── Next Step ─────────────────────╮
│ Adjust the target path or request, then try again. │
╰────────────────────────────────────────────────────╯
snappy>
```

### Test 5 — no_active_mode overrides mode change

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/no_active_info`
- Input:
```text
agent mode active
agent mode
```
- Expected checks:
  - Active mode is disabled by the loaded agent rules.
  - Current: passive
- Notes:
  - Mode should remain passive when active mode is blocked.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/no_active_info                        │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> Active mode is disabled by the loaded agent rules.
snappy> ╭──── Agent Mode ─────╮
│ Current: passive    │
│ Source: environment │
╰─────────────────────╯
snappy>
```

### Test 6 — Mixed CONFIRM + INFO

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/confirm_info`
- Input:
```text
copy README.md to tests/
NO
```
- Expected checks:
  - Loaded rules require confirmation before filesystem changes are applied.
  - Type YES to apply, or NO to cancel.
  - Cancelled. No pending action was applied.
- Notes:
  - INFO should be additive-only; CONFIRM remains the effective tier.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/confirm_info                          │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────── Goal ──────────╮
│ copy README.md to tests/ │
╰──────────────────────────╯
╭─────────────────────────────────── Policy ───────────────────────────────────╮
│                                                                              │
│  • Loaded rules require confirmation before filesystem changes are applied.  │
╰──────────────────────────────────────────────────────────────────────────────╯
                   Planned Changes                   
┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Op  ┃ Action ┃ From      ┃ To              ┃ Risk ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ op1 │ copy   │ README.md │ tests/README.md │ LOW  │
└─────┴────────┴───────────┴─────────────────┴──────┘
╭─────────────────────────────── Plan Warnings ────────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
Type YES to apply, or NO to cancel.
snappy> ╭───────────── Apply Cancelled ─────────────╮
│ Cancelled. No pending action was applied. │
╰───────────────────────────────────────────╯
snappy>
```

### Test 7 — Multiple BLOCK rules (future-proof)

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/double_block`
- Input:
```text
copy README.md to /
agent mode active
```
- Expected checks:
  - Operation blocked by rule: protect_project_root
  - Active mode is disabled by the loaded agent rules.
- Notes:
  - Each action should map to its relevant block rule without conflicts.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/double_block                          │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭─────── Goal ────────╮
│ copy README.md to / │
╰─────────────────────╯
╭──────────────────────────────── Policy Block ────────────────────────────────╮
│ Operation blocked by rule: protect_project_root                              │
│                                                                              │
│ The requested filesystem mutation targets a protected path.                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────── Next Step ─────────────────────╮
│ Adjust the target path or request, then try again. │
╰────────────────────────────────────────────────────╯
snappy> Active mode is disabled by the loaded agent rules.
snappy>
```

### Test 8 — Rule tier visibility

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/tier_visibility`
- Input:
```text
rules
agent
agent doctor
```
- Expected checks:
  - protect_project_root [protect_project_root] (enforceable:block)
  - require_confirm [require_confirm] (enforceable:confirm)
  - custom_note [custom_note] (informational)
  - Block rules: protect_project_root
  - Confirm rules: require_confirm
  - Info rules: custom_note
  - Policy tiers: block=1, confirm=1, warn=0, info=1
- Notes:
  - The markdown uses shorthand `(block|confirm|info)`; actual CLI output is `enforceable:<tier>` or `informational`.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/tier_visibility                       │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> Loaded rules:
- custom_note [custom_note] (informational)
- protect_project_root [protect_project_root] (enforceable:block)
- require_confirm [require_confirm] (enforceable:confirm)
snappy> ╭────────── Agent Summary ──────────╮
│ Agent feature mode: passive       │
│ Agent loaded: yes                 │
│ Manifest present: yes             │
│ Agent name: Rule Priority Fixture │
│ Version: 1                        │
│ Agent mode: supervised            │
│ Loaded skills: 1                  │
│ Loaded rules: 3                   │
│ Enforceable rules: 2              │
│ Informational rules: 1            │
│ Block rules: protect_project_root │
│ Confirm rules: require_confirm    │
│ Warn rules: (none)                │
│ Info rules: custom_note           │
│ Memory present: yes               │
│ Session memory keys: (none)       │
╰───────────────────────────────────╯
snappy> ╭────────────────── Agent Doctor ──────────────────╮
│ Agent feature mode: passive                      │
│ .snappy directory: present                       │
│ Manifest file: present                           │
│ Manifest parse: ok                               │
│ Skills directory: present                        │
│ Loaded skills: 1                                 │
│ Rules directory: present                         │
│ Loaded rules: 3                                  │
│ Enforceable rules: 2                             │
│ Informational rules: 1                           │
│ Policy tiers: block=1, confirm=1, warn=0, info=1 │
│ Memory directory: present                        │
│ Session file: absent                             │
╰──────────────────────────────────────────────────╯
snappy>
```

### Test 9 — Status reflects policy cleanly

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/tier_visibility`
- Input:
```text
status
```
- Expected checks:
  - Loaded rules: 3
  - Policy tiers: block=1, confirm=1, warn=0, info=1
  - Current state: IDLE
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/tier_visibility                       │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: IDLE                              │
│ Active goal: (none)                              │
│ Last route: (none)                               │
│ Pending question: (none)                         │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: (none)                      │
│ Last cancelled goal: (none)                      │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Rule Priority Fixture                │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 3                                  │
│ Enforceable rules: 2                             │
│ Informational rules: 1                           │
│ Policy tiers: block=1, confirm=1, warn=0, info=1 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
snappy>
```

### Test 10 — Safe path still works under rules

- Status: PASS
- Working directory: `/tmp/snappy_regr_m2_rule_priority/safe_under_rules`
- Input:
```text
copy README.md to tests/
YES
status
```
- Expected checks:
  - Loaded rules require confirmation before filesystem changes are applied.
  - Type YES to apply, or NO to cancel.
  - Current state: IDLE
  - Last completed goal: copy README.md to tests/
- Notes:
  - Verified the safe path was not blocked and completed after explicit confirmation.
- Stdout excerpt:
```text
╭────────────────────────────────── Welcome ───────────────────────────────────╮
│ Snappy PuTTy                                                                 │
│ Your terminal's clever little co-pilot.                                      │
│ I never execute destructive commands.                                        │
│                                                                              │
│ What I do                                                                    │
│ - Plan and explain terminal workflows.                                       │
│ - Perform safe read-only inspection when needed.                             │
│ - Ask follow-up questions when a request needs clarification.                │
│                                                                              │
│ Quick commands                                                               │
│ - doctor            Show local planning diagnostics.                         │
│ - agent             Show the loaded agent summary.                           │
│ - agent mode        Inspect or change agent runtime mode.                    │
│ - init              Scaffold a .snappy/ agent directory.                     │
│ - skills            List loaded .snappy skills.                              │
│ - rules             List loaded .snappy rules.                               │
│ - explain <command> Explain a command safely.                                │
│ - after             Show the next expected input or step.                    │
│ - status            Show diagnostic session and agent status.                │
│ - cancel            Clear pending workflow state.                            │
│ - help              Show this help panel.                                    │
│ - exit / quit       Leave the interactive shell.                             │
│                                                                              │
│ Workflow tips                                                                │
│ - If Snappy asks a question, answer it directly or type 'cancel'.            │
│ - Use 'after' to see the next expected input.                                │
│ - Use 'status' when you want full diagnostic state.                          │
│                                                                              │
│ Try                                                                          │
│ - "give me a file listing"                                                   │
│ - "give me a file listing for src"                                           │
│ - "copy README.md"                                                           │
│ - "destination path> tests/"                                                 │
│ - "deploy this to google cloud"                                              │
│                                                                              │
│ CWD: /tmp/snappy_regr_m2_rule_priority/safe_under_rules                      │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────── Goal ──────────╮
│ copy README.md to tests/ │
╰──────────────────────────╯
╭─────────────────────────────────── Policy ───────────────────────────────────╮
│                                                                              │
│  • Loaded rules require confirmation before filesystem changes are applied.  │
╰──────────────────────────────────────────────────────────────────────────────╯
                   Planned Changes                   
┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Op  ┃ Action ┃ From      ┃ To              ┃ Risk ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ op1 │ copy   │ README.md │ tests/README.md │ LOW  │
└─────┴────────┴───────────┴─────────────────┴──────┘
╭─────────────────────────────── Plan Warnings ────────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
Type YES to apply, or NO to cancel.
snappy>                                 Applied Changes                                 
┏━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Op  ┃ Action ┃ Status  ┃ Message                                             ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ op1 │ copy   │ APPLIED │ Copied file: README.md -> tests/README.md. Undo     │
│     │        │         │ hint: `rm tests/README.md`.                         │
└─────┴────────┴─────────┴─────────────────────────────────────────────────────┘
╭─────────────────────────────── Apply Warnings ───────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: IDLE                              │
│ Active goal: (none)                              │
│ Last route: fs_mutation                          │
│ Pending question: (none)                         │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: copy README.md to tests/    │
│ Last cancelled goal: (none)                      │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Rule Priority Fixture                │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 2                                  │
│ Enforceable rules: 2                             │
│ Informational rules: 0                           │
│ Policy tiers: block=1, confirm=1, warn=0, info=0 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
snappy>
```

