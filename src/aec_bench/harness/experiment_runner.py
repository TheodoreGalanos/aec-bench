# ABOUTME: Manifest-aware Harbor import orchestration for the Python harness boundary.
# ABOUTME: Validates Harbor job artefacts against the planning contracts before ledger persistence.

from dataclasses import dataclass, field
from pathlib import Path

from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.harbor_import import import_harbor_job
from aec_bench.harness.progress_tracker import ImportProgressTracker
from aec_bench.harness.scheduler import build_trial_plan, select_manifest_tasks
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record
from aec_bench.tasks.registry import TaskRegistry


class ExperimentImportMismatchError(Exception):
    pass


@dataclass(frozen=True)
class ExperimentImportResult:
    experiment_id: str
    selected_task_count: int
    planned_trial_count: int
    discovered_trials: int
    imported_trials: int
    duplicate_trials: int
    invalid_trials: int
    unexpected_task_ids: list[str] = field(default_factory=list)
    unexpected_agents: list[str] = field(default_factory=list)
    unexpected_backends: list[str] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class HarborImportExperimentRunner:
    repo_root: Path
    tasks_root: Path
    ledger_root: Path

    def import_harbor_job(
        self,
        *,
        job_dir: Path,
        manifest: ExperimentManifest,
    ) -> ExperimentImportResult:
        selected_tasks = self._selected_tasks(manifest)
        selected_task_ids = {task.task_id for task in selected_tasks}
        planned_trials = build_trial_plan(manifest, selected_tasks)
        tracker = ImportProgressTracker(
            experiment_id=manifest.experiment_id,
            selected_task_count=len(selected_task_ids),
        )
        records = import_harbor_job(
            job_dir=job_dir,
            repo_root=self.repo_root,
            experiment_id=manifest.experiment_id,
            dataset_id=manifest.tasks.dataset,
        )
        unexpected_task_ids = sorted(
            {record.task.task_id for record in records if record.task.task_id not in selected_task_ids}
        )
        unexpected_agents = sorted(
            {record.agent.model for record in records if not self._agent_matches_manifest(record, manifest)}
        )
        unexpected_backends = sorted(
            {
                record.environment.compute_backend
                for record in records
                if record.environment.compute_backend != manifest.compute.backend
            }
        )
        if any(record.experiment_id != manifest.experiment_id for record in records):
            raise ExperimentImportMismatchError("Harbor job experiment_id does not match manifest experiment_id")
        if unexpected_task_ids:
            raise ExperimentImportMismatchError(
                f"unexpected task ids for manifest selector: {', '.join(unexpected_task_ids)}"
            )
        # Agent model names may differ from manifest — Azure deployment names
        # resolve to full model identifiers (e.g. "gpt-41-mini" → "gpt-4.1-mini-2025-04-14").
        # Since experiment_id already validates these records belong to our experiment,
        # unexpected agents are logged as warnings, not errors.
        if unexpected_agents:
            import logging

            logging.getLogger(__name__).warning(
                "Resolved model names differ from manifest: %s "
                "(deployment name vs full model identifier — expected with Azure OpenAI)",
                ", ".join(unexpected_agents),
            )
        if unexpected_backends:
            raise ExperimentImportMismatchError(
                f"unexpected compute backends for manifest: {', '.join(unexpected_backends)}"
            )

        output_paths: list[Path] = []
        for record in records:
            tracker.record_discovered()
            try:
                output_paths.append(write_trial_record(ledger_root=self.ledger_root, record=record))
            except DuplicateTrialRecordError:
                tracker.record_duplicate()
            else:
                tracker.record_imported()

        snapshot = tracker.snapshot()
        return ExperimentImportResult(
            experiment_id=snapshot.experiment_id,
            selected_task_count=snapshot.selected_task_count,
            planned_trial_count=len(planned_trials),
            discovered_trials=snapshot.discovered_trials,
            imported_trials=snapshot.imported_trials,
            duplicate_trials=snapshot.duplicate_trials,
            invalid_trials=snapshot.invalid_trials,
            unexpected_task_ids=unexpected_task_ids,
            unexpected_agents=unexpected_agents,
            unexpected_backends=unexpected_backends,
            output_paths=output_paths,
        )

    def _selected_tasks(self, manifest: ExperimentManifest) -> list[TaskDefinition]:
        registry = TaskRegistry(tasks_root=self.tasks_root)
        registry.reload()
        return select_manifest_tasks(registry.all(), manifest)

    def _agent_matches_manifest(
        self,
        record: TrialRecord,
        manifest: ExperimentManifest,
    ) -> bool:
        return any(
            record.agent.model == agent.model and self._adapter_matches_manifest(record=record, agent=agent)
            for agent in manifest.agents
        )

    def _adapter_matches_manifest(self, *, record: TrialRecord, agent: AgentConfig) -> bool:
        if record.agent.adapter == agent.adapter:
            return True
        configuration_import_path = record.agent.configuration.get("import_path")
        manifest_import_path = agent.parameters.get("harbor_import_path")
        return (
            isinstance(configuration_import_path, str)
            and isinstance(manifest_import_path, str)
            and configuration_import_path == manifest_import_path
        )
