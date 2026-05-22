from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from snappy_putty.config import SnappyConfig
from snappy_putty.skills import Skill


SUPPORTED_OUTPUT_KINDS = {
    "code_review_report",
    "documentation_draft",
    "frontend_design_brief",
    "implementation_plan",
    "testing_plan",
    "deployment_plan",
    "general_skill_report",
}

_INTENT_OUTPUT_KINDS = {
    "code_review": "code_review_report",
    "documentation": "documentation_draft",
    "frontend_build": "frontend_design_brief",
    "testing": "testing_plan",
    "deployment": "deployment_plan",
    "project_setup": "implementation_plan",
    "project_extension": "implementation_plan",
    "project_adaptation": "implementation_plan",
}


@dataclass(frozen=True)
class SkillOutputRequest:
    goal: str
    task_intent: str
    selected_skills: list[str]
    project_relationship: str
    snapshot_id: str | None
    files_considered: list[str]
    context_summary: str
    plan_steps: list[Any]
    skill_context: str
    config: SnappyConfig | None = None


@dataclass(frozen=True)
class SkillOutputSection:
    heading: str
    items: list[str] | None = None
    body: str | None = None
    severity: str | None = None


@dataclass(frozen=True)
class SkillOutput:
    output_kind: str
    title: str
    summary: str
    sections: list[SkillOutputSection]
    warnings: list[str] = field(default_factory=list)
    files_referenced: list[str] = field(default_factory=list)
    mutations_applied: bool = False


