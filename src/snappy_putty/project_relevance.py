from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Any

from snappy_putty.project_inspector import ProjectSnapshot
from snappy_putty.skills import SkillMatch


class ProjectRelationship(str, Enum):
    DIRECT_PROJECT_WORK = "direct_project_work"
    PROJECT_EXTENSION = "project_extension"
    PROJECT_ADAPTATION = "project_adaptation"
    UNRELATED = "unrelated"


@dataclass(frozen=True)
class ProjectRelationshipResult:
    is_project_related: bool
    relationship: ProjectRelationship
    confidence: float
    reason: str
    matched_skills: list[str] = field(default_factory=list)

    def as_metadata(self) -> dict[str, Any]:
        return {
            "is_project_related": self.is_project_related,
            "relationship": self.relationship.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "matched_skills": list(self.matched_skills),
        }


_PROJECT_CONTEXT_PATTERNS = (
    r"\bthis\s+(?:project|app|application|repo|repository|codebase|workspace|tool|package|service|api|cli|script)\b",
    r"\bcurrent\s+(?:project|app|application|repo|repository|codebase|workspace|tool|package|service|api|cli|script)\b",
    r"\bfor\s+(?:this|it|the\s+current\s+(?:project|app|application|repo|repository|codebase|workspace|tool|package|service))\b",
    r"\bin\s+(?:this|the\s+current)\s+(?:project|app|application|repo|repository|codebase|workspace)\b",
)
_PROJECT_CONTEXT_RE = re.compile("|".join(_PROJECT_CONTEXT_PATTERNS))

_DIRECT_PROJECT_TERMS = {
    "code",
    "file",
    "folder",
    "directory",
    "test",
    "tests",
    "bug",
    "fix",
    "refactor",
    "function",
    "class",
    "module",
    "cli",
    "api",
    "apis",
    "command",
    "commit",
    "diff",
    "git",
    "staged",
    "endpoint",
    "endpoints",
    "route",
    "routes",
    "server",
    "service",
    "controller",
    "controllers",
    "model",
    "models",
    "package",
    "dependency",
    "readme",
    "docs",
    "documentation",
    "logging",
    "config",
    "implementation",
    "project",
}

_DIRECT_ACTIONS = (
    "inspect",
    "explain",
    "improve",
    "update",
    "modify",
    "add",
    "refactor",
    "review",
    "fix",
    "test",
    "document",
    "summarize",
)

_EXTENSION_INDICATORS = {
    "frontend",
    "front end",
    "ui",
    "interface",
    "web interface",
    "dashboard",
    "admin interface",
    "api",
    "cli",
    "tests",
    "test suite",
    "docs",
    "documentation",
    "docker",
    "container",
    "deployment",
    "deploy",
    "ci",
    "ci/cd",
    "github actions",
    "auth",
    "authentication",
    "database",
    "database integration",
    "monitoring",
    "logging",
    "integration",
    "streamlit",
    "gradio",
    "flask",
    "django",
    "fastapi",
    "react",
    "vue",
    "svelte",
    "next.js",
    "nextjs",
    "express",
    "laravel",
    "rails",
    "spring",
    "tauri",
    "electron",
}

_EXTENSION_VERBS = (
    "add",
    "build",
    "create",
    "implement",
    "set up",
    "setup",
    "integrate",
    "introduce",
    "enable",
    "write",
    "make",
)

_ADAPTATION_VERBS = ("convert", "turn", "move", "migrate", "port", "transform", "rewrite")


def classify_project_relationship(
    user_request: str,
    snapshot: ProjectSnapshot | None,
    *,
    matched_skills: list[SkillMatch] | None = None,
) -> ProjectRelationshipResult:
    lowered = user_request.strip().lower()
    skill_matches = matched_skills or []
    matched_skill_names = [match.skill.metadata.name for match in skill_matches]
    if not lowered or snapshot is None:
        return ProjectRelationshipResult(False, ProjectRelationship.UNRELATED, 0.0, "goal_not_project_related", matched_skill_names)

    if _references_snapshot_artifact(lowered, snapshot):
        return ProjectRelationshipResult(
            True,
            ProjectRelationship.DIRECT_PROJECT_WORK,
            0.92,
            "snapshot_reference_matched",
            matched_skill_names,
        )

    has_project_context = _has_project_context(lowered)
    skill_relationship = _relationship_from_skills(skill_matches, snapshot)
    if has_project_context and skill_relationship is not None:
        return ProjectRelationshipResult(
            True,
            skill_relationship,
            0.88,
            "skill_project_relationship_matched",
            matched_skill_names,
        )

    if _looks_like_adaptation(lowered):
        confidence = 0.82 if has_project_context else 0.68
        return ProjectRelationshipResult(
            True,
            ProjectRelationship.PROJECT_ADAPTATION,
            confidence,
            "project_adaptation_matched",
            matched_skill_names,
        )

    if _looks_like_extension(lowered):
        if has_project_context or _naturally_project_scoped_extension(lowered):
            return ProjectRelationshipResult(
                True,
                ProjectRelationship.PROJECT_EXTENSION,
                0.84 if has_project_context else 0.72,
                "project_extension_matched",
                matched_skill_names,
            )

    if _looks_like_direct_project_work(lowered):
        return ProjectRelationshipResult(
            True,
            ProjectRelationship.DIRECT_PROJECT_WORK,
            0.72,
            "project_terms_matched",
            matched_skill_names,
        )

    return ProjectRelationshipResult(False, ProjectRelationship.UNRELATED, 0.16, "goal_not_project_related", matched_skill_names)


