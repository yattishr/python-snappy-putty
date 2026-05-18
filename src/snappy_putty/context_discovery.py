from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Callable

from snappy_putty.project_inspector import ProjectSnapshot


STRATEGY = "bounded_context_discovery_v1"
MAX_SELECTED_FILES = 12
MAX_EXPANSION_FILES = 5
MAX_TOTAL_FILES = 15
MAX_CONTEXT_BUNDLE_CHARS = 30_000
MAX_PER_FILE_CHARS = 6_000

EXCLUDED_DIRS = {
    ".git",
    ".snappy",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".cache",
    ".turbo",
    ".vite",
    "out",
    ".parcel-cache",
    "vendor",
    "target",
    ".next",
    ".nuxt",
}

CONFIG_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "jsconfig.json",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "nuxt.config.js",
    "nuxt.config.ts",
    "eslint.config.js",
    "eslint.config.mjs",
    ".eslintrc",
    ".eslintrc.json",
    "tailwind.config.js",
    "tailwind.config.ts",
    "postcss.config.js",
    "composer.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
}

LANGUAGE_MAP = {
    ".py": "python",
    ".md": "markdown",
    ".toml": "toml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shell",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".vue": "vue",
    ".svelte": "svelte",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".php": "php",
    ".go": "go",
    ".rs": "rust",
}

SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".vue",
    ".svelte",
    ".json",
    ".css",
    ".scss",
    ".html",
    ".php",
    ".go",
    ".rs",
}
TEST_PATTERNS = ("test_", "_test.", ".test.", ".spec.")
ENTRYPOINT_NAMES = {
    "main.py",
    "cli.py",
    "app.py",
    "commands.py",
    "index.js",
    "cli.js",
    "main.js",
    "src/index.ts",
    "src/cli.ts",
    "index.php",
    "cli.php",
    "console.php",
    "artisan",
    "main.go",
    "main.rs",
}
ENTRYPOINT_MARKERS = (
    'if __name__ == "__main__"',
    "if __name__ == '__main__'",
    "def main(",
    "sys.argv",
    "argparse",
    "click",
    "typer",
    "process.argv",
    "commander",
    "yargs",
    "cac",
    "meow",
    "$argv",
    "Symfony Console",
    "Laravel Artisan",
    "flag.Parse",
    "cobra",
    "urfave/cli",
    "fn main(",
    "clap",
    "structopt",
)
SYMBOL_PATTERNS = {
    "python": re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "javascript": re.compile(r"\b(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", re.MULTILINE),
    "typescript": re.compile(r"\b(?:function|class|interface|type)\s+([A-Za-z_$][A-Za-z0-9_$]*)|\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", re.MULTILINE),
    "go": re.compile(r"^\s*func\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "rust": re.compile(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "php": re.compile(r"\b(?:function|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
}
IMPORT_PATTERNS = {
    "python": re.compile(r"^\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", re.MULTILINE),
    "javascript": re.compile(r"(?:from\s+[\"']([^\"']+)[\"']|require\([\"']([^\"']+)[\"']\))"),
    "typescript": re.compile(r"(?:from\s+[\"']([^\"']+)[\"']|require\([\"']([^\"']+)[\"']\))"),
    "go": re.compile(r"import\s+(?:\(\s*)?[\"`]([^\"`]+)[\"`]"),
    "rust": re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE),
    "php": re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE),
}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "be",
    "for",
    "help",
    "implement",
    "improve",
    "in",
    "me",
    "of",
    "please",
    "the",
    "this",
    "to",
    "with",
}
TERM_EXPANSIONS = {
    "logging": ["log", "logger", "debug", "verbose", "output", "trace"],
    "log": ["logging", "logger", "debug", "verbose", "output", "trace"],
    "cli": ["command", "commands", "terminal", "arg", "args", "main"],
}