def output_kind_for_request(
    task_intent: str,
    selected_skills: list[str],
    skills: list[Skill] | None = None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    by_name = {skill.metadata.name: skill for skill in skills or []}
    for name in selected_skills:
        values = by_name.get(name).metadata.snappy.get("output_kinds") if by_name.get(name) is not None else None
        if not isinstance(values, list):
            continue
        for value in values:
            if value in SUPPORTED_OUTPUT_KINDS:
                return value, warnings
            if isinstance(value, str) and value.strip():
                warnings.append(f"Unknown skill output kind ignored: {value}")
    return _INTENT_OUTPUT_KINDS.get(task_intent, "general_skill_report"), warnings


def build_skill_output_request(
    *,
    plan: Any,
    skills: list[Skill],
    config: SnappyConfig | None = None,
) -> SkillOutputRequest:
    context = plan.context_selection if isinstance(getattr(plan, "context_selection", None), dict) else {}
    routing = context.get("skill_routing") if isinstance(context.get("skill_routing"), dict) else {}
    relationship = context.get("project_relationship") if isinstance(context.get("project_relationship"), dict) else {}
    task_intent = routing.get("task_intent") if isinstance(routing.get("task_intent"), dict) else {}
    selected = [item for item in routing.get("selected_skills", []) if isinstance(item, str)]
    matched = {skill.metadata.name: skill for skill in skills if skill.metadata.name in selected}
    skill_context = "\n\n".join(
        [
            f"Skill: {skill.metadata.name}\nDescription: {skill.metadata.description}\nInstructions:\n{skill.body}"
            for skill in matched.values()
        ]
    )
    files_considered = _dedupe([item for item in getattr(plan, "files_inspected", []) if isinstance(item, str)])
    context_files = context.get("files")
    if isinstance(context_files, list):
        for item in context_files:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                files_considered = _dedupe([*files_considered, item["path"]])
    return SkillOutputRequest(
        goal=str(getattr(plan, "goal", "")),
        task_intent=str(task_intent.get("label") or "general_project_help"),
        selected_skills=selected,
        project_relationship=str(relationship.get("relationship") or "direct_project_work"),
        snapshot_id=str(getattr(plan, "based_on_snapshot_id", "")) or None,
        files_considered=files_considered,
        context_summary=_context_summary(context, files_considered),
        plan_steps=list(getattr(plan, "steps", [])),
        skill_context=skill_context,
        config=config,
    )


def build_skill_output_prompt(request: SkillOutputRequest, output_kind: str) -> str:
    schema = {
        "output_kind": output_kind,
        "title": "string",
        "summary": "string",
        "sections": [{"heading": "string", "items": ["string"], "body": "string", "severity": "string|null"}],
        "warnings": ["string"],
        "files_referenced": ["path"],
        "mutations_applied": False,
    }
    steps = [_step_description(step) for step in request.plan_steps]
    requirements = "\n".join(f"- {item}" for item in output_requirements(output_kind))
    return (
        "Generate a structured non-mutating skill output.\n"
        f"User goal: {request.goal}\n"
        f"Selected skills: {', '.join(request.selected_skills) or '(none)'}\n"
        f"Task intent: {request.task_intent}\n"
        f"Project relationship: {request.project_relationship}\n"
        f"Snapshot ID: {request.snapshot_id or '(none)'}\n"
        f"Files considered: {', '.join(request.files_considered) or '(none)'}\n"
        f"Context summary: {request.context_summary}\n"
        f"Grounded plan steps: {json.dumps(steps)}\n"
        f"Skill context:\n{request.skill_context or '(none)'}\n"
        f"Output kind requirements:\n{requirements}\n"
        "Safety: do not claim files were changed or commands were run. Do not invent unavailable diff data. "
        "Distinguish observed facts from assumptions. Reference file paths only when grounded in files considered.\n"
        f"Return JSON matching this schema: {json.dumps(schema)}"
    )


def generate_skill_output(request: SkillOutputRequest, skills: list[Skill] | None = None) -> SkillOutput:
    output_kind, warnings = output_kind_for_request(request.task_intent, request.selected_skills, skills)
    files = _dedupe(request.files_considered)
    step_items = [_step_description(step) for step in request.plan_steps] or ["Review the confirmed grounded plan."]
    if output_kind == "code_review_report":
        return SkillOutput(
            output_kind=output_kind,
            title="Code Review Report",
            summary=f"Review output for: {request.goal}",
            sections=[
                SkillOutputSection("Summary", body=_grounded_summary(request, files)),
                SkillOutputSection(
                    "Findings",
                    items=[
                        "[Info] Available context supports a snapshot-grounded review report.",
                        "[Info] Confirm findings against an explicit change diff when diff context is required.",
                    ],
                    severity="Info",
                ),
                SkillOutputSection("Suggested Fixes", items=step_items),
                SkillOutputSection("Testing Notes", items=_testing_items(files)),
                SkillOutputSection("Assumptions / Limitations", items=_limitations(request, review=True)),
            ],
            warnings=warnings,
            files_referenced=files,
        )
    if output_kind == "documentation_draft":
        return _documentation_output(request, files, step_items, warnings)
    if output_kind == "frontend_design_brief":
        return _frontend_output(request, files, step_items, warnings)
    if output_kind == "testing_plan":
        return _testing_output(request, files, step_items, warnings)
    if output_kind == "deployment_plan":
        return _deployment_output(request, files, step_items, warnings)
    if output_kind == "implementation_plan":
        return _implementation_output(request, files, step_items, warnings)
    return SkillOutput(
        output_kind="general_skill_report",
        title="Skill Output Report",
        summary=f"Structured output for: {request.goal}",
        sections=[
            SkillOutputSection("Summary", body=_grounded_summary(request, files)),
            SkillOutputSection("Recommended Next Steps", items=step_items),
            SkillOutputSection("Files Referenced", items=files or ["No grounded file references were available."]),
            SkillOutputSection("Assumptions / Limitations", items=_limitations(request)),
        ],
        warnings=warnings,
        files_referenced=files,
    )


def render_skill_output(output: SkillOutput) -> str:
    lines = [f"# {output.title}", "", "## Summary", "", output.summary]
    for section in output.sections:
        lines.extend(["", f"## {section.heading}", ""])
        if section.body:
            lines.append(section.body)
        for item in section.items or []:
            lines.append(f"- {item}")
    if output.files_referenced:
        lines.extend(["", "## Files Referenced", ""])
        lines.extend(f"- `{path}`" for path in output.files_referenced)
    if output.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in output.warnings)
    lines.extend(["", "_No files were changed._"])
    if output.output_kind in {"testing_plan", "deployment_plan"}:
        lines.append("_No commands were run._")
    return "\n".join(lines)


