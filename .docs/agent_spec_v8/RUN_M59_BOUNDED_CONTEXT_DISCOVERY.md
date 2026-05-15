# Snappy M5.9 — Bounded Context Discovery

## Goal

Upgrade Snappy’s planning pipeline so it automatically gathers enough relevant project context before asking the LLM to create a grounded plan.

Snappy should not rely on shallow file heuristics, fixed domain tags, or user-provided context.

Core principle:

```text
Snappy should acquire context automatically, boundedly, and transparently.
```

User experience should feel frictionless:

```text
snappy> help me implement logging

Inspecting project context...
Analyzing relevant files...
Expanding context...
Generating grounded plan...
```

The user should not be asked to manually identify files.

---

## Problem

Current planning can under-select important source files.

Example:

```text
help me implement logging
```

Snappy selected:

```text
pyproject.toml
README.md
docs/ROADMAP.md
tests/test_storage.py
tests/test_tasks.py
src/taskcli/__init__.py
```

But missed likely relevant implementation files such as:

```text
src/taskcli/main.py
src/taskcli/storage.py
src/taskcli/tasks.py
```

This weakens the LLM plan and increases hallucination risk.

---

## M5.9 Scope

Implement:

```text
1. Repo Map v1
2. File Ranking v1
3. Context Compression v1
4. LLM Context Sufficiency Check
5. One Bounded Expansion Pass
6. Plan Context Metadata
```

---

## Non-Goals

Do NOT implement:

```text
embeddings
semantic vector index
long-term code memory
full AST graph
multi-pass autonomous search
repo-wide content stuffing
background indexing daemon
watch mode
dependency graph engine
```

Those belong later.

---

## Architecture

Planning pipeline becomes:

```text
User goal
↓
Relevance / routing checks
↓
ProjectSnapshot
↓
Repo Map
↓
Initial Context Selection
↓
Context Compression
↓
LLM Sufficiency Check
↓
One Bounded Expansion Pass if needed
↓
Final Context Bundle
↓
LLM Grounded Plan
↓
Plan Validator
↓
Session Memory
↓
User Review
```

---

## 1. Repo Map v1

Build a lightweight repo map from the current project snapshot.

The repo map should summarize:

```text
files
languages
source files
test files
docs
config/package files
entrypoint candidates
symbols if cheaply extractable
imports if cheaply extractable
content hints
```

Suggested object:

```json
{
  "root": "/path/to/project",
  "languages": ["python"],
  "files": [
    {
      "path": "src/taskcli/main.py",
      "kind": "source",
      "language": "python",
      "size_bytes": 1234,
      "role_hints": ["entrypoint_candidate", "cli_candidate"],
      "symbols": ["main"],
      "imports": ["sys", "taskcli.storage", "taskcli.tasks"],
      "content_hints": ["sys.argv", "def main", "__main__"]
    }
  ],
  "tests": ["tests/test_tasks.py"],
  "docs": ["README.md"],
  "configs": ["pyproject.toml"],
  "entrypoint_candidates": ["src/taskcli/main.py"]
}
```

### File exclusions

Exclude noisy/generated/vendor paths:

```text
.git/
.snappy/
.venv/
venv/
env/
__pycache__/
.pytest_cache/
node_modules/
dist/
build/
coverage/
.cache/
vendor/
target/
.next/
.nuxt/
```

---

## 2. File Ranking v1

Do not rely on fixed domain tags alone.

Rank files by combining:

```text
goal term match
filename/path relevance
entrypoint likelihood
source/test/doc/config balance
symbol/import/content hints
proximity to selected files
project role
```

### Ranking signals

Suggested scoring:

```text
+10 direct goal term match in path/name
+8 entrypoint candidate
+7 content hint match
+6 symbol/import match
+5 source file related to goal
+4 test file related to selected source
+3 README/docs anchor
+3 package/config anchor
-8 excluded/generated/vendor
```

This should be heuristic and deterministic.

### Goal terms

Derive goal terms from the user goal dynamically.

Example:

