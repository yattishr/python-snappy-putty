from __future__ import annotations

from pathlib import Path

from snappy_putty.fs_ops import list_dir as fs_list_dir

MAX_OUTPUT_CHARS = 5000


def _cap_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... output truncated ..."


def pwd() -> str:
    return str(Path.cwd())


def list_dir(path: str = ".", all: bool = False, long: bool = False) -> str:
    return _cap_output(fs_list_dir(path=path, all=all, long=long))
