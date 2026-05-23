# ABOUTME: Composed Harbor workflow for synchronous dispatch followed by ledger import.
# ABOUTME: Detects the produced Harbor job directory and imports TrialRecords after run completion.

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.harness.experiment_runner import (
    ExperimentImportResult,
    HarborImportExperimentRunner,
)
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
    HarborDispatchResult,
    HarborExperimentDispatcher,
)
from aec_bench.harness.progress_tracker import WorkflowProgressSnapshot, WorkflowProgressTracker
from aec_bench.harness.scheduler import build_trial_plan, select_manifest_tasks
from aec_bench.tasks.registry import TaskRegistry


class HarborWorkflowError(Exception):
    pass


@dataclass(frozen=True)
class HarborWorkflowResult:
    dispatch: HarborDispatchResult
    job_dir: Path
    import_result: ExperimentImportResult


@dataclass(frozen=True)
class SynchronousHarborWorkflow:
    project_root: Path
    repo_root: Path
    tasks_root: Path
    ledger_root: Path
    jobs_root: Path

    def run(
        self,
        *,
        manifest: ExperimentManifest,
        config_path: Path,
        executor: HarborCommandExecutor | None = None,
        progress_callback: Callable[[WorkflowProgressSnapshot], None] | None = None,
    ) -> HarborWorkflowResult:
        registry = TaskRegistry(tasks_root=self.tasks_root)
        registry.reload()
        selected_tasks = select_manifest_tasks(registry.all(), manifest)
        planned_trials = build_trial_plan(manifest, selected_tasks)
        progress_tracker = WorkflowProgressTracker(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(selected_tasks),
            planned_trial_count=len(planned_trials),
        )
        before = self._job_dirs()
        self._emit(progress_callback, progress_tracker.dispatch_started())

        dispatcher = HarborExperimentDispatcher(project_root=self.project_root)
        dispatch_result = dispatcher.dispatch(
            manifest=manifest,
            tasks=selected_tasks,
            config_path=config_path,
            executor=executor,
            execute=True,
        )
        self._emit(
            progress_callback,
            progress_tracker.dispatch_completed(exit_code=dispatch_result.exit_code),
        )
        if dispatch_result.exit_code not in {None, 0}:
            raise HarborWorkflowError(f"Harbor dispatch failed with exit code {dispatch_result.exit_code}")

        after = self._job_dirs()
        job_dir = self._resolve_job_dir(
            manifest=manifest,
            before=before,
            after=after,
        )
        self._emit(progress_callback, progress_tracker.job_dir_identified(job_dir=job_dir))

        import_runner = HarborImportExperimentRunner(
            repo_root=self.repo_root,
            tasks_root=self.tasks_root,
            ledger_root=self.ledger_root,
        )
        self._emit(progress_callback, progress_tracker.import_started(job_dir=job_dir))
        import_result = import_runner.import_harbor_job(job_dir=job_dir, manifest=manifest)
        self._emit(
            progress_callback,
            progress_tracker.import_completed(
                job_dir=job_dir,
                discovered_trials=import_result.discovered_trials,
                imported_trials=import_result.imported_trials,
                duplicate_trials=import_result.duplicate_trials,
                invalid_trials=import_result.invalid_trials,
            ),
        )
        return HarborWorkflowResult(
            dispatch=dispatch_result,
            job_dir=job_dir,
            import_result=import_result,
        )

    def _job_dirs(self) -> set[Path]:
        if not self.jobs_root.exists():
            return set()
        return {child.resolve() for child in self.jobs_root.iterdir() if child.is_dir()}

    def _resolve_job_dir(
        self,
        *,
        manifest: ExperimentManifest,
        before: set[Path],
        after: set[Path],
    ) -> Path:
        new_job_dirs = sorted(after - before)
        if not new_job_dirs:
            raise HarborWorkflowError("no new Harbor job directory found after dispatch")
        # If exactly one new dir, use it directly — Harbor generates its own
        # job ID (UUID) which won't match our experiment_id.
        if len(new_job_dirs) == 1:
            return new_job_dirs[0]
        # Multiple new dirs: try to match by result.json id as a tiebreaker
        matching_dirs = [job_dir for job_dir in new_job_dirs if self._job_result_id(job_dir) == manifest.experiment_id]
        if len(matching_dirs) == 1:
            return matching_dirs[0]
        # Fall back to most recent (last in sorted order = latest timestamp)
        return new_job_dirs[-1]

    def _job_result_id(self, job_dir: Path) -> str | None:
        result_path = job_dir / "result.json"
        if not result_path.exists():
            return None
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        job_id = payload.get("id")
        if isinstance(job_id, str) and job_id:
            return job_id
        return None

    def _emit(
        self,
        progress_callback: Callable[[WorkflowProgressSnapshot], None] | None,
        snapshot: WorkflowProgressSnapshot,
    ) -> None:
        if progress_callback is not None:
            progress_callback(snapshot)
