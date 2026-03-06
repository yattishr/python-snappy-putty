from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.router import classify_input


@pytest.mark.parametrize(
    ("text", "expected_route"),
    [
        ("help", "builtin_help"),
        ("doctor", "builtin_doctor"),
        ("after", "builtin_after"),
        ("status", "builtin_status"),
        ("cancel", "builtin_cancel"),
        ("exit", "builtin_exit"),
        ("quit", "builtin_exit"),
        ("explain git worktree list", "explain"),
        ("explain copy README.md", "explain"),
        ("copy README.md", "fs_mutation"),
        ("copy README.md ../../README2.md", "fs_mutation"),
        ("copy README.md file", "fs_mutation"),
        ("make a folder called sandbox", "fs_mutation"),
        ("create folder named docs", "fs_mutation"),
        ("give me a file listing", "safe_inspect"),
        ("give me a git worktree listing", "safe_inspect"),
        ("list files in src", "safe_inspect"),
        ("show files", "safe_inspect"),
        ("deploy this to google cloud", "ask"),
        ("what should I run to rotate nginx logs", "ask"),
    ],
)
def test_classify_input_routes(text: str, expected_route: str) -> None:
    decision = classify_input(text)
    assert decision.route == expected_route
