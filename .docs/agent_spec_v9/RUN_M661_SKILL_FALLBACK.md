# Snappy M6.6.1 Codex Patch Prompt

## Patch

**M6.6.1 — Disabled Skill Fallback Guard**

## Problem

When a request strongly matches a skill that is disabled by config, Snappy currently reports the disabled skill but still continues into a generic grounded plan.

Example:

```text
Matched task intent: code_review
No matching skill selected.
Skill disabled by config: codeguardian-review
Generating LLM-assisted grounded plan...
```

This is safe, but too quiet. Disabled skills should not feel partially ignored.

---

## Goal

If the best matching skill is disabled by config, Snappy must not silently continue.

It should clearly say the specialized skill is disabled, then ask whether to continue with a generic plan.

---

## Required Behaviour

### 1. Preserve disabled best-match metadata

Task routing should record:

- best matching skill before config filtering
- whether it was disabled by config
- score/confidence
- reason

Example:

```json
{
  "task_intent": "code_review",
  "selected_skills": [],
  "disabled_best_match": "codeguardian-review",
  "disabled_best_match_score": 1.51
}
```

---

### 2. Block silent fallback

If:

- task intent is recognized
- best skill match is disabled
- no suitable enabled skill is selected

then do not immediately generate a grounded plan.

Show:

```text
Matched task intent: code_review
Best matching skill is disabled by config: codeguardian-review
No specialized skill selected.
Continue with generic grounded planning? [YES/NO]>
```

---

### 3. YES continues generically

If user answers YES:

- continue with generic grounded planning
- selected skill remains none
- record metadata:
  - disabled_best_match
  - generic_fallback_confirmed: true

Print:

```text
Continuing without disabled skill: codeguardian-review
Generating generic grounded plan...
```

---

### 4. NO cancels

If user answers NO:

- cancel workflow
- do not generate plan
- do not generate output
- do not mutate files
- record metadata:
  - disabled_best_match
  - generic_fallback_confirmed: false
  - status: cancelled

---

### 5. Enabled alternative may proceed

If another enabled skill is selected with strong enough score, proceed normally.

Do not block merely because a disabled skill also matched.

Block only when the disabled skill is the best/high-confidence match and no suitable enabled skill was selected.

---

## Tests Required

Add/update tests for:

1. Disabled best-match skill blocks silent fallback.
2. YES continues with generic grounded plan.
3. NO cancels without plan/output/mutation.
4. Disabled best-match metadata is recorded.
5. Enabled alternative skill still proceeds normally.
6. Disabled skill never appears as selected skill.
7. Unrelated rejection still works.
8. Existing enabled-skill routing still works.

Likely files:

```text
tests/test_task_router.py
tests/test_active_mode_v1.py
tests/test_skills.py
```

---

## Acceptance Criteria

Done when:

- Snappy detects disabled best-match skills.
- Snappy does not silently continue into generic planning.
- User explicitly confirms generic fallback.
- NO cancels cleanly.
- YES proceeds without selected skill.
- Metadata/history records disabled fallback.
- Existing routing remains green.
- Full tests pass.

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

- auto-enabling skills
- config editing
- skill installation
- plugin system
- M7 execution intelligence
- mutation path changes
