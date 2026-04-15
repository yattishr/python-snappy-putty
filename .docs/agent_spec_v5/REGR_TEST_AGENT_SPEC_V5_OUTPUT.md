# Agent Spec V5 Regression Run

- Run date: 2026-04-15T19:46:59
- Repository: `/home/yattishr/Projects/snappy-putty`
- Python entrypoint: `/home/yattishr/Projects/snappy-putty/.venv/bin/python -m snappy_putty.cli`
- Temp work root: `/tmp/snappy_regr_agent_spec_v5`
- Result: `14/14` documented tests passed

## Summary

- Test 1: Baseline (No Agent Loaded) -> PASS
- Test 2: Agent Runtime Loads -> PASS
- Test 3: Clarification Lock -> PASS
- Test 4: Clarification Accepts Answer -> PASS
- Test 5: Cancel Works During Clarification -> PASS
- Test 6: require_confirm Rule -> PASS
- Test 7: protect_project_root Rule -> PASS
- Test 8: no_active_mode Rule -> PASS
- Test 9: Informational Rule -> PASS
- Test 10: Agent Mode Control -> PASS
- Test 11: Clarification + Rules Together -> PASS
- Test 12: Status Integrity -> PASS
- Test 13: CLI Commands Still Work -> PASS
- Test 14: No Agent Mode Regression -> PASS

## Spec Drift / Setup Notes

- The checked-in `test-snappy-agent` fixture did not include `protect_project_root.md` or `no_active_mode.md`, so those were added in isolated temp repos to execute Tests 7 and 8 exactly.
- Outside the REPL, the CLI command is `snappy agent-doctor`; inside the REPL, the command is `agent doctor`.
- The current `status` panel reports agent presence through agent metadata rows and `Agent feature mode`, not a standalone `Agent loaded:` line.

## Detailed Results

### Test 1 — Baseline (No Agent Loaded)

- Status: PASS
- Working directory: `/home/yattishr/Projects/snappy-putty`
- Launch: `snappy shell`
- Input:
```text
status
give me a file listing for the current directory
git status
```
- Expected checks:
  - Session Status
  - Directory Listing
  - Git Status
  - Agent feature mode: off
- Notes:
  - Baseline run executed from the repo root, which has no `.snappy/` and is a git checkout.
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
│ CWD: /home/yattishr/Projects/snappy-putty                                    │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────── Session Status ───────╮
│ Current state: IDLE         │
│ Active goal: (none)         │
│ Last route: (none)          │
│ Pending question: (none)    │
│ Pending plan: (none)        │
│ Awaiting confirmation: no   │
│ Last completed goal: (none) │
│ Last cancelled goal: (none) │
│ Last failed goal: (none)    │
│ Error message: (none)       │
│ Agent feature mode: off     │
│ Agent mode source: default  │
│ Agent: (none loaded)        │
╰─────────────────────────────╯
snappy> ╭───────────────────────────── Directory Listing ──────────────────────────────╮
│ my-sandbox/                                                                  │
│ mytests/                                                                     │
│ pyproject.toml                                                               │
│ README.md                                                                    │
│ sandbox                                                                      │
│ SKILLS.md                                                                    │
│ src/                                                                         │
│ TASKS.md                                                                     │
│ test-snappy-agent/                                                           │
│ tests/                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────────────────────── Goal ──────────────────────╮
│ give me a file listing for the current directory │
╰────────────────────── ask ───────────────────────╯
╭──────────────────────────────── Assumptions ─────────────────────────────────╮
│                                                                              │
│  • Using requested directory: .                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────── Plan ────────────────────────────────────╮
│                                                                              │
│  1 Resolve target directory - Determine which location to inspect.           │
│  2 Run safe read-only listing - Collect files/folders without changing       │
│    state.                                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
                                    Commands                                    
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Command                  ┃ Risk ┃ Explain                                    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ python-native listing: . │ LOW  │ Read-only listing performed via pathlib    │
│                          │      │ in-process.                                │
└──────────────────────────┴──────┴────────────────────────────────────────────┘
╭────────────────────────────────── Warnings ──────────────────────────────────╮
│                                                                              │
│  • Read-only local directory listing only; no state-changing commands were   │
│    executed.                                                                 │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭───────────────────────────────── Git Status ─────────────────────────────────╮
│ ## main...origin/main                                                        │
│  D .docs/agent_spec_v3/RUN_REGR_TEST_AGENT_SPEC_V3.md                        │
│  M src/snappy_putty/__pycache__/fs_ops.cpython-310.pyc                       │
│  M tests/__pycache__/test_render.cpython-310-pytest-9.0.2.pyc                │
│  M                                                                           │
│ tests/__pycache__/test_session_repl_subprocess.cpython-310-pytest-9.0.2.pyc  │
│  M tests/__pycache__/test_smoke.cpython-310-pytest-9.0.2.pyc                 │
│  M tests/__pycache__/test_state_machine.cpython-310-pytest-9.0.2.pyc         │
│ ?? .docs/RUN_REGR_TEST.md                                                    │
│ ?? .docs/agent_spec_v5/.RUN_REGR_M2_RULE_PRIORITY.md.swp                     │
│ ?? .docs/agent_spec_v5/REGR_TEST_AGENT_SPEC_V5_OUTPUT.md                     │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy>
```

### Test 2 — Agent Runtime Loads

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
status
agent
skills
rules
agent doctor
```
- Expected checks:
  - Agent feature mode: passive
  - Agent loaded: yes
  - Agent Summary
  - Loaded skills:
  - Loaded rules:
  - Agent Doctor
