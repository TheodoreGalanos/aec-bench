# ABOUTME: Tests for harness progress accounting over Harbor-backed experiment imports.
# ABOUTME: Verifies deterministic counters for discovered, imported, duplicate, and invalid trials.

from pathlib import Path

from aec_bench.harness.progress_tracker import ImportProgressTracker, WorkflowProgressTracker


def test_progress_tracker_counts_import_outcomes() -> None:
    tracker = ImportProgressTracker(experiment_id="experiment-001", selected_task_count=12)

    tracker.record_discovered()
    tracker.record_imported()
    tracker.record_discovered()
    tracker.record_duplicate()
    tracker.record_discovered()
    tracker.record_invalid()
    snapshot = tracker.snapshot()

    assert snapshot.experiment_id == "experiment-001"
    assert snapshot.selected_task_count == 12
    assert snapshot.discovered_trials == 3
    assert snapshot.imported_trials == 1
    assert snapshot.duplicate_trials == 1
    assert snapshot.invalid_trials == 1


def test_workflow_progress_tracker_reports_stage_snapshots() -> None:
    tracker = WorkflowProgressTracker(
        experiment_id="experiment-001",
        selected_task_count=12,
        planned_trial_count=60,
    )

    dispatch_started = tracker.dispatch_started()
    dispatch_completed = tracker.dispatch_completed(exit_code=0)
    identified = tracker.job_dir_identified(job_dir=Path("/tmp/jobs/run-001"))
    import_started = tracker.import_started(job_dir=Path("/tmp/jobs/run-001"))
    import_completed = tracker.import_completed(
        job_dir=Path("/tmp/jobs/run-001"),
        discovered_trials=60,
        imported_trials=58,
        duplicate_trials=2,
        invalid_trials=0,
    )

    assert dispatch_started.stage == "dispatch_started"
    assert dispatch_started.planned_trial_count == 60
    assert dispatch_completed.dispatch_exit_code == 0
    assert identified.job_dir == "/tmp/jobs/run-001"
    assert import_started.stage == "import_started"
    assert import_completed.imported_trials == 58
    assert import_completed.duplicate_trials == 2
