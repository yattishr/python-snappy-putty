# Codex Implementation Prompt: M6.1 — Skill-Aware Project Extension Classification

## Context

Snappy has implemented M6 modular skills with folder-based `.snappy/skills/<skill>/SKILL.md` support. Skills can now be discovered, inspected, validated, and included in active planning metadata without directly executing or bypassing confirmation.

A current issue has appeared during testing:

A user can inspect a vanilla Node.js REST API project successfully, but when they ask:

```text
help me build a frontend interface for this application
```

Snappy rejects the request with:

```text
This request does not appear to be related to the current project.
I did not create a grounded project plan because there is no clear connection between the request and the inspected workspace.
No project plan was created.
```

This is too strict.

A request to build a frontend, dashboard, UI, CLI, documentation layer, tests, deployment setup, API layer, admin interface, Streamlit app, Gradio UI, Flask app, Django app, or similar capability may not correspond to existing files yet, but it can still be a valid extension of the current project.

The fix must not be hardcoded only for Node.js or JavaScript. It must work for Python, JavaScript, TypeScript, Go, Ruby, PHP, Java, Rust, and other project types as Snappy gains skills over time.

## Goal

Implement a generalized, language-agnostic project relevance classifier that supports skill-aware project extensions.

Add a new project relationship model so Snappy can distinguish between:

```text
direct_project_work
project_extension
project_adaptation
unrelated
```

This should allow requests that add a plausible new capability to the inspected project to produce a grounded project plan instead of being rejected as unrelated.

## Core Principle

Skills should be semantic bridges.

A skill may help Snappy understand that a user request describes a valid extension of the current project, even if the requested files or framework do not already exist.

However:

```text
Skills instruct. Tools execute. Planner decides. Rules constrain. User confirms. Harness verifies.
```

Skills must never execute directly, bypass rules, bypass confirmation, or weaken safety.

---

## Required Behavior

### 1. Add Project Relationship Classification

Create or update the project relevance logic so it returns a structured relationship result.

The result should include:

```python
{
    "is_project_related": bool,
    "relationship": "direct_project_work" | "project_extension" | "project_adaptation" | "unrelated",
    "confidence": float,
    "reason": str,
    "matched_skills": list[str],
}
```

The exact Python representation may be a dataclass, typed dict, pydantic model, or existing Snappy-style result object. Prefer consistency with the existing codebase.

### 2. Define Relationship Types

#### `direct_project_work`

Use when the request modifies, explains, fixes, reviews, tests, or inspects existing project artifacts.

Examples:

```text
Explain this API.
Fix the product controller.
Add validation to the model.
Write tests for the current auth module.
Review this codebase.
```

#### `project_extension`

Use when the request adds a new capability, layer, interface, integration, or support structure to the current project.

Examples:

```text
Build a frontend interface for this application.
Add a Streamlit dashboard for this project.
Add a Gradio UI for this app.
Create a CLI for this tool.
Add Docker support.
Add GitHub Actions.
Add documentation.
Add authentication.
Add a database integration.
Add monitoring.
Add an admin interface.
```

#### `project_adaptation`

Use when the request transforms the project into a new architectural, framework, packaging, or language mode.

Examples:

```text
Convert this REST API to FastAPI.
Turn this Python script into a Flask app.
Move this vanilla JavaScript app to React.
Add TypeScript to this project.
Turn this package into a CLI tool.
```

#### `unrelated`

Use when the request has no meaningful connection to the inspected project.

Examples:

```text
Write a poem about Batman.
Explain quantum mechanics.
Build a crypto trading bot.
Plan my holiday.
```

Unless the user clearly connects the request to the project, these should remain rejected as unrelated.

---

## Classification Requirements

### 3. Treat Plausible Project Additions as Related

Treat a request as `project_extension` when:

1. A valid project snapshot exists; and
2. The user references the current project, app, application, workspace, codebase, repo, or uses contextual phrasing such as:

```text
this project
this app
this application
this repo
this codebase
this workspace
for this
for it
for the current project
```

or the request clearly follows immediately from an inspected project context; and

3. The request asks to add a plausible project capability, such as:

```text
frontend
UI
web interface
dashboard
admin interface
API
CLI
tests
docs
documentation
Docker
deployment
CI/CD
GitHub Actions
auth
authentication
database integration
monitoring
logging
framework integration
Streamlit
Gradio
Flask
Django
FastAPI
React
Vue
Svelte
Next.js
Express
Laravel
Rails
Spring
Tauri
Electron
```

Do not limit this list to these exact items. Implement the logic in a maintainable and extensible way.

### 4. Make the Classifier Language-Agnostic

Do not hardcode only Node.js or JavaScript rules.

Expected examples:

