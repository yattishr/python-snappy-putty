# Agent Spec V4 Regression Output

- Source spec: `.docs/agent_spec_v3/RUN_REGR_TEST_AGENT_SPEC_V3.md`
- Run date: `2026-04-11`
- Runner: `/home/yattishr/Projects/snappy-putty/.venv/bin/python`

## Test 1 — Baseline (No Agent Loaded)

- Result: **PASS**
- Checks passed for baseline shell without .snappy.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.A42S19FEb7                                                     │
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
│ README.md                                                                    │
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
│ ## master                                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> 
```

## Test 2 — Agent Runtime Loads

- Result: **PASS**
- Agent runtime loaded and surfaced through status/agent/skills/rules/doctor.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────────── Session Status ───────────────╮
│ Current state: IDLE                         │
│ Active goal: (none)                         │
│ Last route: (none)                          │
│ Pending question: (none)                    │
│ Pending plan: (none)                        │
│ Awaiting confirmation: no                   │
│ Last completed goal: (none)                 │
│ Last cancelled goal: (none)                 │
│ Last failed goal: (none)                    │
│ Error message: (none)                       │
│ Agent feature mode: passive                 │
│ Agent mode source: environment              │
│ Agent name: Fixture Agent                   │
│ Agent version: 1                            │
│ Agent mode: passive                         │
│ Loaded skills: 1                            │
│ Loaded rules: 1                             │
│ Enforceable rules: 0                        │
│ Informational rules: 1                      │
│ Agent memory: present                       │
│ Agent memory session keys: last_goal, notes │
╰─────────────────────────────────────────────╯
snappy> ╭──────────── Agent Summary ────────────╮
│ Agent feature mode: passive           │
│ Agent loaded: yes                     │
│ Manifest present: yes                 │
│ Agent name: Fixture Agent             │
│ Version: 1                            │
│ Agent mode: passive                   │
│ Loaded skills: 1                      │
│ Loaded rules: 1                       │
│ Enforceable rules: 0                  │
│ Informational rules: 1                │
│ Memory present: yes                   │
│ Session memory keys: last_goal, notes │
╰───────────────────────────────────────╯
snappy> Loaded skills:
- Docker Logs [low]
snappy> Loaded rules:
- Confirm Destructive Actions [confirm_destructive_actions] (informational)
snappy> ╭─────── Agent Doctor ────────╮
│ Agent feature mode: passive │
│ .snappy directory: present  │
│ Manifest file: present      │
│ Manifest parse: ok          │
│ Skills directory: present   │
│ Loaded skills: 1            │
│ Rules directory: present    │
│ Loaded rules: 1             │
│ Enforceable rules: 0        │
│ Informational rules: 1      │
│ Memory directory: present   │
│ Session file: present       │
│ Session parse: ok           │
╰─────────────────────────────╯
snappy> 
```

## Test 3 — Clarification Lock

- Result: **PASS**
- Clarification lock blocked the new intent and preserved state.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.A42S19FEb7                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>You have a pending question.
Answer it, or type 'cancel' to abandon the current goal.
destination path>╭────────── Session Status ───────────╮
│ Current state: CLARIFICATION        │
│ Active goal: copy README.md         │
│ Last route: fs_mutation             │
│ Pending question: destination path> │
│ Pending plan: (none)                │
│ Awaiting confirmation: no           │
│ Last completed goal: (none)         │
│ Last cancelled goal: (none)         │
│ Last failed goal: (none)            │
│ Error message: (none)               │
│ Agent feature mode: off             │
│ Agent mode source: default          │
│ Agent: (none loaded)                │
╰─────────────────────────────────────╯
destination path>
```

## Test 4 — Clarification Accepts Answer

- Result: **PASS**
- Clarification answer resumed normal planning flow.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.A42S19FEb7                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>╭────────── Goal ──────────╮
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
snappy> 
```

## Test 5 — Cancel Works During Clarification

