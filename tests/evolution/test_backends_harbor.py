# ABOUTME: Tests for the Harbor evolution solve backend.
# ABOUTME: Uses stub TrialRunner and backend to verify snapshot injection and task iteration.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    prompt: str = "You are an engineering agent.",
    skills: list[SkillEntry] | None = None,
    version: str = "evo-0",
) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt=prompt,
        skills=skills or [],
        workspace_version=version,
    )


def _make_skill(name: str = "cable-sizing", body: str = "I_z >= I_b") -> SkillEntry:
    return SkillEntry(
        name=name,
        description="Cable sizing reference",
        discipline="electrical",
        body=body,
    )


# ---------------------------------------------------------------------------
# Stub types that satisfy the duck-typed interfaces used by make_harbor_solve_fn
# ---------------------------------------------------------------------------


@dataclass
class StubTrialRecord:
    """Minimal stand-in for TrialRecord (the real one is a Pydantic model)."""

    trial_id: str


@dataclass
class StubTask:
    """Stub matching the ResolvedTaskInstance shape expected by the solve fn."""

    instance_dir: Path
    task: Any = None
    verifier_script: Path = field(default_factory=Path)


class StubTrialRunner:
    """A trial runner that records calls and returns a minimal record."""

    def __init__(self, workspace_root: Path) -> None:
        self.calls: list[dict[str, Any]] = []
        self.workspace_root = workspace_root

    def run(self, **kwargs: Any) -> StubTrialRecord:
        self.calls.append(kwargs)
        return StubTrialRecord(trial_id=kwargs["trial_id"])


class FailingTrialRunner:
    """A trial runner that always raises RuntimeError."""

    def run(self, **kwargs: Any) -> None:
        raise RuntimeError("Expected failure — testing injection only")


# ---------------------------------------------------------------------------
# TestMakeHarborSolveFn
# ---------------------------------------------------------------------------


