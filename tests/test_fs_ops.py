from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty import cli
from snappy_putty.fs_ops import list_dir, plan_fs_intent


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
