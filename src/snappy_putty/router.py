from __future__ import annotations

from dataclasses import dataclass, field
import re

from snappy_putty.fs_ops import looks_like_fs_mutation_intent
from snappy_putty.git_read import parse_git_read_intent


ROUTE_BUILTIN_HELP = "builtin_help"
ROUTE_BUILTIN_DOCTOR = "builtin_doctor"
ROUTE_BUILTIN_EXIT = "builtin_exit"
ROUTE_BUILTIN_AFTER = "builtin_after"
ROUTE_BUILTIN_STATUS = "builtin_status"
ROUTE_BUILTIN_CANCEL = "builtin_cancel"
ROUTE_EXPLAIN = "explain"
ROUTE_FS_MUTATION = "fs_mutation"
ROUTE_GIT_READ = "git_read"
ROUTE_SAFE_INSPECT = "safe_inspect"
ROUTE_INSPECT_PROJECT = "inspect_project"
ROUTE_INSPECT_FILES = "inspect_files"
ROUTE_INSPECT_STRUCTURE = "inspect_structure"
ROUTE_INSPECT_FILE = "inspect_file"
ROUTE_SHOW_SNAPSHOT = "show_snapshot"
ROUTE_SHOW_PLAN = "show_plan"
ROUTE_REFRESH_SNAPSHOT = "refresh_snapshot"
ROUTE_ASK = "ask"
ROUTE_UNKNOWN = "unknown"

_EXPLAIN_PATTERN = re.compile(r"^\s*explain(?:\s+(?P<command>.+))?\s*$", flags=re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    payload: dict[str, str] = field(default_factory=dict)


def _is_safe_inspection_intent(text: str) -> bool:
    lowered = text.lower()
    has_list_verb = any(token in lowered for token in ("list", "listing", "show"))
    has_path_noun = any(token in lowered for token in ("file", "files", "directory", "directories", "folder", "folders"))
    if has_list_verb and has_path_noun:
        return True
    if "git worktree" in lowered and any(token in lowered for token in ("list", "listing", "show")):
        return True
    return False


def _is_supported_ask_intent(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    if "?" in lowered:
        return True

    ask_prefixes = (
        "deploy",
        "summarize",
        "what ",
        "how ",
        "why ",
        "when ",
        "where ",
        "which ",
        "who ",
        "can ",
        "could ",
        "should ",
        "would ",
        "help ",
        "plan ",
        "suggest ",
        "recommend ",
        "troubleshoot ",
        "fix ",
        "debug ",
    )
    return any(lowered.startswith(prefix) for prefix in ask_prefixes)


def classify_input(text: str) -> RouteDecision:
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered == "inspect project":
        return RouteDecision(route=ROUTE_INSPECT_PROJECT, payload={"text": stripped})
    if lowered == "inspect files":
        return RouteDecision(route=ROUTE_INSPECT_FILES, payload={"text": stripped})
    if lowered == "inspect structure":
        return RouteDecision(route=ROUTE_INSPECT_STRUCTURE, payload={"text": stripped})
    if lowered.startswith("inspect file"):
        path = stripped[len("inspect file") :].strip()
        return RouteDecision(route=ROUTE_INSPECT_FILE, payload={"text": stripped, "path": path})
    if lowered == "show snapshot":
        return RouteDecision(route=ROUTE_SHOW_SNAPSHOT, payload={"text": stripped})
    if lowered == "show plan":
        return RouteDecision(route=ROUTE_SHOW_PLAN, payload={"text": stripped})
    if lowered == "refresh snapshot":
        return RouteDecision(route=ROUTE_REFRESH_SNAPSHOT, payload={"text": stripped})

    if lowered == "help":
        return RouteDecision(route=ROUTE_BUILTIN_HELP, payload={"text": stripped})
    if lowered == "doctor":
        return RouteDecision(route=ROUTE_BUILTIN_DOCTOR, payload={"text": stripped})
    if lowered == "after":
        return RouteDecision(route=ROUTE_BUILTIN_AFTER, payload={"text": stripped})
    if lowered == "status":
        return RouteDecision(route=ROUTE_BUILTIN_STATUS, payload={"text": stripped})
    if lowered == "cancel":
        return RouteDecision(route=ROUTE_BUILTIN_CANCEL, payload={"text": stripped})
    if lowered in {"exit", "quit"}:
        return RouteDecision(route=ROUTE_BUILTIN_EXIT, payload={"text": stripped})

    explain_match = _EXPLAIN_PATTERN.match(stripped)
    if explain_match:
        command = (explain_match.group("command") or "").strip()
        return RouteDecision(route=ROUTE_EXPLAIN, payload={"command": command, "text": stripped})

    if looks_like_fs_mutation_intent(stripped):
        return RouteDecision(route=ROUTE_FS_MUTATION, payload={"intent": stripped})

    git_intent = parse_git_read_intent(stripped)
    if git_intent is not None:
        payload = {"intent": stripped, "kind": git_intent.kind}
        if git_intent.count is not None:
            payload["count"] = str(git_intent.count)
        if git_intent.commit is not None:
            payload["commit"] = git_intent.commit
        return RouteDecision(route=ROUTE_GIT_READ, payload=payload)

    if _is_safe_inspection_intent(stripped):
        return RouteDecision(route=ROUTE_SAFE_INSPECT, payload={"intent": stripped})

    if _is_supported_ask_intent(stripped):
        return RouteDecision(route=ROUTE_ASK, payload={"intent": stripped})

    return RouteDecision(route=ROUTE_UNKNOWN, payload={"text": stripped})
