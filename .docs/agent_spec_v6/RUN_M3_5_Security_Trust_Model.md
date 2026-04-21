# Snappy — M3.5 Security & Trust Model  
## Codex Implementation Prompt

You are implementing **M3.5 — Security & Trust Model** for the `snappy_putty` codebase.

## Mission

Introduce a bounded **Security & Trust Model** that hardens Snappy against unsafe execution caused by input-channel confusion, trust-boundary violations, and workflow-state corruption.

This patch should strengthen the existing supervised agent loop and pre-M4 workflow snapshot model.

This is **not** a broad security rewrite.
This is **not** authentication, encryption, permissions, or a general policy DSL.

---

## Scope

Implement the following:

1. Define and enforce trust boundaries in code comments / structure where appropriate
2. Enforce strict input-channel separation
3. Prevent command-shaped clarification input from being interpreted as clarification data
4. Preserve strict confirmation-input behavior
5. Ensure the control layer remains the final authority before execution
6. Enforce workflow-state integrity invariants
7. Add focused tests for security/trust behaviors

---

## Non-Goals

Do **not** implement any of the following:

- user authentication
- encryption
- user/role permissions
- external sandboxing
- generalized policy DSL
- memory persistence
- autonomous continuation
- broad UX redesign
- large-scale CLI refactor unrelated to trust/safety boundaries

Do not drift into M4, M5, M6, or Policy Engine v2.

---

## Problem Context

Snappy already has:
- a bounded supervised agent loop
- clarification and confirmation paths
- control-layer enforcement
- workflow snapshot stabilization work

However, the system still needs explicit trust-boundary enforcement.

Examples of risks this patch must address:

- clarification input being mistaken for command input
- command-shaped input being accepted as raw clarification data
- workflow state becoming inconsistent during guided input
- future continuation/memory work persisting unsafe or ambiguous state
- accidental execution paths that bypass the control layer

---

## Trust Model

### Trusted
- system code
- built-in control-layer logic
- internal lifecycle transitions
- workflow-state mutation helpers

### Semi-Trusted
- top-level user command input
- clarification answers
- confirmation responses

### Untrusted
- file contents
- `.snappy` rule files
- arbitrary free-text input beyond its expected channel
- future external data sources

This trust model does not need a runtime “trust enum” unless the code clearly benefits from it, but the implementation should reflect these boundaries.

---

## Required Security Guarantees

### Guarantee 1 — Clarification input is data-only
While a clarification question is pending:
- user input must be treated as an answer to that pending question
- command-shaped input must **not** be interpreted as a new executable command
- suspicious command-shaped input should be rejected, with the existing workflow preserved

Expected behavior:
- keep session in `CLARIFICATION`
- preserve active workflow
- preserve pending question
- do not generate a malformed plan
- do not begin a new goal
- allow `cancel` to abandon the current goal

### Guarantee 2 — Confirmation input is strict
While confirmation is pending:
- only exact confirmation values are accepted according to existing product rules
- all other input is rejected
- active workflow and pending plan remain intact
- no execution occurs

### Guarantee 3 — No execution bypass
No route may execute a filesystem mutation or similar controlled action unless it passes through the control layer and the existing confirmation/blocked flow where applicable.

### Guarantee 4 — Workflow integrity
At all times:
- at most one active workflow may exist
- clarification cannot start a new goal
- reflection cannot trigger execution
- blocked outcomes cannot silently downgrade to confirmation or success
- terminal cleanup must leave the workflow state coherent

---

## Implementation Targets

Focus on the parts of the codebase that currently mediate:
- REPL command intake
- clarification input handling
- confirmation input handling
- workflow snapshot mutation
- control-layer gating for execution
- status/state consistency where required for correctness

Likely files may include:
- `src/snappy_putty/cli.py`
- `src/snappy_putty/session.py`
- related tests

Use actual project structure rather than inventing parallel layers.

---

## Clarification Input Protection

Implement a guard for clarification input so that command-shaped input is rejected instead of being consumed as raw answer data.

### Required behavior

Given a pending clarification such as:
- destination path expected

If the user enters something like:
- `copy README.md README_manual_12.md`
- `move a b`
- `delete file.txt`
- other obvious command-like input

Then Snappy must:
- reject that input as clarification data
- keep the current clarification active
- prompt the user to answer the pending question or cancel
- avoid planning/execution based on the bad answer