@dataclass(frozen=True)
class RepoFile:
    path: str
    kind: str
    language: str | None
    size_bytes: int
    role_hints: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    content_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepoMap:
    root: str
    languages: list[str]
    files: list[RepoFile]
    tests: list[str]
    docs: list[str]
    configs: list[str]
    entrypoint_candidates: list[str]


@dataclass(frozen=True)
class SelectedContextFile:
    path: str
    role: str
    kind: str
    score: int
    reason: str
    imports: list[str]
    symbols: list[str]
    content_hints: list[str]
    snippet: str


@dataclass(frozen=True)
class SufficiencyResult:
    sufficient: bool
    reason: str
    missing_context_queries: list[str] = field(default_factory=list)
    files_to_read_next: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextDiscoveryResult:
    goal: str
    snapshot_id: str
    repo_map: RepoMap
    selected_context: list[SelectedContextFile]
    sufficiency: dict[str, Any]
    expanded: bool
    rejected_expansion_files: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy": STRATEGY,
            "max_files": MAX_SELECTED_FILES,
            "max_expansion_files": MAX_EXPANSION_FILES,
            "max_total_files": MAX_TOTAL_FILES,
            "expanded": self.expanded,
            "sufficiency": self.sufficiency,
            "files": [
                {"path": item.path, "role": item.role, "score": item.score, "reason": item.reason}
                for item in self.selected_context
            ],
            "rejected_expansion_files": list(self.rejected_expansion_files),
        }

    def bundle_payload(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "snapshot_id": self.snapshot_id,
            "repo_map_summary": repo_map_summary(self.repo_map),
            "selected_context": [asdict(item) for item in self.selected_context],
            "sufficiency": self.sufficiency,
        }


def build_repo_map(snapshot: ProjectSnapshot) -> RepoMap:
    root = Path(snapshot.root_path)
    files: list[RepoFile] = []
    for path in _iter_files(root):
        rel_path = str(path.relative_to(root)).replace(os.sep, "/")
        text = _read_sample(path)
        language = LANGUAGE_MAP.get(path.suffix.lower())
        kind = _file_kind(rel_path)
        role_hints = _role_hints(rel_path, text)
        files.append(
            RepoFile(
                path=rel_path,
                kind=kind,
                language=language,
                size_bytes=_safe_size(path),
                role_hints=role_hints,
                symbols=_extract_symbols(language, text),
                imports=_extract_imports(language, text),
                content_hints=_content_hints(text),
            )
        )
    languages = sorted({item.language for item in files if item.language})
    return RepoMap(
        root=str(root),
        languages=languages,
        files=files,
        tests=[item.path for item in files if item.kind == "test"],
        docs=[item.path for item in files if item.kind == "doc"],
        configs=[item.path for item in files if item.kind == "config"],
        entrypoint_candidates=[item.path for item in files if "entrypoint_candidate" in item.role_hints],
    )


def discover_context(
    goal: str,
    snapshot: ProjectSnapshot,
    *,
    sufficiency_checker: Callable[[str, RepoMap, list[SelectedContextFile]], SufficiencyResult] | None = None,
    progress: Callable[[str], None] | None = None,
) -> ContextDiscoveryResult:
    _emit(progress, "Building repo map...")
    repo_map = build_repo_map(snapshot)
    _emit(progress, "Analyzing relevant files...")
    terms = derive_goal_terms(goal)
    ranked = rank_files(goal, repo_map, terms=terms)
    selected_paths = _balanced_selection(ranked, repo_map, max_files=MAX_SELECTED_FILES)
    _emit(progress, "Preparing context...")
    selected = compress_context(repo_map, selected_paths, ranked)
    _emit(progress, "Checking context sufficiency...")
    initial = sufficiency_checker(goal, repo_map, selected) if sufficiency_checker else heuristic_sufficiency(goal, repo_map, selected)
    expanded = False
    rejected: list[str] = []
    final = initial
    if not initial.sufficient:
        expansion = _expansion_paths(initial, ranked, repo_map, selected_paths, rejected)
        if expansion:
            expanded = True
            _emit(progress, "Expanding context...")
            selected_paths = _dedupe([*selected_paths, *expansion])[:MAX_TOTAL_FILES]
            selected = compress_context(repo_map, selected_paths, ranked)
            final = sufficiency_checker(goal, repo_map, selected) if sufficiency_checker else heuristic_sufficiency(goal, repo_map, selected)
    return ContextDiscoveryResult(
        goal=goal,
        snapshot_id=snapshot.snapshot_id,
        repo_map=repo_map,
        selected_context=selected,
        sufficiency={
            "initial_sufficient": initial.sufficient,
            "expanded": expanded,
            "final_sufficient": final.sufficient,
            "reason": final.reason,
            "missing_context_queries": final.missing_context_queries,
            "files_to_read_next": final.files_to_read_next,
        },
        expanded=expanded,
        rejected_expansion_files=rejected,
    )


