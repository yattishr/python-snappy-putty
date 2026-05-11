from __future__ import annotations

from snappy_putty.run_harness import ActionEnvelope, StepResult, add_action, complete_run, load_last_run, record_step, start_run


def test_run_object_creation_records_core_fields(tmp_path):
    run = start_run(tmp_path, goal="help me improve this CLI", mode="active", plan_id="plan-1", snapshot_id="snap-1")

    assert run.run_id.startswith("run_")
    assert (tmp_path / ".snappy" / "runs" / f"{run.run_id}.json").is_file()
    assert run.goal == "help me improve this CLI"
    assert run.mode == "active"
    assert run.state == "RUNNING"
    assert run.plan_id == "plan-1"
    assert run.snapshot_id == "snap-1"


def test_step_result_recording_updates_run_file(tmp_path):
    run = start_run(tmp_path, goal="show file listing", mode="active")
    run = add_action(
        tmp_path,
        run,
        ActionEnvelope(
            action_id="action_001",
            tool="list_files",
            risk="LOW",
            scope="read_only",
            target=".",
            requires_confirmation=False,
        ),
    )

    run = record_step(
        tmp_path,
        run,
        StepResult(
            step_number=1,
            description="List files",
            action="list_files",
            action_id="action_001",
            status="success",
            started_at="2026-05-11T18:20:03+02:00",
            completed_at="2026-05-11T18:20:04+02:00",
            files_touched=["README.md"],
            summary="Listed files successfully.",
            error=None,
        ),
    )

    stored = load_last_run(tmp_path)
    assert stored is not None
    assert stored.run_id == run.run_id
    assert stored.actions[0].tool == "list_files"
    assert stored.steps[0].status == "success"
    assert stored.steps[0].files_touched == ["README.md"]
    assert stored.steps[0].summary == "Listed files successfully."


def test_completion_summary_sets_terminal_fields(tmp_path):
    run = start_run(tmp_path, goal="show file listing", mode="active")

    completed = complete_run(tmp_path, run, result="success", summary="Run result: success")

    assert completed.completed_at is not None
    assert completed.result == "success"
    assert completed.state == "SUCCESS"
    assert completed.summary == "Run result: success"
