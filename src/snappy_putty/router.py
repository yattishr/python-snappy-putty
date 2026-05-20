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
ROUTE_DESTRUCTIVE_INTENT = "destructive_or_high_risk_intent"
ROUTE_FS_MUTATION = "fs_mutation"
ROUTE_GIT_READ = "git_read"
ROUTE_SAFE_INSPECT = "safe_inspect"
ROUTE_INSPECT_PROJECT = "inspect_project"
ROUTE_INSPECT_FILES = "inspect_files"
ROUTE_INSPECT_STRUCTURE = "inspect_structure"
ROUTE_INSPECT_FILE = "inspect_file"
ROUTE_SHOW_SNAPSHOT = "show_snapshot"
ROUTE_SHOW_PLAN = "show_plan"
ROUTE_SHOW_LAST_RUN = "show_last_run"
ROUTE_SHOW_RUNS = "show_runs"
ROUTE_SHOW_PENDING = "show_pending"
ROUTE_RESUME_PENDING = "resume_pending"
ROUTE_CLEAR_PENDING = "clear_pending"
ROUTE_PARK_PENDING = "park_pending"
ROUTE_WHY_PLAN = "why_plan"
ROUTE_EXPLAIN_STEP = "explain_step"
ROUTE_REFINE_PLAN = "refine_plan"
ROUTE_REFRESH_SNAPSHOT = "refresh_snapshot"
ROUTE_ASK = "ask"
ROUTE_OUT_OF_SCOPE = "out_of_scope"
ROUTE_UNKNOWN = "unknown"

_EXPLAIN_PATTERN = re.compile(r"^\s*explain(?:\s+(?P<command>.+))?\s*$", flags=re.IGNORECASE | re.DOTALL)
_EXPLAIN_STEP_PATTERN = re.compile(r"^\s*explain\s+step\s+(?P<step>\d+)\s*$", flags=re.IGNORECASE)
_REFINE_STEP_PATTERN = re.compile(
    r"^\s*refine\s+step\s+(?P<step>\d+)(?:\s+(?P<change>.+))?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_REFINE_PLAN_PATTERN = re.compile(r"^\s*refine\s+plan(?:\s+(?P<change>.+))?\s*$", flags=re.IGNORECASE | re.DOTALL)
_WRAPPING_QUOTES = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
}
_DESTRUCTIVE_VERBS = (
    "delete",
    "remove",
    "wipe",
    "erase",
    "destroy",
    "drop",
    "purge",
    "overwrite",
    "reset",
    "reset hard",
    "force push",
    "rm -rf",
    "clean",
)
_BROAD_DESTRUCTIVE_TARGETS = (
    "all files",
    "everything",
    "filesystem",
    "root",
    "home directory",
    "repo",
    "repository",
    "project",
    "production",
    "database",
    ".env",
    "secrets",
    "credentials",
)
_UNSAFE_SCOPED_TARGETS = {"/", "~", "$home", "..", ".env", ".git"}
_BROAD_CLEANUP_PHRASES = (
    "clean the entire filesystem",
    "clean entire filesystem",
    "clean the whole filesystem",
    "clean whole filesystem",
    "clean the entire machine",
    "clean entire machine",
    "clean everything",
    "clean all files",
    "clean all data",
    "wipe environment",
    "reset the environment",
    "reset environment",
    "reset everything",
    "remove all artifacts",
    "delete all artifacts",
    "purge all artifacts",
)


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
    if lowered in {"show directory tree", "show tests"}:
        return True
    if re.match(r"^\s*read\s+\S+", lowered):
        return True
    if "git worktree" in lowered and any(token in lowered for token in ("list", "listing", "show")):
        return True
    return False


def _destructive_intent_payload(text: str) -> dict[str, str] | None:
    stripped = text.strip()
    lowered = stripped.lower()
    if not lowered:
        return None

    matched_verb = next((verb for verb in _DESTRUCTIVE_VERBS if re.search(rf"\b{re.escape(verb)}\b", lowered)), None)
    if matched_verb is None:
        return None

    if any(phrase in lowered for phrase in _BROAD_CLEANUP_PHRASES):
        return {"intent": stripped, "kind": "cleanup_broad", "reason": "destructive_intent"}

    if matched_verb == "clean" and not any(target in lowered for target in ("build", "dist", "output", "cache", "temp", "temporary")):
        return None

    if "rm -rf" in lowered and re.search(r"rm\s+-rf\s+/(?:\s|$)", lowered):
        return {"intent": stripped, "kind": "broad", "reason": "destructive_intent"}

    if any(target in lowered for target in _BROAD_DESTRUCTIVE_TARGETS):
        return {"intent": stripped, "kind": "broad", "reason": "destructive_intent"}

    tokens = re.split(r"\s+", stripped)
    target = tokens[-1].strip("\"'") if tokens else ""
    if target.lower() in _UNSAFE_SCOPED_TARGETS or target.startswith("/"):
        return {"intent": stripped, "kind": "broad", "reason": "destructive_intent", "target": target}

    return {"intent": stripped, "kind": "scoped", "reason": "destructive_scoped_operation", "target": target}


