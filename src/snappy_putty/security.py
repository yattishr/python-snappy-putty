from __future__ import annotations

import logging
import re


logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = (
    r"\bignore\s+previous\s+instructions?\b",
    r"\boverride\s+system\s+prompt\b",
    r"\bbypass\s+safety\b",
    r"\bact\s+as\s+root\b",
    r"\bexecute\s+command\b",
    r"\bsimulate\s+system\b",
)


def sanitize_user_prompt(text: str) -> str:
    sanitized = text
    matched = False
    for raw_pattern in _INJECTION_PATTERNS:
        pattern = re.compile(raw_pattern, flags=re.IGNORECASE)
        if pattern.search(sanitized):
            matched = True
            sanitized = pattern.sub("", sanitized)

    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if matched:
        logger.warning("Potential prompt injection detected and sanitized.")
    return sanitized
