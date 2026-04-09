# Snappy — Agent Spec V3: Safe Rule Enforcement

## Goal
Turn passive agent rules into active safeguards through a small, predefined set of runtime enforcement hooks.

This milestone must make rules operational **without**:
- changing core routing behavior
- allowing arbitrary rule-defined logic
- making markdown files executable
- introducing skill-based routing fallback
- introducing autonomy

Rules should become **declarative switches** that activate known internal protections.

---

## GLOBAL RULES

- Do not replace, rewrite, or remove any existing routing, parsing, prompting, state machine, planning, execution, or confirmation behavior unless a chunk explicitly states otherwise.
- Add Agent Spec V3 support incrementally and non-destructively.
- All new behavior must be additive only.
- Markdown rule files must not execute arbitrary logic.
- Rule files may declare rule identity and human-readable intent, but runtime behavior must be mapped only through predefined internal rule hooks.
- Existing commands and flows must continue to work exactly as before when no supported rule is loaded.
- If a rule is unknown, unsupported, or malformed, it must be ignored safely and surfaced as informational only.
- Do not implement skill-aware routing in this milestone.
- Do not implement persistent session resume in this milestone.
- Do not let rules modify agent mode persistence, filesystem layout, or planner internals outside approved hook points.

---

## MILESTONE SHAPE

This milestone introduces:

1. A rule registry that distinguishes:
   - loaded rules
   - supported/enforceable rules
   - unsupported/informational rules

2. A small internal rule hook system

3. First enforced rules:
   - `require_confirm`
   - `protect_project_root`
   - optional: `no_active_mode`

4. Visibility upgrades:
   - `status`
   - `agent`
   - `agent doctor`

5. Tests proving that rule enforcement works and that behavior is unchanged when rules are absent

---

## SUPPORTED RULES FOR V3

### 1. require_confirm
Intent:
All filesystem mutation operations must require confirmation before execution.

Enforcement:
- If a filesystem mutation reaches planning/execution, confirmation must be required.
- This rule strengthens an existing safety path.
- It must not weaken or bypass any current confirmation behavior.

Notes:
- If confirmation is already required, behavior remains the same.
- This rule is still valuable because it formalizes enforcement through the rule engine.

---

### 2. protect_project_root
Intent:
Prevent dangerous filesystem mutations targeting:
- `/`
- home directory
- project root
- equivalent dangerous top-level targets as already recognized by Snappy safety logic

Enforcement:
- Before mutation execution, inspect source/target paths as relevant
- If a protected path is targeted by a dangerous mutation, block execution
- Surface a clear safety message
- Preserve state appropriately
- Do not execute the operation

Notes:
- Use existing path safety helpers where possible
- Do not invent broad heuristics if existing safe logic already exists
- Keep this deterministic and narrow

---

### 3. no_active_mode (optional but recommended)
Intent:
Disallow switching the current session into `active` mode when this rule is loaded.

Enforcement:
- If user runs `agent mode active`
- and this rule is loaded/enforced
- reject the mode switch with a clear message

Example message:
Active mode is disabled by the loaded agent rules.

Notes:
- Session stays in current mode
- This is low-risk and useful for repo-specific governance

---

## RULE FILE CONTRACT

Rule markdown files remain simple and declarative.

Example:

# Rule: require_confirm

All filesystem mutations require confirmation before execution.

Runtime behavior must be determined by the rule identifier only:
- `require_confirm`
- `protect_project_root`
- `no_active_mode`

Do not parse free-form markdown into executable behavior.

---

## CHUNK 1 — Add enforceable rule classification

### Goal
Extend the rule registry so Snappy can distinguish between:
- loaded rules
- enforceable supported rules
- unsupported informational rules

### Requirements
- Keep loading `.snappy/rules/*.md` as it works today
- Parse rule name/identifier as today
- Add internal classification such as:
  - loaded
  - supported_for_enforcement = true/false
- Supported rule names for V3:
  - require_confirm
  - protect_project_root
  - no_active_mode
- Unsupported rules should still appear in `rules` output, but marked as informational or unsupported
- Do not enforce anything yet in this chunk

### Tests
1. supported rule is marked enforceable
2. unsupported rule is loaded but not enforceable
3. malformed rule still warns safely
4. no runtime behavior changes yet

---

## CHUNK 2 — Add internal rule hook system

### Goal
Create a small internal enforcement layer with predefined hook points.

### Requirements
- Add a rule evaluation mechanism that can answer questions like:
  - is `require_confirm` active?
  - is `protect_project_root` active?
  - is `no_active_mode` active?
- Keep this internal and deterministic
- Do not let rules inject arbitrary behavior
- Hook points should be explicit functions, for example:
  - before_filesystem_mutation_plan_or_execute(...)
  - before_agent_mode_change(...)
- Prefer a very small number of hooks
- Do not enforce anything outside these hooks

### Tests
1. supported loaded rules are visible to hook evaluator
2. unsupported rules do not activate hooks
3. absent rules produce default behavior

---

## CHUNK 3 — Enforce require_confirm

### Goal
Formalize confirmation enforcement through the rule hook system.

### Requirements
- On filesystem mutation flows, if `require_confirm` is active, confirmation must be required before execution
- Reuse existing confirmation mechanisms
- Do not duplicate confirmation flow logic
- If current behavior already requires confirmation, preserve existing UX
- This chunk is successful if confirmation is now governed by the rule engine at the relevant hook point

