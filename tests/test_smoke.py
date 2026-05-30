import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tests.agent_fixtures import load_agent_fixture
import snappy_putty.agent as agent_module
import snappy_putty.cli as cli_module
from snappy_putty.cli import app
from snappy_putty.models import AgentOutput


runner = CliRunner()


def test_default_openai_model_is_current() -> None:
    assert agent_module.DEFAULT_OPENAI_MODEL == "gpt-5.4-mini"


def _shell_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path
    env["SNAPPY_PUTTY_NO_SPINNER"] = "1"
    return env


def test_cli_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Snappy PuTTy CLI" in result.stdout


def test_cli_help_command_shows_repl_commands() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "Workflow" in result.stdout
    assert "show plan" in result.stdout
    assert "Display current stored plan" in result.stdout
    assert "why this plan" in result.stdout
    assert "Explain current plan" in result.stdout
    assert "explain step N" in result.stdout
    assert "Explain one plan step" in result.stdout
    assert "refine step N" in result.stdout
    assert "Refine one plan step" in result.stdout
    assert "show pending" in result.stdout
    assert "Show parked goal" in result.stdout
    assert "resume pending" in result.stdout
    assert "Resume parked goal when IDLE" in result.stdout
    assert "clear pending" in result.stdout
    assert "Remove parked goal" in result.stdout
    assert "cancel" in result.stdout
    assert "Cancel active workflow" in result.stdout


def test_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Context snapshot report" in result.stdout
    assert "System Snapshot" in result.stdout


