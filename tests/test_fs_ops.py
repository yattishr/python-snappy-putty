from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty import cli
from snappy_putty.fs_ops import list_dir, parse_incomplete_fs_intent, plan_fs_intent


def test_listing_uses_python_logic_and_shows_repo_entries() -> None:
    root = Path(__file__).resolve().parents[1]
    listing = list_dir(str(root))
    assert "README.md" in listing
    assert "src/" in listing


def test_fs_plan_only_does_not_mutate_filesystem(tmp_path: Path) -> None:
    source = tmp_path / "alpha.txt"
    source.write_text("hello", encoding="utf-8")

    mkdir_plan = plan_fs_intent("make a folder called plans", cwd=tmp_path)
    assert mkdir_plan is not None
    assert mkdir_plan.ops[0].action == "mkdir"
    assert not (tmp_path / "plans").exists()

    copy_plan = plan_fs_intent("copy alpha.txt to beta.txt", cwd=tmp_path)
    assert copy_plan is not None
    assert any(op.action == "copy" for op in copy_plan.ops)
    assert not (tmp_path / "beta.txt").exists()

    move_plan = plan_fs_intent("move alpha.txt to moved.txt", cwd=tmp_path)
    assert move_plan is not None
    assert any(op.action == "move" for op in move_plan.ops)
    assert source.exists()
    assert not (tmp_path / "moved.txt").exists()

    rename_plan = plan_fs_intent("rename alpha.txt to renamed.txt", cwd=tmp_path)
    assert rename_plan is not None
    assert any(op.action == "rename" for op in rename_plan.ops)
    assert source.exists()
    assert not (tmp_path / "renamed.txt").exists()


def test_apply_cancelled_when_confirmation_is_not_yes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")

    handled = cli._handle_fs_intent("copy alpha.txt to beta.txt", prompt_reader=lambda _: "no")
    assert handled is True
    assert (tmp_path / "alpha.txt").exists()
    assert not (tmp_path / "beta.txt").exists()


def test_apply_runs_when_confirmation_is_exact_yes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    source = tmp_path / "alpha.txt"
    source.write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    handled = cli._handle_fs_intent("copy alpha.txt to beta.txt", prompt_reader=lambda _: "YES")
    assert handled is True
    assert source.exists()
    assert (tmp_path / "beta.txt").exists()


def test_incomplete_copy_intent_prompts_for_destination(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    source = tmp_path / "alpha.txt"
    source.write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    responses = iter(["beta.txt", "YES"])
    handled = cli._handle_fs_intent("copy alpha.txt file", prompt_reader=lambda _: next(responses))
    assert handled is True
    assert source.exists()
    assert (tmp_path / "beta.txt").exists()


def test_copy_space_separated_outside_workspace_is_blocked(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("hello", encoding="utf-8")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    plan = plan_fs_intent("copy README.md README2.md", cwd=tmp_path, workspace_root=workspace_root)
    assert plan is not None
    assert plan.ops == []
    assert any("workspace root" in warning.lower() for warning in plan.warnings)


def test_copy_with_parent_relative_destination_is_not_treated_as_incomplete() -> None:
    assert parse_incomplete_fs_intent("copy README.md ../../README2.md") is None


def test_copy_space_separated_keeps_src_and_dst_and_is_not_incomplete(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("hello", encoding="utf-8")

    plan = plan_fs_intent("copy README.md README.md", cwd=tmp_path, workspace_root=tmp_path)
    assert plan is not None
    assert len(plan.ops) == 1
    assert plan.ops[0].action == "copy"
    assert plan.ops[0].src == "README.md"
    assert plan.ops[0].dst == "README.md"
    assert parse_incomplete_fs_intent("copy README.md README.md") is None


def test_copy_single_arg_requires_destination_prompt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    source = tmp_path / "README.md"
    source.write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    responses = iter(["sandbox/README-copy.md", "YES"])
    handled = cli._handle_fs_intent("copy README.md", prompt_reader=lambda _: next(responses), workspace_root=tmp_path)
    assert handled is True
    assert (tmp_path / "sandbox/README-copy.md").exists()


def test_copy_to_form_parses_destination_without_prompt(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("hello", encoding="utf-8")

    plan = plan_fs_intent("copy README.md to sandbox/README-copy.md", cwd=tmp_path, workspace_root=tmp_path)
    assert plan is not None
    assert [op.action for op in plan.ops] == ["mkdir", "copy"]
    assert plan.ops[1].src == "README.md"
    assert plan.ops[1].dst == "sandbox/README-copy.md"


def test_existing_destination_requires_overwrite_confirmation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SNAPPY_PUTTY_NO_SPINNER", "1")
    source = tmp_path / "README.md"
    destination = tmp_path / "README.copy.md"
    source.write_text("hello", encoding="utf-8")
    destination.write_text("existing", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    responses = iter(["NO"])
    handled = cli._handle_fs_intent("copy README.md README.copy.md", prompt_reader=lambda _: next(responses), workspace_root=tmp_path)
    assert handled is True
    assert destination.read_text(encoding="utf-8") == "existing"
