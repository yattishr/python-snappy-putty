# Snappy M5.6 — Plan Integrity Validator

## Goal

Ensure that plan refinements do NOT:

- break snapshot grounding
- introduce new files
- expand scope beyond original intent
- create internal inconsistencies

This is a **post-refinement validation layer**.

---

## Where It Runs

After ANY refinement:

```
refine plan
refine step <n>
```

Flow becomes:

```
refinement request
↓
apply refinement
↓
validate_plan_integrity(plan, snapshot)
↓
ACCEPT or REJECT
```

---

## Core Function

Add:

```python
def validate_plan_integrity(plan, snapshot) -> ValidationResult:
```

Return:

```python
ValidationResult(
    valid: bool,
    errors: list[str],
    warnings: list[str]
)
```

---

## Validation Rules

### 1. Snapshot Binding (HARD FAIL)

All referenced files must exist in snapshot:

```
step.files ⊆ snapshot.files
```

If not:

```
❌ Reject refinement
Reason: introduces files not present in project snapshot
```

---

### 2. No New Files / Directories (HARD FAIL)

Refinement must NOT introduce:

```
new file paths
new directories
```

Example (reject):

```
"add utils/logger.py"
```

---

### 3. Scope Restriction Only (HARD FAIL)

Refinement may:

```
✔ narrow scope
✔ reduce files
✔ specialize behavior
```

Refinement may NOT:

```
❌ add new steps
❌ expand to new modules
❌ increase file set
```

Check:

```
refined_files ⊆ original_files
```

---

### 4. Step Consistency (SOFT FAIL → WARNING)

Ensure:

```
- steps still reference valid files
- no empty steps
- step numbering still logical
```

If violated:

```
⚠️ Warning: refinement may have introduced inconsistencies
```

---

### 5. Plan Coherence (SOFT FAIL → WARNING)

If multiple refinements cause drift:

```
- unrelated steps
- contradictory instructions
```

Emit:

```
⚠️ Plan may no longer be coherent after multiple refinements
```

---

## Behavior on Validation Failure

If HARD FAIL:

```
Refinement rejected.

Reason:
- introduces files not present in snapshot

No changes were applied to the plan.
```

Do NOT mutate:

```
plan
session.json
history.md (except rejection event)
```

---

## Behavior on Warning

Allow refinement but show:

```
⚠️ Warning:
This refinement may reduce plan coherence.

You can continue refining or revert.
```

---

## History Logging

### Accepted refinement

```
## <timestamp>
Event: Plan refined
Change: <description>
Validation: passed
```

### Rejected refinement

```
## <timestamp>
Event: Plan refinement rejected
Reason: introduces_non_snapshot_files
Validation: failed
```

---

## Tests Required

### Test 1 — Reject new file

Input:

```
refine step 2 → "add utils/logger.py"
```

Expected:

- refinement rejected
- plan unchanged
- error message shown

---

### Test 2 — Allow narrowing

```
refine step 2 → "limit to CLI only"
```

Expected:

- refinement accepted
- plan updated

---

### Test 3 — Reject expansion

```
refine plan → "also update config files"
```

(if not in original plan)

Expected:

- rejected

---

### Test 4 — Multiple refinements coherence warning

After several refinements:

- plan still valid
- warning emitted

---

## Acceptance Criteria

Snappy must guarantee:

```
Refinements cannot:
- escape snapshot
- expand scope
- introduce hallucinated structure
```

And:

```
Every refinement is either:
✔ accepted safely
❌ rejected cleanly
⚠️ accepted with warning
```

---

## Non-Negotiable Principle

```
Refinement must NEVER become a hidden planning backdoor.
```

---

## Verification

Manual:

```
show plan
refine step 2 → add new file → should FAIL
refine step 2 → narrow scope → should PASS
refine multiple times → check warnings
```

---

## Outcome

With M5.6:

```
Plans become stable under pressure.
Refinement becomes safe.
User trust increases.
```

---

## Final Note

Without this layer:

> refinement = silent chaos

With this layer:

> refinement = controlled evolution