- Result: **PASS**
- Cancel during clarification returned the session to IDLE cleanly.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.A42S19FEb7                                                     │
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

## Test 6 — require_confirm Rule

- Result: **PASS**
- require_confirm enforced confirmation and NO cancelled without file creation.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
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
│ Agent name: Fixture Agent                             │
│ Agent version: 1                                      │
│ Agent mode: passive                                   │
│ Loaded skills: 1                                      │
│ Loaded rules: 2                                       │
│ Enforceable rules: 1                                  │
│ Informational rules: 1                                │
│ Agent memory: present                                 │
│ Agent memory session keys: last_goal, notes           │
╰───────────────────────────────────────────────────────╯
snappy> 
```

## Test 7 — protect_project_root Rule

- Result: **PASS**
- protect_project_root blocked execution and avoided false completion.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
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
│ Agent name: Fixture Agent                                      │
│ Agent version: 1                                               │
│ Agent mode: passive                                            │
│ Loaded skills: 1                                               │
│ Loaded rules: 3                                                │
│ Enforceable rules: 2                                           │
│ Informational rules: 1                                         │
│ Agent memory: present                                          │
│ Agent memory session keys: last_goal, notes                    │
╰────────────────────────────────────────────────────────────────╯
snappy> 
```

## Test 8 — no_active_mode Rule

- Result: **FAIL**
- no_active_mode rule did not preserve the prior mode.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> Active mode is disabled by the loaded agent rules.
snappy> ╭─ Agent Mode ─╮
│ Agent Mode   │
╰──────────────╯
Current: passive
Source: environment

Select mode:
1. off
2. passive
3. active
Enter choice > Invalid mode. Choose: off, passive, active
snappy> 
```

## Test 9 — Informational Rule

- Result: **PASS**
- Informational rule was listed and did not alter behavior surfaces.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> Loaded rules:
- custom_note [custom_note] (informational)
- no_active_mode [no_active_mode] (enforceable)
- protect_project_root [protect_project_root] (enforceable)
- require_confirm [require_confirm] (enforceable)
- Confirm Destructive Actions [confirm_destructive_actions] (informational)
snappy> ╭──────────── Agent Summary ────────────╮
│ Agent feature mode: passive           │
│ Agent loaded: yes                     │
│ Manifest present: yes                 │
│ Agent name: Fixture Agent             │
│ Version: 1                            │
│ Agent mode: passive                   │
│ Loaded skills: 1                      │
│ Loaded rules: 5                       │
│ Enforceable rules: 3                  │
│ Informational rules: 2                │
│ Memory present: yes                   │
│ Session memory keys: last_goal, notes │
╰───────────────────────────────────────╯
snappy> ╭─────── Agent Doctor ────────╮
│ Agent feature mode: passive │
│ .snappy directory: present  │
│ Manifest file: present      │
│ Manifest parse: ok          │
│ Skills directory: present   │
│ Loaded skills: 1            │
│ Rules directory: present    │
│ Loaded rules: 5             │
│ Enforceable rules: 3        │
│ Informational rules: 2      │
│ Memory directory: present   │
│ Session file: present       │
│ Session parse: ok           │
╰─────────────────────────────╯
snappy> 
```

## Test 10 — Agent Mode Control

- Result: **FAIL**
- Agent mode control did not reflect expected transitions.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.A42S19FEb7                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭─ Agent Mode ─╮
│ Agent Mode   │
╰──────────────╯
Current: off
Source: default