class TestMakeHarborSolveFn:
    def test_returns_callable(self) -> None:
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        solve_fn = make_harbor_solve_fn(
            trial_runner=None,
            backend=None,
            tasks=[],
            adapter=None,
            experiment_id="evo-test",
        )
        assert callable(solve_fn)

    def test_returns_empty_for_no_tasks(self) -> None:
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        solve_fn = make_harbor_solve_fn(
            trial_runner=None,
            backend=None,
            tasks=[],
            adapter=None,
            experiment_id="evo-test",
        )
        snapshot = _make_snapshot()
        result = solve_fn(snapshot, batch_size=5)
        assert result == []

    def test_injects_snapshot_before_run(self, tmp_path: Path) -> None:
        """Verify that system_prompt.md is written to the task instance dir before run."""
        import aec_bench.evolution.backends.harbor as harbor_mod
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        instance_dir = tmp_path / "tasks" / "electrical" / "test-task"
        instance_dir.mkdir(parents=True)
        (instance_dir / "instruction.md").write_text("Test instruction.")

        injected_paths: list[Path] = []
        original_inject = harbor_mod.inject_snapshot_into_workspace

        def tracking_inject(snapshot: WorkspaceSnapshot, workspace_dir: Path) -> None:
            injected_paths.append(workspace_dir)
            original_inject(snapshot, workspace_dir)

        harbor_mod.inject_snapshot_into_workspace = tracking_inject

        try:
            task = StubTask(instance_dir=instance_dir)
            solve_fn = make_harbor_solve_fn(
                trial_runner=FailingTrialRunner(),
                backend=None,
                tasks=[task],
                adapter=None,
                experiment_id="evo-test",
            )

            snapshot = _make_snapshot(
                prompt="Evolved prompt.",
                skills=[_make_skill(name="test-skill", body="Content.")],
                version="evo-1",
            )

            result = solve_fn(snapshot, batch_size=1)

            # Run failed, so result is empty
            assert result == []
            # But injection happened before the run
            assert len(injected_paths) == 1
            assert injected_paths[0] == instance_dir
            # And the file exists with the correct content
            assert (instance_dir / "system_prompt.md").exists()
            content = (instance_dir / "system_prompt.md").read_text()
            assert "Evolved prompt." in content
        finally:
            harbor_mod.inject_snapshot_into_workspace = original_inject

    def test_calls_trial_runner_with_correct_args(self, tmp_path: Path) -> None:
        """Verify that trial_runner.run() receives the expected keyword arguments."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        instance_dir = tmp_path / "task-a"
        instance_dir.mkdir()

        runner = StubTrialRunner(tmp_path)
        task = StubTask(instance_dir=instance_dir)

        solve_fn = make_harbor_solve_fn(
            trial_runner=runner,
            backend="stub-backend",
            tasks=[task],
            adapter="stub-adapter",
            experiment_id="exp-42",
            runtime_image="custom-image",
            adapter_revision="rev-abc",
        )

        snapshot = _make_snapshot(version="evo-2")
        records = solve_fn(snapshot, batch_size=1)

        assert len(records) == 1
        assert len(runner.calls) == 1

        call = runner.calls[0]
        assert call["trial_id"] == "evo-exp-42-c0-t0"
        assert call["experiment_id"] == "exp-42"
        assert call["task"] is task
        assert call["task_revision"] == "evolution"
        assert call["backend"] == "stub-backend"
        assert call["adapter"] == "stub-adapter"
        assert call["runtime_image"] == "custom-image"
        assert call["adapter_revision"] == "rev-abc"

    def test_trial_id_increments_across_calls(self, tmp_path: Path) -> None:
        """call_count in trial_id increments between separate solve() invocations."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        instance_dir = tmp_path / "task-b"
        instance_dir.mkdir()

        runner = StubTrialRunner(tmp_path)
        task = StubTask(instance_dir=instance_dir)

        solve_fn = make_harbor_solve_fn(
            trial_runner=runner,
            backend=None,
            tasks=[task],
            adapter=None,
            experiment_id="exp-99",
        )

        snapshot = _make_snapshot()
        solve_fn(snapshot, batch_size=1)
        solve_fn(snapshot, batch_size=1)

        assert runner.calls[0]["trial_id"] == "evo-exp-99-c0-t0"
        assert runner.calls[1]["trial_id"] == "evo-exp-99-c1-t0"

    def test_batch_size_limits_tasks_run(self, tmp_path: Path) -> None:
        """batch_size caps how many tasks are executed in one solve() call."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        tasks = []
        for i in range(5):
            d = tmp_path / f"task-{i}"
            d.mkdir()
            tasks.append(StubTask(instance_dir=d))

        runner = StubTrialRunner(tmp_path)
        solve_fn = make_harbor_solve_fn(
            trial_runner=runner,
            backend=None,
            tasks=tasks,
            adapter=None,
            experiment_id="exp-batch",
        )

        snapshot = _make_snapshot()
        records = solve_fn(snapshot, batch_size=3)

        assert len(records) == 3
        assert len(runner.calls) == 3

    def test_failed_tasks_are_skipped(self, tmp_path: Path) -> None:
        """Per-task exceptions are caught; other tasks in the batch still run."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        good_dir = tmp_path / "good-task"
        good_dir.mkdir()
        bad_dir = tmp_path / "bad-task"
        bad_dir.mkdir()

        call_order: list[str] = []

        class SelectiveRunner:
            """Fails for bad-task, succeeds for good-task."""

            def run(self, **kwargs: Any) -> StubTrialRecord:
                tid = kwargs["trial_id"]
                call_order.append(tid)
                if "t0" in tid:
                    raise RuntimeError("bad task exploded")
                return StubTrialRecord(trial_id=tid)

        bad_task = StubTask(instance_dir=bad_dir)
        good_task = StubTask(instance_dir=good_dir)

        solve_fn = make_harbor_solve_fn(
            trial_runner=SelectiveRunner(),
            backend=None,
            tasks=[bad_task, good_task],
            adapter=None,
            experiment_id="exp-partial",
        )

        snapshot = _make_snapshot()
        records = solve_fn(snapshot, batch_size=2)

        # Only the good task produced a record
        assert len(records) == 1
        assert records[0].trial_id == "evo-exp-partial-c0-t1"
        # Both tasks were attempted
        assert len(call_order) == 2

    def test_default_runtime_image(self, tmp_path: Path) -> None:
        """runtime_image defaults to 'evolution' when not specified."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        instance_dir = tmp_path / "task-default"
        instance_dir.mkdir()

        runner = StubTrialRunner(tmp_path)
        solve_fn = make_harbor_solve_fn(
            trial_runner=runner,
            backend=None,
            tasks=[StubTask(instance_dir=instance_dir)],
            adapter=None,
            experiment_id="exp-default",
        )

        solve_fn(_make_snapshot(), batch_size=1)

        assert runner.calls[0]["runtime_image"] == "evolution"

    def test_adapter_revision_none_by_default(self, tmp_path: Path) -> None:
        """adapter_revision defaults to None when not specified."""
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn

        instance_dir = tmp_path / "task-rev"
        instance_dir.mkdir()

        runner = StubTrialRunner(tmp_path)
        solve_fn = make_harbor_solve_fn(
            trial_runner=runner,
            backend=None,
            tasks=[StubTask(instance_dir=instance_dir)],
            adapter=None,
            experiment_id="exp-rev",
        )

        solve_fn(_make_snapshot(), batch_size=1)

        assert runner.calls[0]["adapter_revision"] is None