### Important
Do not attempt to support “escape to new command” behavior in this patch.
Keep it strict:
- answer the pending question
- or type `cancel`

### Detection heuristic
Use a practical, bounded heuristic.
For example:
- if clarification expects a path-like answer and input begins with a recognized command verb or otherwise clearly matches command syntax, reject it

Do not overengineer NLP classification.
Keep the heuristic simple, deterministic, and testable.

---

## Confirmation Input Protection

Preserve the existing strict confirmation model.

Requirements:
- invalid confirmation input must not mutate or clear the pending workflow
- no new command may start while confirmation is pending
- status should remain coherent after invalid confirmation input

Do not loosen YES/NO behavior in this patch.

---

## Control Layer Enforcement

Audit and strengthen execution entry points so that controlled actions still must pass through the existing policy gate.

Requirements:
- no clarification continuation path may bypass control checks
- no confirmation path may bypass control checks
- no execution helper should be callable from an unguarded path if it performs controlled mutation

If a helper is already safe, leave it alone.
Only tighten paths where necessary.

---

## Workflow Integrity / Snapshot Safety

Use the active workflow snapshot as the authoritative in-flight workflow model.

Requirements:
- clarification rejection must not corrupt `active_workflow`
- invalid confirmation input must not corrupt `active_workflow`
- blocked / cancelled / completed cleanup must leave snapshot state coherent
- no branch should leave a half-updated workflow snapshot

If small helper methods improve integrity, add them.
Do not redesign the entire snapshot system.

---

## Suggested Implementation Strategy

### Step 1
Identify current clarification-input handling and where raw clarification text is converted into actionable planning data.

### Step 2
Add a bounded helper for detecting command-shaped input during clarification.
Possible names:
- `is_command_shaped_input(...)`
- `should_reject_clarification_input(...)`

Use project naming style.

### Step 3
Update clarification handling so rejected command-shaped input:
- preserves the current workflow
- does not start or plan a new goal
- returns the appropriate prompt/message

### Step 4
Audit confirmation handling and ensure strict behavior still holds under the snapshot model.

### Step 5
Audit execution paths for control-layer bypass risk and tighten only where needed.

### Step 6
Add tests.

---

## Required Tests

Add or update tests for at least:

1. **command-shaped clarification input is rejected**
   - begin a clarification flow
   - enter a full command instead of an answer
   - expect clarification to remain active
   - expect no malformed plan
   - expect no new goal

2. **normal clarification answer still works**
   - begin clarification flow
   - enter valid destination answer
   - expect planning/confirmation to proceed correctly

3. **invalid confirmation input preserves pending workflow**
   - begin confirmation flow
   - enter invalid input
   - expect confirmation to remain active
   - expect no execution
   - expect snapshot/session state to remain coherent

4. **new command during confirmation is rejected**
   - begin confirmation flow
   - enter command-shaped input
   - expect it to be treated as invalid confirmation input
   - expect no new goal

5. **blocked flow remains terminal and coherent**
   - blocked execution path
   - ensure workflow/result state remains consistent
   - ensure no downgrade into other flow types

6. **no execution bypass via clarification continuation**
   - ensure clarification completion still routes through planning + policy gate

7. **status/state integrity after trust-boundary rejection**
   - after rejected clarification or invalid confirmation input
   - status/session state remains truthful

---

## Acceptance Criteria

Implementation is complete only if all of the following are true:

- command-shaped clarification input is rejected
- clarification workflow remains active after rejection
- confirmation remains strict and preserves pending state on invalid input
- no new goal starts while clarification or confirmation is pending
- no malformed plan is generated from rejected clarification input
- control layer remains mandatory before execution
- active workflow snapshot remains coherent across rejection, blocking, cancellation, and success paths
- tests cover the required trust/safety behaviors

---

## Code Quality Rules

- preserve project style and naming
- keep the patch bounded
- do not introduce broad refactors unless directly required for trust correctness
- prefer deterministic guards over clever heuristics
- add comments only where they clarify trust-boundary logic
- do not add a large abstraction layer unless truly needed

---

## Deliverables

Return:

1. code changes
2. tests
3. concise implementation summary including:
   - files changed
   - how clarification-input rejection works
   - what trust/safety invariants are now enforced
   - any remaining follow-up items that should be tracked separately

---

## Final Principle

**Input channels are not interchangeable.**
Clarification input is not command input.
Confirmation input is not free text.
No execution without the control layer.
