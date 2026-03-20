from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


DEFAULT_COMMIT_COUNT = 5
MAX_COMMIT_COUNT = 20
_HEX_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class GitReadIntent:
    kind: str
    text: str
    count: int | None = None
    commit: str | None = None


@dataclass(frozen=True)
class GitReadResult:
    ok: bool
    title: str
    body: str
    summary: str
    error_message: str | None = None


def parse_git_read_intent(text: str) -> GitReadIntent | None:
    stripped = text.strip()
    lowered = stripped.lower()
    if not stripped:
        return None

    commit_match = re.search(r"\b(?:show|inspect)\s+(?:specific\s+)?commit\s+([0-9a-f]{7,40})\b", lowered)
    if commit_match:
        return GitReadIntent(kind="show_commit", text=stripped, commit=commit_match.group(1))

    literal_show_match = re.fullmatch(r"git\s+show\s+([0-9a-f]{7,40})", lowered)
    if literal_show_match:
        return GitReadIntent(kind="show_commit", text=stripped, commit=literal_show_match.group(1))

    if lowered.startswith("git status") or ("repo" in lowered and "status" in lowered):
        return GitReadIntent(kind="status", text=stripped)

    commit_count = _parse_commit_count(lowered)
    if commit_count is not None or "recent commit" in lowered or "recent commits" in lowered:
        return GitReadIntent(kind="recent_commits", text=stripped, count=commit_count or DEFAULT_COMMIT_COUNT)
    if lowered.startswith("git log") or re.search(r"\bshow(?: me)?(?: the)? last \d+ commits?\b", lowered):
        return GitReadIntent(kind="recent_commits", text=stripped, count=commit_count or DEFAULT_COMMIT_COUNT)

    if lowered in {"git branch", "branches"}:
        return GitReadIntent(kind="branch_list", text=stripped)
    if re.search(r"\bwhat branch am i on\b", lowered) or re.search(r"\bcurrent branch\b", lowered):
        return GitReadIntent(kind="current_branch", text=stripped)
    if lowered.startswith("git branch --show-current"):
        return GitReadIntent(kind="current_branch", text=stripped)
    if re.search(r"\b(list|show)\s+(all\s+)?branches\b", lowered) or re.search(r"\bbranch list\b", lowered):
        return GitReadIntent(kind="branch_list", text=stripped)
    if lowered.startswith("git branch"):
        return GitReadIntent(kind="branch_list", text=stripped)

    if re.search(r"\b(show|list)\s+remotes\b", lowered) or re.search(r"\bwhat(?:'s| is)?\s+the remotes\b", lowered):
        return GitReadIntent(kind="remotes", text=stripped)
    if lowered.startswith("git remote"):
        return GitReadIntent(kind="remotes", text=stripped)

    if re.search(r"\bwhat changed\b", lowered) or re.search(r"\bshow diff summary\b", lowered) or "diff summary" in lowered:
        return GitReadIntent(kind="diff_summary", text=stripped)
    if lowered.startswith("git diff"):
        return GitReadIntent(kind="diff_summary", text=stripped)

    return None


def execute_git_read(intent: GitReadIntent, repo_root: Path) -> GitReadResult:
    inside_repo = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if inside_repo.returncode != 0 or inside_repo.stdout.strip().lower() != "true":
        message = f"{repo_root} is not a Git repository."
        return GitReadResult(
            ok=False,
            title="Git Read Failed",
            body=message,
            summary="Git read failed: no repository found.",
            error_message=message,
        )

    command = _command_for_intent(intent)
    if command is None:
        message = f"Unsupported Git read intent: {intent.text}"
        return GitReadResult(
            ok=False,
            title="Git Read Failed",
            body=message,
            summary="Git read failed: unsupported intent.",
            error_message=message,
        )

    completed = _run_git(repo_root, command)
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "Git command failed.").strip()
        return GitReadResult(
            ok=False,
            title="Git Read Failed",
            body=error,
            summary=f"Git read failed for {intent.kind.replace('_', ' ')}.",
            error_message=error,
        )

    rendered = _render_output(intent=intent, stdout=completed.stdout, repo_root=repo_root)
    return GitReadResult(ok=True, title=rendered[0], body=rendered[1], summary=rendered[2])


def _parse_commit_count(lowered: str) -> int | None:
    count_match = re.search(r"\b(?:last|show(?: me)?(?: the)?)\s+(\d+)\s+commits?\b", lowered)
    if not count_match:
        return None
    return min(max(int(count_match.group(1)), 1), MAX_COMMIT_COUNT)


def _command_for_intent(intent: GitReadIntent) -> list[str] | None:
    if intent.kind == "status":
        return ["status", "--short", "--branch"]
    if intent.kind == "recent_commits":
        count = min(max(intent.count or DEFAULT_COMMIT_COUNT, 1), MAX_COMMIT_COUNT)
        return ["log", "--oneline", f"-{count}"]
    if intent.kind == "current_branch":
        return ["branch", "--show-current"]
    if intent.kind == "branch_list":
        return ["branch", "--all", "--verbose"]
    if intent.kind == "remotes":
        return ["remote", "-v"]
    if intent.kind == "diff_summary":
        return ["diff", "--stat"]
    if intent.kind == "show_commit" and intent.commit and _HEX_COMMIT_RE.fullmatch(intent.commit):
        return ["show", "--stat", "--decorate", "--summary", intent.commit]
    return None


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(args=["git", *args], returncode=1, stdout="", stderr=str(exc))


def _render_output(intent: GitReadIntent, stdout: str, repo_root: Path) -> tuple[str, str, str]:
    content = stdout.strip()
    if intent.kind == "status":
        body = content or "Working tree is clean."
        return "Git Status", body, "Git status retrieved."
    if intent.kind == "recent_commits":
        count = intent.count or DEFAULT_COMMIT_COUNT
        body = content or "No commits found."
        return "Recent Commits", body, f"Showing the last {count} commit(s)."
    if intent.kind == "current_branch":
        branch_name = content
        if not branch_name:
            detached = _run_git(repo_root, ["rev-parse", "--short", "HEAD"])
            branch_name = f"Detached HEAD at {detached.stdout.strip() or 'unknown'}"
        return "Current Branch", branch_name, f"Current branch: {branch_name}."
    if intent.kind == "branch_list":
        body = content or "No branches found."
        return "Branches", body, "Git branch list retrieved."
    if intent.kind == "remotes":
        body = content or "No remotes configured."
        return "Remotes", body, "Git remotes retrieved."
    if intent.kind == "diff_summary":
        body = content or "No unstaged diff summary."
        return "Diff Summary", body, "Git diff summary retrieved."
    if intent.kind == "show_commit":
        body = content or f"No output for commit {intent.commit}."
        return "Commit Details", body, f"Showing commit {intent.commit}."
    return "Git Read", content or "No output.", "Git read completed."