Select mode:
1. off
2. passive
3. active
Enter choice > Invalid mode. Choose: off, passive, active
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
snappy> Agent mode set to: active (session)
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
│ Agent feature mode: active  │
│ Agent mode source: session  │
│ Agent: (none loaded)        │
╰─────────────────────────────╯
snappy> Agent mode set to: off (session)
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
│ Agent mode source: session  │
│ Agent: (none loaded)        │
╰─────────────────────────────╯
snappy> 
```

## Test 11 — Clarification + Rules Together

- Result: **PASS**
- Clarification lock, rules, and cancel remained compatible.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> destination path>You have a pending question.
Answer it, or type 'cancel' to abandon the current goal.
destination path>Cleared pending question/plan state.
snappy> ╭────────────── Session Status ───────────────╮
│ Current state: IDLE                         │
│ Active goal: (none)                         │
│ Last route: builtin_cancel                  │
│ Pending question: (none)                    │
│ Pending plan: (none)                        │
│ Awaiting confirmation: no                   │
│ Last completed goal: (none)                 │
│ Last cancelled goal: copy README.md         │
│ Last failed goal: (none)                    │
│ Error message: (none)                       │
│ Agent feature mode: passive                 │
│ Agent mode source: environment              │
│ Agent name: Fixture Agent                   │
│ Agent version: 1                            │
│ Agent mode: passive                         │
│ Loaded skills: 1                            │
│ Loaded rules: 5                             │
│ Enforceable rules: 3                        │
│ Informational rules: 2                      │
│ Agent memory: present                       │
│ Agent memory session keys: last_goal, notes │
╰─────────────────────────────────────────────╯
snappy> 
```

## Test 12 — Status Integrity

- Result: **PASS**
- Status retained the required diagnostic fields with agent metadata.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.hwUNhPLCY3                                                     │
│ Tools: git ✓ docker ✓ gcloud ✓ kubectl ✗ terraform ✗                         │
╰──────────────────────────────────────────────────────────────────────────────╯
snappy> ╭────────────── Session Status ───────────────╮
│ Current state: IDLE                         │
│ Active goal: (none)                         │
│ Last route: (none)                          │
│ Pending question: (none)                    │
│ Pending plan: (none)                        │
│ Awaiting confirmation: no                   │
│ Last completed goal: (none)                 │
│ Last cancelled goal: (none)                 │
│ Last failed goal: (none)                    │
│ Error message: (none)                       │
│ Agent feature mode: passive                 │
│ Agent mode source: environment              │
│ Agent name: Fixture Agent                   │
│ Agent version: 1                            │
│ Agent mode: passive                         │
│ Loaded skills: 1                            │
│ Loaded rules: 5                             │
│ Enforceable rules: 3                        │
│ Informational rules: 2                      │
│ Agent memory: present                       │
│ Agent memory session keys: last_goal, notes │
╰─────────────────────────────────────────────╯
snappy> 
```

## Test 13 — CLI Commands Still Work

- Result: **PASS**
- Core CLI commands worked outside the REPL without crashes.\n- Evidence:\n```text
                                                                                
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
---INIT---
Initialized agent scaffold at /tmp/tmp.A42S19FEb7/.snappy
---SKILLS---
Loaded skills:
- Docker Logs [low]
---RULES---
Loaded rules:
- custom_note [custom_note] (informational)
- no_active_mode [no_active_mode] (enforceable)
- protect_project_root [protect_project_root] (enforceable)
- require_confirm [require_confirm] (enforceable)
- Confirm Destructive Actions [confirm_destructive_actions] (informational)
---AGENT---
╭──────────── Agent Summary ────────────╮
│ Agent feature mode: passive           │
│ Agent loaded: yes                     │
│ Manifest present: yes                 │
│ Agent name: Fixture Agent             │
│ Version: 1                            │
│ Agent mode: passive                   │
│ Loaded skills: 1                      │
│ Loaded rules: 5                       │
│ Enforceable rules: 3                  │
│ Informational rules: 2                │
│ Memory present: yes                   │
│ Session memory keys: last_goal, notes │
╰───────────────────────────────────────╯
```

## Test 14 — No Agent Mode Regression

- Result: **FAIL**
- Core shell workflow regressed when no agent was loaded.\n- Evidence:\n```text
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
│ CWD: /tmp/tmp.w0nXzsYKuE                                                     │
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

## Summary

- Passed: **11**
- Failed: **3**
- Verdict: **FAIL**
