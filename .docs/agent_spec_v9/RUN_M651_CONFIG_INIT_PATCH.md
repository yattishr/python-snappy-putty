# Snappy M6.5.1 Codex Patch Prompt

## Patch

**M6.5.1 — Config Init + Migration Polish**

## Goal

Improve `snappy init` and config initialization so Snappy creates or repairs `.snappy/snappy.yaml` safely, preserves existing project state, and explicitly enables detected skills.

No manual YAML editing should be required for normal setup.

---

## Problem

Current behaviour can leave users with legacy or malformed config like:

```yaml
name: vanilla-nodejs-rest-api
version: 1
mode: supervised
confirmations: true
dry_run: false
skills: []
rules: []
memory: true
```

But M6.5 expects structured config:

```yaml
version: 1

agent:
  name: ...
  mode: off

skills:
  enabled: []
  disabled: []
```

Also, `snappy init` should create a valid modern config automatically without overwriting existing skills.

---

## Required Behaviour

### 1. `snappy init` creates `.snappy/snappy.yaml`

When running:

```bash
snappy init
```

Snappy should:

- create `.snappy/` if missing
- create `.snappy/snappy.yaml` if missing
- preserve existing `.snappy/skills/`
- preserve existing `.snappy/memory/`
- preserve existing `.snappy/logs/`
- never delete user-created skill folders

If modern config already exists and validates:

```text
.snappy/snappy.yaml already exists and is valid. No changes made.
```

---

## 2. Existing skills must be explicitly enabled

If valid skills exist in:

```text
.snappy/skills/<skill>/SKILL.md
```

then generated config should include them under `skills.enabled`.

Example detected skills:

```text
codeguardian-review
frontend-design
doc-coauthoring
```

Generated config:

```yaml
skills:
  enabled:
    - codeguardian-review
    - doc-coauthoring
    - frontend-design
  disabled: []
```

If no valid skills exist:

```yaml
skills:
  enabled: []
  disabled: []
```

Important semantic change:

```yaml
skills:
  enabled: []
  disabled: []
```

means:

```text
No skills are explicitly enabled.
```

It must no longer mean “load all valid skills.”

---

## 3. Update skill loading semantics

Change skill loader behaviour:

- If config exists:
  - only skills listed in `skills.enabled` may load
  - skills listed in `skills.disabled` must not load
  - `disabled` wins over `enabled`
  - empty `enabled` means no enabled skills
- If config does not exist:
  - preserve backwards-compatible default behaviour if needed, but prefer warning that project config is missing
  - do not break existing tests unless they explicitly assume no config

This makes `snappy init` the explicit project setup step.

---

## 4. Legacy config migration

If `.snappy/snappy.yaml` exists but uses legacy flat fields:

```yaml
name:
mode:
confirmations:
dry_run:
skills: []
rules: []
memory: true
```

then `snappy init` should detect legacy format and migrate safely.

Expected behaviour:

- create backup before writing:
  - `.snappy/snappy.yaml.bak`
  - if that exists, use timestamped backup
- migrate known fields:
  - `name` -> `agent.name`
  - `mode`:
    - `active` -> `active`
    - `off` -> `off`
    - `supervised` -> `off`
    - `passive` -> `off`
    - unknown -> `off`
  - `confirmations: true` -> `rules.confirmation_required: true`
  - `memory: true` -> `memory.enabled: true`
- ignore unsupported `dry_run`, but warn
- replace invalid `skills: []` with detected skills under `skills.enabled`
- replace invalid `rules: []` with structured defaults

Print a useful message:

```text
Detected legacy Snappy config.
Backup written to .snappy/snappy.yaml.bak
Migrated config to current schema.
Detected 3 skills and enabled them.
```

---

## 5. `snappy config init` should share behaviour

`snappy config init` and `snappy init` should use the same underlying config initialization function.

Suggested function:

```python
init_project_config(root: Path, *, migrate: bool = True) -> InitConfigResult
```

Avoid duplicate logic.

---

## 6. Generated default config

Use only supported modes:

```yaml
version: 1

agent:
  name: <project-folder-name>
  mode: off
  description: Project-local Snappy configuration.

planning:
  allow_project_extensions: true
  prefer_small_steps: true
  inspect_before_mutation: true
  max_context_files: null

skills:
  enabled:
    # detected valid skills, sorted alphabetically
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

---

## 7. CLI output examples

### No config, skills exist

```text
Created .snappy/snappy.yaml
Detected 3 skills:
- codeguardian-review
- doc-coauthoring
- frontend-design
Enabled all detected skills by default.
```

### No config, no skills

```text
Created .snappy/snappy.yaml
No skills detected. skills.enabled is empty.
```

### Modern valid config exists

```text
.snappy/snappy.yaml already exists and is valid. No changes made.
```

### Legacy config exists

```text
Detected legacy Snappy config.
Backup written to .snappy/snappy.yaml.bak
Migrated config to current schema.
Enabled detected skills: codeguardian-review, frontend-design
```

---

## 8. Tests Required

Add or update tests for:

1. `snappy init` creates `.snappy/snappy.yaml`.
2. `snappy init` preserves existing skill folders.
3. Existing valid skills are listed under `skills.enabled`.
4. No skills means `enabled: []`.
5. `enabled: []` means no skills load when config exists.
6. `disabled` wins over `enabled`.
7. Legacy flat config is detected and migrated.
8. Migration writes backup.
9. `mode: supervised` migrates to `agent.mode: off`.
10. `confirmations: true` migrates to `rules.confirmation_required: true`.
11. Unsupported `dry_run` produces warning and is removed.
12. Existing valid modern config is not overwritten.
13. `snappy config init` shares the same behaviour.
14. Full test suite remains green.

Likely files:

```text
tests/test_config.py
tests/test_skills.py
tests/test_cli_init.py
```

Use existing test structure where appropriate.

---

## Acceptance Criteria

Done when:

- `snappy init` creates modern `.snappy/snappy.yaml`.
- Existing skills are explicitly enabled by default.
- Empty `skills.enabled` means no enabled skills when config exists.
- Existing skills/rules/memory/logs are preserved.
- Legacy flat config is migrated with backup.
- Invalid old modes like `supervised` safely become `off`.
- `snappy config validate` passes after init/migration.
- `snappy config init` uses same logic.
- Tests pass.

---

## Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
git diff --check
```

---

## Non-Goals

Do not implement:

- remote skill installation
- skill marketplace
- plugin system
- sandboxing
- M7 execution intelligence
- automatic skill downloading
- destructive cleanup of `.snappy/`

This is a polish patch, not a new architecture layer.
