# Snappy M6.5 Codex Implementation Prompt

## Milestone

**M6.5 — Agent Configuration Layer**

## Goal

Implement a project-level configuration layer for Snappy using `.snappy/snappy.yaml`.

M6.5 should allow each project to define its own Snappy agent identity, default behaviour, enabled/disabled skills, planning preferences, safety posture, memory settings, and logging defaults.

This milestone must remain local, deterministic, and configuration-focused.

Do **not** implement plugin installation, remote skill marketplaces, sandbox execution, autonomous loops, or full M8 tool/plugin systems.

---

## Current Context

Snappy already has:

- Core CLI / REPL
- Project inspection and snapshots
- Rules and confirmation flow
- Active planning
- M6 modular skills:
  - folder-based `.snappy/skills/<skill>/SKILL.md`
  - legacy flat skill support
  - `snappy skills`
  - `snappy skills inspect <name>`
  - `snappy skills validate [path]`
- M6.1 skill-aware project relevance classification:
  - `direct_project_work`
  - `project_extension`
  - `project_adaptation`
  - `unrelated`
  - skill metadata support:
    - `x-snappy.project_relationships`
    - `x-snappy.extension_targets`
    - `x-snappy.indicators`

M6.5 builds on that foundation.

---

## Core Principle

Project config may customize Snappy behaviour, but it must not weaken hard safety rules.

Use this precedence model:

```text
Built-in hard safety rules
  > Project config
  > Skill metadata
  > Planner suggestions
  > User request
```

If there is uncertainty, preserve safety.

---

## Required File

Support this file:

```text
.snappy/snappy.yaml
```

If the file does not exist, Snappy must behave exactly as it does today using safe built-in defaults.

---

## Example `.snappy/snappy.yaml`

```yaml
version: 1

agent:
  name: Snappy Dev Agent
  mode: off
  description: Project-local development assistant for this repo.

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: 8

skills:
  enabled:
    - frontend-design
    - doc-coauthoring
  disabled:
    - brand-guidelines

rules:
  confirmation_required: true
  allow_file_writes: true
  allow_shell_commands: false
  protected_paths:
    - .env
    - .git/
    - node_modules/
    - package-lock.json

memory:
  enabled: true
  snapshot_on_inspect: true

logging:
  level: info
  trace_enabled: true
```

---

## Implementation Requirements

### 1. Add Config Loader

Create a new module:

```text
src/snappy_putty/config.py
```

The module should provide:

```python
load_project_config(root: Path) -> SnappyConfig
load_effective_config(root: Path, env: Mapping[str, str] | None = None) -> SnappyConfig
validate_config(config: SnappyConfig) -> list[ConfigIssue]
```

The exact type names may be adjusted to match the existing codebase style.

The loader must:

- Look for `.snappy/snappy.yaml`
- Return safe defaults if the file does not exist
- Parse YAML safely
- Handle malformed YAML gracefully
- Preserve useful validation messages
- Avoid crashing normal CLI workflows due to non-critical config issues

Use PyYAML if already available. If not, add minimal YAML support in the same way the project already handles dependencies.

---

### 2. Define Built-In Defaults

If no config exists, behaviour should remain unchanged.

Suggested defaults:

```yaml
version: 1

agent:
  name: Snappy
  mode: off
  description: ""

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: null

skills:
  enabled: []
  disabled: []

rules:
  confirmation_required: true
  allow_file_writes: true
  allow_shell_commands: false
  protected_paths:
    - .env
    - .git/

memory:
  enabled: true
  snapshot_on_inspect: true

logging:
  level: info
  trace_enabled: true
```

Important:

- `enabled: []` should mean “no explicit allowlist; load all valid skills unless disabled.”
- `disabled: []` should mean no skills are disabled.
- `allow_shell_commands: false` must not be interpreted as disabling existing safe/internal commands unless the current architecture already supports shell execution policies.

---

### 3. Config Schema

Support these top-level fields:

```yaml
version:
agent:
planning:
skills:
rules:
memory:
logging:
```

Unknown top-level fields should produce warnings, not hard failures.

#### `version`

Required if config file exists.

Valid:

```yaml
version: 1
```

Unsupported versions should produce a validation error.

#### `agent`

Fields:

```yaml
agent:
  name: string
  mode: off | active
  description: string
```

Rules:

- Valid modes are only `off` and `active`.
- `passive` is no longer supported and should be treated as invalid.
- Invalid `mode` should fall back to safe default `off` and emit validation warning/error.
- Do not allow config to silently force unsafe active execution if current CLI/session explicitly says otherwise.
- Session/CLI explicit mode should override project config.

#### `planning`

Fields:

```yaml
planning:
  allow_project_extensions: boolean
  prefer_small_steps: boolean
  inspect_before_mutation: boolean
  max_context_files: integer | null
```

Rules:

- `allow_project_extensions: false` should make M6.1 project-extension classification more conservative.
- `inspect_before_mutation: true` should reinforce existing behaviour.
- `max_context_files` should be passed into context selection/planning if applicable, but do not destabilize existing context discovery.

#### `skills`

Fields:

```yaml
skills:
  enabled:
    - skill-name
  disabled:
    - skill-name
```

Rules:

- If `enabled` is non-empty, only those skills should be loaded/considered.
- `disabled` always wins over `enabled`.
- Missing listed skills should produce a warning, not crash.
- Invalid skill names should produce a validation issue.
- Disabled skills must not appear in active planning matched-skills metadata.
- `snappy skills` should clearly show if a skill is disabled by config.

#### `rules`

Fields:

```yaml
rules:
  confirmation_required: boolean
  allow_file_writes: boolean
  allow_shell_commands: boolean
  protected_paths:
    - path
```

Rules:

- Project config may make rules stricter.
- Project config must not bypass hard safety protections.
- `confirmation_required: false` should not bypass existing high-risk or mutation confirmations unless the current rule system explicitly supports that safely.
- Prefer interpreting `confirmation_required: false` as a soft preference, not a hard override.
- `protected_paths` should be merged with built-in protected paths.
- Invalid paths should produce validation warnings.

#### `memory`

Fields:

```yaml
memory:
  enabled: boolean
  snapshot_on_inspect: boolean
```

Rules:

- `snapshot_on_inspect: false` may prevent automatic snapshot write if safe and compatible with current project inspector.
- If `memory.enabled: false`, avoid writing optional memory/history where possible, but do not break required runtime state unless that state already has a safe alternate.

#### `logging`

Fields:

```yaml
logging:
  level: debug | info | warning | error
  trace_enabled: boolean
```

Rules:

- Unknown logging levels should fall back to `info`.
- `trace_enabled` should be passed where trace logging exists.
- Do not remove important error visibility.

---

## CLI Requirements

Add config commands.

Minimum required:

```bash
snappy config
snappy config init
snappy config validate
```

Optional but useful:

```bash
snappy config explain
```

### `snappy config`

Show the effective config for the current project.

It should include:

- Config source:
  - defaults only
  - `.snappy/snappy.yaml`
- Agent name
- Agent mode
- Planning settings
- Skill enabled/disabled settings
- Rule settings
- Memory settings
- Logging settings
- Validation warnings/errors if present

### `snappy config init`

Create:

```text
.snappy/snappy.yaml
```

Rules:

- Create `.snappy/` if missing.
- Do not overwrite an existing config unless there is already an existing project convention for force flags.
- If config exists, print a friendly message saying it already exists.
- Generated config should be safe and minimal.

Suggested generated config:

```yaml
version: 1

agent:
  name: Snappy
  mode: off
  description: Project-local Snappy configuration.

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: null

skills:
  enabled: []
  disabled: []

rules:
  confirmation_required: true
  allow_file_writes: true
  allow_shell_commands: false
  protected_paths:
    - .env
    - .git/

memory:
  enabled: true
  snapshot_on_inspect: true

logging:
  level: info
  trace_enabled: true
```