- Notes:
  - Executed with `SNAPPY_AGENT_MODE=passive` so loaded rules were active in-session.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
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
│ Agent name: Snappy Dev Agent                     │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 3                                  │
│ Enforceable rules: 2                             │
│ Informational rules: 1                           │
│ Policy tiers: block=1, confirm=1, warn=0, info=1 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
snappy> ╭────────── Agent Summary ──────────╮
│ Agent feature mode: passive       │
│ Agent loaded: yes                 │
│ Manifest present: yes             │
│ Agent name: Snappy Dev Agent      │
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
snappy> Loaded skills:
- copy [LOW]
snappy> Loaded rules:
- custom_note [custom_note] (informational)
- protect_project_root [protect_project_root] (enforceable:block)
- require_confirm [require_confirm] (enforceable:confirm)
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

### Test 3 — Clarification Lock

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md
show me all files
status
```
- Expected checks:
  - You have a pending question.
  - destination path>
  - Current state: CLARIFICATION
  - Active goal: copy README.md
  - Pending question: destination path>
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>You have a pending question.
Answer it, or type 'cancel' to abandon the current goal.
destination path>╭───────────────── Session Status ─────────────────╮
│ Current state: CLARIFICATION                     │
│ Active goal: copy README.md                      │
│ Last route: fs_mutation                          │
│ Pending question: destination path>              │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: (none)                      │
│ Last cancelled goal: (none)                      │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Snappy Dev Agent                     │
│ Agent version: 1                                 │
│ Agent mode: supervised                           │
│ Loaded skills: 1                                 │
│ Loaded rules: 3                                  │
│ Enforceable rules: 2                             │
│ Informational rules: 1                           │
│ Policy tiers: block=1, confirm=1, warn=0, info=1 │
│ Agent memory: present                            │
╰──────────────────────────────────────────────────╯
destination path>
```

### Test 4 — Clarification Accepts Answer

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md
tests/
NO
```
- Expected checks:
  - Goal
  - Planned Changes
  - Type YES to apply, or NO to cancel.
- Notes:
  - Second input was consumed as the destination answer and advanced to confirmation.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>╭────────── Goal ──────────╮
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

### Test 5 — Cancel Works During Clarification

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md
cancel
status
```
- Expected checks:
  - Cleared pending question/plan state.
  - Current state: IDLE
  - Pending question: (none)
  - Last cancelled goal: copy README.md
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>Cleared pending question/plan state.
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: IDLE                              │
│ Active goal: (none)                              │
│ Last route: builtin_cancel                       │
│ Pending question: (none)                         │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: (none)                      │
│ Last cancelled goal: copy README.md              │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Snappy Dev Agent                     │
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