def derive_goal_terms(goal: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[a-z0-9_]+", goal.lower()):
        if len(token) < 3 or token in STOP_WORDS:
            continue
        terms.append(token)
        terms.extend(TERM_EXPANSIONS.get(token, []))
        if token.endswith("ing") and len(token) > 5:
            terms.append(token[:-3])
        if token.endswith("s") and len(token) > 4:
            terms.append(token[:-1])
    return _dedupe(terms)


def rank_files(goal: str, repo_map: RepoMap, *, terms: list[str] | None = None) -> dict[str, tuple[int, list[str]]]:
    active_terms = terms or derive_goal_terms(goal)
    selected_source_names: set[str] = set()
    scores: dict[str, tuple[int, list[str]]] = {}
    for item in repo_map.files:
        score = 0
        reasons: list[str] = []
        path_lower = item.path.lower()
        text_fields = " ".join([path_lower, *item.symbols, *item.imports, *item.content_hints]).lower()
        if any(term in path_lower for term in active_terms):
            score += 10
            reasons.append("goal term match in path/name")
        if "entrypoint_candidate" in item.role_hints:
            score += 8
            reasons.append("entrypoint candidate")
        if any(term in " ".join(item.content_hints).lower() for term in active_terms):
            score += 7
            reasons.append("content hint match")
        if any(term in " ".join([*item.symbols, *item.imports]).lower() for term in active_terms):
            score += 6
            reasons.append("symbol/import match")
        if item.kind == "source":
            if any(term in text_fields for term in active_terms) or _implementation_name(item.path):
                score += 5
                reasons.append("source file related to goal")
                selected_source_names.add(Path(item.path).stem)
        if item.kind == "doc":
            score += 3
            reasons.append("README/docs anchor")
        if item.kind == "config":
            score += 3
            reasons.append("package/config anchor")
        if item.kind == "test":
            score += 1
            reasons.append("test anchor")
        scores[item.path] = (score, reasons or ["project file"])

    for item in repo_map.files:
        if item.kind != "test":
            continue
        test_name = Path(item.path).stem.lower()
        if any(name and name in test_name for name in selected_source_names):
            score, reasons = scores[item.path]
            scores[item.path] = (score + 4, [*reasons, "test file related to selected source"])
    return scores


def compress_context(
    repo_map: RepoMap,
    paths: list[str],
    ranked: dict[str, tuple[int, list[str]]],
) -> list[SelectedContextFile]:
    by_path = {item.path: item for item in repo_map.files}
    total = 0
    compressed: list[SelectedContextFile] = []
    for path in paths:
        item = by_path.get(path)
        if item is None or total >= MAX_CONTEXT_BUNDLE_CHARS:
            continue
        snippet = _snippet(Path(repo_map.root) / path, item, budget=min(MAX_PER_FILE_CHARS, MAX_CONTEXT_BUNDLE_CHARS - total))
        total += len(snippet)
        score, reasons = ranked.get(path, (0, ["selected by context discovery"]))
        compressed.append(
            SelectedContextFile(
                path=path,
                role=_role(item),
                kind=item.kind,
                score=score,
                reason=" + ".join(_dedupe(reasons)),
                imports=item.imports,
                symbols=item.symbols,
                content_hints=item.content_hints,
                snippet=snippet,
            )
        )
    return compressed


def heuristic_sufficiency(goal: str, repo_map: RepoMap, selected: list[SelectedContextFile]) -> SufficiencyResult:
    selected_paths = {item.path for item in selected}
    has_source = sum(1 for item in selected if item.kind == "source") >= min(2, len([f for f in repo_map.files if f.kind == "source"]))
    has_entrypoint = not repo_map.entrypoint_candidates or any(path in selected_paths for path in repo_map.entrypoint_candidates)
    has_test = not repo_map.tests or any(item.kind == "test" for item in selected)
    if has_source and has_entrypoint and has_test:
        return SufficiencyResult(True, "Selected context includes source implementation, entrypoint if detected, and tests/docs anchors where available.")
    missing: list[str] = []
    files: list[str] = []
    if not has_entrypoint:
        missing.append("primary entrypoint")
        files.extend(repo_map.entrypoint_candidates[:2])
    if not has_source:
        missing.append("implementation source files")
    if not has_test:
        missing.append("related tests")
        files.extend(repo_map.tests[:2])
    return SufficiencyResult(False, f"Missing {', '.join(missing)}.", missing, _dedupe(files))


def repo_map_summary(repo_map: RepoMap) -> dict[str, Any]:
    return {
        "root": repo_map.root,
        "languages": repo_map.languages,
        "file_count": len(repo_map.files),
        "source_files": [item.path for item in repo_map.files if item.kind == "source"][:50],
        "test_files": repo_map.tests[:30],
        "docs": repo_map.docs[:20],
        "configs": repo_map.configs[:20],
        "entrypoint_candidates": repo_map.entrypoint_candidates[:20],
    }


def build_llm_context_prompt(bundle: ContextDiscoveryResult) -> str:
    return json.dumps(bundle.bundle_payload(), indent=2)


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        current = Path(current_root)
        for filename in filenames:
            path = current / filename
            rel_parts = path.relative_to(root).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue
            files.append(path)
    return sorted(files, key=lambda item: str(item.relative_to(root)))


def _file_kind(path: str) -> str:
    name = Path(path).name
    lower = path.lower()
    if name in CONFIG_FILES:
        return "config"
    if name.lower().startswith("readme") or lower.startswith("docs/") or lower.endswith(".md"):
        return "doc"
    if lower.startswith("tests/") or any(pattern in name for pattern in TEST_PATTERNS):
        return "test"
    if Path(path).suffix.lower() in SOURCE_SUFFIXES:
        return "source"
    return "other"


def _role_hints(path: str, text: str) -> list[str]:
    hints: list[str] = []
    name = Path(path).name
    if name in ENTRYPOINT_NAMES or path in ENTRYPOINT_NAMES or path.startswith("cmd/") and name == "main.go":
        hints.append("entrypoint_candidate")
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in ENTRYPOINT_MARKERS):
        hints.append("entrypoint_candidate")
    if "cli" in path.lower() or "command" in path.lower():
        hints.append("cli_candidate")
    return _dedupe(hints)