```text
help me implement logging
```

Derived terms:

```text
logging
log
logger
debug
verbose
output
trace
```

Do not require the term to exist in a fixed domain list.

For unknown goals, tokenize the user goal and use meaningful terms.

### Entrypoint detection

Detect entrypoints across languages.

Examples:

#### Python

```text
main.py
cli.py
app.py
commands.py
files containing:
- if __name__ == "__main__"
- def main(
- sys.argv
- argparse
- click
- typer
```

#### JavaScript / TypeScript / Node

```text
package.json
bin entries in package.json
index.js
cli.js
main.js
src/index.ts
src/cli.ts
files containing:
- process.argv
- commander
- yargs
- cac
- meow
```

#### PHP

```text
composer.json
bin entries in composer.json
index.php
cli.php
console.php
artisan
files containing:
- $argv
- Symfony Console
- Laravel Artisan
```

#### Go

```text
main.go
cmd/*/main.go
files containing:
- flag.Parse
- cobra
- urfave/cli
```

#### Rust

```text
src/main.rs
Cargo.toml bin targets
files containing:
- clap
- structopt
```

#### Generic fallback

```text
main.*
cli.*
app.*
commands.*
package/manifest declared entrypoints
argument parsing patterns
```

---

## 3. Context Selection Rules

Select a balanced context set.

Default limits:

```text
max selected files: 12
max expansion files: 5
max total files after expansion: 15
```

For implementation planning, prefer:

```text
at least 2 source files if available
at least 1 test file if tests exist
at least 1 doc/config anchor if available
entrypoint candidate if detected
```

Do not let docs/config crowd out source files.

For the sample Python test project and goal:

```text
help me implement logging
```

Expected selected files should include at minimum:

```text
src/taskcli/main.py
src/taskcli/storage.py
src/taskcli/tasks.py
tests/test_storage.py
tests/test_tasks.py
README.md
pyproject.toml
```

`docs/ROADMAP.md` may be included if budget allows.

---

## 4. Context Compression v1

Do not send the entire repo.

For selected files, send compressed context.

Each selected file should include:

```text
path
kind/role
why selected
score
imports if available
symbols/functions/classes if available
content hints
short snippet
```

Snippet policy:

```text
small file: full content allowed if under budget
medium file: first 40 lines + relevant matched snippets
large file: matched snippets + symbols/imports only
```

Add a simple total character/token budget.

Suggested M5.9 limits:

```text
max context bundle chars: 30000
max per-file chars: 6000
```

These can be constants.

---

## 5. LLM Context Sufficiency Check

Before generating the final plan, ask the LLM a bounded sufficiency question.

This is internal only.

The user should not be asked.

Prompt intent:

```text
Given the user goal, repo map summary, and selected file summaries, is this enough context to create a grounded implementation plan?
```

Expected strict JSON output:

```json
{
  "sufficient": true,
  "reason": "The selected files include the CLI entrypoint, task logic, storage logic, tests, and README.",
  "missing_context_queries": [],
  "files_to_read_next": []
}
```

If insufficient:

```json
{
  "sufficient": false,
  "reason": "The selected files do not include the CLI entrypoint.",
  "missing_context_queries": ["CLI entrypoint", "argument parsing"],
  "files_to_read_next": ["src/taskcli/main.py"]
}
```

### Rules

- This is not the final plan.
- This must not mutate state.
- This must not create a plan.
- This must not ask the user.
- This must not execute tools outside bounded file inspection.
- The LLM may only request files that exist in the repo map.

---

## 6. One Bounded Expansion Pass

If sufficiency check returns:

```text
sufficient = false
```

Then Snappy may perform ONE automatic expansion pass.

Expansion behavior:

```text
- add requested files that exist in repo map
- add top-ranked files matching missing_context_queries
- do not exceed max total files
- do not exceed context budget
- re-compress context
```

Maximum expansion passes:

```text
1
```

If still insufficient after expansion, do not keep searching forever.

Return honest no-plan or cautious plan depending on confidence.

Preferred behavior for insufficient implementation context:

```text
I could not gather enough grounded context to create a reliable implementation plan.

Missing context:
- primary CLI entrypoint
- storage implementation

No plan was created.
```

But if enough partial context exists and the prompt can safely produce a plan, the plan must clearly state uncertainty.

---

## 7. Final Context Bundle

The final context bundle passed to the planning LLM should include:

```json
{
  "goal": "help me implement logging",
  "snapshot_id": "snap_xxx",
  "repo_map_summary": {},
  "selected_context": [
    {
      "path": "src/taskcli/main.py",
      "role": "cli_entrypoint",
      "score": 28,
      "reason": "entrypoint candidate + imports task/storage + contains def main",
      "snippet": "..."
    }
  ],
  "sufficiency": {
    "initial_sufficient": false,
    "expanded": true,
    "final_sufficient": true,
    "reason": "Added src/taskcli/main.py and storage.py."
  }
}
```

---

## 8. Plan Context Metadata

Persist context selection metadata with the plan.

Example:

```json
{
  "context_selection": {
    "strategy": "bounded_context_discovery_v1",
    "max_files": 12,
    "expanded": true,
    "sufficiency": {
      "initial_sufficient": false,
      "final_sufficient": true,
      "reason": "Added CLI entrypoint and storage module."
    },
    "files": [
      {
        "path": "src/taskcli/main.py",
        "role": "cli_entrypoint",
        "score": 28,
        "reason": "entrypoint candidate + contains def main"
      }
    ]
  }
}
```

This allows:

```text
why this plan
```

to explain context choices using actual evidence.

---

## 9. User-Facing Progress Messages

Snappy must show lightweight progress notifications during bounded context discovery so the user knows the system is working.

These messages should be concise, sequential, and non-technical.

Example flow:

```text
Inspecting project context...
Building repo map...
Analyzing relevant files...
Checking whether context is sufficient...
Expanding context...
Generating grounded plan...
```

Only show:

```text
Expanding context...
```

if an expansion pass actually happens.

Progress Rules
- Progress messages must not expose raw internal JSON.
- Progress messages must not print file snippets.
- Progress messages must not overwhelm the user.
- Each stage should print once.
- If a stage is skipped, do not show it.
- If planning fails, show the final reason clearly.

Suggested stages

```text
Inspecting project context...
Building repo map...
Analyzing relevant files...
Preparing context...
Checking context sufficiency...
Expanding context...
Generating grounded plan...
Validating plan...
```

Example success

```text
Inspecting project context...
Building repo map...
Analyzing relevant files...
Preparing context...
Checking context sufficiency...
Expanding context...
Generating grounded plan...
Validating plan...
```

Example no expansion
```text
Inspecting project context...
Building repo map...
Analyzing relevant files...
Preparing context...
Checking context sufficiency...
Generating grounded plan...
Validating plan...
```

Example failure
```text
Inspecting project context...
Building repo map...
Analyzing relevant files...
Checking context sufficiency...

I could not gather enough grounded context to create a reliable implementation plan.

No plan was created.
```

Optional implementation detail

Add a small progress helper so output remains consistent:

```python
def emit_progress(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")
```

Or if using Rich status/spinner:

```python
with console.status("Analyzing relevant files..."):
    ...
```

Keep it simple for M5.9. Do not add async progress tracking or background tasks.


---

## 10. Safety and Validation

Before final plan persistence, validate:

```text
all referenced files exist in ProjectSnapshot
all referenced selected-context files exist
no excluded paths included
no files outside project root
no invented files unless explicitly marked as proposed new files
```

If LLM requests files outside the project root or excluded paths, ignore and log as rejected context expansion.

---

## 11. History Logging

Append concise history events.

### Context discovery started

```md
## <timestamp>
Event: Context discovery started
Goal: help me implement logging
Snapshot ID: snap_xxx
Strategy: bounded_context_discovery_v1
```

### Context expanded

```md
## <timestamp>
Event: Context expanded
Goal: help me implement logging
Added files:
- src/taskcli/main.py
- src/taskcli/storage.py
Reason: Initial context lacked entrypoint/storage implementation.
```

