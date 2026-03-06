from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import shlex
import shutil

from snappy_putty.fs_models import FsApplyItem, FsApplyResult, FsPlan, PlannedOp


MAX_OPS = 20
FILLER_WORDS = {"file", "please"}
PATH_FILLER_WORDS = {"file", "please", "called"}
PATH_SEPARATORS = {"to", "into"}


@dataclass(frozen=True)
class PathResolution:
    path: Path | None
    warning: str | None = None


def _format_entry(entry: Path, long: bool = False) -> str:
    suffix = "/" if entry.is_dir() else ""
    name = f"{entry.name}{suffix}"
    if not long:
        return name
    stat = entry.stat()
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
    size = stat.st_size if entry.is_file() else 0
    return f"{modified}  {size:>10}  {name}"


def list_dir(path: str = ".", all: bool = False, long: bool = False) -> str:
    target = Path(path).expanduser()
    if not target.exists():
        return f"Directory not found: {target}"
    if not target.is_dir():
        return f"Not a directory: {target}"

    items = sorted(target.iterdir(), key=lambda item: item.name.lower())
    lines: list[str] = []
    for item in items:
        if not all and item.name.startswith("."):
            continue
        lines.append(_format_entry(item, long=long))
    return "\n".join(lines) if lines else "(directory is empty)"


def _resolve_in_scope(raw_path: str, cwd: Path, workspace_root: Path | None = None) -> PathResolution:
    value = raw_path.strip()
    if not value:
        return PathResolution(path=None, warning="Path is required.")

    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return PathResolution(path=None, warning="Absolute paths are blocked in v0.1. Use a path under the current working directory.")
    if ".." in candidate.parts:
        return PathResolution(path=None, warning="Paths containing '..' are blocked in v0.1 for safety.")

    resolved_cwd = cwd.resolve()
    resolved_workspace = (workspace_root or resolved_cwd).resolve()
    resolved_target = (resolved_cwd / candidate).resolve()
    try:
        resolved_target.relative_to(resolved_cwd)
    except ValueError:
        return PathResolution(path=None, warning="Path escapes the current working directory subtree.")
    try:
        resolved_target.relative_to(resolved_workspace)
    except ValueError:
        return PathResolution(path=None, warning=f"Path escapes workspace root: {resolved_workspace}")
    return PathResolution(path=resolved_target)


def _as_display_path(path: Path, cwd: Path) -> str:
    return str(path.relative_to(cwd.resolve()))


def plan_mkdir(path: str, cwd: Path | None = None, op_id: str = "op1", workspace_root: Path | None = None) -> PlannedOp:
    base = (cwd or Path.cwd()).resolve()
    resolved = _resolve_in_scope(path, base, workspace_root=workspace_root)
    if resolved.warning:
        raise ValueError(resolved.warning)
    assert resolved.path is not None
    if resolved.path.exists():
        raise ValueError(f"Destination already exists: {_as_display_path(resolved.path, base)}")
    return PlannedOp(
        op_id=op_id,
        action="mkdir",
        src=None,
        dst=_as_display_path(resolved.path, base),
        notes=["Creates a directory if it does not already exist."],
        risk="low",
    )


def _validate_file_source(src: str, cwd: Path, workspace_root: Path | None = None) -> Path:
    resolved_src = _resolve_in_scope(src, cwd, workspace_root=workspace_root)
    if resolved_src.warning:
        raise ValueError(resolved_src.warning)
    assert resolved_src.path is not None
    if not resolved_src.path.exists():
        raise ValueError(f"Source does not exist: {_as_display_path(resolved_src.path, cwd)}")
    if not resolved_src.path.is_file():
        raise ValueError(f"Source must be a file: {_as_display_path(resolved_src.path, cwd)}")
    return resolved_src.path


