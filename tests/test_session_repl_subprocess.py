import os
from pathlib import Path
import subprocess
import sys


def _repl_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    return env


def test_repl_pending_question_consumes_next_input_as_answer(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="give me a file listing for\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Which directory path should I list?" in proc.stdout
    assert "Directory not found" in proc.stdout
    assert "Session Status" not in proc.stdout


def test_repl_confirmation_flow_applies_on_yes(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Type YES to apply, or NO to cancel." in proc.stdout
    assert (tmp_path / "README-copy.md").exists()


def test_repl_after_status_cancel(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nstatus\nafter\ncancel\nafter\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Session Status" in proc.stdout
    assert "Awaiting confirmation: yes" in proc.stdout
    assert "Pending confirmation: type YES to continue or NO to cancel." in proc.stdout
    assert "Cleared pending question/plan state." in proc.stdout
    assert "No active task." in proc.stdout
    assert not (tmp_path / "README-copy.md").exists()
