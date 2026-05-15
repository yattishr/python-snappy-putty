from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


_NOISY_DIRS = {
    ".git",
    ".snappy",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    "vendor",
    "target",
}

_CONFIG_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
}

_LANGUAGE_MAP = {
    ".py": "python",
    ".md": "markdown",
    ".toml": "toml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shell",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
}

_FRAMEWORK_MARKERS = {
    "typer": "typer",
    "rich": "rich",
    "pytest": "pytest",
    "pydantic": "pydantic",
    "prompt_toolkit": "prompt_toolkit",
    "click": "click",
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
    "streamlit": "streamlit",
    "gradio": "gradio",
}

_SNAPSHOT_TTL_SECONDS = 600


@dataclass(frozen=True)
class ProjectSnapshot:
    snapshot_id: str
    root_path: str
    created_at: str
    root_hash: str | None
    git_branch: str | None
    git_status_summary: str | None
    languages: list[str]
    package_managers: list[str]
    frameworks: list[str]
    config_files: list[str]
    docs: list[str]
    test_files: list[str]
    source_files: list[str]
    entry_points: list[str]
    file_count: int
    sampled_files: list[str]


def project_root(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()).resolve()


def inspect_project(root: Path | None = None) -> ProjectSnapshot:
    active_root = project_root(root)
    files = list(_iter_project_files(active_root))
    rel_paths = [str(path.relative_to(active_root)) for path in files]
    root_hash = _compute_root_hash(active_root, files)
    git_branch, git_status_summary = _git_metadata(active_root)
    languages = _detect_languages(files)
    package_managers = _detect_package_managers(active_root, files)
    frameworks = _detect_frameworks(active_root, files)
    config_files = [path for path in rel_paths if Path(path).name in _CONFIG_FILES]
    docs = _detect_docs(rel_paths)
    test_files = _detect_test_files(rel_paths)
    source_files = _detect_source_files(rel_paths)
    entry_points = _detect_entry_points(active_root, files, rel_paths)
    sampled_files = _sampled_files(config_files, docs, test_files, source_files, entry_points, all_paths=rel_paths)

    return ProjectSnapshot(
        snapshot_id=_make_snapshot_id(active_root, root_hash, git_branch, git_status_summary),
        root_path=str(active_root),
        created_at=_utc_now(),
        root_hash=root_hash,
        git_branch=git_branch,
        git_status_summary=git_status_summary,
        languages=languages,
        package_managers=package_managers,
        frameworks=frameworks,
        config_files=config_files,
        docs=docs,
        test_files=test_files,
        source_files=source_files,
        entry_points=entry_points,
        file_count=len(files),
        sampled_files=sampled_files,
    )


