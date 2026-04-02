import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tests.agent_fixtures import load_agent_fixture
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


def test_agent_command_runs(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        load_agent_fixture("valid_agent", Path.cwd())

        result = runner.invoke(app, ["agent"])

        assert result.exit_code == 0
        assert "Agent Summary" in result.stdout
        assert "Agent name: Fixture Agent" in result.stdout
        assert "Version: 1" in result.stdout
        assert "Session memory keys: last_goal" in result.stdout


def test_agent_doctor_command_runs(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        load_agent_fixture("valid_agent", Path.cwd())

        result = runner.invoke(app, ["agent-doctor"])

        assert result.exit_code == 0
        assert "Agent Doctor" in result.stdout
        assert ".snappy directory: present" in result.stdout
        assert "Manifest parse: ok" in result.stdout
        assert "Session parse: ok" in result.stdout


def test_init_scaffolds_agent_directory() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Initialized agent scaffold" in result.stdout
        assert Path(".snappy").is_dir()
        assert Path(".snappy/snappy.yaml").is_file()
        assert Path(".snappy/skills").is_dir()
        assert Path(".snappy/rules").is_dir()
        assert Path(".snappy/memory").is_dir()
        manifest = Path(".snappy/snappy.yaml").read_text(encoding="utf-8")
        assert "version: 1" in manifest
        assert "mode: supervised" in manifest


def test_init_refuses_to_overwrite_existing_agent_directory_without_force() -> None:
    with runner.isolated_filesystem():
        agent_root = Path(".snappy")
        agent_root.mkdir()
        manifest_path = agent_root / "snappy.yaml"
        manifest_path.write_text("name: custom\n", encoding="utf-8")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Refusing to overwrite existing .snappy/" in result.stdout
        assert manifest_path.read_text(encoding="utf-8") == "name: custom\n"


def test_init_force_overwrites_scaffold_files() -> None:
    with runner.isolated_filesystem():
        agent_root = Path(".snappy")
        agent_root.mkdir()
        manifest_path = agent_root / "snappy.yaml"
        manifest_path.write_text("name: old\n", encoding="utf-8")

        result = runner.invoke(app, ["init", "--force"])

        assert result.exit_code == 0
        assert "Initialized agent scaffold" in result.stdout
        manifest = manifest_path.read_text(encoding="utf-8")
        assert "name: old" not in manifest
        assert "version: 1" in manifest
        assert Path(".snappy/skills").is_dir()
        assert Path(".snappy/rules").is_dir()
        assert Path(".snappy/memory").is_dir()


def test_skills_lists_loaded_skill_names(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        skills_dir = Path(".snappy/skills")
        skills_dir.mkdir(parents=True)
        (skills_dir / "docker.md").write_text(
            "\n".join(
                [
                    "# Skill: Docker Logs",
                    "Description:",
                    "Inspect running container logs safely.",
                    "Intent examples:",
                    "- show docker logs for api",
                    "Risk: low",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["skills"])

        assert result.exit_code == 0
        assert "Loaded skills:" in result.stdout
        assert "Docker Logs [low]" in result.stdout


def test_skills_skips_invalid_skill_files_with_warning(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        skills_dir = Path(".snappy/skills")
        skills_dir.mkdir(parents=True)
        (skills_dir / "broken.md").write_text(
            "# Skill: Broken Skill\nDescription:\nOnly description.\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["skills"])
        output = " ".join(result.stdout.split())

        assert result.exit_code == 0
        assert "No skills loaded." in result.stdout
        assert (
            "Warning: skipped .snappy/skills/broken.md because Intent examples section was missing or malformed."
            in output
        )


def test_skills_reports_missing_or_malformed_risk_value(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        skills_dir = Path(".snappy/skills")
        skills_dir.mkdir(parents=True)
        (skills_dir / "copy.md").write_text(
            "\n".join(
                [
                    "# Skill: copy",
                    "Description:",
                    "Copy files from one place to another.",
                    "Intent examples:",
                    "- copy README.md to docs/",
                    "Risk:",
                    "LOW",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["skills"])
        output = " ".join(result.stdout.split())

        assert result.exit_code == 0
        assert "No skills loaded." in result.stdout
        assert (
            "Warning: skipped .snappy/skills/copy.md because Risk value was missing or malformed."
            in output
        )


def test_rules_lists_loaded_rule_names(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        rules_dir = Path(".snappy/rules")
        rules_dir.mkdir(parents=True)
        (rules_dir / "safety.md").write_text(
            "# Rule: Confirm Destructive Actions\nAlways ask for confirmation before destructive commands.\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["rules"])

        assert result.exit_code == 0
        assert "Loaded rules:" in result.stdout
        assert "Confirm Destructive Actions" in result.stdout


def test_rules_handles_empty_rules_directory(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        Path(".snappy/rules").mkdir(parents=True)

        result = runner.invoke(app, ["rules"])

        assert result.exit_code == 0
        assert "No rules loaded." in result.stdout


def test_rules_skips_malformed_markdown_with_warning(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "passive")
        rules_dir = Path(".snappy/rules")
        rules_dir.mkdir(parents=True)
        (rules_dir / "broken.md").write_text("Rule without heading\n", encoding="utf-8")

        result = runner.invoke(app, ["rules"])

        assert result.exit_code == 0
        assert "No rules loaded." in result.stdout
        assert "Skipped invalid rule file broken.md" in result.stdout


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


def test_shell_agent_command_runs() -> None:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_AGENT_MODE"] = "passive"
    with runner.isolated_filesystem():
        load_agent_fixture("valid_agent", Path.cwd())

        proc = subprocess.run(
            [sys.executable, "-m", "snappy_putty.cli", "shell"],
            input="agent\nexit\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )

    assert proc.returncode == 0
    assert "Agent Summary" in proc.stdout
    assert "Agent name: Fixture Agent" in proc.stdout


def test_shell_agent_doctor_command_runs() -> None:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_AGENT_MODE"] = "passive"
    with runner.isolated_filesystem():
        load_agent_fixture("valid_agent", Path.cwd())

        proc = subprocess.run(
            [sys.executable, "-m", "snappy_putty.cli", "shell"],
            input="agent doctor\nexit\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )

    assert proc.returncode == 0
    assert "Agent Doctor" in proc.stdout
    assert "Session parse: ok" in proc.stdout


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


def test_ask_unknown_command_stays_local_and_does_not_call_agent(monkeypatch) -> None:
    def fail_handle_ask(*args, **kwargs):
        raise AssertionError("handle_ask should not run for unknown commands")

    monkeypatch.setattr("snappy_putty.cli.handle_ask", fail_handle_ask)
    result = runner.invoke(app, ["ask", "do something random and undefined"])
    assert result.exit_code == 0
    assert "I don't recognize that command. Try 'help' to see what I can do." in result.stdout
