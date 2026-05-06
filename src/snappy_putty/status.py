from __future__ import annotations

import os
import random
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from typing import Iterator

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

STATUS_LINES = [
    "🐶 Sniffing around...",
    "🐾 Fetching a plan...",
    "🧠 Chewing on that command...",
    "🔎 Inspecting the filesystem...",
    "📦 Packing things carefully...",
    "☁️ Consulting the cloud spirits...",
    "🛠️ Assembling a safe plan...",
]

MODE_STATUS_LINES: dict[str, list[str]] = {
    "ask": [
        "🐾 Mapping your next steps...",
        "🧭 Finding a practical path...",
    ],
    "explain": [
        "🧠 Breaking that command down...",
        "🔬 Inspecting command semantics...",
    ],
    "plan": [
        "🧭 Planning grounded project changes...",
        "🛠️ Building a supervised project plan...",
    ],
    "fs": [
        "🔎 Scanning directories safely...",
        "📁 Reading local paths carefully...",
    ],
    "cloud": [
        "☁️ Checking cloud-side options...",
        "🛰️ Mapping deployment branches...",
    ],
}

_BUSY_DEPTH: ContextVar[int] = ContextVar("snappy_putty_busy_depth", default=0)


def get_status_message(mode: str | None = None) -> str:
    pool = list(STATUS_LINES)
    if mode:
        pool.extend(MODE_STATUS_LINES.get(mode, []))
    return random.choice(pool)


def _spinner_disabled() -> bool:
    return os.getenv("SNAPPY_PUTTY_NO_SPINNER") == "1"


@contextmanager
def busy(message: str | None = None, *, console: Console | None = None) -> Iterator[None]:
    if _spinner_disabled() or _BUSY_DEPTH.get() > 0:
        with nullcontext():
            yield
        return

    token = _BUSY_DEPTH.set(_BUSY_DEPTH.get() + 1)
    try:
        display = console or Console()
        text = message or get_status_message()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            console=display,
            transient=True,
        ) as progress:
            progress.add_task(text, total=None)
            yield
    finally:
        _BUSY_DEPTH.reset(token)
