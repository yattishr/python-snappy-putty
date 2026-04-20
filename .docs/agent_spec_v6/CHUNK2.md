M3.3 + M3.4 — ExecutionResult Model and Reflection Layer (Dependent on State Machine)
Implement only this chunk. Do not add features outside scope, even if they seem adjacent.

## Mission

Add a structured `ExecutionResult` object for all terminal loop outcomes, and add a reflection step that maps execution outcomes into terminal loop states.

This chunk is only about:
- `ExecutionResult`
- terminal outcome capture
- reflection step
- mapping result status to terminal state

Do not redesign planning.
Do not add autonomy, memory, skills, retries, or custom rule DSL.

---

## Preconditions

Assume explicit M3 loop states and transition enforcement already exist or are being introduced separately.

Relevant states:
- `EXECUTING`
- `REFLECTING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`
- `BLOCKED`
- `IDLE`

---

## Required `ExecutionResult` Model

Introduce a structured result object using the project’s preferred style (dataclass, TypedDict, or equivalent).

Minimum shape:

```python
{
  "goal": str,
  "status": "completed" | "failed" | "cancelled" | "blocked",
  "operations": [
    {
      "action": str,
      "status": "applied" | "skipped" | "failed",
      "message": str,
    }
  ],
  "error": str | None,
  "warnings": list[str],
}
```

## Requirements:

- must be created for every terminal loop outcome
- must be available to the reflection step
- must not be mutated once reflection begins

If a richer existing operation/apply result already exists, extend or adapt it instead of inventing an overlapping model.


## Required Reflection Behavior

Add a reflection step that maps ExecutionResult.status to terminal loop states:

- completed -> COMPLETED
- failed -> FAILED
- cancelled -> CANCELLED
- blocked -> BLOCKED

Reflection must:

- not replan
- not retry
- not create a new goal
- not mutate the plan
- not trigger execution

Reflection is terminal interpretation only.

## Integration Targets

Wire ExecutionResult into:

- successful execution/apply path
- execution failure path
- cancellation path
- policy-blocked path

Ensure all terminal outcomes flow through:
```
... -> REFLECTING -> terminal state -> IDLE
```


## Required Tests

Add or update tests for:

- successful execution produces ExecutionResult(status="completed")
- failed execution produces ExecutionResult(status="failed")
- cancelled flow produces ExecutionResult(status="cancelled")
- blocked flow produces ExecutionResult(status="blocked")
- reflection maps each result status to correct terminal state
- terminal handling returns the loop to IDLE


## Acceptance Criteria
- every terminal loop outcome produces an ExecutionResult
- reflection exists and maps outcome to terminal state
- no terminal path skips reflection
- no reflection path performs replanning or retries
- loop returns cleanly to IDLE


## Deliverables

Return:

- code changes
- tests
- concise summary of:
- where ExecutionResult is defined
- where it is produced
- how reflection is invoked
- any remaining gaps for loop orchestration