def snapshot_to_payload(snapshot: ProjectSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def snapshot_from_payload(payload: Any) -> ProjectSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("project snapshot must be a JSON object")
    return ProjectSnapshot(
        snapshot_id=_require_str(payload, "snapshot_id"),
        root_path=_require_str(payload, "root_path"),
        created_at=_require_str(payload, "created_at"),
        root_hash=_optional_str(payload, "root_hash"),
        git_branch=_optional_str(payload, "git_branch"),
        git_status_summary=_optional_str(payload, "git_status_summary"),
        languages=_require_str_list(payload, "languages"),
        package_managers=_require_str_list(payload, "package_managers"),
        frameworks=_require_str_list(payload, "frameworks"),
        config_files=_require_str_list(payload, "config_files"),
        docs=_require_str_list(payload, "docs"),
        test_files=_require_str_list(payload, "test_files"),
        source_files=_require_str_list(payload, "source_files"),
        entry_points=_require_str_list(payload, "entry_points"),
        file_count=_require_int(payload, "file_count"),
        sampled_files=_require_str_list(payload, "sampled_files"),
    )


def is_project_snapshot_valid(root: Path, snapshot: ProjectSnapshot) -> bool:
    active_root = project_root(root)
    if Path(snapshot.root_path).resolve() != active_root:
        return False
    try:
        created_at = datetime.fromisoformat(snapshot.created_at)
    except ValueError:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(created_at.tzinfo) - created_at).total_seconds()
    if age_seconds > _SNAPSHOT_TTL_SECONDS:
        return False

    current_files = list(_iter_project_files(active_root))
    current_hash = _compute_root_hash(active_root, current_files)
    _, current_status = _git_metadata(active_root)
    return snapshot.root_hash == current_hash and snapshot.git_status_summary == current_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _make_snapshot_id(root: Path, root_hash: str | None, git_branch: str | None, git_status_summary: str | None) -> str:
    material = "|".join(
        [
            str(root),
            root_hash or "",
            git_branch or "",
            git_status_summary or "",
            _utc_now(),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"snap_{digest}"


def _git_metadata(root: Path) -> tuple[str | None, str | None]:
    try:
        import subprocess

        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if inside.returncode != 0 or inside.stdout.strip().lower() != "true":
            return None, None

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        branch_name = branch.stdout.strip() if branch.returncode == 0 and branch.stdout.strip() else "unknown"

        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0:
            return branch_name, "unknown"
        status_lines = _snapshot_relevant_git_status_lines(status.stdout)
        return branch_name, "dirty" if status_lines else "clean"
    except OSError:
        return None, None


def _snapshot_relevant_git_status_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.strip() and not _git_status_line_is_snappy_only(line)]


def _git_status_line_is_snappy_only(line: str) -> bool:
    paths = _git_status_paths(line)
    return bool(paths) and all(path == ".snappy" or path.startswith(".snappy/") for path in paths)


def _git_status_paths(line: str) -> list[str]:
    content = line[3:].strip() if len(line) > 3 else ""
    if not content:
        return []
    if " -> " in content:
        return [part.strip().strip('"') for part in content.split(" -> ") if part.strip()]
    return [content.strip('"')]


def _iter_project_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = [name for name in dirnames if name not in _NOISY_DIRS]
        for filename in filenames:
            path = current_path / filename
            if any(part in _NOISY_DIRS for part in path.parts):
                continue
            files.append(path)
    files.sort(key=lambda path: str(path.relative_to(root)))
    return files


def _compute_root_hash(root: Path, files: list[Path]) -> str | None:
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        rel = str(path.relative_to(root)).replace(os.sep, "/")
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(b"\0")
        if path.name in _CONFIG_FILES or path.suffix in {".md", ".toml", ".json", ".yaml", ".yml"}:
            try:
                sample = path.read_text(encoding="utf-8", errors="ignore")[:2048]
            except OSError:
                sample = ""
            digest.update(sample.encode("utf-8", errors="ignore"))
            digest.update(b"\0")
    return digest.hexdigest()


def _detect_languages(files: list[Path]) -> list[str]:
    languages: set[str] = set()
    for path in files:
        language = _LANGUAGE_MAP.get(path.suffix.lower())
        if language:
            languages.add(language)
    return sorted(languages)


def _detect_package_managers(root: Path, files: list[Path]) -> list[str]:
    rel_names = {path.name for path in files}
    result: list[str] = []
    if "pyproject.toml" in rel_names or "requirements.txt" in rel_names or "setup.py" in rel_names:
        result.append("pip")
    if "package.json" in rel_names:
        result.append("npm")
    if "Cargo.toml" in rel_names:
        result.append("cargo")
    if "go.mod" in rel_names:
        result.append("go")
    return result


def _detect_frameworks(root: Path, files: list[Path]) -> list[str]:
    frameworks: set[str] = set()
    for path in files:
        if path.name not in _CONFIG_FILES and path.suffix not in {".toml", ".txt", ".cfg", ".ini", ".json", ".md"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for needle, framework in _FRAMEWORK_MARKERS.items():
            if needle in content:
                frameworks.add(framework)
    return sorted(frameworks)


def _detect_docs(rel_paths: list[str]) -> list[str]:
    docs: list[str] = []
    for path in rel_paths:
        name = Path(path).name.lower()
        if name.startswith("readme") or path.startswith("docs/") or name.endswith(".md"):
            docs.append(path)
    return docs[:20]


def _detect_test_files(rel_paths: list[str]) -> list[str]:
    tests: list[str] = []
    for path in rel_paths:
        name = Path(path).name
        if "/tests/" in f"/{path}/" or name.startswith("test_") or name.endswith("_test.py"):
            tests.append(path)
    return tests[:40]


def _detect_source_files(rel_paths: list[str]) -> list[str]:
    source_files: list[str] = []
    for path in rel_paths:
        if path.startswith("src/") or path.startswith("lib/") or path.startswith("app/"):
            source_files.append(path)
        elif path.endswith(".py") and not path.startswith("tests/"):
            source_files.append(path)
    return source_files[:100]


def _detect_entry_points(root: Path, files: list[Path], rel_paths: list[str]) -> list[str]:
    entry_points: list[str] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if "[project.scripts]" in text or "console_scripts" in text:
            for path in rel_paths:
                if path.endswith("cli.py") or path.endswith("main.py"):
                    entry_points.append(path)
                    break
    package_json = root / "package.json"
    if package_json.is_file():
        entry_points.append("package.json")
    return entry_points


def _sampled_files(*groups: list[str], all_paths: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
            if len(ordered) >= 12:
                return ordered
    for item in all_paths:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
        if len(ordered) >= 12:
            break
    return ordered


def _require_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when present")
    return value


def _require_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_str_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain strings only")
        result.append(item)
    return result