```text
JavaScript/Node project + "build a frontend interface for this application"
=> project_extension

Python project + "build a Streamlit dashboard for this project"
=> project_extension

Python project + "add a Gradio UI for this app"
=> project_extension

Python project + "turn this script into a Flask app"
=> project_adaptation or project_extension, depending on existing structure

Python project + "add a Django admin interface"
=> project_extension

Go project + "add a CLI"
=> project_extension

Any project + "add Docker support"
=> project_extension

Any project + "write tests"
=> project_extension or direct_project_work, depending on whether tests already exist
```

### 5. Skill Matching Must Inform Relevance

If a loaded skill matches the user request and the request references the current project/app/codebase/workspace, Snappy should not reject the request as unrelated unless there is a strong reason.

Example:

A `frontend-design` skill with this description:

```yaml
---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications, including websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI.
---
```

should help classify:

```text
help me build a frontend interface for this application
```

as:

```json
{
  "is_project_related": true,
  "relationship": "project_extension",
  "matched_skills": ["frontend-design"]
}
```

### 6. Support Optional `x-snappy.project_relationships` Metadata

Extend `SKILL.md` parsing to support optional Snappy metadata in frontmatter.

Example:

```yaml
---
name: streamlit-dashboard
description: Use this skill when the user asks to build a Streamlit dashboard, analytics interface, data app, or Python-based frontend for the current project.
x-snappy:
  project_relationships:
    - project_extension
  extension_targets:
    - python
  indicators:
    - streamlit
    - dashboard
    - data app
    - analytics interface
---
```

Another example:

```yaml
---
name: flask-web-interface
description: Use this skill when the user asks to build a Flask web interface, lightweight Python web app, admin UI, or browser-based frontend for the current Python project.
x-snappy:
  project_relationships:
    - project_extension
    - project_adaptation
  extension_targets:
    - python
---
```

Rules:

- This metadata is optional.
- Existing skills without `x-snappy` must continue to work.
- If metadata is absent, infer from the skill name and description.
- `x-snappy.project_relationships` may inform relevance classification.
- `x-snappy.extension_targets` may inform language/project compatibility.
- These fields must not create execution authority.

---

## Planning Behavior

### 7. Project Extension Requests Should Create Grounded Plans

For `project_extension` requests, Snappy should create a grounded project plan.

The plan should first inspect relevant existing project files before proposing new files.

Examples of useful inspection steps:

For JavaScript/Node projects:

```text
- inspect package.json
- inspect server.js or app.js
- inspect routes/controllers/models
- identify API endpoints
- identify static asset support or frontend integration surface
```

For Python projects:

```text
- inspect pyproject.toml, requirements.txt, setup.py, or poetry.lock
- inspect app.py, main.py, server.py, src/ package layout
- inspect existing framework usage
- inspect data/model files relevant to the requested interface
```

For any project:

```text
- identify entry points
- identify package/dependency manager
- identify existing tests/docs/deployment files
- propose files to create or modify
- ask for confirmation before mutation
```

### 8. Do Not Mutate Without Confirmation

Even when a skill matches and the request is classified as `project_extension`, Snappy must not write, delete, rename, install, or execute anything without the normal planning, rule evaluation, and confirmation flow.

---

## Safety Requirements

Keep existing protections intact.

### Skills Must Not

```text
- execute directly
- call tools directly
- bypass rules
- bypass confirmation
- weaken risk classification
- override block rules
- silently install dependencies
- silently create files
- silently modify files
```

### Project Relevance Must Not Become Too Loose

Do not classify everything as project-related merely because a skill matched.

A skill match should strengthen relevance only when there is clear project context, such as:

```text
this project
this app
this application
this repo
this codebase
current workspace
for it
```

or when the command happens within an active inspected project session and the request is naturally project-scoped.

Unrelated requests should still be rejected.

---

## Snapshot Freshness Requirement

During testing, a project was inspected with one snapshot ID, but active planning later reported using a different snapshot ID.

Investigate whether active planning is sometimes using stale snapshots.

Expected behavior:

- After `inspect project`, the next planning request should use the latest saved project snapshot.
- If multiple snapshots exist, prefer the most recent valid snapshot for the current workspace root.
- Add or update tests to verify this behavior.

---

## CLI / UX Requirements

When Snappy classifies a request as `project_extension`, the user-facing response should avoid saying the request is unrelated.

Preferred behavior:

```text
Inspecting project context...
Using snapshot: <latest snapshot id>
Matched skill: frontend-design
Classified request as project_extension: the user wants to add a frontend interface to the current application.

Proposed plan:
1. Inspect package.json and server entry point.
2. Inspect controllers/routes to identify API endpoints.
3. Propose frontend file structure.
4. Build the interface after confirmation.
```

Exact wording can follow existing Snappy style, but the relationship classification and matched skill should be visible in metadata, history, or debug/plan output where appropriate.

---

## Regression Tests