### `snappy config validate`

Validate `.snappy/snappy.yaml`.

Output should include:

- Valid/invalid status
- Warnings
- Errors
- Unknown fields
- Missing referenced skills
- Invalid mode/logging values
- Unsafe attempted overrides if detected

Do not require skills to exist for config validation to run, but warn when referenced skills are missing.

### `snappy config explain` optional

Explain how project config affects Snappy behaviour.

This can be simple, for example:

```text
This project uses off mode by default.
Project extensions are allowed.
Skills are loaded from .snappy/skills unless disabled.
File writes require confirmation.
Protected paths: .env, .git/
```

---

## Skill Integration

Update skill loading so it accepts effective config.

Requirements:

- Respect `skills.enabled`
- Respect `skills.disabled`
- `disabled` wins over `enabled`
- CLI output should make disabled/missing skill configuration understandable
- Planning should only receive enabled/allowed skills
- Disabled skills must not match project relevance
- Disabled skills must not appear in LLM planning context
- Existing behaviour should remain unchanged when no config exists

Example:

```yaml
skills:
  enabled:
    - frontend-design
  disabled:
    - brand-guidelines
```

Expected:

- `frontend-design` loads if present and valid
- `doc-coauthoring` does not load because enabled list is an allowlist
- `brand-guidelines` does not load because disabled wins
- `snappy skills` should show enough information to make this obvious

---

## Planning Integration

Effective config should be available to active planning.

Planning should be able to use:

```yaml
planning:
  allow_project_extensions
  prefer_small_steps
  inspect_before_mutation
  max_context_files
```

Requirements:

- `allow_project_extensions: false` should make project-extension classification more conservative.
- Direct project work should still work.
- Unrelated rejection should still work.
- Skill-aware classification should respect skill toggles.
- `inspect_before_mutation: true` should reinforce plan-first/inspect-first behaviour.
- `max_context_files` should be passed to context selection if there is a clean integration point.

Do not rewrite the planner unnecessarily.

---

## Rule Integration

Effective config should be available to the rule / confirmation layer where appropriate.

Requirements:

- Merge configured `protected_paths` with built-in protected paths.
- Do not allow project config to remove built-in hard protections.
- Do not allow project config to bypass existing high-risk confirmations.
- If `confirmation_required: false`, handle carefully:
  - It may reduce prompts only for safe read-only actions if architecture supports it.
  - It must not skip mutation confirmations.
  - It must not skip protected-path or high-risk confirmations.
- If rule integration is not yet cleanly available, store parsed config and expose it to CLI/planner now, then add TODO comments/tests for later safe integration. Do not hack around safety.

---

## Environment Overrides

Support minimal environment overrides only if straightforward.

Suggested:

```bash
SNAPPY_AGENT_MODE=off|active
SNAPPY_DISABLE_PROJECT_CONFIG=1
```

Rules:

- `SNAPPY_DISABLE_PROJECT_CONFIG=1` should ignore `.snappy/snappy.yaml` and use defaults/env overrides.
- `SNAPPY_AGENT_MODE` should override project config but not explicit CLI/session mode.
- Invalid env values should warn and fall back safely.

If env handling is already centralized elsewhere, integrate there. Otherwise keep this minimal.

---

## Error Handling

Bad config must not create weird half-broken behaviour.

Cases:

- Missing config → use defaults
- Malformed YAML → show validation error, use defaults or safest partial config
- Unsupported version → show validation error, use defaults
- Unknown fields → warning
- Invalid mode → warning/error, fallback to passive
- Invalid logging level → warning, fallback to info
- Invalid skills list type → warning/error, treat as empty list
- Missing enabled skill → warning
- Disabled unknown skill → warning
- Config tries to weaken hard safety → warning, ignore unsafe override

---

## Tests Required

Add new tests, likely:

```text
tests/test_config.py
```

Also update existing tests where needed:

