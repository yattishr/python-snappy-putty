M3.5 regression follow-up: command-shaped clarification input is still being accepted in the destination-path continuation flow.

Exact repro:

1. Run:
   copy README.md

2. At the pending clarification prompt:
   destination path>copy README.md README_manual_12.md

Actual behavior:
- Snappy accepts the full command-shaped input as clarification data
- It builds a malformed plan
- Goal becomes: `copy README.md to copy README.md README_manual_12.md`
- Destination becomes: `copy`
- It proceeds to CONFIRMATION

Expected behavior:
- Reject this as command-shaped clarification input
- Keep the workflow in CLARIFICATION
- Preserve the pending question
- Do not generate a plan
- Do not start confirmation
- Allow only:
  - a valid destination answer
  - or explicit control commands like `cancel`, `status`, `help`, `exit`

Please investigate why the current trust-boundary guard did not trigger for this exact `copy README.md` -> `destination path>` path, especially in the default/off mode shown by the session output.

Requirements:
- fix the actual route, not just adjacent clarification handlers
- add a regression test for this exact repro
- confirm whether the clarification protection currently depends on agent mode, route family, or a specific handler branch
- summarize the root cause clearly
