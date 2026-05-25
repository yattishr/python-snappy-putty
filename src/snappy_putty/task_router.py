from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import re
from typing import Any

from snappy_putty.config import SnappyConfig
from snappy_putty.project_inspector import ProjectSnapshot
from snappy_putty.project_relevance import ProjectRelationship
from snappy_putty.skills import Skill, SkillMatch


TASK_INTENT_LABELS = {
    "code_review",
    "frontend_build",
    "documentation",
    "testing",
    "deployment",
    "project_setup",
    "project_extension",
    "project_adaptation",
    "general_project_help",
    "unrelated",
}

INTENT_INDICATORS: dict[str, tuple[str, ...]] = {
    "code_review": (
        "review my code",
        "review latest changes",
        "inspect the diff",
        "pr feedback",
        "mr feedback",
        "pull request",
        "merge request",
        "code review",
        "find risks",
    ),
    "frontend_build": (
        "build a frontend",
        "create a ui",
        "make an interface",
        "build a dashboard",
        "landing page",
        "style this page",
        "frontend",
        "front end",
        "interface",
        "dashboard",
    ),
    "documentation": (
        "write docs",
        "create readme",
        "document this api",
        "improve docs",
        "usage guide",
        "documentation",
        "readme",
    ),
    "testing": (
        "write tests",
        "add unit tests",
        "integration tests",
        "test this feature",
        "test coverage",
    ),
    "deployment": (
        "add docker",
        "create dockerfile",
        "github actions",
        "deployment setup",
        "ci/cd",
        "deploy",
        "container",
    ),
    "project_setup": (
        "set up project",
        "initialize project",
        "scaffold",
        "starter project",
        "new package",
    ),
    "project_extension": (
        "add feature",
        "extend this",
        "build",
        "create",
        "implement",
    ),
    "project_adaptation": (
        "turn this into",
        "convert this to",
        "migrate this to",
        "make this a package",
        "port this",
        "rewrite this in",
    ),
    "general_project_help": (
        "help me",
        "improve this project",
        "explain project",
        "project architecture",
        "codebase",
        "commit message",
        "staged changes",
    ),
}

INTENT_RELATIONSHIP_HINTS = {
    "code_review": [ProjectRelationship.DIRECT_PROJECT_WORK.value],
    "frontend_build": [ProjectRelationship.PROJECT_EXTENSION.value],
    "documentation": [ProjectRelationship.DIRECT_PROJECT_WORK.value, ProjectRelationship.PROJECT_EXTENSION.value],
    "testing": [ProjectRelationship.DIRECT_PROJECT_WORK.value, ProjectRelationship.PROJECT_EXTENSION.value],
    "deployment": [ProjectRelationship.PROJECT_EXTENSION.value],
    "project_setup": [ProjectRelationship.PROJECT_EXTENSION.value],
    "project_extension": [ProjectRelationship.PROJECT_EXTENSION.value],
    "project_adaptation": [ProjectRelationship.PROJECT_ADAPTATION.value],
    "general_project_help": [ProjectRelationship.DIRECT_PROJECT_WORK.value],
    "unrelated": [ProjectRelationship.UNRELATED.value],
}

UNRELATED_INDICATORS = (
    "poster",
    "batman",
    "movie",
    "recipe",
    "vacation",
    "workout",
    "poem",
    "story",
)


@dataclass(frozen=True)
class TaskIntent:
    label: str
    confidence: float
    indicators: list[str] = field(default_factory=list)
    reason: str = ""

    def as_metadata(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "indicators": list(self.indicators),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SkillRouteCandidate:
    skill_name: str
    score: float
    reasons: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    relationship_hints: list[str] = field(default_factory=list)

    def as_metadata(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "score": self.score,
            "reasons": list(self.reasons),
            "matched_terms": list(self.matched_terms),
            "relationship_hints": list(self.relationship_hints),
        }


@dataclass(frozen=True)
class SkillRouteResult:
    selected_skills: list[str]
    candidates: list[SkillRouteCandidate]
    task_intent: TaskIntent
    confidence: float
    reason: str
    disabled_best_match: str | None = None
    disabled_best_match_score: float | None = None
    disabled_best_match_reason: str = ""
    generic_fallback_confirmed: bool | None = None
    status: str = ""

    def as_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "task_intent": self.task_intent.as_metadata(),
            "selected_skills": list(self.selected_skills),
            "skill_route_confidence": self.confidence,
            "skill_route_reason": self.reason,
            "skill_candidates": [candidate.as_metadata() for candidate in self.candidates],
        }
        if self.disabled_best_match:
            metadata["disabled_best_match"] = self.disabled_best_match
            metadata["disabled_best_match_score"] = self.disabled_best_match_score
            metadata["disabled_best_match_reason"] = self.disabled_best_match_reason
        if self.generic_fallback_confirmed is not None:
            metadata["generic_fallback_confirmed"] = self.generic_fallback_confirmed
        if self.status:
            metadata["status"] = self.status
        return metadata

    def with_generic_fallback_confirmation(self, confirmed: bool) -> SkillRouteResult:
        return replace(
            self,
            generic_fallback_confirmed=confirmed,
            status="" if confirmed else "cancelled",
        )


