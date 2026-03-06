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


def test_repl_incomplete_copy_then_no_does_not_apply(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nREADME.copy.md\nNO\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert (tmp_path / "README.md").exists()
    assert not (tmp_path / "README.copy.md").exists()


def test_repl_incomplete_copy_then_yes_applies(tmp_path: Path) -> None:
    original = tmp_path / "README.md"
    original.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nREADME.copy.md\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert original.exists()
    assert (tmp_path / "README.copy.md").exists()


def test_repl_inline_copy_space_separated_then_yes_applies(tmp_path: Path) -> None:
    original = tmp_path / "README.md"
    original.write_text("demo", encoding="utf-8")
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
    assert original.exists()
    assert (tmp_path / "README-copy.md").exists()


def test_repl_inline_copy_to_path_then_yes_applies(tmp_path: Path) -> None:
    original = tmp_path / "README.md"
    original.write_text("demo", encoding="utf-8")
    (tmp_path / "sandbox").mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to sandbox/README.md\nYES\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert original.exists()
    assert (tmp_path / "sandbox/README.md").exists()


def test_repl_incomplete_copy_destination_then_no_does_not_apply(tmp_path: Path) -> None:
    original = tmp_path / "README.md"
    original.write_text("demo", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nREADME-copy.md\nNO\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_repl_env(),
        timeout=20,
    )
    assert proc.returncode == 0
    assert original.exists()
    assert not (tmp_path / "README-copy.md").exists()