### Test 6 — require_confirm Rule

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md to README-copy.md
NO
status
```
- Expected checks:
  - Type YES to apply, or NO to cancel.
  - Cancelled. No pending action was applied.
  - Current state: IDLE
- Notes:
  - Verified `README-copy.md` was not created after declining confirmation.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────────── Goal ──────────────╮
│ copy README.md to README-copy.md │
╰──────────────────────────────────╯
╭─────────────────────────────────── Policy ───────────────────────────────────╮
│                                                                              │
│  • Loaded rules require confirmation before filesystem changes are applied.  │
╰──────────────────────────────────────────────────────────────────────────────╯
                  Planned Changes                   
┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Op  ┃ Action ┃ From      ┃ To             ┃ Risk ┃
┡━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━┩
│ op1 │ copy   │ README.md │ README-copy.md │ LOW  │
└─────┴────────┴───────────┴────────────────┴──────┘
╭─────────────────────────────── Plan Warnings ────────────────────────────────╮
│                                                                              │
│  • none                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
Type YES to apply, or NO to cancel.
snappy> ╭───────────── Apply Cancelled ─────────────╮
│ Cancelled. No pending action was applied. │
╰───────────────────────────────────────────╯
snappy> ╭─────────────────── Session Status ────────────────────╮
│ Current state: IDLE                                   │
│ Active goal: (none)                                   │
│ Last route: fs_mutation                               │
│ Pending question: (none)                              │
│ Pending plan: (none)                                  │
│ Awaiting confirmation: no                             │
│ Last completed goal: (none)                           │
│ Last cancelled goal: copy README.md to README-copy.md │
│ Last failed goal: (none)                              │
│ Error message: (none)                                 │
│ Agent feature mode: passive                           │
│ Agent mode source: environment                        │
│ Agent name: Snappy Dev Agent                          │
│ Agent version: 1                                      │
│ Agent mode: supervised                                │
│ Loaded skills: 1                                      │
│ Loaded rules: 3                                       │
│ Enforceable rules: 2                                  │
│ Informational rules: 1                                │
│ Policy tiers: block=1, confirm=1, warn=0, info=1      │
│ Agent memory: present                                 │
╰───────────────────────────────────────────────────────╯
snappy>
```

### Test 7 — protect_project_root Rule

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md to /
```
- Expected checks:
  - Policy Block
  - Operation blocked by rule: protect_project_root
- Notes:
  - Added `protect_project_root.md` to the temp agent fixture because the checked-in fixture did not include it.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
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

### Test 8 — no_active_mode Rule

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_no_active`
- Launch: `snappy shell`
- Input:
```text
agent mode active
agent mode
```
- Expected checks:
  - Active mode is disabled by the loaded agent rules.
  - Current: passive
- Notes:
  - Used a dedicated temp repo that adds `no_active_mode.md`.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_no_active                          │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> Active mode is disabled by the loaded agent rules.
snappy> ╭──── Agent Mode ─────╮
│ Current: passive    │
│ Source: environment │
╰─────────────────────╯
snappy>
```

### Test 9 — Informational Rule

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
rules
agent
agent doctor
```
- Expected checks:
  - custom_note
  - informational
  - Agent Doctor
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
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
│ Agent name: Snappy Dev Agent      │
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

### Test 10 — Agent Mode Control

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_modes`
- Launch: `snappy shell`
- Input:
```text
agent mode
agent mode passive
agent mode active
agent mode off
```
- Expected checks:
  - Current: passive
  - Agent mode set to: passive (session)
  - Agent mode set to: active (session)
  - Agent mode set to: off (session)
- Notes:
  - Used the agent fixture without `no_active_mode.md` so active mode switching could be exercised.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_modes                              │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭──── Agent Mode ─────╮
│ Current: passive    │
│ Source: environment │
╰─────────────────────╯
snappy> Agent mode set to: passive (session)
snappy> Agent mode set to: active (session)
snappy> Agent mode set to: off (session)
snappy>
```

### Test 11 — Clarification + Rules Together

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
copy README.md
show me all files
cancel
status
```
- Expected checks:
  - You have a pending question.
  - Cleared pending question/plan state.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>You have a pending question.
Answer it, or type 'cancel' to abandon the current goal.
destination path>Cleared pending question/plan state.
snappy> ╭───────────────── Session Status ─────────────────╮
│ Current state: IDLE                              │
│ Active goal: (none)                              │
│ Last route: builtin_cancel                       │
│ Pending question: (none)                         │
│ Pending plan: (none)                             │
│ Awaiting confirmation: no                        │
│ Last completed goal: (none)                      │
│ Last cancelled goal: copy README.md              │
│ Last failed goal: (none)                         │
│ Error message: (none)                            │
│ Agent feature mode: passive                      │
│ Agent mode source: environment                   │
│ Agent name: Snappy Dev Agent                     │
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

### Test 12 — Status Integrity

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5/agent_runtime`
- Launch: `snappy shell`
- Input:
```text
status
```
- Expected checks:
  - Current state:
  - Active goal:
  - Pending question:
  - Last route:
  - Last completed goal:
  - Agent feature mode:
  - Loaded rules:
- Notes:
  - Current status output does not include a literal `Agent loaded:` line; agent presence is reflected by agent metadata rows.
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
│ CWD: /tmp/snappy_regr_agent_spec_v5/agent_runtime                            │
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
│ Agent name: Snappy Dev Agent                     │
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

### Test 13 — CLI Commands Still Work

- Status: PASS
- Working directory: `/tmp/snappy_regr_agent_spec_v5`
- Launch: `multiple`
- Input:
```text
snappy --help
snappy init
snappy skills
snappy rules
snappy agent
snappy agent-doctor
```
- Expected checks:
  - PASS: snappy --help -> expected `Snappy PuTTy CLI`
  - PASS: snappy init -> expected `Initialized agent scaffold`
  - PASS: snappy skills -> expected `Loaded skills:`
  - PASS: snappy rules -> expected `Loaded rules:`
  - PASS: snappy agent -> expected `Agent Summary`
  - PASS: snappy agent-doctor -> expected `Agent Doctor`
- Notes:
  - The documented `snappy agent doctor` invocation maps to the actual Typer command `snappy agent-doctor` outside the REPL.
- Stdout excerpt:
```text
$ snappy --help
Usage: python -m snappy_putty.cli [OPTIONS] COMMAND [ARGS]...                  
                                                                                
 Snappy PuTTy CLI                                                               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ ask           Generate suggestion-only plan for an intent.                   │
│ explain       Explain a command with safety-aware suggestions.               │
│ doctor        Show local context snapshot for planning.                      │
│ agent         Show a summary of the currently loaded .snappy agent.          │
│ agent-doctor  Inspect the .snappy runtime surface and loaded agent           │
│               artifacts.                                                     │
│ init          Scaffold a minimal .snappy/ directory.                         │
│ skills        List passive skills loaded from .snappy/skills/*.md.           │
│ rules         List passive rules loaded from .snappy/rules/*.md.             │
│ shell         Start interactive REPL mode.                                   │
╰──────────────────────────────────────────────────────────────────────────────╯

$ snappy init
Initialized agent scaffold at /tmp/snappy_regr_agent_spec_v5/cli_init/.snappy

$ snappy skills
Loaded skills:
- copy [LOW]

$ snappy rules
Loaded rules:
- custom_note [custom_note] (informational)
- protect_project_root [protect_project_root] (enforceable:block)
- require_confirm [require_confirm] (enforceable:confirm)

$ snappy agent
╭────────── Agent Summary ──────────╮
│ Agent feature mode: passive       │
│ Agent loaded: yes                 │
│ Manifest present: yes             │
│ Agent name: Snappy Dev Agent      │
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

$ snappy agent-doctor
╭────────────────── Agent Doctor ──────────────────╮
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
```

### Test 14 — No Agent Mode Regression

- Status: PASS
- Working directory: `/home/yattishr/Projects/snappy-putty`
- Launch: `snappy shell`
- Input:
```text
copy README.md
cancel
status
```
- Expected checks:
  - Cleared pending question/plan state.
  - Current state: IDLE
  - Agent feature mode: off
- Notes:
  - Executed from the repo root without a `.snappy/` directory loaded.
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
│ CWD: /home/yattishr/Projects/snappy-putty                                    │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>Cleared pending question/plan state.
snappy> ╭────────── Session Status ───────────╮
│ Current state: IDLE                 │
│ Active goal: (none)                 │
│ Last route: builtin_cancel          │
│ Pending question: (none)            │
│ Pending plan: (none)                │
│ Awaiting confirmation: no           │
│ Last completed goal: (none)         │
│ Last cancelled goal: copy README.md │
│ Last failed goal: (none)            │
│ Error message: (none)               │
│ Agent feature mode: off             │
│ Agent mode source: default          │
│ Agent: (none loaded)                │
╰─────────────────────────────────────╯
snappy>
```

