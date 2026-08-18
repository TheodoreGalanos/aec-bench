# ABOUTME: Composed Harbor workflow for synchronous dispatch followed by ledger import.
# ABOUTME: Detects the produced Harbor job directory and imports TrialRecords after run completion.

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.experiment_runner import (
    ExperimentImportResult,
    HarborImportExperimentRunner,
)
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
    HarborDispatchResult,
    HarborExperimentDispatcher,
)
from aec_bench.harness.model_execution.llm_reviewer import (
    ReviewerJobResult,
    ReviewerRunConfig,
    reviewer_config_from_manifest,
    run_harbor_job_reviewer,
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
    reviewer_result: ReviewerJobResult | None = None


@dataclass(frozen=True)
class HarborDispatchOnlyResult:
    """Completed Harbor dispatch whose artifacts have not entered a TrialRecord ledger."""

    dispatch: HarborDispatchResult
    job_dir: Path
    resolved_tasks: tuple[TaskDefinition, ...]


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
        reviewer_config: ReviewerRunConfig | None = None,
        record_transform: Callable[[TrialRecord], TrialRecord] | None = None,
        resolved_tasks: tuple[TaskDefinition, ...] | None = None,
        task_path_overrides: Mapping[str, Path] | None = None,
        environment_binding: HarborEnvironmentBinding | None = None,
    ) -> HarborWorkflowResult:
        dispatch = self.dispatch_only(
            manifest=manifest,
            config_path=config_path,
            executor=executor,
            progress_callback=progress_callback,
            resolved_tasks=resolved_tasks,
            task_path_overrides=task_path_overrides,
            environment_binding=environment_binding,
        )
        return self.import_dispatched(
            manifest=manifest,
            dispatched=dispatch,
            progress_callback=progress_callback,
            reviewer_config=reviewer_config,
            record_transform=record_transform,
        )

    def import_dispatched(
        self,
        *,
        manifest: ExperimentManifest,
        dispatched: HarborDispatchOnlyResult,
        progress_callback: Callable[[WorkflowProgressSnapshot], None] | None = None,
        reviewer_config: ReviewerRunConfig | None = None,
        record_transform: Callable[[TrialRecord], TrialRecord] | None = None,
    ) -> HarborWorkflowResult:
        """Import one completed dispatch without repeating its backend effect."""

        selected_tasks = list(dispatched.resolved_tasks)
        job_dir = dispatched.job_dir
        effective_reviewer_config = reviewer_config or reviewer_config_from_manifest(manifest.reviewer)
        reviewer_result: ReviewerJobResult | None = None
        if effective_reviewer_config is not None and effective_reviewer_config.enabled:
            reviewer_result = run_harbor_job_reviewer(
                job_dir=job_dir,
                repo_root=self.repo_root,
                config=effective_reviewer_config,
            )

        import_runner = HarborImportExperimentRunner(
            repo_root=self.repo_root,
            tasks_root=self.tasks_root,
            ledger_root=self.ledger_root,
        )
        progress_tracker = WorkflowProgressTracker(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(selected_tasks),
            planned_trial_count=len(build_trial_plan(manifest, selected_tasks)),
        )
        self._emit(progress_callback, progress_tracker.import_started(job_dir=job_dir))
        import_result = import_runner.import_harbor_job(
            job_dir=job_dir,
            manifest=manifest,
            record_transform=record_transform,
            resolved_tasks=tuple(selected_tasks),
        )
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
            dispatch=dispatched.dispatch,
            job_dir=job_dir,
            import_result=import_result,
            reviewer_result=reviewer_result,
        )

    def dispatch_only(
        self,
        *,
        manifest: ExperimentManifest,
        config_path: Path,
        executor: HarborCommandExecutor | None = None,
        progress_callback: Callable[[WorkflowProgressSnapshot], None] | None = None,
        resolved_tasks: tuple[TaskDefinition, ...] | None = None,
        task_path_overrides: Mapping[str, Path] | None = None,
        environment_binding: HarborEnvironmentBinding | None = None,
    ) -> HarborDispatchOnlyResult:
        """Dispatch exact Harbor tasks and locate their job without importing trial evidence."""

        if resolved_tasks is None:
            registry = TaskRegistry(tasks_root=self.tasks_root)
            registry.reload()
            selected_tasks = select_manifest_tasks(
                registry.all(),
                manifest,
                project_root=self.project_root,
            )
        else:
            selected_tasks = list(resolved_tasks)
            if (
                select_manifest_tasks(
                    selected_tasks,
                    manifest,
                    project_root=self.project_root,
                )
                != selected_tasks
            ):
                raise HarborWorkflowError("prevalidated tasks do not satisfy the experiment manifest selector")
        planned_trials = build_trial_plan(manifest, selected_tasks)
        progress_tracker = WorkflowProgressTracker(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(selected_tasks),
            planned_trial_count=len(planned_trials),
        )
        before = self._job_dirs()
        self._emit(progress_callback, progress_tracker.dispatch_started())

        dispatcher = HarborExperimentDispatcher(
            project_root=self.project_root,
            jobs_dir=self.jobs_root,
        )
        dispatch_result = dispatcher.dispatch(
            manifest=manifest,
            tasks=selected_tasks,
            config_path=config_path,
            task_path_overrides=task_path_overrides,
            environment_binding=environment_binding,
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
        return HarborDispatchOnlyResult(
            dispatch=dispatch_result,
            job_dir=job_dir,
            resolved_tasks=tuple(selected_tasks),
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
        raise HarborWorkflowError(
            "Harbor dispatch produced multiple job directories without one exact experiment match"
        )

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