Add tests covering the following cases.

### Test 1: Node REST API + Frontend Request

Given:

```text
server.js
controllers/productControllers.js
models/productModel.js
data/products.json
package.json
.snappy/skills/frontend-design/SKILL.md
```

When the user asks:

```text
help me build a frontend interface for this application
```

Then:

```text
- request is classified as project_extension
- frontend-design skill is matched
- a grounded project plan is created
- plan includes inspecting API routes/controllers before creating frontend files
- no files are written without confirmation
```

### Test 2: Python Project + Streamlit Skill

Given a Python project with:

```text
app.py or main.py
requirements.txt or pyproject.toml
.snappy/skills/streamlit-dashboard/SKILL.md
```

When the user asks:

```text
build a Streamlit dashboard for this project
```

Then:

```text
- request is classified as project_extension
- streamlit-dashboard skill is matched
- a grounded plan is created
- no files are written without confirmation
```

### Test 3: Python Project + Gradio Skill

Given a Python project with:

```text
main.py
requirements.txt or pyproject.toml
.snappy/skills/gradio-interface/SKILL.md
```

When the user asks:

```text
add a Gradio UI for this app
```

Then:

```text
- request is classified as project_extension
- gradio-interface skill is matched
- a grounded plan is created
- no files are written without confirmation
```

### Test 4: Python Project + Flask Adaptation

Given a Python script project with:

```text
main.py
requirements.txt or pyproject.toml
.snappy/skills/flask-web-interface/SKILL.md
```

When the user asks:

```text
turn this script into a Flask app
```

Then:

```text
- request is classified as project_adaptation or project_extension, whichever best fits existing architecture
- flask-web-interface skill is matched if appropriate
- a grounded plan is created
- no files are written without confirmation
```

### Test 5: Generic Docker Extension

Given any inspected project.

When the user asks:

```text
add Docker support for this project
```

Then:

```text
- request is classified as project_extension
- plan is grounded in detected package manager/language/runtime
- no files are written without confirmation
```

### Test 6: Unrelated Request Still Rejected

Given any inspected project.

When the user asks:

```text
write me a poem about Batman
```

Then:

```text
- request is classified as unrelated
- no grounded project plan is created
```

### Test 7: Skill Match Alone Does Not Override Relevance

Given a frontend-design skill.

When the user asks a generic non-project request with no current-project reference:

```text
design me a poster for a birthday party
```

Then:

```text
- frontend-design may match semantically
- but the request should not be forced into project_extension unless the user links it to the current project
- no project plan should be created unless appropriate
```

### Test 8: Latest Snapshot Is Used

Given:

```text
- project inspection creates snapshot A
- later project inspection creates snapshot B for the same workspace root
```

When the user asks for active planning after snapshot B:

Then:

```text
- planning uses snapshot B
- not stale snapshot A
```

---

## Implementation Guidance

Prefer adding a small, isolated classifier module or function rather than scattering if-statements across the planner.

Suggested names, adjusted to existing style:

```text
project_relevance.py
classify_project_relationship(...)
ProjectRelationshipResult
ProjectRelationship
```

Possible inputs:

```python
classify_project_relationship(
    user_request: str,
    snapshot: ProjectSnapshot | dict | None,
    matched_skills: list[Skill],
    recent_context: dict | None = None,
) -> ProjectRelationshipResult
```

Possible enum:

```python
class ProjectRelationship(str, Enum):
    DIRECT_PROJECT_WORK = "direct_project_work"
    PROJECT_EXTENSION = "project_extension"
    PROJECT_ADAPTATION = "project_adaptation"
    UNRELATED = "unrelated"
```

Keep implementation deterministic where possible. If existing planning uses an LLM classifier, this deterministic layer should act as a guardrail and source of structured metadata.

---

## Acceptance Criteria

This patch is complete when:

```text
- Project relationship classification exists.
- `project_extension` and `project_adaptation` are supported.
- Skills can influence project relevance without gaining execution power.
- Optional `x-snappy.project_relationships` metadata is parsed and used.
- Node frontend extension request no longer gets rejected as unrelated.
- Python Streamlit/Gradio/Flask/Django-style extension requests can be classified properly.
- Unrelated requests still get rejected.
- Active planning uses the latest valid snapshot for the current workspace root.
- Tests cover the above behavior.
- Existing M6 safety guarantees remain intact.
```

---

## Verification Commands

Run:

```bash
python -m py_compile src/snappy_putty/*.py
python -m pytest
```

Expected result:

```text
All tests pass.
```

---

## Non-Goals

Do not implement:

```text
- skill marketplace
- remote skill installation
- autonomous skill chaining
- sandbox execution
- formal plugin system
- automatic dependency installation
- unconfirmed file creation
- unconfirmed command execution
```

Those belong to later milestones.

This is an M6.1 refinement only.
