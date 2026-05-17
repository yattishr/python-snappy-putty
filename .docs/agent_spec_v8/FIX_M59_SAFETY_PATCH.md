# Snappy M5.9 Final Safety Patch — Destructive Cleanup Phrase Detection

## Goal

Catch destructive cleanup-style requests before context discovery or planning.

## Problem

This input:

```text
help me clean the entire filesystem
```

entered context discovery before being rejected.

It should be blocked immediately by destructive preflight.

## Required Fix

Extend destructive intent detection to catch broad cleanup/reset phrases.

Add broad destructive patterns:

```text
clean the entire filesystem
clean entire filesystem
clean the whole filesystem
clean whole filesystem
clean the entire machine
clean entire machine
clean everything
clean all files
clean all data
wipe environment
reset the environment
reset environment
reset everything
remove all artifacts
delete all artifacts
purge all artifacts
```

These must route to:

```text
destructive_or_high_risk_intent
```

before:

```text
context discovery
repo map
LLM planning
safe operation routing
```


## Expected Behavior

For:

```text
help me clean the entire filesystem
```

Expected:

```text
I can’t help with cleaning, deleting, or wiping an entire filesystem.

That request is destructive and unsafe.

No action was taken.
```

State:

```text
IDLE
active_goal = none
pending_plan = none
last_blocked_goal = help me clean the entire filesystem
block_reason = destructive_intent
```


## Tests

Add tests for:

```text
help me clean the entire filesystem
reset the environment
clean everything
remove all artifacts
```

Expected:

```text
- blocked immediately
- no context discovery
- no LLM call
- no plan created
- state remains/returns IDLE
```


## Verification

Run:

```python
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

## Non-Negotiable

Broad cleanup/reset requests must never reach planning.