def _validate_destination(
    dst: str,
    cwd: Path,
    *,
    op_id: str,
    allow_missing_parent: bool = False,
    allow_existing: bool = False,
    workspace_root: Path | None = None,
) -> tuple[Path, PlannedOp | None, bool]:
    resolved_dst = _resolve_in_scope(dst, cwd, workspace_root=workspace_root)
    if resolved_dst.warning:
        raise ValueError(resolved_dst.warning)
    assert resolved_dst.path is not None
    destination_exists = resolved_dst.path.exists()
    if destination_exists and not allow_existing:
        raise ValueError(f"Destination already exists: {_as_display_path(resolved_dst.path, cwd)}")
    parent = resolved_dst.path.parent
    mkdir_op = None
    if not parent.exists():
        if not allow_missing_parent:
            raise ValueError(
                f"Destination parent does not exist: {_as_display_path(parent, cwd)}. "
                "Plan a mkdir operation for the parent first."
            )
        mkdir_op = PlannedOp(
            op_id=op_id,
            action="mkdir",
            src=None,
            dst=_as_display_path(parent, cwd),
            notes=["Destination parent is missing and must be created first."],
            risk="low",
        )
    return resolved_dst.path, mkdir_op, destination_exists


def plan_copy_file(
    src: str,
    dst: str,
    cwd: Path | None = None,
    op_id: str = "op1",
    *,
    allow_missing_parent: bool = False,
    allow_existing: bool = False,
    workspace_root: Path | None = None,
) -> PlannedOp:
    base = (cwd or Path.cwd()).resolve()
    src_path = _validate_file_source(src, base, workspace_root=workspace_root)
    dst_path, _, destination_exists = _validate_destination(
        dst,
        base,
        op_id=op_id,
        allow_missing_parent=allow_missing_parent,
        allow_existing=allow_existing,
        workspace_root=workspace_root,
    )
    notes = ["Copies file contents without removing the source."]
    if destination_exists:
        notes.append("Destination exists; overwrite confirmation is required before apply.")
    return PlannedOp(
        op_id=op_id,
        action="copy",
        src=_as_display_path(src_path, base),
        dst=_as_display_path(dst_path, base),
        notes=notes,
        risk="low",
    )


def plan_move_file(
    src: str,
    dst: str,
    cwd: Path | None = None,
    op_id: str = "op1",
    *,
    allow_missing_parent: bool = False,
    allow_existing: bool = False,
    workspace_root: Path | None = None,
) -> PlannedOp:
    base = (cwd or Path.cwd()).resolve()
    src_path = _validate_file_source(src, base, workspace_root=workspace_root)
    dst_path, _, destination_exists = _validate_destination(
        dst,
        base,
        op_id=op_id,
        allow_missing_parent=allow_missing_parent,
        allow_existing=allow_existing,
        workspace_root=workspace_root,
    )
    notes = ["Moves a file to a new destination path."]
    if destination_exists:
        notes.append("Destination exists; overwrite confirmation is required before apply.")
    return PlannedOp(
        op_id=op_id,
        action="move",
        src=_as_display_path(src_path, base),
        dst=_as_display_path(dst_path, base),
        notes=notes,
        risk="med",
    )


def plan_rename_file(
    src: str,
    new_name_or_dst: str,
    cwd: Path | None = None,
    op_id: str = "op1",
    *,
    allow_missing_parent: bool = False,
    allow_existing: bool = False,
    workspace_root: Path | None = None,
) -> PlannedOp:
    base = (cwd or Path.cwd()).resolve()
    src_path = _validate_file_source(src, base, workspace_root=workspace_root)
    if "/" not in new_name_or_dst and "\\" not in new_name_or_dst:
        dst_hint = str(Path(src).parent / new_name_or_dst)
    else:
        dst_hint = new_name_or_dst
    dst_path, _, destination_exists = _validate_destination(
        dst_hint,
        base,
        op_id=op_id,
        allow_missing_parent=allow_missing_parent,
        allow_existing=allow_existing,
        workspace_root=workspace_root,
    )
    notes = ["Renames a file; source and destination stay within the working tree scope."]
    if destination_exists:
        notes.append("Destination exists; overwrite confirmation is required before apply.")
    return PlannedOp(
        op_id=op_id,
        action="rename",
        src=_as_display_path(src_path, base),
        dst=_as_display_path(dst_path, base),
        notes=notes,
        risk="med",
    )


def _extract_two_paths(text: str, pattern: re.Pattern[str]) -> tuple[str, str] | None:
    match = pattern.search(text)
    if not match:
        return None
    left = (match.group("src_q") or match.group("src") or "").strip()
    right = (match.group("dst_q") or match.group("dst") or "").strip()
    if not left or not right:
        return None
    return left, right


