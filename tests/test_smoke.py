import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import snappy_putty.agent as agent_module
from snappy_putty.cli import app


runner = CliRunner()


def test_cli_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Snappy PuTTy CLI" in result.stdout


def test_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Context snapshot report" in result.stdout
    assert "System Snapshot" in result.stdout


def test_ask_runs_and_renders_commands() -> None:
    result = runner.invoke(app, ["ask", "give me a file listing"])
    assert result.exit_code == 0
    assert "Directory Listing" in result.stdout
    assert "Commands" in result.stdout


def test_ask_listing_for_src_path() -> None:
    result = runner.invoke(app, ["ask", "give me a file listing for src"])
    assert result.exit_code == 0
    assert "Directory Listing" in result.stdout
    assert "snappy_putty" in result.stdout


def test_explain_high_risk_warning() -> None:
    result = runner.invoke(app, ["explain", "rm -rf /"])
    assert result.exit_code == 0
    assert "High risk warning" in result.stdout


def test_explain_does_not_claim_local_repo_or_cwd() -> None:
    result = runner.invoke(app, ["explain", "git worktree list"])
    assert result.exit_code == 0
    lowered = result.stdout.lower()
    assert "current directory is not a git repo" not in lowered
    assert "not a git repository" not in lowered
    assert str(Path.cwd()) not in result.stdout


def test_ask_git_worktree_listing_mentions_repo_requirement() -> None:
    result = runner.invoke(app, ["ask", "give me a git worktree listing"])
    assert result.exit_code == 0
    lowered = result.stdout.lower()
    assert "git repository" in lowered


def test_google_cloud_deploy_cli_question() -> None:
    result = runner.invoke(app, ["ask", "deploy this to google cloud"])
    assert result.exit_code == 0
    assert "Do you want to deploy a web service, or publish/distribute this CLI?" in result.stdout
    assert "Cloud Run Job" in result.stdout
    assert "twine check" in result.stdout


def test_shell_starts_and_exits_with_exit_input() -> None:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="exit\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=20,
    )
    assert proc.returncode == 0
    assert "Snappy PuTTy" in proc.stdout
    assert "give me a file listing for src" in proc.stdout


def test_ask_parses_fenced_json_and_renders(monkeypatch) -> None:
    async def fake_run_with_sdk(mode: str, user_text: str, snapshot) -> str:
        return """```json
{
  "goal": "Fenced Goal",
  "assumptions": ["test assumption"],
  "question": null,
  "plan": [{"step": 1, "action": "inspect", "why": "test"}],
  "commands": [{"cmd": "ls -la", "explain": "list files", "risk": "low"}],
  "warnings": []
}
```"""

    monkeypatch.setattr(agent_module, "_run_with_sdk", fake_run_with_sdk)
    result = runner.invoke(app, ["ask", "show me status"])
    assert result.exit_code == 0
    assert "Fenced Goal" in result.stdout
    assert "Commands" in result.stdout