def output_requirements(output_kind: str) -> list[str]:
    requirements = {
        "code_review_report": [
            "Summary",
            "Findings with severity labels where possible",
            "File references where grounded",
            "Suggested fixes",
            "Testing recommendations",
            "Assumptions and limitations",
            "Explicitly state that no files were changed",
        ],
        "documentation_draft": [
            "Proposed title",
            "Overview",
            "Installation or setup",
            "Usage",
            "Project structure when known",
            "API or CLI examples when known",
            "Next documentation gaps",
            "Explicitly state that no files were changed",
        ],
        "frontend_design_brief": [
            "UI direction",
            "User flows",
            "Screens and components",
            "API integration points",
            "Suggested file structure",
            "Styling approach",
            "Accessibility considerations",
            "Implementation sequence",
            "Explicitly state that no files were changed",
        ],
        "testing_plan": [
            "Test scope",
            "Suggested test files",
            "Unit tests",
            "Integration tests",
            "Edge cases",
            "Commands as suggestions only",
            "Explicitly state that no commands were run",
        ],
        "deployment_plan": [
            "Deployment target assumptions",
            "Config files likely involved",
            "Environment variables",
            "Build steps as suggestions only",
            "Risks",
            "Verification checklist",
            "Explicitly state that no files were changed and no commands were run",
        ],
        "implementation_plan": [
            "Goal",
            "Steps",
            "Files likely involved",
            "Risks",
            "Acceptance checks",
            "Explicitly state that no files were changed",
        ],
    }
    return requirements.get(output_kind, ["Summary", "Grounded next steps", "Assumptions and limitations", "No mutation claims"])


def _documentation_output(request: SkillOutputRequest, files: list[str], steps: list[str], warnings: list[str]) -> SkillOutput:
    return SkillOutput(
        "documentation_draft",
        "Documentation Draft",
        f"Draft documentation outline for: {request.goal}",
        [
            SkillOutputSection("Proposed Title", body=request.goal.strip().rstrip(".") or "Project Documentation"),
            SkillOutputSection("Overview", body=_grounded_summary(request, files)),
            SkillOutputSection("Installation / Setup", items=["Document prerequisites and setup steps visible from project configuration."]),
            SkillOutputSection("Usage", items=["Describe the primary user workflow from the considered files."]),
            SkillOutputSection("Project Structure", items=files or ["Project structure was not available in the selected context."]),
            SkillOutputSection("API / CLI Examples", items=["Add examples only for interfaces confirmed by grounded context."]),
            SkillOutputSection("Next Documentation Gaps", items=[*steps, *_limitations(request)]),
        ],
        warnings,
        files,
    )


def _frontend_output(request: SkillOutputRequest, files: list[str], steps: list[str], warnings: list[str]) -> SkillOutput:
    headings = [
        ("UI Direction", ["Derive interface tone and density from the current product context."]),
        ("User Flows", ["Map primary entry, task completion, error, and empty-state flows."]),
        ("Screens / Components", ["Identify route shells, reusable controls, data states, and responsive layouts."]),
        ("API Integration Points", ["Bind UI data requirements to confirmed project interfaces only."]),
        ("Suggested File Structure", files or ["Confirm the frontend structure before proposing new file paths."]),
        ("Styling Approach", ["Reuse the existing design system and style conventions where present."]),
        ("Accessibility", ["Cover keyboard paths, labels, focus order, contrast, and loading feedback."]),
        ("Implementation Sequence", steps),
    ]
    return SkillOutput(
        "frontend_design_brief",
        "Frontend Design Brief",
        f"Design brief for: {request.goal}",
        [SkillOutputSection(heading, items=items) for heading, items in headings],
        warnings,
        files,
    )