def _content_hints(text: str) -> list[str]:
    hints = [marker for marker in ENTRYPOINT_MARKERS if marker.lower() in text.lower()]
    for marker in ("logging", "logger", "debug", "storage", "task", "config", "http", "websocket", "reconnect"):
        if marker in text.lower():
            hints.append(marker)
    return _dedupe(hints)[:20]


def _extract_symbols(language: str | None, text: str) -> list[str]:
    pattern = SYMBOL_PATTERNS.get(language or "")
    if pattern is None:
        return []
    symbols: list[str] = []
    for match in pattern.finditer(text):
        value = next((group for group in match.groups() if group), None)
        if value:
            symbols.append(value)
    return _dedupe(symbols)[:30]


def _extract_imports(language: str | None, text: str) -> list[str]:
    pattern = IMPORT_PATTERNS.get(language or "")
    if pattern is None:
        return []
    imports: list[str] = []
    for match in pattern.finditer(text):
        value = next((group for group in match.groups() if group), None)
        if value:
            imports.append(value.strip())
    return _dedupe(imports)[:30]


def _balanced_selection(ranked: dict[str, tuple[int, list[str]]], repo_map: RepoMap, *, max_files: int) -> list[str]:
    by_path = {item.path: item for item in repo_map.files}
    ordered = sorted(ranked, key=lambda path: (-ranked[path][0], _kind_priority(by_path[path].kind), path))
    selected: list[str] = []
    for path in repo_map.entrypoint_candidates:
        _append(selected, path)
        break
    for path in ordered:
        if _low_signal_path(path):
            continue
        if by_path[path].kind == "source":
            _append(selected, path)
        if len([item for item in selected if by_path[item].kind == "source"]) >= 2:
            break
    for path in ordered:
        if by_path[path].kind == "test":
            _append(selected, path)
            break
    for group in (repo_map.docs, repo_map.configs):
        if group:
            _append(selected, group[0])
    for path in ordered:
        if _low_signal_path(path):
            continue
        _append(selected, path)
        if len(selected) >= max_files:
            break
    return selected[:max_files]


