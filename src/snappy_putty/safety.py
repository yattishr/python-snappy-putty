from __future__ import annotations

import re

from snappy_putty.models import SuggestedCommand


HIGH_RISK_PATTERNS = (
    r"\brm\s+-rf\b",
    r"\bmkfs\b",
    r"\bdd\b",
    r"\biptables\b",
    r"\bchmod\s+-R\b",
    r"\bchown\s+-R\b",
    r"\bkubectl\s+delete\b",
    r"\bterraform\s+apply\b",
)

MED_RISK_PATTERNS = (
    r"\bsystemctl\s+restart\b",
    r"\bgcloud\s+run\s+deploy\b",
    r"\bdocker\s+system\s+prune\b",
)


def score_risk(command: str) -> str:
    text = command.strip()
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return "high"
    for pattern in MED_RISK_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return "med"
    return "low"


def _risk_rank(level: str) -> int:
    return {"low": 0, "med": 1, "high": 2}.get(level, 0)


def attach_risk_tags(commands: list[SuggestedCommand]) -> list[SuggestedCommand]:
    tagged: list[SuggestedCommand] = []
    for cmd in commands:
        detected = score_risk(cmd.cmd)
        final = detected if _risk_rank(detected) > _risk_rank(cmd.risk) else cmd.risk
        tagged.append(SuggestedCommand(cmd=cmd.cmd, explain=cmd.explain, risk=final))
    return tagged