### Scope
- Filesystem mutation flows only
- Do not alter safe inspect, git read, or unrelated routes

### Tests
1. mutation with `require_confirm` loaded requires confirmation
2. cancellation still works
3. confirmation YES still executes
4. no regressions to existing mutation behavior
5. with no rule loaded, current default behavior remains unchanged

---

## CHUNK 4 — Enforce protect_project_root

### Goal
Block dangerous filesystem mutations against protected roots when the rule is active.

### Requirements
- Hook into mutation safety evaluation before execution
- Block dangerous targets involving:
  - `/`
  - home directory
  - project root
  - any already-defined protected targets in current Snappy logic
- Surface a clear message explaining that the rule blocked execution
- Preserve deterministic session state
- Do not execute the blocked operation
- Reuse existing path normalization/safety logic where possible

### Example message
Operation blocked by rule: protect_project_root

The requested filesystem mutation targets a protected path.

### Tests
1. dangerous mutation against project root is blocked when rule active
2. dangerous mutation against home/root is blocked when rule active
3. safe mutation still allowed
4. with rule absent, existing safety behavior remains unchanged
5. blocked operation does not mutate completion state incorrectly

---

## CHUNK 5 — Enforce no_active_mode

### Goal
Allow agent rules to restrict session mode changes to prevent `active` mode.

### Requirements
- When user runs:
  - `agent mode active`
- and `no_active_mode` is active
- reject the change with a clear message
- keep current mode unchanged
- `agent mode off` and `agent mode passive` remain allowed unless otherwise restricted in future milestones

### Tests
1. active mode switch blocked when rule loaded
2. passive mode switch still allowed
3. off mode switch still allowed
4. current session mode remains unchanged after blocked attempt

---

## CHUNK 6 — Visibility in status, agent, and agent doctor

### Goal
Make enforced rule state visible and inspectable.

### Requirements
Update outputs to distinguish between:
- loaded rules
- enforceable rules
- currently active enforced protections

#### status
Show concise rule info, for example:
- Loaded rules: require_confirm, protect_project_root
- Enforced rules: require_confirm, protect_project_root

#### agent
Show richer rule summary, including unsupported rules if present.

#### agent doctor
Report:
- rule files found
- supported enforceable rules
- unsupported informational rules
- any malformed rule files
- whether enforcement hooks are active

### Tests
1. status shows enforced rules when present
2. agent shows rule classification correctly
3. agent doctor reports supported vs unsupported rules
4. no-agent case remains clean

---

## CHUNK 7 — Regression and rule-specific smoke coverage

### Goal
Prove that V3 adds safe rule enforcement without destabilizing the CLI.

### Requirements
- Keep all existing regression coverage intact
- Add rule-specific smoke tests for:
  - require_confirm
  - protect_project_root
  - no_active_mode
- Verify that clarification lock behavior still works
- Verify that passive agent inspection still works
- Verify that session-only agent mode control still works
- Verify behavior remains unchanged when no supported rules are loaded

### Tests to include
1. no-rule baseline
2. require_confirm enforcement
3. protect_project_root enforcement
4. no_active_mode enforcement
5. unsupported rule remains informational only
6. existing REPL and CLI commands still behave as expected

---

## EXECUTION ORDER

Run the chunks in exact order from Chunk 1 to Chunk 7.

Do not begin the next chunk until the current chunk is implemented and complete.

After each chunk:
- stop
- summarize files changed
- summarize tests added or updated
- state any risks introduced
- do not continue automatically

---

## CHUNK COMPLETION RULE

After completing each chunk, provide:

- summary of files changed
- summary of logic added
- summary of tests added/updated
- any risks or edge cases observed
- confirmation whether existing regression tests still pass

---

## OUT OF SCOPE FOR V3

Do not implement any of the following in this milestone:
- skill-aware routing fallback
- rule-defined arbitrary planner behavior
- markdown-executed actions
- persistent session resume from memory/session.json
- agent-suggested clarification answers
- automatic command execution in active mode
- project-level mode persistence
- queueing/suspending multiple goals
- free-form rule DSL

---

## ACCEPTANCE CRITERIA

This milestone is complete when:

- supported rules are classified as enforceable
- rule enforcement is driven through explicit internal hook points
- `require_confirm` is operational through the rule engine
- `protect_project_root` is operational through the rule engine
- `no_active_mode` is operational if implemented
- unsupported rules remain informational only
- visibility surfaces show loaded vs enforced rules clearly
- existing regression tests still pass
- new rule-specific tests pass
- no routing or execution regressions are introduced outside intended rule hooks

---

## RECOMMENDED TEST RULE FILES

### .snappy/rules/require_confirm.md
# Rule: require_confirm

All filesystem mutations require confirmation before execution.

### .snappy/rules/protect_project_root.md
# Rule: protect_project_root

Prevent dangerous filesystem mutations targeting protected root paths.

### .snappy/rules/no_active_mode.md
# Rule: no_active_mode

Disallow switching this session into active agent mode.

### .snappy/rules/custom_note.md
# Rule: custom_note

This is an informational rule and should not be enforced by runtime hooks.