def classify_task_intent(user_request: str, snapshot: ProjectSnapshot | None = None) -> TaskIntent:
    lowered = user_request.strip().lower()
    if not lowered:
        return TaskIntent("unrelated", 0.0, [], "empty_request")

    scores: dict[str, float] = {}
    indicators: dict[str, list[str]] = {}
    for label, phrases in INTENT_INDICATORS.items():
        for phrase in phrases:
            if phrase in lowered:
                scores[label] = scores.get(label, 0.0) + (0.45 if " " in phrase else 0.25)
                indicators.setdefault(label, []).append(phrase)

    token_set = set(_tokens(lowered))
    if {"review", "code"} <= token_set or {"inspect", "diff"} <= token_set:
        scores["code_review"] = scores.get("code_review", 0.0) + 0.45
        indicators.setdefault("code_review", []).append("review/diff tokens")
    if "mr-style" in lowered or "pr-style" in lowered or ({"review", "changes"} <= token_set and token_set & {"mr", "pr", "feedback"}):
        scores["code_review"] = scores.get("code_review", 0.0) + 0.55
        indicators.setdefault("code_review", []).append("review feedback tokens")
    if token_set & {"frontend", "ui", "interface", "dashboard"}:
        scores["frontend_build"] = scores.get("frontend_build", 0.0) + 0.35
    if token_set & {"docs", "documentation", "readme"}:
        scores["documentation"] = scores.get("documentation", 0.0) + 0.35
    if token_set & {"test", "tests", "pytest", "coverage"}:
        scores["testing"] = scores.get("testing", 0.0) + 0.35
    if token_set & {"docker", "dockerfile", "deploy", "deployment", "ci", "cicd"}:
        scores["deployment"] = scores.get("deployment", 0.0) + 0.35

    if not scores and any(term in lowered for term in UNRELATED_INDICATORS) and not _has_project_context(lowered):
        return TaskIntent("unrelated", 0.74, [term for term in UNRELATED_INDICATORS if term in lowered], "unrelated_terms_without_project_context")

    if not scores and _has_project_context(lowered):
        return TaskIntent("general_project_help", 0.46, ["project context"], "project_context_without_specific_task_intent")

    if not scores:
        return TaskIntent("unrelated", 0.28, [], "no_task_intent_indicators")

    label, raw_score = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0]
    confidence = min(0.96, 0.38 + raw_score)
    if snapshot is not None and _snapshot_supports_intent(label, snapshot):
        confidence = min(0.98, confidence + 0.06)
    return TaskIntent(label, round(confidence, 3), indicators.get(label, []), f"{label}_indicators_matched")


def route_task(
    user_request: str,
    skills: list[Skill],
    *,
    snapshot: ProjectSnapshot | None = None,
    config: SnappyConfig | None = None,
    limit: int = 3,
) -> SkillRouteResult:
    raw_candidates: list[SkillRouteCandidate] = []
    disabled_names = set(config.skills.disabled) if config is not None else set()
    intent = classify_task_intent(user_request, snapshot)
    if intent.label != "unrelated":
        raw_candidates = [_score_skill(user_request, skill, intent, snapshot) for skill in skills]
        raw_candidates = [candidate for candidate in raw_candidates if candidate.score >= 0.24]
        raw_candidates.sort(key=lambda item: (-item.score, item.skill_name))

    available_skills = _filter_allowed_skills(skills, config)
    if intent.label == "unrelated" and intent.confidence >= 0.7 and not _explicit_skill_request(user_request, available_skills):
        return SkillRouteResult([], [], intent, intent.confidence, "request_classified_unrelated")

    candidates = [_score_skill(user_request, skill, intent, snapshot) for skill in available_skills]
    candidates = [candidate for candidate in candidates if candidate.score >= 0.24]
    candidates.sort(key=lambda item: (-item.score, item.skill_name))

    selected = _select_candidates(candidates, intent, limit=limit)
    confidence = min(1.0, selected[0].score if selected else intent.confidence)
    reason = "selected_matching_skill" if selected else "no_matching_skill_selected"
    if _is_ambiguous(candidates):
        reason = "ambiguous_skill_candidates"
    disabled_best = _disabled_best_match(raw_candidates, disabled_names, selected)
    return SkillRouteResult(
        [candidate.skill_name for candidate in selected],
        candidates[:limit],
        intent,
        round(confidence, 3),
        reason,
        disabled_best_match=disabled_best.skill_name if disabled_best is not None else None,
        disabled_best_match_score=disabled_best.score if disabled_best is not None else None,
        disabled_best_match_reason=", ".join(disabled_best.reasons) if disabled_best is not None else "",
    )


