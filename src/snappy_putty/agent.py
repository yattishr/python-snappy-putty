from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from snappy_putty.context import ContextSnapshot
from snappy_putty.fs_ops import list_dir
from snappy_putty.models import AgentOutput, PlanStep, Snippet, SuggestedCommand
from snappy_putty.security import sanitize_user_prompt
from snappy_putty.safety import attach_risk_tags
from snappy_putty.status import busy, get_status_message

try:
    from agents import Agent, Runner
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Agent = None
    Runner = None


ASK_INSTRUCTIONS = """You are Snappy PuTTy AskMode, a suggestion-only planning assistant.
Return output that exactly matches the requested structured schema.
Never execute shell commands. Never claim a command was executed.
May inspect provided context and use read-only tools only when needed to fulfill the request.
Ask at most one clarifying question when ambiguity blocks action.
Provide practical plan steps and suggested commands with risk tags.
Risk tags must be one of: low, med, high.
For med/high risk commands, include safer alternatives and explicit warnings.
If user asks about deploying to Google Cloud and the project appears to be a CLI
(pyproject.toml present and no clear web framework markers), ask exactly one clarifying
question: "Do you want to deploy a web service, or publish/distribute this CLI?"
Then provide two explicit plan branches for those choices.
Return raw JSON only, with no markdown fences.
Keep responses concise and actionable."""

EXPLAIN_INSTRUCTIONS = """You are Snappy PuTTy ExplainMode.
Return output that exactly matches the requested structured schema.
Explain command meaning, syntax, and typical usage.
Mention prerequisites generically (for example, "must run inside a git repo"),
but do not claim anything about the user's current environment unless explicitly provided in user input.
Do not troubleshoot failures unless the user asks why it failed, says it is not working,
or provides error output.
Never execute shell commands. Never claim a command was executed.
Return raw JSON only, with no markdown fences.
Keep responses concise and actionable."""


@dataclass(frozen=True)
class AgentRunResult:
    output: AgentOutput
    raw_model_text: str | None = None
    parse_error: str | None = None
    directory_listing: str | None = None


def parse_agent_output(value: Any) -> AgentOutput:
    if isinstance(value, AgentOutput):
        return value
    if isinstance(value, str):
        candidate = extract_json(value)
        data = json.loads(candidate)
        return AgentOutput.model_validate(data)
    return AgentOutput.model_validate(value)


