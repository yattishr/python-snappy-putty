from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.agent import extract_json, parse_agent_output
from snappy_putty.models import AgentOutput


def test_parse_agent_output_from_json() -> None:
    raw = """{
      "goal": "inspect logs",
      "assumptions": ["docker available"],
      "question": null,
      "plan": [
        {"step": 1, "action": "inspect status", "why": "understand current state"}
      ],
      "commands": [
        {"cmd": "docker ps", "explain": "list containers", "risk": "low"}
      ],
      "warnings": []
    }"""
    parsed = parse_agent_output(raw)
    assert isinstance(parsed, AgentOutput)
    assert parsed.goal == "inspect logs"
    assert parsed.commands[0].risk == "low"
    assert parsed.snippets == []


def test_parse_agent_output_with_snippets() -> None:
    raw = {
        "goal": "deploy",
        "assumptions": [],
        "question": None,
        "plan": [{"step": 1, "action": "build", "why": "artifact"}],
        "commands": [{"cmd": "python -m build", "explain": "build package", "risk": "low"}],
        "warnings": [],
        "snippets": [{"title": "Dockerfile", "language": "dockerfile", "content": "FROM python:3.10"}],
    }
    parsed = parse_agent_output(raw)
    assert parsed.snippets[0].title == "Dockerfile"


def test_parse_agent_output_rejects_invalid_risk() -> None:
    raw = {
        "goal": "x",
        "assumptions": [],
        "question": None,
        "plan": [{"step": 1, "action": "a", "why": "b"}],
        "commands": [{"cmd": "echo hi", "explain": "test", "risk": "critical"}],
        "warnings": [],
    }
    with pytest.raises(ValidationError):
        parse_agent_output(raw)


def test_extract_json_from_fenced_block() -> None:
    raw = "prefix\n```json\n{\"goal\":\"x\"}\n```\nsuffix"
    assert extract_json(raw) == "{\"goal\":\"x\"}"


def test_parse_agent_output_ignores_extra_fields_from_fence() -> None:
    raw = """```json
{
  "goal": "inspect logs",
  "assumptions": [],
  "question": null,
  "plan": [{"step": 1, "action": "inspect", "why": "context"}],
  "commands": [{"cmd": "ls -la", "explain": "list", "risk": "low", "extra_nested": 123}],
  "warnings": [],
  "extra_top": "ignored"
}
```"""
    parsed = parse_agent_output(raw)
    assert parsed.goal == "inspect logs"
    assert parsed.commands[0].cmd == "ls -la"