def route_to_skill_matches(route: SkillRouteResult, skills: list[Skill]) -> list[SkillMatch]:
    by_name = {skill.metadata.name: skill for skill in skills}
    candidates = {candidate.skill_name: candidate for candidate in route.candidates}
    matches: list[SkillMatch] = []
    for name in route.selected_skills:
        skill = by_name.get(name)
        candidate = candidates.get(name)
        if skill is not None and candidate is not None:
            matches.append(SkillMatch(skill=skill, score=candidate.score, reasons=list(candidate.reasons)))
    return matches


def _score_skill(
    user_request: str,
    skill: Skill,
    intent: TaskIntent,
    snapshot: ProjectSnapshot | None,
) -> SkillRouteCandidate:
    lowered = user_request.lower()
    reasons: list[str] = []
    matched_terms: list[str] = []
    relationship_hints = _string_list(skill.metadata.snappy.get("project_relationships"))
    score = 0.0

    explicit_match = _skill_name_matches_request(skill.metadata.name, lowered)
    if explicit_match:
        score += 0.9
        reasons.append("explicit skill name matched")
        matched_terms.append(skill.metadata.name)

    task_intents = _string_list(skill.metadata.snappy.get("task_intents"))
    if intent.label in task_intents:
        score += 0.7
        reasons.append(f"matched task_intent {intent.label}")

    inferred_intents = _infer_skill_intents(skill)
    if intent.label in inferred_intents:
        score += 0.35
        reasons.append(f"inferred task intent {intent.label}")

    indicators = _string_list(skill.metadata.snappy.get("indicators"))
    for indicator in indicators:
        indicator_lower = indicator.lower()
        if indicator_lower and indicator_lower in lowered:
            score += 0.45
            reasons.append(f"matched indicator {indicator}")
            matched_terms.append(indicator)
            break

    skill_text = " ".join([skill.metadata.name.replace("-", " "), skill.metadata.description, " ".join(_headings(skill.body))]).lower()
    request_tokens = set(_tokens(lowered))
    skill_tokens = set(_tokens(skill_text))
    token_hits = sorted(request_tokens & skill_tokens)
    if token_hits:
        score += min(0.35, 0.06 * len(token_hits))
        reasons.append(f"matched terms: {', '.join(token_hits[:6])}")
        matched_terms.extend(token_hits[:6])

    if relationship_hints and intent.label in INTENT_RELATIONSHIP_HINTS:
        if set(relationship_hints) & set(INTENT_RELATIONSHIP_HINTS[intent.label]):
            score += 0.16
            reasons.append("matched relationship hint")

    extension_targets = _string_list(skill.metadata.snappy.get("extension_targets"))
    if snapshot is not None and extension_targets:
        project_terms = set(snapshot.languages) | set(snapshot.package_managers) | set(snapshot.frameworks)
        target_hits = sorted(set(extension_targets) & project_terms)
        if target_hits:
            score += min(0.16, 0.05 * len(target_hits))
            reasons.append(f"matched project target: {', '.join(target_hits)}")
            matched_terms.extend(target_hits)

    return SkillRouteCandidate(
        skill_name=skill.metadata.name,
        score=round(score, 3),
        reasons=reasons,
        matched_terms=_dedupe(matched_terms),
        relationship_hints=relationship_hints,
    )


def _select_candidates(candidates: list[SkillRouteCandidate], intent: TaskIntent, *, limit: int) -> list[SkillRouteCandidate]:
    if not candidates:
        return []
    best = candidates[0]
    if best.score < 0.34 and intent.confidence < 0.55:
        return []
    if _is_ambiguous(candidates):
        return [candidate for candidate in candidates[:limit] if best.score - candidate.score <= 0.08]
    return [best]