def looks_like_fs_mutation_intent(intent: str) -> bool:
    lowered = intent.strip().lower()
    if not lowered:
        return False
    if lowered.startswith(("copy ", "move ", "rename ", "mkdir ")):
        return True
    if lowered.startswith(("make ", "create ")) and any(token in lowered for token in ("folder", "directory")):
        return True
    return False


def parse_incomplete_fs_intent(intent: str) -> tuple[str, str] | None:
    parsed = _parse_two_path_intent(intent)
    if parsed is None:
        return None
    action, src, dst = parsed
    if not src or dst:
        return None
    return action, src


def _parse_two_path_intent(intent: str) -> tuple[str, str | None, str | None] | None:
    try:
        tokens = shlex.split(intent.strip())
    except ValueError:
        return None
    if not tokens:
        return None

    action = tokens[0].lower()
    if action not in {"copy", "move", "rename"}:
        return None

    rest = [token for token in tokens[1:] if token.lower() != "please"]
    if not rest:
        return action, None, None

    lowered = [token.lower() for token in rest]
    separator_idx = next((idx for idx, token in enumerate(lowered) if token in PATH_SEPARATORS), None)

    if separator_idx is not None:
        src_tokens = [token for token in rest[:separator_idx] if token.lower() not in PATH_FILLER_WORDS]
        dst_tokens = [token for token in rest[separator_idx + 1 :] if token.lower() not in PATH_FILLER_WORDS]
        src = src_tokens[0] if src_tokens else None
        dst = dst_tokens[0] if dst_tokens else None
        return action, src, dst

    path_tokens = [token for token in rest if token.lower() not in PATH_FILLER_WORDS]
    if not path_tokens:
        return action, None, None
    if len(path_tokens) == 1:
        return action, path_tokens[0], None
    return action, path_tokens[0], path_tokens[1]


