# Snappy Regression Test Output

Run date: 2026-03-21

Execution notes:
- CLI used: `PYTHONPATH=src SNAPPY_PUTTY_NO_SPINNER=1 .venv/bin/python -m snappy_putty.cli shell`
- Each regression case was run in a fresh REPL session.
- `exit` was appended after each case only to terminate the REPL cleanly.
- Filesystem mutation cases that referenced `a.txt` were run in isolated temp directories with `a.txt` pre-created.
- Tests 10 and 11 were capped with a 12 second shell timeout because the CLI did not return.

## Summary

- PASS: 9
- FAIL: 2
- Failed tests:
  - 10. Git Write Safety
  - 11. Command Override After Ask

## Per-Test Results

### 1. Session Baseline

Status: PASS

Commands:
```text
status
```

Output excerpt:
```text
Current state: IDLE
Active goal: (none)
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected baseline state.

### 2. Clarification Flow (FS Intent)

Status: PASS

Commands:
```text
copy README.md
status
```

Output excerpt:
```text
destination path>
Current state: CLARIFICATION
Active goal: copy README.md
Pending question: destination path>
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected clarification state.

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
Cancelled. No pending action was applied.
Current state: IDLE
Active goal: (none)
Last cancelled goal: copy a.txt to c.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected cancel behavior.

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
Copied file: a.txt -> d.txt. Undo hint: `rm d.txt`.
Current state: IDLE
Active goal: (none)
Last completed goal: copy a.txt to d.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected completion state. `d.txt` was created.

### 5. FS Failure Path

Status: PASS

Commands:
```text
copy to 
status
```

Output excerpt:
```text
Could not parse filesystem action. Try examples: copy A to B, move A to B, rename A to B, make a folder called X.
Current state: IDLE
Active goal: (none)
Last failed goal: copy to
Error message: Failed to parse filesystem action.
Pending question: (none)
Pending plan: (none)
```

Comparison: Matches expected failure handling.

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
destination path>
Cleared pending question/plan state.
Current state: IDLE
Active goal: (none)
Last cancelled goal: copy a.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected explicit cancel behavior.

### 7. Safe Inspect (Directory Listing)

Status: PASS

Commands:
```text
give me a file listing for the current directory
status
```

Output excerpt:
```text
Directory Listing
Current state: IDLE
Last route: safe_inspect
Last completed goal: give me a file listing for the current directory
Active goal: (none)
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no
```

Comparison: Matches expected safe inspect behavior.

### 8. Git Read: Status

Status: PASS

Commands:
```text
git status
status
```

Output excerpt:
```text
Git Status
Current state: IDLE
Last route: git_read
Last completed goal: git status
Active goal: (none)
Pending question: (none)
Pending plan: (none)
```

Comparison: Matches expected Git read behavior.

### 9. Git Read: Recent Commit

Status: PASS

Commands:
```text
show last 5 commits
status
```

Output excerpt:
```text
Recent Commits
Current state: IDLE
Last route: git_read
Last completed goal: show last 5 commits
Active goal: (none)
Pending question: (none)
Pending plan: (none)
```

Comparison: Matches expected Git read behavior.

### 10. Git Write Safety

Status: FAIL

Commands:
```text
git push
status
```

Observed output before timeout:
```text
snappy [ask]> [non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: max retries reached, giving up on this batch.
```

Comparison:
- PASS condition satisfied: no Git push was executed.
- FAIL condition: the CLI never returned local guidance or a clean status state within 12 seconds.
- FAIL condition: `status` was not processed because the first command blocked the REPL.

### 11. Command Override After Ask

Status: FAIL

Commands:
```text
git push
give me a file listing for the current directory
status
```

Observed output before timeout:
```text
snappy [ask]> [non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: request failed: [Errno -3] Temporary failure in name resolution
[non-fatal] Tracing: max retries reached, giving up on this batch.
```

Comparison:
- FAIL condition: the second command never ran because `git push` blocked in the ask path.
- FAIL condition: there was no override, no directory listing, and no final `IDLE` state.

## Root Cause Analysis

Primary root cause:
- Unsupported Git write intents are not classified separately. In [`src/snappy_putty/router.py:42`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/router.py#L42), `git push` does not match `parse_git_read_intent`, so it falls through to `ROUTE_ASK` at [`src/snappy_putty/router.py:79`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/router.py#L79).

Secondary root cause:
- The ask path is synchronous and blocks the REPL while it waits for the SDK call. In [`src/snappy_putty/cli.py:310`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py#L310) to [`src/snappy_putty/cli.py:313`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py#L313), `ROUTE_ASK` immediately calls `handle_ask()`. That then calls `plan_with_agent()` at [`src/snappy_putty/cli.py:369`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py#L369) to [`src/snappy_putty/cli.py:373`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/cli.py#L373).

Trigger for the hang:
- In [`src/snappy_putty/agent.py:485`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/agent.py#L485) to [`src/snappy_putty/agent.py:487`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/agent.py#L487), the code tries the OpenAI Agents SDK first for generic ask intents. In this environment, network access is restricted but `OPENAI_API_KEY` is present, so `git push` causes repeated trace/export retries before eventual fallback. During that time, the REPL cannot consume `status` or the next user command.

Behavioral impact:
- Test 10 fails because Git write requests are not rejected quickly and locally.
- Test 11 fails because the single-threaded ask flow prevents command override while the first ask request is blocked.

## Suggested Fixes

1. Add explicit Git write detection in the router.
   - Introduce a `git_write` or `unsupported_git_write` route for commands like `git push`, `git commit`, `git merge`, `git rebase`, `git reset`, `git tag -d`, and `git branch -D`.
   - Return immediate local guidance instead of sending those intents to the SDK.

2. Keep Git safety handling local and deterministic.
   - For Git write routes, print a short unsupported/safety message and move the session back to `IDLE`.
   - Record a stable route value so `status` reflects what happened.

3. Avoid SDK-first behavior for obviously unsupported local intents.
   - Short-circuit unsupported write operations before [`plan_with_agent()`](/home/yattishr/Projects/snappy-putty/src/snappy_putty/agent.py#L457) is called.
   - This removes network dependency from safety-critical rejection paths.

4. Add regression coverage for the failing path.
   - Add a subprocess REPL test for `git push` followed by `status`.
   - Add a subprocess REPL test for `git push` followed by a safe-inspect command to verify override behavior.

## Final Result

Overall result: FAIL

Failed tests:
- 10. Git Write Safety
- 11. Command Override After Ask
