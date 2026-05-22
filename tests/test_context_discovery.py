from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from snappy_putty import active_planner
from snappy_putty.context_discovery import (
    SufficiencyResult,
    build_repo_map,
    derive_goal_terms,
    discover_context,
)
from snappy_putty.project_inspector import inspect_project


def _taskcli_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'taskcli'\n[project.scripts]\ntaskcli = 'taskcli.main:main'\n",
        encoding="utf-8",
    )
    src_dir = root / "src" / "taskcli"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text(
        "import argparse\nfrom .storage import load_tasks\nfrom .tasks import list_tasks\n\n"
        "def main():\n    parser = argparse.ArgumentParser()\n    return list_tasks(load_tasks())\n",
        encoding="utf-8",
    )
    (src_dir / "tasks.py").write_text("def list_tasks(tasks):\n    return tasks\n", encoding="utf-8")
    (src_dir / "storage.py").write_text("def load_tasks():\n    return []\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_tasks.py").write_text("def test_tasks():\n    assert True\n", encoding="utf-8")
    (tests_dir / "test_storage.py").write_text("def test_storage():\n    assert True\n", encoding="utf-8")
    (root / "README.md").write_text("# Task CLI\n", encoding="utf-8")


def test_repo_map_excludes_noise(tmp_path: Path) -> None:
    for dirname in [".git", ".snappy", ".venv", "node_modules"]:
        noisy = tmp_path / dirname
        noisy.mkdir()
        (noisy / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")

    repo_map = build_repo_map(inspect_project(tmp_path))

    paths = {item.path for item in repo_map.files}
    assert "src/app.py" in paths
    assert not any(path.startswith((".git/", ".snappy/", ".venv/", "node_modules/")) for path in paths)


def test_node_project_inspection_includes_javascript_sources(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts": {"start": "node src/index.js"}}\n', encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.js").write_text("console.log('hello')\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)

    assert "package.json" in snapshot.config_files
    assert "src/index.js" in snapshot.source_files
    assert "javascript" in snapshot.languages


def test_typescript_project_inspection_includes_tsx_sources(tmp_path: Path) -> None:
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"jsx": "react-jsx"}}\n', encoding="utf-8")
    (tmp_path / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "App.tsx").write_text("export function App() { return <main /> }\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)

    assert "tsconfig.json" in snapshot.config_files
    assert "vite.config.ts" in snapshot.config_files
    assert "src/App.tsx" in snapshot.source_files
    assert "typescript" in snapshot.languages


def test_node_project_inspection_excludes_generated_directories(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.js").write_text("export {}\n", encoding="utf-8")
    generated_dirs = [
        "node_modules",
        "build",
        "dist",
        ".next",
        ".turbo",
        ".vite",
        "out",
        ".cache",
        ".parcel-cache",
    ]
    for dirname in generated_dirs:
        generated = tmp_path / dirname
        generated.mkdir()
        (generated / "artifact.js").write_text("ignored\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)
    inspected = set(snapshot.config_files + snapshot.source_files + snapshot.test_files + snapshot.sampled_files)

    assert "src/index.js" in snapshot.source_files
    assert not any(path.startswith(f"{dirname}/") for dirname in generated_dirs for path in inspected)
    assert ".gitignore" not in inspected


def test_repo_map_excludes_gitignore(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (tmp_path / "server.js").write_text("require('http')\n", encoding="utf-8")

    result = discover_context("help me improve this api", inspect_project(tmp_path))
    paths = [item.path for item in result.repo_map.files]

    assert ".gitignore" not in paths


def test_python_project_inspection_behavior_stays_stable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_app():\n    assert True\n", encoding="utf-8")

    snapshot = inspect_project(tmp_path)

    assert "pyproject.toml" in snapshot.config_files
    assert "src/app.py" in snapshot.source_files
    assert "tests/test_app.py" in snapshot.test_files
    assert "python" in snapshot.languages


def test_cli_project_selects_entrypoint_and_balanced_context(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)

    result = discover_context("help me improve this CLI", inspect_project(tmp_path))
    paths = [item.path for item in result.selected_context]

    assert paths[0] == "src/taskcli/main.py"
    assert "src/taskcli/tasks.py" in paths
    assert "src/taskcli/storage.py" in paths
    assert "tests/test_tasks.py" in paths
    assert "README.md" in paths


def test_logging_goal_selects_implementation_files(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)

    result = discover_context("help me implement logging", inspect_project(tmp_path))
    paths = [item.path for item in result.selected_context]

    assert "src/taskcli/main.py" in paths
    assert "src/taskcli/storage.py" in paths
    assert "src/taskcli/tasks.py" in paths
    assert paths.count("src/taskcli/__init__.py") == 0


def test_unknown_domain_terms_are_derived_and_select_matching_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "websocket_reconnect.py").write_text("def reconnect():\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")

    result = discover_context("help me improve websocket reconnect behavior", inspect_project(tmp_path))

    assert "websocket" in derive_goal_terms("help me improve websocket reconnect behavior")
    assert "reconnect" in derive_goal_terms("help me improve websocket reconnect behavior")
    assert "src/websocket_reconnect.py" in [item.path for item in result.selected_context]


def test_sufficiency_check_expands_once_and_ignores_missing_files(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)
    (tmp_path / "src" / "taskcli" / "diagnostics.py").write_text("def diagnostics():\n    pass\n", encoding="utf-8")
    calls = 0

    def checker(goal, repo_map, selected):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SufficiencyResult(
                False,
                "Need extra context.",
                ["diagnostics implementation"],
                ["src/taskcli/diagnostics.py", "src/taskcli/missing.py"],
            )
        return SufficiencyResult(True, "Enough context after expansion.")

    result = discover_context("help me improve CLI", inspect_project(tmp_path), sufficiency_checker=checker)

    assert calls == 2
    assert result.expanded is True
    assert "src/taskcli/missing.py" in result.rejected_expansion_files
    assert "src/taskcli/diagnostics.py" in [item.path for item in result.selected_context]


def test_expansion_is_capped(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)
    extras = tmp_path / "src" / "taskcli"
    for index in range(10):
        (extras / f"extra_{index}.py").write_text(f"def extra_{index}():\n    pass\n", encoding="utf-8")

    def checker(goal, repo_map, selected):
        if not any(item.path.endswith("extra_0.py") for item in selected):
            return SufficiencyResult(False, "Need many extras.", ["extra"], [f"src/taskcli/extra_{index}.py" for index in range(10)])
        return SufficiencyResult(True, "Enough.")

    result = discover_context("help me improve CLI", inspect_project(tmp_path), sufficiency_checker=checker)

    assert len(result.selected_context) <= 15


def test_plan_stores_context_metadata(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)

    plan = active_planner.create_llm_assisted_plan(
        "help me implement logging",
        inspect_project(tmp_path),
        client=active_planner._MockLLMPlannerClient(),
    )
    payload = active_planner.plan_to_payload(plan)

    assert payload["context_selection"]["strategy"] == "bounded_context_discovery_v1"
    assert payload["context_selection"]["files"]
    assert payload["context_selection"]["sufficiency"]["final_sufficient"] is True
    assert json.loads(json.dumps(payload))


class _CountingMockPlanner(active_planner._MockLLMPlannerClient):
    def __init__(self) -> None:
        self.sufficiency_checks = 0
        self.prompts: list[str] = []

    def check_context_sufficiency(self, prompt: str) -> dict[str, object]:
        self.sufficiency_checks += 1
        return super().check_context_sufficiency(prompt)

    def create_plan(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return super().create_plan(prompt)


def test_repeated_planning_on_unchanged_snapshot_reuses_cached_context(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)
    snapshot = inspect_project(tmp_path)
    client = _CountingMockPlanner()

    first = active_planner.create_llm_assisted_plan("help me implement logging", snapshot, client=client)
    second = active_planner.create_llm_assisted_plan("help me implement logging", snapshot, client=client)

    assert first.context_selection["cache_hit"] is False
    assert second.context_selection["cache_hit"] is True
    assert client.sufficiency_checks == 1
    assert (tmp_path / ".snappy" / "cache").is_dir()


def test_changed_file_hash_invalidates_context_cache(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)
    snapshot = inspect_project(tmp_path)
    first = discover_context("help me implement logging", snapshot)
    assert first.cache_hit is False

    (tmp_path / "src" / "taskcli" / "storage.py").write_text("def load_tasks():\n    return ['changed']\n", encoding="utf-8")
    changed_snapshot = replace(inspect_project(tmp_path), snapshot_id=snapshot.snapshot_id)
    second = discover_context("help me implement logging", changed_snapshot)

    assert second.cache_hit is False
    assert second.cache_key != first.cache_key


def test_package_lock_is_not_entrypoint_for_vanilla_node_api_goal(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text('{"name": "demo", "packages": {}}\n', encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "routes.js").write_text("export function usersRoute(req, res) { res.end('ok') }\n", encoding="utf-8")
    (src_dir / "server.js").write_text("import { usersRoute } from './routes.js'\nexport function start() {}\n", encoding="utf-8")

    result = discover_context("help me add an API route spec", inspect_project(tmp_path))
    selected = [item.path for item in result.selected_context]

    assert "package-lock.json" not in result.repo_map.entrypoint_candidates
    assert "package-lock.json" not in selected
    assert "src/routes.js" in selected


def test_package_lock_is_not_added_by_context_expansion_for_non_dependency_goal(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text(
        '{"name": "demo", "packages": {"node_modules/cac": {"version": "1.0.0"}}}\n',
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text('{"scripts": {"start": "node server.js"}}\n', encoding="utf-8")
    (tmp_path / "server.js").write_text(
        "const http = require('http')\n"
        "http.createServer((_req, res) => res.end('ok'))\n",
        encoding="utf-8",
    )
    (tmp_path / "routes.js").write_text("function listProducts() { return [] }\n", encoding="utf-8")
    calls = 0

    def checker(goal, repo_map, selected):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SufficiencyResult(False, "Need more API context.", ["api entrypoint"], ["package-lock.json"])
        return SufficiencyResult(True, "Enough context without lockfiles.")

    result = discover_context("help me design a frontend for this API", inspect_project(tmp_path), sufficiency_checker=checker)
    selected = [item.path for item in result.selected_context]

    assert calls == 1
    assert result.expanded is False
    assert "package-lock.json" not in result.repo_map.entrypoint_candidates
    assert "package-lock.json" not in selected


def test_generated_planner_payload_is_smaller_on_repeated_calls(tmp_path: Path) -> None:
    _taskcli_project(tmp_path)
    (tmp_path / "src" / "taskcli" / "storage.py").write_text(
        "def load_tasks():\n"
        "    data = []\n"
        + "\n".join(f"    data.append('task-{index}')" for index in range(300))
        + "\n    return data\n",
        encoding="utf-8",
    )
    snapshot = inspect_project(tmp_path)
    first_context = discover_context("help me implement logging", snapshot)
    second_context = discover_context("help me implement logging", snapshot)

    first_parts = active_planner.build_llm_prompt_parts("help me implement logging", snapshot, context_bundle=first_context)
    second_parts = active_planner.build_llm_prompt_parts("help me implement logging", snapshot, context_bundle=second_context)

    assert first_context.cache_hit is False
    assert second_context.cache_hit is True
    assert first_parts.stable_prefix == second_parts.stable_prefix
    assert len(second_parts.dynamic_payload) < len(first_parts.dynamic_payload)


def test_context_cache_can_be_disabled_with_env(tmp_path: Path, monkeypatch) -> None:
    _taskcli_project(tmp_path)
    snapshot = inspect_project(tmp_path)
    calls = 0

    def checker(goal, repo_map, selected):
        nonlocal calls
        calls += 1
        return SufficiencyResult(True, "Enough context.")

    monkeypatch.setenv("SNAPPY_DISABLE_CONTEXT_CACHE", "1")

    first = discover_context("help me improve CLI", snapshot, sufficiency_checker=checker)
    second = discover_context("help me improve CLI", snapshot, sufficiency_checker=checker)

    assert first.cache_hit is False
    assert second.cache_hit is False
    assert calls == 2
