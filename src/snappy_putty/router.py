from __future__ import annotations

from dataclasses import dataclass, field
import re

from snappy_putty.fs_ops import looks_like_fs_mutation_intent


ROUTE_BUILTIN_HELP = "builtin_help"
ROUTE_BUILTIN_DOCTOR = "builtin_doctor"
ROUTE_BUILTIN_EXIT = "builtin_exit"
ROUTE_EXPLAIN = "explain"
ROUTE_FS_MUTATION = "fs_mutation"
ROUTE_SAFE_INSPECT = "safe_inspect"
ROUTE_ASK = "ask"

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


def classify_input(text: str) -> RouteDecision:
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered == "help":
        return RouteDecision(route=ROUTE_BUILTIN_HELP, payload={"text": stripped})
    if lowered == "doctor":
        return RouteDecision(route=ROUTE_BUILTIN_DOCTOR, payload={"text": stripped})
    if lowered in {"exit", "quit"}:
        return RouteDecision(route=ROUTE_BUILTIN_EXIT, payload={"text": stripped})

    explain_match = _EXPLAIN_PATTERN.match(stripped)
    if explain_match:
        command = (explain_match.group("command") or "").strip()
        return RouteDecision(route=ROUTE_EXPLAIN, payload={"command": command, "text": stripped})

    if looks_like_fs_mutation_intent(stripped):
        return RouteDecision(route=ROUTE_FS_MUTATION, payload={"intent": stripped})

    if _is_safe_inspection_intent(stripped):
        return RouteDecision(route=ROUTE_SAFE_INSPECT, payload={"intent": stripped})

    return RouteDecision(route=ROUTE_ASK, payload={"intent": stripped})
