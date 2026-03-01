from __future__ import annotations

from pathlib import Path
import subprocess


MAX_OUTPUT_CHARS = 5000


def _cap_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... output truncated ..."


def pwd() -> str:
    return str(Path.cwd())


def list_dir(path: str = ".", all: bool = False, long: bool = False) -> str:
    target = Path(path).expanduser()
    if not target.exists():
        return f"Directory not found: {target}"
    if not target.is_dir():
        return f"Not a directory: {target}"

    cmd = ["ls"]
    if all:
        cmd.append("-a")
    if long:
        cmd.append("-l")
    cmd.append(str(target))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as err:
        return f"Unable to list directory: {err}"

    if result.returncode != 0:
        message = result.stderr.strip() or "unknown ls error"
        return _cap_output(f"Unable to list directory: {message}")

    output = result.stdout.rstrip()
    return _cap_output(output or "(directory is empty)")