def _has_project_context(text: str) -> bool:
    return bool(_PROJECT_CONTEXT_RE.search(text))


def _references_snapshot_artifact(text: str, snapshot: ProjectSnapshot) -> bool:
    goal_tokens = set(_tokens(text))
    known_paths = {
        *snapshot.sampled_files,
        *snapshot.config_files,
        *snapshot.docs,
        *snapshot.test_files,
        *snapshot.source_files,
        *snapshot.entry_points,
    }
    for path in known_paths:
        normalized = path.lower().replace("\\", "/")
        basename = Path(normalized).name
        if normalized and (normalized in text or basename in goal_tokens):
            return True
    return False


def _relationship_from_skills(matches: list[SkillMatch], snapshot: ProjectSnapshot) -> ProjectRelationship | None:
    for match in matches:
        if not _skill_targets_snapshot(match, snapshot):
            continue
        raw_relationships = match.skill.metadata.snappy.get("project_relationships")
        relationships = [item for item in raw_relationships if isinstance(item, str)] if isinstance(raw_relationships, list) else []
        if ProjectRelationship.PROJECT_ADAPTATION.value in relationships:
            return ProjectRelationship.PROJECT_ADAPTATION
        if ProjectRelationship.PROJECT_EXTENSION.value in relationships:
            return ProjectRelationship.PROJECT_EXTENSION
        inferred = _infer_skill_relationship(match)
        if inferred is not None:
            return inferred
    return None


def _skill_targets_snapshot(match: SkillMatch, snapshot: ProjectSnapshot) -> bool:
    raw_targets = match.skill.metadata.snappy.get("extension_targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        return True
    targets = {str(item).strip().lower() for item in raw_targets if isinstance(item, str) and str(item).strip()}
    if not targets:
        return True
    project_markers = {*(item.lower() for item in snapshot.languages), *(item.lower() for item in snapshot.package_managers), *(item.lower() for item in snapshot.frameworks)}
    return bool(targets & project_markers)


def _infer_skill_relationship(match: SkillMatch) -> ProjectRelationship | None:
    text = f"{match.skill.metadata.name} {match.skill.metadata.description}".lower()
    if _looks_like_adaptation(text):
        return ProjectRelationship.PROJECT_ADAPTATION
    if any(indicator in text for indicator in _EXTENSION_INDICATORS):
        return ProjectRelationship.PROJECT_EXTENSION
    return None


def _looks_like_adaptation(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(verb)}\b", text) for verb in _ADAPTATION_VERBS) and bool(
        re.search(r"\b(?:to|into|from)\b", text)
    )


def _looks_like_extension(text: str) -> bool:
    has_indicator = any(indicator in text for indicator in _EXTENSION_INDICATORS)
    has_verb = any(re.search(rf"\b{re.escape(verb)}\b", text) for verb in _EXTENSION_VERBS)
    return has_indicator and has_verb


def _naturally_project_scoped_extension(text: str) -> bool:
    if re.search(r"\b(?:write|add|create)\s+(?:tests|test suite|docs|documentation)\b", text):
        return True
    if "docker support" in text or "github actions" in text or "ci/cd" in text:
        return True
    if any(
        indicator in text
        for indicator in (
            "frontend",
            "front end",
            "web interface",
            "dashboard",
            "admin interface",
            "streamlit",
            "gradio",
            "api",
            "cli",
            "authentication",
            "monitoring",
            "database integration",
        )
    ):
        return True
    return False


def _looks_like_direct_project_work(text: str) -> bool:
    tokens = set(_tokens(text))
    if tokens & _DIRECT_PROJECT_TERMS:
        return True
    return any(re.search(rf"\b{re.escape(action)}\b", text) for action in _DIRECT_ACTIONS) and any(
        term in text for term in _DIRECT_PROJECT_TERMS
    )


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_.-]+", text.lower())
