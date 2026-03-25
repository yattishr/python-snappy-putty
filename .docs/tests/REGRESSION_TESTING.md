# Snappy Regression Checklist
This checklist ensures that Snappy’s single-goal state machine, routing, and execution flows remain stable after changes. Automate them via integration tests.

---
## 1. Session Baseline
```text
status
```

Expected Outcome:
Current state: IDLE
Active goal: (none)
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no

## 2. Clarification Flow (FS Intent)
```text
copy README.md
status
```

Expected Outcome:
Current state: CLARIFICATION
Active goal: copy README.md
Pending question: destination path>
Awaiting confirmation: no
Pending plan: (none)

## 3. Confirmation Cancel Flow
```text
copy a.txt to c.txt
NO
status
```

Expected Outcome:
Current state: IDLE
Active goal: (none)
Last cancelled goal: copy a.txt to c.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no

## 4. Successful FS Execution
```text
copy a.txt to d.txt
YES
status
```

Expected Outcome:
Current state: IDLE
Active goal: (none)
Last completed goal: copy a.txt to d.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no

## 5. FS Failure Path
```text
copy to 
status
```

Expected Outcome:
Current state: IDLE
Active goal: (none)
Last failed goal: copy to
Error message: Failed to parse filesystem action.
Pending question: (none)
Pending plan: (none)

## 6. Explicit Cancel Command
```text
copy a.txt 
cancel 
status
```

Expected Outcome:
Current state: IDLE
Active goal: (none)
Last cancelled goal: copy a.txt
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no

## 7. Safe Inspect (Directory Listing)
```text
give me a file listing for the current directory
status
```

Expected Outcome:
Directory listing is displayed
Current state: IDLE
Last route: safe_inspect
Last completed goal: give me a file listing for the current directory
Active goal: (none)
Pending question: (none)
Pending plan: (none)
Awaiting confirmation: no

## 8. Git Read: Status
```text
git status
status
```

Expected Outcome:
Git status output is displayed
Current state: IDLE
Last route: git_read
Last completed goal: git status
Active goal: (none)
Pending question: (none)
Pending plan: (none)

## 9. Git Read: Recent Commit
```text
show last 5 commits
status
```

Expected Outcome:
Commit list is displayed
Current state: IDLE
Last route: git_read
Last completed goal: show last 5 commits
Active goal: (none)
Pending question: (none)
Pending plan: (none)

## 10. Git Write Safety
```text
git push
status
```

Expected Outcome:
No Git write operation is executed
Falls back to safe guidance OR unsupported message
Current state is NOT stuck (may be CLARIFICATION or IDLE) 
No filesystem or Git mutation occurs 
No unintended side effects

## 11. Command Override After Ask
```text
git push
give me a file listing for the current directory
status
```

Expected Outcome:
Directory listing executes successfully
No contamination from previous git push intent
Last route: safe_inspect
Current state: IDLE
Last completed goal reflects the listing command
Active goal: (none)
Pending question: (none)
Pending plan: (none)

# Regression Red Flags
If any of the following occur, there is a regression:

- State stuck in PLANNING, EXECUTING, COMPLETED, FAILED, or CANCELLED
- Active goal not cleared after completion
- Pending question or plan persists after completion
- Git read commands routed incorrectly to ask
- New commands inherit previous intent context incorrectly
- Safe inspect does not update Last completed goal
- Git write commands are executed (this must NEVER happen)

---