def _expansion_paths(
    sufficiency: SufficiencyResult,
    ranked: dict[str, tuple[int, list[str]]],
    repo_map: RepoMap,
    selected: list[str],
    rejected: list[str],
) -> list[str]:
    known = {item.path for item in repo_map.files}
    additions: list[str] = []
    for path in sufficiency.files_to_read_next:
        if path in known and path not in selected:
            _append(additions, path)
        elif path not in known:
            _append(rejected, path)
    terms = derive_goal_terms(" ".join(sufficiency.missing_context_queries))
    if terms:
        query_ranked = rank_files(" ".join(terms), repo_map, terms=terms)
        for path in sorted(query_ranked, key=lambda item: (-query_ranked[item][0], item)):
            if path not in selected:
                _append(additions, path)
            if len(additions) >= MAX_EXPANSION_FILES:
                break
    for path in sorted(ranked, key=lambda item: (-ranked[item][0], item)):
        if path not in selected:
            _append(additions, path)
        if len(additions) >= MAX_EXPANSION_FILES:
            break
    return additions[:MAX_EXPANSION_FILES]


def _snippet(path: Path, item: RepoFile, *, budget: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if len(text) <= budget:
        return text
    lines = text.splitlines()
    if len(text) <= MAX_PER_FILE_CHARS * 2:
        return "\n".join(lines[:40])[:budget]
    relevant: list[str] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(hint.lower() in lowered for hint in [*item.content_hints, *item.symbols]):
            start = max(0, index - 2)
            end = min(len(lines), index + 3)
            relevant.extend(lines[start:end])
            relevant.append("...")
        if len("\n".join(relevant)) >= budget:
            break
    return ("\n".join(relevant) or "\n".join(lines[:20]))[:budget]


def _role(item: RepoFile) -> str:
    if "entrypoint_candidate" in item.role_hints:
        return "cli_entrypoint" if "cli_candidate" in item.role_hints else "entrypoint"
    return item.kind


def _kind_priority(kind: str) -> int:
    return {"source": 0, "test": 1, "doc": 2, "config": 3, "other": 4}.get(kind, 5)


def _implementation_name(path: str) -> bool:
    return Path(path).name not in {"__init__.py", "index.ts", "index.js"}


def _low_signal_path(path: str) -> bool:
    return Path(path).name in {"__init__.py", "mod.rs"}


def _read_sample(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:80_000]
    except OSError:
        return ""


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)