def _is_supported_ask_intent(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    if "?" in lowered:
        return True

    ask_prefixes = (
        "deploy",
        "summarize",
        "give me",
        "tell me",
        "show me",
        "latest",
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


def _is_tech_related_intent(text: str) -> bool:
    lowered = text.lower()
    tech_terms = (
        "software",
        "hardware",
        "technology",
        "tech",
        "code",
        "coding",
        "program",
        "programming",
        "app",
        "application",
        "cli",
        "terminal",
        "shell",
        "command",
        "repository",
        "repo",
        "git",
        "branch",
        "commit",
        "pull request",
        "bug",
        "error",
        "stack trace",
        "debug",
        "fix",
        "build",
        "deploy",
        "test",
        "refactor",
        "script",
        "function",
        "class",
        "api",
        "sdk",
        "package",
        "dependency",
        "install",
        "version",
        "database",
        "server",
        "client",
        "network",
        "linux",
        "windows",
        "mac",
        "python",
        "javascript",
        "typescript",
        "rust",
        "go",
        "java",
        "c++",
        "c#",
        "ruby",
        "php",
        "html",
        "css",
        "react",
        "node",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "openai",
        "llm",
        "ai",
        "machine learning",
        "security",
        "database",
        "sql",
        "regex",
        "vim",
        "neovim",
    )

    def _term_matches(term: str) -> bool:
        if term in {"c++", "c#"}:
            return term in lowered
        return re.search(rf"\b{re.escape(term)}\b", lowered) is not None

    return any(_term_matches(term) for term in tech_terms)


def _is_out_of_scope_intent(text: str) -> bool:
    lowered = text.lower().strip()
    if not _is_supported_ask_intent(lowered):
        return False
    if _is_tech_related_intent(lowered):
        return False

    topical_markers = (
        "news",
        "weather",
        "forecast",
        "sports",
        "score",
        "scores",
        "politics",
        "election",
        "celebrity",
        "movie",
        "movies",
        "music",
        "recipe",
        "recipes",
        "travel",
        "restaurant",
        "restaurants",
        "shopping",
        "fashion",
        "joke",
        "story",
        "poem",
        "finance",
        "stock",
        "stocks",
        "crypto",
        "bitcoin",
        "crypto price",
        "latest news",
        "breaking news",
    )
    return any(marker in lowered for marker in topical_markers)


def classify_input(text: str) -> RouteDecision:
    stripped = _strip_wrapping_quotes(text.strip())
    lowered = stripped.lower()

    destructive_payload = _destructive_intent_payload(stripped)
    if destructive_payload is not None:
        return RouteDecision(route=ROUTE_DESTRUCTIVE_INTENT, payload=destructive_payload)

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
    if lowered == "show last run":
        return RouteDecision(route=ROUTE_SHOW_LAST_RUN, payload={"text": stripped})
    if lowered == "show runs":
        return RouteDecision(route=ROUTE_SHOW_RUNS, payload={"text": stripped})
    if lowered == "show pending":
        return RouteDecision(route=ROUTE_SHOW_PENDING, payload={"text": stripped})
    if lowered == "resume pending":
        return RouteDecision(route=ROUTE_RESUME_PENDING, payload={"text": stripped})
    if lowered == "clear pending":
        return RouteDecision(route=ROUTE_CLEAR_PENDING, payload={"text": stripped})
    if lowered in {"park", "park this"}:
        return RouteDecision(route=ROUTE_PARK_PENDING, payload={"text": stripped})
    if lowered in {"why this plan", "why plan"}:
        return RouteDecision(route=ROUTE_WHY_PLAN, payload={"text": stripped})
    explain_step_match = _EXPLAIN_STEP_PATTERN.match(stripped)
    if explain_step_match:
        return RouteDecision(route=ROUTE_EXPLAIN_STEP, payload={"text": stripped, "step": explain_step_match.group("step")})
    refine_plan_match = _REFINE_PLAN_PATTERN.match(stripped)
    if refine_plan_match:
        payload = {"text": stripped, "scope": "plan"}
        change = (refine_plan_match.group("change") or "").strip()
        if change:
            payload["change"] = change
        return RouteDecision(route=ROUTE_REFINE_PLAN, payload=payload)
    refine_step_match = _REFINE_STEP_PATTERN.match(stripped)
    if refine_step_match:
        payload = {"text": stripped, "scope": "step", "step": refine_step_match.group("step")}
        change = (refine_step_match.group("change") or "").strip()
        if change:
            payload["change"] = change
        return RouteDecision(route=ROUTE_REFINE_PLAN, payload=payload)
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

    if _is_out_of_scope_intent(stripped):
        return RouteDecision(route=ROUTE_OUT_OF_SCOPE, payload={"intent": stripped})

    if _is_supported_ask_intent(stripped):
        return RouteDecision(route=ROUTE_ASK, payload={"intent": stripped})

    return RouteDecision(route=ROUTE_UNKNOWN, payload={"text": stripped})


def _strip_wrapping_quotes(text: str) -> str:
    if len(text) < 2:
        return text
    closing = _WRAPPING_QUOTES.get(text[0])
    if closing is not None and text[-1] == closing:
        return text[1:-1].strip()
    return text