```text
tests/test_skills.py
tests/test_active_mode_v1.py
tests/test_context_discovery.py
```

### Config loader tests

Cover:

1. Missing config returns defaults.
2. Valid config loads correctly.
3. Malformed YAML produces validation issue and safe fallback.
4. Unsupported version produces validation issue.
5. Unknown top-level field produces warning.
6. Invalid agent mode falls back to off.
7. Invalid logging level falls back to info.
8. Protected paths merge with defaults.
9. Env disables project config.
10. Env agent mode overrides project config.

### CLI tests

Cover:

1. `snappy config` shows effective config.
2. `snappy config init` creates `.snappy/snappy.yaml`.
3. `snappy config init` does not overwrite existing config.
4. `snappy config validate` reports valid config.
5. `snappy config validate` reports malformed config.
6. Optional: `snappy config explain` prints human-readable summary.

### Skills integration tests

Cover:

1. No config → existing skill loading unchanged.
2. `skills.enabled` allowlist filters skills.
3. `skills.disabled` blocks skill.
4. Disabled wins over enabled.
5. Missing configured skill produces warning.
6. Disabled skill does not appear in active planning matched skills.
7. Disabled skill does not influence M6.1 project relevance.

### Planning integration tests

Cover:

1. `allow_project_extensions: true` allows project-extension request where appropriate.
2. `allow_project_extensions: false` makes project-extension request conservative.
3. Direct project work still works when extensions are disabled.
4. Unrelated request remains rejected.
5. Planner metadata includes relevant config source/details if existing metadata pattern supports it.

### Safety tests

Cover:

1. `confirmation_required: false` does not bypass mutation confirmation.
2. Config cannot unprotect built-in protected paths.
3. Disabled skill cannot cause execution or confirmation bypass.
4. Project config cannot weaken hard safety rules.

---

## Acceptance Criteria

M6.5 is complete when:

- `.snappy/snappy.yaml` is supported.
- Missing config preserves existing behaviour.
- Config loader, defaults, and validation exist.
- `snappy config` displays effective config.
- `snappy config init` creates a safe starter config.
- `snappy config validate` reports useful validation output.
- Skills can be enabled/disabled through config.
- Skill toggles affect skill listing, planning, and project relevance.
- Active planning receives effective config.
- Planning can respect `allow_project_extensions`.
- Protected paths are merged safely.
- Unsafe config attempts are warned and ignored.
- Tests cover valid, missing, malformed, restrictive, and unsafe config cases.
- Full test suite passes.

---

## Explicit Non-Goals

Do not implement:

- Remote config sync
- User profiles
- Skill marketplace
- `snappy install <skill-pack>`
- Plugin runtime
- External tool installation
- Sandboxed execution
- Full formal tool abstraction
- Autonomous multi-step loops
- Cloud registry
- Policy server
- Secrets management

Those belong later, especially M8.

---

## Suggested Implementation Order

1. Add `config.py` with defaults, types, loader, validator.
2. Add tests for config loading/validation.
3. Add CLI commands:
   - `snappy config`
   - `snappy config init`
   - `snappy config validate`
4. Wire effective config into skill loading.
5. Add skill filtering tests.
6. Wire effective config into active planner/project relevance.
7. Add planning/relevance tests.
8. Wire safe rule/protected-path config where cleanly possible.
9. Add safety tests.
10. Run full verification.

---

## Verification Commands

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Expected:

- Existing tests remain green.
- New tests cover M6.5 behaviour.
- No regression in M6/M6.1 skill behaviour.
- No confirmation bypass.
- No unsafe config weakening.

---

## Final Implementation Note

Keep M6.5 boring and deterministic.

This milestone is not about making Snappy more autonomous.

It is about making Snappy project-aware, inspectable, configurable, and safer to operate across different repositories.

The correct mental model:

```text
M6 gave Snappy capabilities.
M6.1 taught Snappy how capabilities relate to project extensions.
M6.5 gives each project control over which capabilities and behaviours are allowed.
```
