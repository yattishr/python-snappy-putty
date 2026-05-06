from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty import status


def test_get_status_message_uses_mode_pool(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_choice(values: list[str]) -> str:
        captured["values"] = values
        return values[0]

    monkeypatch.setattr(status.random, "choice", fake_choice)
    message = status.get_status_message("ask")
    assert message == captured["values"][0]
    assert any(line in captured["values"] for line in status.MODE_STATUS_LINES["ask"])


def test_get_status_message_supports_plan_mode(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_choice(values: list[str]) -> str:
        captured["values"] = values
        return values[0]

    monkeypatch.setattr(status.random, "choice", fake_choice)
    status.get_status_message("plan")
    assert any(line in captured["values"] for line in status.MODE_STATUS_LINES["plan"])


def test_busy_respects_no_spinner_env(monkeypatch) -> None:
    class _ShouldNotRun:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("Spinner should be suppressed when SNAPPY_PUTTY_NO_SPINNER=1")

    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    monkeypatch.setattr(status, "Progress", _ShouldNotRun)
    with status.busy("quiet mode"):
        assert True