def plan_fs_intent(intent: str, cwd: Path | None = None, workspace_root: Path | None = None) -> FsPlan | None:
    base = (cwd or Path.cwd()).resolve()
    normalized = re.sub(r"\bplease\b", "", intent.strip(), flags=re.IGNORECASE).strip()
    lower = normalized.lower()

    mkdir_pattern = re.compile(
        r"\b(?:make|create|mkdir)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)?\s*(?:called|named)?\s*[\"']?(?P<dst>[^\"']+?)[\"']?\s*$",
        flags=re.IGNORECASE,
    )
    copy_pattern = re.compile(
        r"\bcopy\s+(?:file\s+)?(?:[\"'](?P<src_q>[^\"']+)[\"']|(?P<src>\S+))(?:\s+file)?\s+to\s+(?:[\"'](?P<dst_q>[^\"']+)[\"']|(?P<dst>\S+))\s*$",
        flags=re.IGNORECASE,
    )
    move_pattern = re.compile(
        r"\bmove\s+(?:file\s+)?(?:[\"'](?P<src_q>[^\"']+)[\"']|(?P<src>\S+))(?:\s+file)?\s+to\s+(?:[\"'](?P<dst_q>[^\"']+)[\"']|(?P<dst>\S+))\s*$",
        flags=re.IGNORECASE,
    )
    rename_pattern = re.compile(
        r"\brename\s+(?:file\s+)?(?:[\"'](?P<src_q>[^\"']+)[\"']|(?P<src>\S+))(?:\s+file)?\s+to\s+(?:[\"'](?P<dst_q>[^\"']+)[\"']|(?P<dst>\S+))\s*$",
        flags=re.IGNORECASE,
    )

    ops: list[PlannedOp] = []
    warnings: list[str] = []

    try:
        if "copy " in lower:
            parsed = _extract_two_paths(normalized, copy_pattern)
            if parsed:
                src, dst = parsed
            else:
                token_parsed = _parse_two_path_intent(normalized)
                if token_parsed is None or token_parsed[0] != "copy":
                    return None
                _, src, dst = token_parsed
                if not src or not dst:
                    return None
            resolved_dst = _resolve_in_scope(dst, base, workspace_root=workspace_root)
            if resolved_dst.warning:
                warnings.append(resolved_dst.warning)
            else:
                assert resolved_dst.path is not None
                if not resolved_dst.path.parent.exists():
                    ops.append(
                        PlannedOp(
                            op_id="op1",
                            action="mkdir",
                            src=None,
                            dst=_as_display_path(resolved_dst.path.parent, base),
                            notes=["Destination parent does not exist and will be created first."],
                            risk="low",
                        )
                    )
                ops.append(
                    plan_copy_file(
                        src=src,
                        dst=dst,
                        cwd=base,
                        op_id=f"op{len(ops) + 1}",
                        allow_missing_parent=True,
                        allow_existing=True,
                        workspace_root=workspace_root,
                    )
                )
        elif "move " in lower:
            parsed = _extract_two_paths(normalized, move_pattern)
            if parsed:
                src, dst = parsed
            else:
                token_parsed = _parse_two_path_intent(normalized)
                if token_parsed is None or token_parsed[0] != "move":
                    return None
                _, src, dst = token_parsed
                if not src or not dst:
                    return None
            resolved_dst = _resolve_in_scope(dst, base, workspace_root=workspace_root)
            if resolved_dst.warning:
                warnings.append(resolved_dst.warning)
            else:
                assert resolved_dst.path is not None
                if not resolved_dst.path.parent.exists():
                    ops.append(
                        PlannedOp(
                            op_id="op1",
                            action="mkdir",
                            src=None,
                            dst=_as_display_path(resolved_dst.path.parent, base),
                            notes=["Destination parent does not exist and will be created first."],
                            risk="low",
                        )
                    )
                ops.append(
                    plan_move_file(
                        src=src,
                        dst=dst,
                        cwd=base,
                        op_id=f"op{len(ops) + 1}",
                        allow_missing_parent=True,
                        allow_existing=True,
                        workspace_root=workspace_root,
                    )
                )
        elif "rename " in lower:
            parsed = _extract_two_paths(normalized, rename_pattern)
            if parsed:
                src, dst = parsed
            else:
                token_parsed = _parse_two_path_intent(normalized)
                if token_parsed is None or token_parsed[0] != "rename":
                    return None
                _, src, dst = token_parsed
                if not src or not dst:
                    return None
            resolved_dst = _resolve_in_scope(dst, base, workspace_root=workspace_root)
            if resolved_dst.warning and "/" in dst:
                warnings.append(resolved_dst.warning)
            else:
                src_resolved = _resolve_in_scope(src, base, workspace_root=workspace_root)
                if src_resolved.warning:
                    warnings.append(src_resolved.warning)
                else:
                    assert src_resolved.path is not None
                    if "/" in dst or "\\" in dst:
                        target_parent = _resolve_in_scope(dst, base, workspace_root=workspace_root).path
                        if target_parent is not None and not target_parent.parent.exists():
                            ops.append(
                                PlannedOp(
                                    op_id="op1",
                                    action="mkdir",
                                    src=None,
                                    dst=_as_display_path(target_parent.parent, base),
                                    notes=["Destination parent does not exist and will be created first."],
                                    risk="low",
                                )
                            )
                    ops.append(
                        plan_rename_file(
                            src=src,
                            new_name_or_dst=dst,
                            cwd=base,
                            op_id=f"op{len(ops) + 1}",
                            allow_missing_parent=True,
                            allow_existing=True,
                            workspace_root=workspace_root,
                        )
                    )
        elif any(token in lower for token in ("make ", "create ", "mkdir ")):
            match = mkdir_pattern.search(normalized)
            if not match:
                return None
            dst = match.group("dst").strip()
            ops.append(plan_mkdir(path=dst, cwd=base, op_id="op1", workspace_root=workspace_root))
        else:
            return None
    except ValueError as err:
        warnings.append(str(err))

    if len(ops) > MAX_OPS:
        warnings.append(f"Plan has {len(ops)} operations, which exceeds the maximum of {MAX_OPS}. Confirmation is required to continue.")

    deduped_warnings = list(dict.fromkeys(warnings))
    return FsPlan(
        goal=intent,
        cwd=str(base),
        ops=ops,
        warnings=deduped_warnings,
        requires_confirmation=bool(ops),
    )


def _undo_hint(action: str, src: str | None, dst: str | None) -> str:
    if action == "mkdir" and dst:
        return f"Undo hint: `rmdir {dst}` (works only if empty)."
    if action == "copy" and dst:
        return f"Undo hint: `rm {dst}`."
    if action in {"move", "rename"} and src and dst:
        return f"Undo hint: `mv {dst} {src}`."
    return "Undo hint: manual rollback may be required."


