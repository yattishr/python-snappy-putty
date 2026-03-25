# Snappy Regression Test Output

Run date: 2026-03-25

Execution notes:
- CLI used: `PYTHONPATH=src SNAPPY_PUTTY_NO_SPINNER=1 /home/yattishr/Projects/snappy-putty/.venv/bin/python -m snappy_putty.cli shell`
- Each regression case was run in a fresh REPL session.
- `exit` was appended after each case only to terminate the REPL cleanly.
- Filesystem mutation cases that referenced `a.txt` were run in isolated temp directories with `a.txt` pre-created.
- Git-read and git-write cases were run inside a fresh temporary git repository with one initial commit.
- `SNAPPY_AGENT_MODE` was left unset, so the default feature mode (`off`) was used during regression execution.

## Summary

- PASS: 11
- FAIL: 0
- Failed tests: (none)

## Per-Test Results

### 1. Session Baseline

Status: PASS

Commands:
```text
status
```

Output excerpt:
```text
│ Current state: IDLE
│ Active goal: (none)
│ Last route: (none)
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 2. Clarification Flow (FS Intent)

Status: PASS

Commands:
```text
copy README.md
status
```

Output excerpt:
```text
│ Current state: CLARIFICATION
│ Active goal: copy README.md
│ Last route: fs_mutation
│ Pending question: destination path>
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 3. Confirmation Cancel Flow

Status: PASS

Commands:
```text
copy a.txt to c.txt
NO
status
```

Output excerpt:
```text
Type YES to apply, or NO to cancel.
│ Cancelled. No pending action was applied. │
│ Current state: IDLE
│ Active goal: (none)
│ Last route: fs_mutation
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: copy a.txt to c.txt
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome. Verified c.txt was not created.

### 4. Successful FS Execution

Status: PASS

Commands:
```text
copy a.txt to d.txt
YES
status
```

Output excerpt:
```text
Type YES to apply, or NO to cancel.
│ Current state: IDLE
│ Active goal: (none)
│ Last route: fs_mutation
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: copy a.txt to d.txt
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome. Verified d.txt was created.

### 5. FS Failure Path

Status: PASS

Commands:
```text
copy to
status
```

Output excerpt:
```text
snappy> Could not parse filesystem action. Try examples: copy A to B, move A to B,
│ Current state: IDLE
│ Active goal: (none)
│ Last route: fs_mutation
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: (none)
│ Last failed goal: copy to
│ Error message: Failed to parse filesystem action.
```

Comparison: Matches expected outcome.

### 6. Explicit Cancel Command

Status: PASS

Commands:
```text
copy a.txt
cancel
status
```

Output excerpt:
```text
snappy> destination path>Cleared pending question/plan state.
│ Current state: IDLE
│ Active goal: (none)
│ Last route: builtin_cancel
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: copy a.txt
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 7. Safe Inspect (Directory Listing)

Status: PASS

Commands:
```text
give me a file listing for the current directory
status
```

Output excerpt:
```text
snappy> ╭───────────────────────────── Directory Listing ──────────────────────────────╮
│ Current state: IDLE
│ Active goal: (none)
│ Last route: safe_inspect
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: give me a file listing for the current directory
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 8. Git Read: Status

Status: PASS

Commands:
```text
git status
status
```

Output excerpt:
```text
snappy> ╭───────────────────────────────── Git Status ─────────────────────────────────╮
│ Current state: IDLE
│ Active goal: (none)
│ Last route: git_read
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: git status
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 9. Git Read: Recent Commit

Status: PASS

Commands:
```text
show last 5 commits
status
```

Output excerpt:
```text
snappy> ╭─────────────────────────────── Recent Commits ───────────────────────────────╮
│ Current state: IDLE
│ Active goal: (none)
│ Last route: git_read
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: show last 5 commits
│ Last cancelled goal: (none)
│ Last failed goal: (none)
│ Error message: (none)
```

Comparison: Matches expected outcome.

### 10. Git Write Safety

Status: PASS

Commands:
```text
git push
status
```

Output excerpt:
```text
snappy> I don't recognize that command. Try 'help' to see what I can do.
│ Current state: IDLE
│ Active goal: (none)
│ Last route: unknown
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: (none)
│ Last cancelled goal: (none)
│ Last failed goal: git push
│ Error message: Unrecognized command
```

Comparison: Matches expected outcome. Verified no git status change before/after.

### 11. Command Override After Ask

Status: PASS

Commands:
```text
git push
give me a file listing for the current directory
status
```

Output excerpt:
```text
snappy> I don't recognize that command. Try 'help' to see what I can do.
snappy> ╭───────────────────────────── Directory Listing ──────────────────────────────╮
│ Current state: IDLE
│ Active goal: (none)
│ Last route: safe_inspect
│ Pending question: (none)
│ Pending plan: (none)
│ Awaiting confirmation: no
│ Last completed goal: give me a file listing for the current directory
│ Last cancelled goal: (none)
│ Last failed goal: git push
│ Error message: (none)
```

Comparison: Matches expected outcome.