def _is_ambiguous(candidates: list[SkillRouteCandidate]) -> bool:
    return len(candidates) > 1 and candidates[0].score >= 0.34 and candidates[0].score - candidates[1].score <= 0.08


def _disabled_best_match(
    raw_candidates: list[SkillRouteCandidate],
    disabled_names: set[str],
    selected: list[SkillRouteCandidate],
) -> SkillRouteCandidate | None:
    if not raw_candidates or selected:
        return None
    best = raw_candidates[0]
    if best.skill_name not in disabled_names:
        return None
    if best.score < 0.34:
        return None
    return best


def _filter_allowed_skills(skills: list[Skill], config: SnappyConfig | None) -> list[Skill]:
    if config is None:
        return list(skills)
    enabled = set(config.skills.enabled)
    disabled = set(config.skills.disabled)
    explicit_project_config = config.path is not None
    allowed: list[Skill] = []
    for skill in skills:
        name = skill.metadata.name
        if name in disabled:
            continue
        if explicit_project_config and name not in enabled:
            continue
        allowed.append(skill)
    return allowed


def _infer_skill_intents(skill: Skill) -> set[str]:
    text = " ".join(
        [
            skill.metadata.name.replace("-", " "),
            skill.metadata.description,
            " ".join(_string_list(skill.metadata.snappy.get("indicators"))),
        ]
    ).lower()
    inferred: set[str] = set()
    for label, phrases in INTENT_INDICATORS.items():
        if any(phrase in text for phrase in phrases):
            inferred.add(label)
    if "review" in text and any(term in text for term in ("code", "diff", "pr", "mr", "merge request", "pull request")):
        inferred.add("code_review")
    if "frontend" in text or "ui" in text or "interface" in text:
        inferred.add("frontend_build")
    if "doc" in text or "readme" in text:
        inferred.add("documentation")
    if "test" in text:
        inferred.add("testing")
    if "docker" in text or "deploy" in text or "ci/cd" in text or "github actions" in text:
        inferred.add("deployment")
    if any(term in text for term in ("commit message", "git commit", "project", "codebase", "help")):
        inferred.add("general_project_help")
    return inferred


def _explicit_skill_request(user_request: str, skills: list[Skill]) -> bool:
    lowered = user_request.lower()
    return any(_skill_name_matches_request(skill.metadata.name, lowered) for skill in skills)


def _skill_name_matches_request(skill_name: str, request_lower: str) -> bool:
    normalized = skill_name.lower()
    spaced = normalized.replace("-", " ")
    compact = normalized.replace("-", "")
    request_compact = re.sub(r"[^a-z0-9]+", "", request_lower)
    generic_parts = {"design", "review", "helper", "support", "frontend", "backend", "testing", "deployment"}
    parts = [part for part in normalized.split("-") if len(part) >= 6 and part not in generic_parts]
    return normalized in request_lower or spaced in request_lower or compact in request_compact or any(part in request_lower for part in parts)


def _snapshot_supports_intent(label: str, snapshot: ProjectSnapshot) -> bool:
    if label == "frontend_build":
        return bool(set(snapshot.languages) & {"javascript", "typescript", "vue", "svelte"} or set(snapshot.frameworks) & {"react", "vue", "svelte"})
    if label == "documentation":
        return bool(snapshot.docs)
    if label == "testing":
        return bool(snapshot.test_files)
    if label == "deployment":
        return bool(set(snapshot.config_files) & {"Dockerfile", "docker-compose.yml", ".github/workflows"})
    return bool(snapshot.source_files or snapshot.sampled_files)


def _has_project_context(text: str) -> bool:
    return bool(re.search(r"\b(this|current)\s+(project|app|application|repo|repository|codebase|workspace|package|service|api|cli)\b", text))


def _headings(body: str) -> list[str]:
    headings: list[str] = []
    for line in body.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", line)
        if match:
            headings.append(match.group("title"))
    return headings


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _tokens(text: str) -> list[str]:
    stopwords = {"the", "this", "that", "for", "with", "and", "or", "a", "an", "to", "me", "my", "use", "when"}
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1 and token not in stopwords]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def route_metadata(route: SkillRouteResult | None) -> dict[str, Any] | None:
    return route.as_metadata() if route is not None else None