### Context selected

```md
## <timestamp>
Event: Context selected
Goal: help me implement logging
Files:
- src/taskcli/main.py
- src/taskcli/storage.py
- src/taskcli/tasks.py
- tests/test_storage.py
- tests/test_tasks.py
- README.md
Sufficiency: true
```

---

## 12. Tests Required

Add tests for the context discovery module and planning integration.

### Test 1 — Repo map excludes noise

Given a project with:

```text
.git/
.snappy/
.venv/
node_modules/
src/
tests/
```

Expected:

```text
excluded paths do not appear in repo map
```

### Test 2 — CLI project selects entrypoint

For the test project and goal:

```text
help me improve this CLI
```

Expected selected files include:

```text
src/taskcli/main.py
src/taskcli/tasks.py
src/taskcli/storage.py
tests/test_tasks.py
README.md
```

### Test 3 — Logging goal selects implementation files

For:

```text
help me implement logging
```

Expected selected files include:

```text
src/taskcli/main.py
src/taskcli/storage.py
src/taskcli/tasks.py
```

Not only:

```text
src/taskcli/__init__.py
```

### Test 4 — Unknown domain still works

For an unfamiliar goal:

```text
help me improve websocket reconnect behavior
```

Expected:

```text
- terms derived from user goal
- matching files selected if present
- no dependency on static tag list
```

### Test 5 — Sufficiency check expansion

Mock LLM sufficiency response:

```json
{
  "sufficient": false,
  "files_to_read_next": ["src/taskcli/main.py"]
}
```

Expected:

```text
- one expansion pass occurs
- requested file added if it exists
- final context includes expanded file
```

### Test 6 — Expansion capped

If LLM asks for many files:

```text
- only max expansion files are added
- max total file count respected
```

### Test 7 — Nonexistent requested files ignored

If LLM asks for:

```text
src/taskcli/missing.py
```

Expected:

```text
- ignored
- logged or warned internally
- no crash
```

### Test 8 — Plan stores context metadata

After plan creation, stored plan includes:

```text
context_selection.strategy
context_selection.files
context_selection.sufficiency
```

### Test 9 — Why-this-plan uses context metadata

`why this plan` should use context metadata to explain:

```text
why files were selected
what evidence drove selection
what context expansion occurred
```

### Test 10 — No user prompt during context discovery

Planning should not ask the user which files to inspect.

Expected UX:

```text
Inspecting project context...
Analyzing relevant files...
Generating grounded plan...
```

---

## 13. Manual Verification

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Manual REPL:

```text
agent mode active
help me implement logging
show plan
why this plan
status
```

Expected:

```text
- relevant implementation files are included
- context expansion occurs if needed
- plan is more specific and less uncertain
- why-this-plan explains file selection using context metadata
- no user is asked to pick files manually
```

Also test an unfamiliar goal in a sample project containing matching names:

```text
help me improve websocket reconnect behavior
```

Expected:

```text
- Snappy derives goal terms
- searches repo map/content hints
- selects relevant files if present
- does not require a predefined websocket tag
```

---

## Non-Negotiable Rules

```text
Tags are hints.
Repo discovery is truth.
```

```text
Do not send the whole repo.
Do not ask the user to pick files.
Do not run unbounded search.
Do not hallucinate missing files into the plan.
```

```text
Maximum one automatic expansion pass in M5.9.
```

---

## Acceptance Criteria

M5.9 is complete when:

```text
- Snappy builds a lightweight repo map
- Snappy ranks files dynamically from the user goal and repo evidence
- Snappy compresses selected context
- Snappy performs one bounded LLM sufficiency check
- Snappy expands context once if needed
- Snappy persists context selection metadata with the plan
- Snappy avoids narrow hardcoded-only tag behavior
- Snappy no longer misses obvious implementation files in the sample project
- full test suite passes
```

After M5.9 passes manual testing, M5 can be locked and Snappy can move to M6.
