# ABOUTME: Adapts one supported artifact-task experiment to Harbor dispatch and record import.
# ABOUTME: Keeps remote import separate from local live attempt workspaces and rejects unsupported recipes.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.artifact_tasks import AttemptRecipeSpec, SingleAttemptSpec
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import HarborWorkflowResult, SynchronousHarborWorkflow
from aec_bench.harness.model_execution.llm_reviewer import ReviewerRunConfig
from aec_bench.harness.progress_tracker import WorkflowProgressSnapshot
from aec_bench.harness.scheduler import build_trial_plan
from aec_bench.harness.trial import PlannedTrial
from aec_bench.ledger.reader import read_trial_record
from aec_bench.tasks.instance import ResolvedTaskInstance


@dataclass
class HarborExperimentRuntime:
    workflow: SynchronousHarborWorkflow
    manifest: ExperimentManifest
    config_path: Path
    executor: HarborCommandExecutor | None = None
    progress_callback: Callable[[WorkflowProgressSnapshot], None] | None = None
    environment_binding: HarborEnvironmentBinding | None = None
    task_path_overrides: Mapping[str, Path] | None = None
    last_result: HarborWorkflowResult | None = field(default=None, init=False)

    def run_experiment(
        self,
        *,
        tasks: Sequence[ResolvedTaskInstance],
        trials: Sequence[PlannedTrial],
        recipe_spec: AttemptRecipeSpec,
        reviewer: ReviewerRunConfig | None,
        verify: bool,
    ) -> list[TrialRecord]:
        if not isinstance(recipe_spec, SingleAttemptSpec):
            raise ValueError(f"Harbor does not support attempt recipe: {recipe_spec.kind}")
        resolved_tasks = tuple(task.task for task in tasks)
        effective_manifest = self.manifest.model_copy(update={"disable_verification": not verify})
        expected_trials = build_trial_plan(effective_manifest, list(resolved_tasks))
        if list(trials) != expected_trials:
            raise ValueError("planned trials do not match the Harbor experiment manifest")
        overrides = {task.task.task_id: task.instance_dir.resolve() for task in tasks}
        overrides.update(self.task_path_overrides or {})
        result = self.workflow.run(
            manifest=effective_manifest,
            config_path=self.config_path,
            executor=self.executor,
            progress_callback=self.progress_callback,
            reviewer_config=reviewer,
            resolved_tasks=resolved_tasks,
            task_path_overrides=overrides,
            environment_binding=self.environment_binding,
        )
        self.last_result = result
        return [
            read_trial_record(path, ledger_root=self.workflow.ledger_root) for path in result.import_result.ledger_paths
        ]


__all__ = ("HarborExperimentRuntime",)
