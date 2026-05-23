# ABOUTME: Tests for the local evolution solve backend.
# ABOUTME: Verifies task batch selection covers suites across repeated cycles.

from pathlib import Path

from aec_bench.evolution.backends.local import _select_task_batch


def test_select_task_batch_rotates_across_calls(tmp_path: Path) -> None:
    task_dirs = [tmp_path / f"task-{idx}" for idx in range(5)]

    first = _select_task_batch(task_dirs, batch_size=2, start_index=0)
    second = _select_task_batch(task_dirs, batch_size=2, start_index=2)
    third = _select_task_batch(task_dirs, batch_size=2, start_index=4)

    assert first == [task_dirs[0], task_dirs[1]]
    assert second == [task_dirs[2], task_dirs[3]]
    assert third == [task_dirs[4], task_dirs[0]]