def test_agent_command_runs(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
        load_agent_fixture("valid_agent", Path.cwd())

        result = runner.invoke(app, ["agent"])

        assert result.exit_code == 0
        assert "Agent Summary" in result.stdout
        assert "Agent name: Fixture Agent" in result.stdout
        assert "Version: 1" in result.stdout
        assert "Block rules: (none)" in result.stdout
        assert "Confirm rules: (none)" in result.stdout
        assert "Warn rules: (none)" in result.stdout
        assert "Info rules: confirm_destructive_actions" in result.stdout
        assert "Session memory keys: last_goal" in result.stdout


def test_agent_doctor_command_runs(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
        load_agent_fixture("valid_agent", Path.cwd())

        result = runner.invoke(app, ["agent-doctor"])

        assert result.exit_code == 0
        assert "Agent Doctor" in result.stdout
        assert ".snappy directory: present" in result.stdout
        assert "Manifest parse: ok" in result.stdout
        assert "Policy tiers: block=0, confirm=0, warn=0, info=1" in result.stdout
        assert "Session parse: ok" in result.stdout


def test_init_scaffolds_agent_directory() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Created .snappy/snappy.yaml" in result.stdout
        assert Path(".snappy").is_dir()
        assert Path(".snappy/snappy.yaml").is_file()
        assert Path(".snappy/skills").is_dir()
        assert Path(".snappy/memory").is_dir()
        manifest = Path(".snappy/snappy.yaml").read_text(encoding="utf-8")
        assert "version: 1" in manifest
        assert "mode: off" in manifest


def test_init_refuses_to_overwrite_existing_agent_directory_without_force() -> None:
    with runner.isolated_filesystem():
        agent_root = Path(".snappy")
        agent_root.mkdir()
        manifest_path = agent_root / "snappy.yaml"
        manifest_path.write_text("version: 1\nagent:\n  name: custom\n  mode: off\n", encoding="utf-8")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert ".snappy/snappy.yaml already exists and is valid. No changes made." in result.stdout
        assert manifest_path.read_text(encoding="utf-8") == "version: 1\nagent:\n  name: custom\n  mode: off\n"


def test_init_force_overwrites_scaffold_files() -> None:
    with runner.isolated_filesystem():
        agent_root = Path(".snappy")
        agent_root.mkdir()
        manifest_path = agent_root / "snappy.yaml"
        manifest_path.write_text("name: old\n", encoding="utf-8")

        result = runner.invoke(app, ["init", "--force"])

        assert result.exit_code == 0
        assert "Migrated config to current schema." in result.stdout
        manifest = manifest_path.read_text(encoding="utf-8")
        assert "name: old" in manifest
        assert "mode: off" in manifest
        assert "version: 1" in manifest
        assert Path(".snappy/skills").is_dir()
        assert Path(".snappy/memory").is_dir()


def test_skills_lists_loaded_skill_names(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
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
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
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
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
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
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
        rules_dir = Path(".snappy/rules")
        rules_dir.mkdir(parents=True)
        (rules_dir / "safety.md").write_text(
            "# Rule: Confirm Destructive Actions\nAlways ask for confirmation before destructive commands.\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["rules"])

        assert result.exit_code == 0
        assert "Loaded rules:" in result.stdout
        assert "Confirm Destructive Actions [confirm_destructive_actions] (informational)" in result.stdout


def test_rules_handles_empty_rules_directory(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
        Path(".snappy/rules").mkdir(parents=True)

        result = runner.invoke(app, ["rules"])

        assert result.exit_code == 0
        assert "No rules loaded." in result.stdout


def test_rules_skips_malformed_markdown_with_warning(monkeypatch) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
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
    env = _shell_env()
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
    assert "Project-Aware AI Co-Pilot" in proc.stdout
    assert "Try asking:" in proc.stdout
    assert "help • skills • inspect • status • exit" in proc.stdout
    assert "Quick commands" not in proc.stdout


def test_shell_agent_command_runs() -> None:
    env = _shell_env()
    env["SNAPPY_AGENT_MODE"] = "active"
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
    env = _shell_env()
    env["SNAPPY_AGENT_MODE"] = "active"
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
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    monkeypatch.setattr(agent_module, "is_llm_available", lambda session_mode=None: True)

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
    result = runner.invoke(app, ["explain", "du -sh ."])
    assert result.exit_code == 0
    assert "Fenced Goal" in result.stdout
    assert "Commands" in result.stdout


def test_explain_active_mode_reports_unavailable_llm(monkeypatch) -> None:
    monkeypatch.setenv("SNAPPY_AGENT_MODE", "active")
    monkeypatch.setattr(agent_module, "is_llm_available", lambda session_mode=None: False)

    result = runner.invoke(app, ["explain", "git diff"])

    assert result.exit_code == 0
    assert "This command requires LLM support, but the LLM is unavailable." in result.stdout
    assert "No explanation was generated." in result.stdout
    assert "OpenAI Agents SDK could not be reached" not in result.stdout


def test_handle_explain_passes_session_mode(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def fake_plan_with_agent(*, mode, user_text, snapshot, session_mode=None):
        seen["mode"] = mode
        seen["user_text"] = user_text
        seen["session_mode"] = session_mode
        return agent_module.AgentRunResult(
            output=AgentOutput(
                goal=user_text,
                assumptions=[],
                question=None,
                plan=[],
                commands=[],
                warnings=[],
            )
        )

    monkeypatch.setattr(cli_module, "plan_with_agent", fake_plan_with_agent)

    cli_module.handle_explain("git diff", session_mode="active")

    assert seen == {"mode": "explain", "user_text": "git diff", "session_mode": "active"}


def test_ask_unknown_command_stays_local_and_does_not_call_agent(monkeypatch) -> None:
    def fail_handle_ask(*args, **kwargs):
        raise AssertionError("handle_ask should not run for unknown commands")

    monkeypatch.setattr("snappy_putty.cli.handle_ask", fail_handle_ask)
    result = runner.invoke(app, ["ask", "do something random and undefined"])
    assert result.exit_code == 0
    assert "I don't recognize that command. Try 'help' to see what I can do." in result.stdout


def test_ask_out_of_scope_request_is_declined_without_calling_agent(monkeypatch) -> None:
    def fail_handle_ask(*args, **kwargs):
        raise AssertionError("handle_ask should not run for out-of-scope requests")

    monkeypatch.setattr("snappy_putty.cli.handle_ask", fail_handle_ask)
    result = runner.invoke(app, ["ask", "give me the latest news on the election"])
    assert result.exit_code == 0
    assert "I can only help with software, hardware, and technology topics." in result.stdout
    assert "Try asking about code, debugging, CLIs, repos, APIs, or hardware." in result.stdout


def test_shell_workflow_ux_smoke_clarification_confirmation_and_after(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md\nhelp\ncancel\ncopy README.md README-copy.md\nmaybe\nafter\nYES\nafter\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_shell_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Your pending question is still active." in proc.stdout
    assert "Please answer YES or NO." in proc.stdout
    assert "Awaiting confirmation: Ready to apply changes" in proc.stdout
    assert "Files may be modified." in proc.stdout
    assert "No pending next step." in proc.stdout


def test_shell_workflow_ux_smoke_same_file_no_op(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README.md\nstatus\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=_shell_env(),
        timeout=20,
    )

    assert proc.returncode == 0
    output = " ".join(proc.stdout.split())
    assert "No-Op Request" in output
    assert "same source and destination." in output
    assert "Source and destination resolve to the same file." in output
    assert "Current state: IDLE" in output


def test_shell_workflow_ux_smoke_blocked_rule_is_prominent(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _shell_env()
    env["SNAPPY_AGENT_MODE"] = "active"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to /\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Policy Block" in proc.stdout
    assert "Operation blocked by rule: protect_project_root" in proc.stdout
    assert "Next Step" in proc.stdout


def test_shell_workflow_ux_smoke_combined_block_and_confirm_stays_blocked(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "protect_project_root.md").write_text(
        "# Rule: protect_project_root\nProtect the project root from dangerous mutations.\n",
        encoding="utf-8",
    )
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _shell_env()
    env["SNAPPY_AGENT_MODE"] = "active"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md to /\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Policy Block" in proc.stdout
    assert "Operation blocked by rule: protect_project_root" in proc.stdout
    assert "Additional policy context: confirmation rule(s) also matched:" in proc.stdout
    assert "require_confirm" in proc.stdout
    assert "Type YES to apply, or NO to cancel." not in proc.stdout


def test_shell_workflow_ux_smoke_confirm_and_info_show_policy_without_block(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".snappy" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "require_confirm.md").write_text(
        "# Rule: require_confirm\nAll filesystem mutations require confirmation before execution.\n",
        encoding="utf-8",
    )
    (rules_dir / "custom_note.md").write_text(
        "# Rule: custom_note\nHuman-readable guidance only.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    env = _shell_env()
    env["SNAPPY_AGENT_MODE"] = "active"

    proc = subprocess.run(
        [sys.executable, "-m", "snappy_putty.cli", "shell"],
        input="copy README.md README-copy.md\nNO\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=20,
    )

    assert proc.returncode == 0
    assert "Policy" in proc.stdout
    assert "Loaded rules require confirmation before filesystem changes are applied." in proc.stdout
    assert "Policy Block" not in proc.stdout
    assert "Ready to apply changes" in proc.stdout
    assert "Files may be modified." in proc.stdout