def extract_json(text: str) -> str:
    fenced_json = re.search(r"```json\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced_json:
        return fenced_json.group(1).strip()

    fenced_any = re.search(r"```[a-zA-Z0-9_-]*\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced_any:
        return fenced_any.group(1).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first : last + 1]
    return text


def _build_prompt(mode: str, user_text: str, snapshot: ContextSnapshot | None) -> str:
    if mode == "explain" or snapshot is None:
        schema = {
            "goal": "string",
            "assumptions": ["string"],
            "question": "string | null",
            "plan": [{"step": 1, "action": "string", "why": "string"}],
            "commands": [{"cmd": "string", "explain": "string", "risk": "low|med|high"}],
            "warnings": ["string"],
            "snippets": [{"title": "string", "language": "string", "content": "string"}],
        }
        return (
            f"Mode: {mode}\n"
            f"User input: {user_text}\n"
            f"Output schema JSON shape: {json.dumps(schema)}\n"
            f"Return only valid JSON matching the schema."
        )

    if snapshot.in_git_repo:
        git_text = f"branch={snapshot.git_branch or 'unknown'}, state={snapshot.git_state or 'unknown'}"
    else:
        git_text = "not a git repository"
    tool_summary = ", ".join(f"{name}={'yes' if ok else 'no'}" for name, ok in snapshot.tools.items())
    project_summary = ", ".join(snapshot.project_types) if snapshot.project_types else "none detected"
    schema = {
        "goal": "string",
        "assumptions": ["string"],
        "question": "string | null",
        "plan": [{"step": 1, "action": "string", "why": "string"}],
        "commands": [{"cmd": "string", "explain": "string", "risk": "low|med|high"}],
        "warnings": ["string"],
        "snippets": [{"title": "string", "language": "string", "content": "string"}],
    }
    return (
        f"Mode: {mode}\n"
        f"User input: {user_text}\n"
        f"Context:\n"
        f"- OS: {snapshot.os_name}\n"
        f"- Platform: {snapshot.platform_info}\n"
        f"- CWD: {snapshot.cwd}\n"
        f"- Git status: {git_text}\n"
        f"- Tools: {tool_summary}\n"
        f"- Project types: {project_summary}\n"
        f"Output schema JSON shape: {json.dumps(schema)}\n"
        f"Return only valid JSON matching the schema."
    )


def _single_line_command(command: str) -> str:
    return " ".join(command.splitlines()).strip()


def _is_listing_request(text: str) -> bool:
    normalized = text.lower()
    listing_tokens = ("list", "listing", "files", "folders", "directories", "directory")
    return any(token in normalized for token in listing_tokens)


def _extract_requested_path(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\b(?:the\s+)?(?:current|working)\s+(?:directory|folder)\b", lowered):
        return "."
    if re.search(r"\b(?:cwd|current dir|current folder|here)\b", lowered):
        return "."

    quoted = re.search(r"[\"']([^\"']+)[\"']", text)
    if quoted:
        return quoted.group(1).strip()

    marker = re.search(r"\b(?:for|in|under|of)\s+([./~\w-][\w./~-]*)\b", text, flags=re.IGNORECASE)
    if marker:
        candidate = marker.group(1).strip()
        if candidate.lower() in {"the", "a", "an", "my", "this", "that"}:
            return None
        return candidate
    return None


def _listing_request_is_ambiguous(text: str) -> bool:
    lowered = text.lower()
    if not _is_listing_request(lowered):
        return False
    ambiguous_patterns = (
        "which directory",
        "what directory",
        "for a directory",
        "for directory",
        "for folder",
        "for path",
    )
    if any(pattern in lowered for pattern in ambiguous_patterns):
        return True
    if re.search(r"\b(?:for|in|under|of)\s*$", lowered):
        return True
    return False


def _listing_output(user_text: str, target_path: str, listing_text: str, requested_path: bool) -> AgentRunResult:
    assumption = f"Using requested directory: {target_path}" if requested_path else f"No path provided; defaulting to cwd: {Path.cwd()}"
    output = AgentOutput(
        goal=user_text,
        assumptions=[assumption],
        question=None,
        plan=[
            PlanStep(step=1, action="Resolve target directory", why="Determine which location to inspect."),
            PlanStep(step=2, action="Run safe read-only listing", why="Collect files/folders without changing state."),
        ],
        commands=[
            SuggestedCommand(
                cmd=f"python-native listing: {target_path}",
                explain="Read-only listing performed via pathlib in-process.",
                risk="low",
            )
        ],
        warnings=["Read-only local directory listing only; no state-changing commands were executed."],
        snippets=[],
    )
    return AgentRunResult(output=_apply_safety(output), directory_listing=listing_text)


def _listing_followup_output(user_text: str) -> AgentRunResult:
    output = AgentOutput(
        goal=user_text,
        assumptions=["Directory target is unclear from request."],
        question="Which directory path should I list?",
        plan=[PlanStep(step=1, action="Collect target path", why="Need a concrete directory to list safely.")],
        commands=[],
        warnings=["Reply with a path like `.`, `src`, or `/absolute/path`."],
        snippets=[],
    )
    return AgentRunResult(output=output)


def _is_google_cloud_deploy_request(text: str) -> bool:
    normalized = text.lower()
    return "deploy" in normalized and ("google cloud" in normalized or "gcloud" in normalized)


def _is_git_worktree_listing_request(text: str) -> bool:
    normalized = text.lower()
    return "git worktree" in normalized and any(token in normalized for token in ("list", "listing", "show"))


def _has_web_framework_markers(cwd: str) -> bool:
    root = Path(cwd)
    file_markers = ("manage.py", "wsgi.py", "asgi.py")
    for marker in file_markers:
        if (root / marker).exists():
            return True
    dependency_markers = ("fastapi", "flask", "django", "starlette", "streamlit", "gradio")
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        lowered = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        if any(token in lowered for token in dependency_markers):
            return True
    return False


def _looks_like_cli_project(snapshot: ContextSnapshot) -> bool:
    has_pyproject = "pyproject.toml" in snapshot.project_types
    return has_pyproject and not _has_web_framework_markers(snapshot.cwd)


def _cloud_deploy_cli_branch_output(user_text: str) -> AgentOutput:
    dockerfile_snippet = Snippet(
        title="Cloud Run Dockerfile Option",
        language="dockerfile",
        content=(
            "FROM python:3.10-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "RUN pip install --no-cache-dir -e .\n"
            'CMD ["snappy", "--help"]\n'
        ),
    )
    return AgentOutput(
        goal=user_text,
        assumptions=[
            "Project appears to be a CLI (pyproject.toml present, no web framework marker found).",
            "You want Google Cloud-oriented deployment guidance.",
        ],
        question="Do you want to deploy a web service, or publish/distribute this CLI?",
        plan=[
            PlanStep(step=1, action="Branch A (default for CLI): Cloud Run Job path", why="Run CLI tasks as one-off/batch executions."),
            PlanStep(step=2, action="Build container and push to Artifact Registry", why="Cloud Run Jobs consume container images from registries."),
            PlanStep(step=3, action="Create and execute a Cloud Run Job", why="Validate runtime behavior for the CLI workload."),
            PlanStep(step=4, action="Branch B: Publish/distribute CLI path", why="Use when users should install and run locally."),
            PlanStep(step=5, action="Build and validate package artifacts", why="Ensure wheel/sdist integrity before upload."),
            PlanStep(step=6, action="Upload to TestPyPI first, then production index", why="Reduce release risk and verify install flow."),
        ],
        commands=[
            SuggestedCommand(
                cmd="gcloud auth configure-docker us-central1-docker.pkg.dev",
                explain="Branch A: configure Docker auth for Artifact Registry (GCR is legacy).",
                risk="med",
            ),
            SuggestedCommand(
                cmd="docker build -t us-central1-docker.pkg.dev/PROJECT_ID/snappy-putty/snappy-putty:latest .",
                explain="Branch A: build container image for Cloud Run Job.",
                risk="med",
            ),
            SuggestedCommand(
                cmd="docker push us-central1-docker.pkg.dev/PROJECT_ID/snappy-putty/snappy-putty:latest",
                explain="Branch A: push image to Artifact Registry (preferred over legacy GCR).",
                risk="med",
            ),
            SuggestedCommand(
                cmd="gcloud run jobs create snappy-putty-job --image us-central1-docker.pkg.dev/PROJECT_ID/snappy-putty/snappy-putty:latest --region us-central1",
                explain="Branch A: create Cloud Run Job definition.",
                risk="med",
            ),
            SuggestedCommand(
                cmd="gcloud run jobs execute snappy-putty-job --region us-central1",
                explain="Branch A: execute the Cloud Run Job.",
                risk="med",
            ),
            SuggestedCommand(
                cmd="python -m pip install build twine",
                explain="Branch B: install packaging and publishing tooling.",
                risk="low",
            ),
            SuggestedCommand(
                cmd="python -m build",
                explain="Branch B: build wheel and source distribution artifacts.",
                risk="low",
            ),
            SuggestedCommand(
                cmd="twine check dist/*",
                explain="Branch B: verify package metadata and distribution files.",
                risk="low",
            ),
            SuggestedCommand(
                cmd="python -m twine upload --repository testpypi dist/*",
                explain="Branch B: upload to TestPyPI first for validation.",
                risk="med",
            ),
            SuggestedCommand(
                cmd="python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple snappy-putty",
                explain="Branch B: validate installation from TestPyPI.",
                risk="low",
            ),
            SuggestedCommand(
                cmd="python -m twine upload dist/*",
                explain="Branch B: publish to production index after TestPyPI verification.",
                risk="med",
            ),
        ],
        warnings=[
            "Use Artifact Registry (`*.pkg.dev`) for new workflows; GCR is legacy.",
            "For Cloud Run Jobs, pin immutable image tags (for example git SHA) rather than reusing `latest`.",
            "Before `gcloud run jobs execute`, run `gcloud run jobs describe snappy-putty-job --region us-central1` to confirm config.",
            "For package publishing, run `twine check dist/*` and upload to TestPyPI before production.",
        ],
        snippets=[dockerfile_snippet],
    )


def _fallback_output(mode: str, user_text: str, snapshot: ContextSnapshot) -> AgentOutput:
    if _is_google_cloud_deploy_request(user_text) and _looks_like_cli_project(snapshot):
        return _cloud_deploy_cli_branch_output(user_text)

    suggestions: list[SuggestedCommand]
    if mode == "explain":
        suggestions = [
            SuggestedCommand(
                cmd=user_text,
                explain="Review this command carefully and use dry-run alternatives when possible.",
                risk="low",
            )
        ]
    else:
        suggestions = [
            SuggestedCommand(
                cmd="snappy doctor",
                explain="Inspect local context safely without changing filesystem state.",
                risk="low",
            )
        ]

    return AgentOutput(
        goal=user_text,
        assumptions=["OpenAI Agents SDK could not be reached; using local fallback output."],
        question=None,
        plan=[
            PlanStep(step=1, action=f"Interpret user {mode} request", why="Establish intent."),
            PlanStep(step=2, action="Prepare safe, suggestion-only steps", why="Avoid command execution."),
        ],
        commands=suggestions,
        warnings=["Fallback mode is active; suggestions may be generic."],
        snippets=[],
    )


def _git_worktree_output(user_text: str, snapshot: ContextSnapshot) -> AgentRunResult:
    if not snapshot.in_git_repo:
        output = AgentOutput(
            goal=user_text,
            assumptions=["Git worktree commands must be run from inside a git repository."],
            question=None,
            plan=[
                PlanStep(step=1, action="Locate the target git repository", why="`git worktree list` requires repo context."),
                PlanStep(step=2, action="Run read-only worktree listing", why="Inspect configured worktrees safely."),
            ],
            commands=[SuggestedCommand(cmd="git worktree list", explain="List worktrees once inside a git repo.", risk="low")],
            warnings=["This request needs a git repository context before listing worktrees."],
            snippets=[],
        )
        return AgentRunResult(output=_apply_safety(output))

    output = AgentOutput(
        goal=user_text,
        assumptions=[
            f"Current repo branch context: {snapshot.git_branch or 'unknown'}",
            "This request should be run from a git repository context.",
        ],
        question=None,
        plan=[
            PlanStep(step=1, action="Check repository worktrees", why="Gather current worktree topology."),
            PlanStep(step=2, action="Review listed paths and branches", why="Confirm expected checkout layout."),
        ],
        commands=[SuggestedCommand(cmd="git worktree list", explain="Read-only worktree overview.", risk="low")],
        warnings=["Review worktree paths before running branch operations."],
        snippets=[],
    )
    return AgentRunResult(output=_apply_safety(output))


def _apply_safety(output: AgentOutput) -> AgentOutput:
    normalized_commands = [item.model_copy(update={"cmd": _single_line_command(item.cmd)}) for item in output.commands]
    tagged = attach_risk_tags(normalized_commands)
    warnings = list(output.warnings)
    for item in tagged:
        if item.risk == "high":
            warnings.append(f"High risk warning: `{item.cmd}` can be destructive or irreversible.")
            if "terraform apply" in item.cmd:
                warnings.append("Tool guidance: run `terraform plan` and review output before `terraform apply`.")
            elif "kubectl delete" in item.cmd:
                warnings.append("Tool guidance: run `kubectl get` and scope with `--namespace`/label selectors before delete.")
            else:
                warnings.append("Tool guidance: validate target paths/resources explicitly and back up critical data first.")
        elif item.risk == "med":
            warnings.append(f"Medium risk warning: `{item.cmd}` may change system or service state.")
            if "gcloud run" in item.cmd:
                warnings.append("Tool guidance: confirm project/region with `gcloud config list` and inspect resource settings before apply.")
            elif "docker" in item.cmd:
                warnings.append("Tool guidance: verify image tag and registry path, then inspect the image locally before push/prune.")
            elif "systemctl restart" in item.cmd:
                warnings.append("Tool guidance: check service status/logs (`systemctl status`, `journalctl`) before restart.")
            else:
                warnings.append("Tool guidance: review command flags and target scope before execution.")
    # keep order stable while removing duplicates
    deduped_warnings = list(dict.fromkeys(warnings))
    return output.model_copy(update={"commands": tagged, "warnings": deduped_warnings})


async def _run_with_sdk(mode: str, user_text: str, snapshot: ContextSnapshot | None) -> str:
    if Agent is None or Runner is None:
        raise RuntimeError("openai-agents is not installed")
    model = os.getenv("SNAPPY_PUTTY_MODEL", "gpt-4.1-mini")
    instructions = EXPLAIN_INSTRUCTIONS if mode == "explain" else ASK_INSTRUCTIONS
    planner = Agent(
        name="Snappy PuTTy Planner",
        instructions=instructions,
        model=model,
    )
    result = await Runner.run(planner, _build_prompt(mode=mode, user_text=user_text, snapshot=snapshot))
    return str(result.final_output)


def plan_with_agent(mode: str, user_text: str, snapshot: ContextSnapshot | None = None) -> AgentRunResult:
    if mode == "ask" and snapshot is None:
        raise ValueError("AskMode requires context snapshot.")

    sanitized_user_text = sanitize_user_prompt(user_text)
    effective_text = sanitized_user_text

    if mode == "ask" and _is_git_worktree_listing_request(effective_text):
        return _git_worktree_output(user_text=effective_text, snapshot=snapshot)

    if mode == "ask" and _is_listing_request(effective_text):
        if _listing_request_is_ambiguous(effective_text):
            return _listing_followup_output(effective_text)

        selected_path = _extract_requested_path(effective_text) or "."
        with busy(get_status_message("fs")):
            listing_text = list_dir(path=selected_path)
        return _listing_output(
            user_text=effective_text,
            target_path=selected_path,
            listing_text=listing_text,
            requested_path=_extract_requested_path(effective_text) is not None,
        )

    if mode == "ask" and _is_google_cloud_deploy_request(effective_text) and _looks_like_cli_project(snapshot):
        output = _apply_safety(_cloud_deploy_cli_branch_output(effective_text))
        return AgentRunResult(output=output)

    try:
        raw_text = asyncio.run(_run_with_sdk(mode=mode, user_text=effective_text, snapshot=snapshot))
        parsed = parse_agent_output(raw_text)
        return AgentRunResult(output=_apply_safety(parsed))
    except (ValidationError, ValueError) as err:
        fallback_snapshot = snapshot if snapshot is not None else ContextSnapshot(
            os_name="unknown",
            platform_info="unknown",
            cwd="unknown",
            in_git_repo=False,
            git_branch=None,
            git_state=None,
            tools={},
            project_types=[],
        )
        fallback = _apply_safety(_fallback_output(mode=mode, user_text=effective_text, snapshot=fallback_snapshot))
        return AgentRunResult(output=fallback, raw_model_text=locals().get("raw_text"), parse_error=str(err))
    except Exception:
        fallback_snapshot = snapshot if snapshot is not None else ContextSnapshot(
            os_name="unknown",
            platform_info="unknown",
            cwd="unknown",
            in_git_repo=False,
            git_branch=None,
            git_state=None,
            tools={},
            project_types=[],
        )
        fallback = _apply_safety(_fallback_output(mode=mode, user_text=effective_text, snapshot=fallback_snapshot))
        return AgentRunResult(output=fallback)
