from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def append_history_event(root: Path, event: str, details: dict[str, Any]) -> None:
    history_path = _history_path(root)
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = _timestamp()
        lines = [f"## {timestamp}", f"Event: {event}"]
        for key in sorted(details):
            value = details[key]
            if isinstance(value, list):
                lines.append(f"{key}:")
                if value:
                    lines.extend(f"- {item}" for item in value)
                else:
                    lines.append("- (none)")
            else:
                lines.append(f"{key}: {value}")
        history_path.write_text(
            (history_path.read_text(encoding="utf-8") if history_path.exists() else "") + "\n".join(lines) + "\n\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _history_path(root: Path) -> Path:
    return root.resolve() / ".snappy" / "memory" / "history.md"


def _timestamp() -> str:
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S %z")[:-2] + ":" + now.strftime("%z")[-2:]