def apply_fs_plan(
    plan: FsPlan,
    cwd: Path | None = None,
    *,
    workspace_root: Path | None = None,
    allow_overwrite: bool = False,
    allow_excess_ops: bool = False,
) -> FsApplyResult:
    base = (cwd or Path(plan.cwd)).resolve()
    root = (workspace_root or base).resolve()
    results: list[FsApplyItem] = []
    warnings = list(plan.warnings)

    try:
        base.relative_to(root)
    except ValueError:
        return FsApplyResult(
            goal=plan.goal,
            results=[],
            warnings=warnings + [f"Refusing apply: current directory {base} is outside workspace root {root}."],
        )

    if len(plan.ops) > MAX_OPS and not allow_excess_ops:
        return FsApplyResult(
            goal=plan.goal,
            results=[],
            warnings=warnings + [f"Refusing apply: plan exceeds maximum operation count ({MAX_OPS})."],
        )

    for op in plan.ops:
        try:
            if op.action == "mkdir":
                if op.dst is None:
                    raise ValueError("Missing destination path for mkdir operation.")
                target = _resolve_in_scope(op.dst, base, workspace_root=root)
                if target.warning or target.path is None:
                    raise ValueError(target.warning or "Invalid mkdir destination.")
                if target.path.exists():
                    raise ValueError(f"Destination already exists: {op.dst}")
                target.path.mkdir(parents=False, exist_ok=False)
                results.append(
                    FsApplyItem(
                        op_id=op.op_id,
                        action=op.action,
                        status="applied",
                        message=f"Created directory: {op.dst}. {_undo_hint(op.action, op.src, op.dst)}",
                    )
                )
            elif op.action == "copy":
                if op.src is None or op.dst is None:
                    raise ValueError("Missing source or destination for copy operation.")
                src = _resolve_in_scope(op.src, base, workspace_root=root)
                dst = _resolve_in_scope(op.dst, base, workspace_root=root)
                if src.warning or src.path is None:
                    raise ValueError(src.warning or "Invalid source path.")
                if dst.warning or dst.path is None:
                    raise ValueError(dst.warning or "Invalid destination path.")
                if not src.path.is_file():
                    raise ValueError(f"Source must be a file: {op.src}")
                if dst.path.exists() and not allow_overwrite:
                    raise ValueError(f"Destination already exists: {op.dst}")
                shutil.copy2(src.path, dst.path)
                results.append(
                    FsApplyItem(
                        op_id=op.op_id,
                        action=op.action,
                        status="applied",
                        message=f"Copied file: {op.src} -> {op.dst}. {_undo_hint(op.action, op.src, op.dst)}",
                    )
                )
            elif op.action in {"move", "rename"}:
                if op.src is None or op.dst is None:
                    raise ValueError("Missing source or destination for move/rename operation.")
                src = _resolve_in_scope(op.src, base, workspace_root=root)
                dst = _resolve_in_scope(op.dst, base, workspace_root=root)
                if src.warning or src.path is None:
                    raise ValueError(src.warning or "Invalid source path.")
                if dst.warning or dst.path is None:
                    raise ValueError(dst.warning or "Invalid destination path.")
                if not src.path.is_file():
                    raise ValueError(f"Source must be a file: {op.src}")
                if dst.path.exists() and not allow_overwrite:
                    raise ValueError(f"Destination already exists: {op.dst}")
                src.path.replace(dst.path)
                verb = "Moved file" if op.action == "move" else "Renamed file"
                results.append(
                    FsApplyItem(
                        op_id=op.op_id,
                        action=op.action,
                        status="applied",
                        message=f"{verb}: {op.src} -> {op.dst}. {_undo_hint(op.action, op.src, op.dst)}",
                    )
                )
            else:
                results.append(FsApplyItem(op_id=op.op_id, action=op.action, status="skipped", message="Unsupported operation in v0.1."))
        except Exception as err:
            results.append(FsApplyItem(op_id=op.op_id, action=op.action, status="failed", message=str(err)))
    return FsApplyResult(goal=plan.goal, results=results, warnings=warnings)