def _implementation_output(request: SkillOutputRequest, files: list[str], steps: list[str], warnings: list[str]) -> SkillOutput:
    return SkillOutput(
        "implementation_plan",
        "Implementation Plan",
        f"Implementation plan for: {request.goal}",
        [
            SkillOutputSection("Goal", body=request.goal),
            SkillOutputSection("Steps", items=steps),
            SkillOutputSection("Files Likely Involved", items=files or ["No grounded file references were selected."]),
            SkillOutputSection("Risks", items=_limitations(request)),
            SkillOutputSection("Acceptance Checks", items=_testing_items(files)),
        ],
        warnings,
        files,
    )


def _testing_output(request: SkillOutputRequest, files: list[str], steps: list[str], warnings: list[str]) -> SkillOutput:
    return SkillOutput(
        "testing_plan",
        "Testing Plan",
        f"Testing plan for: {request.goal}",
        [
            SkillOutputSection("Test Scope", items=steps),
            SkillOutputSection("Suggested Test Files", items=files or ["Confirm test locations from project context."]),
            SkillOutputSection("Unit Tests", items=["Cover focused behavior and failure branches near the affected modules."]),
            SkillOutputSection("Integration Tests", items=["Cover workflow boundaries described by the grounded plan."]),
            SkillOutputSection("Edge Cases", items=["Include invalid input, missing context, and state restoration cases where relevant."]),
            SkillOutputSection("Suggested Commands", items=["Run the project's focused test command after approval."]),
        ],
        warnings,
        files,
    )


def _deployment_output(request: SkillOutputRequest, files: list[str], steps: list[str], warnings: list[str]) -> SkillOutput:
    return SkillOutput(
        "deployment_plan",
        "Deployment Plan",
        f"Deployment plan for: {request.goal}",
        [
            SkillOutputSection("Deployment Target Assumptions", items=_limitations(request)),
            SkillOutputSection("Config Files Likely Involved", items=files or ["No grounded deployment config paths were selected."]),
            SkillOutputSection("Environment Variables", items=["List required secrets and runtime configuration before deployment."]),
            SkillOutputSection("Build Steps", items=[f"Suggested only: {item}" for item in steps]),
            SkillOutputSection("Risks", items=["Validate target platform, secret handling, rollback path, and artifact provenance."]),
            SkillOutputSection("Verification Checklist", items=_testing_items(files)),
        ],
        warnings,
        files,
    )


def _context_summary(context: dict[str, Any], files: list[str]) -> str:
    sufficiency = context.get("sufficiency")
    sufficiency_reason = sufficiency.get("reason") if isinstance(sufficiency, dict) else None
    if isinstance(sufficiency_reason, str) and sufficiency_reason.strip():
        return f"{len(files)} considered file(s); context sufficiency: {sufficiency_reason}"
    return f"{len(files)} considered file(s) from the confirmed grounded plan."


def _grounded_summary(request: SkillOutputRequest, files: list[str]) -> str:
    snapshot = request.snapshot_id or "the current snapshot"
    file_text = ", ".join(f"`{path}`" for path in files[:4]) if files else "the selected project context"
    return f"Grounded in snapshot {snapshot} and {file_text}."


def _limitations(request: SkillOutputRequest, *, review: bool = False) -> list[str]:
    items = [f"Project relationship: {request.project_relationship}."]
    if review:
        items.append("I reviewed the current workspace snapshot, not a line-by-line MR diff.")
    if not request.skill_context:
        items.append("Selected skill instructions were not available at output generation time.")
    return items


def _testing_items(files: list[str]) -> list[str]:
    referenced = ", ".join(files[:3]) if files else "the affected paths"
    return [
        f"Verify behavior around {referenced}.",
        "Add regression checks for any confirmed issue before applying a fix.",
    ]


def _step_description(step: Any) -> str:
    if isinstance(step, dict):
        return str(step.get("description") or step.get("action") or "Review the grounded step.")
    return str(getattr(step, "description", None) or getattr(step, "action", None) or step)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
