# ABOUTME: Runs ordinary artifact-task attempts in isolated local workspaces.
# ABOUTME: Keeps one adapter execution separate from selection, verification, and persistence.

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from aec_bench.adapters.base import Adapter, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.identity import (
    EntityIdentity,
    EntityKey,
    EntityKind,
    PortableRelativePath,
    new_entity_id,
    validate_uuidv7,
)
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import AttemptRecipe as CanonicalAttemptRecipe
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, RunPlan
from aec_bench.contracts.run_plan import PlannedTrial as CanonicalPlannedTrial
from aec_bench.contracts.run_plan import SingleAttemptRecipe as CanonicalSingleAttemptRecipe
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt
from aec_bench.contracts.trial_record import (
    ExecutionStatus,
    PlannedTrialBinding,
    TrialRecord,
)
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    FailureKind,
    FinalizationState,
    ReconciliationState,
    TrialFinalization,
    WorkerOutcome,
)
from aec_bench.execution.operational import AttemptRecord, OperationalStore, WorkItemRecord
from aec_bench.harness.artifact.execution import execute_attempt
from aec_bench.harness.artifact.recipes import (
    AttemptRecipe,
    AttemptRunner,
    best_of,
    build_attempt_recipe,
    self_select,
    single_attempt,
)
from aec_bench.harness.artifact.recording import (
    build_failed_materialized_record,
    build_materialized_record,
)
from aec_bench.harness.artifact.values import AttemptSelection, AttemptSelectionEvidence, TaskAttempt
from aec_bench.harness.artifact.verification import (
    DEFAULT_VERIFIER_RETRY_TARGET_REWARD,
    build_verifier_retry_instruction,
    evaluate_selected_attempt,
    prepare_verifier_retry_workspace,
    should_run_verifier_feedback_retry,
    with_reviewer_summary,
    write_verifier_retry_summary,
)
from aec_bench.harness.artifact.workspace_port import (
    capture_final_workspace_manifest,
    dispose_workspace,
    export_selected_workspace,
    fork_attempt_workspace,
    materialize_base_workspace,
    resolve_workspace_path,
)
from aec_bench.harness.artifact.workspace_port import (
    workspace_delta as build_workspace_delta,
)
from aec_bench.harness.compilation.task_snapshot import TaskSnapshotError, assert_task_snapshot_matches_directory
from aec_bench.harness.model_execution.llm_reviewer import ReviewerRunConfig, run_workspace_reviewer
from aec_bench.harness.workspace_evidence import WorkspaceManifest
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.ledger.writer import (
    DuplicateAppendOnlyFileError,
    DuplicateTrialRecordError,
    write_append_only_json_at,
    write_trial_record_at,
)
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.tasks.snapshot import build_task_snapshot_archive
from aec_bench.trials import PlannedTrial

AdapterBuilder = Callable[..., Adapter]


class ImportedExperimentRuntime(Protocol):
    def run_experiment(
        self,
        *,
        tasks: Sequence[ResolvedTaskInstance],
        trials: Sequence[PlannedTrial],
        recipe_spec: CanonicalAttemptRecipe,
        reviewer: ReviewerRunConfig | None,
        verify: bool,
    ) -> list[TrialRecord]: ...


class LocalTaskRuntime:
    """Execute exactly one local adapter call in an isolated workspace."""

    def __init__(
        self,
        *,
        work_root: Path | None = None,
        artifact_root: Path | None = None,
        adapter_builder: AdapterBuilder | None = None,
        constitutional_model: str | None = None,
        normalise: bool = True,
        agent_files: Mapping[str, Path] | None = None,
    ) -> None:
        self._work_root = work_root
        self._adapter_builder = adapter_builder
        self._constitutional_model = constitutional_model
        self._normalise = normalise
        self._agent_files = dict(agent_files or {})
        self._artifact_root = artifact_root or (
            (work_root / "artifacts")
            if work_root is not None
            else Path(tempfile.mkdtemp(prefix="aec-bench-artifacts-"))
        )
        self._artifact_root.parent.mkdir(parents=True, exist_ok=True)
        self._attempt_workspaces: list[Path] = []
        self._task_revisions: dict[Path, str] = {}
        self._workspace_manifests: dict[Path, WorkspaceManifest] = {}
        self._workspace_inherited_paths: dict[Path, set[str]] = {}

    @property
    def artifact_root(self) -> Path:
        return self._artifact_root

    @property
    def attempt_workspaces(self) -> tuple[Path, ...]:
        return tuple(self._attempt_workspaces)

    def task_revision(self, task: ResolvedTaskInstance) -> str:
        """Resolve one task revision once for all trials that use this runtime."""
        source = task.instance_dir.resolve()
        revision = self._task_revisions.get(source)
        if revision is None:
            revision = hashlib.sha256(build_task_snapshot_archive(source)).hexdigest()
            self._task_revisions[source] = revision
        return revision

    def base_workspace_manifest(self, workspace: Path) -> WorkspaceManifest:
        """Return the actor-visible manifest captured before execution."""

        try:
            return self._workspace_manifests[workspace]
        except KeyError as error:
            raise RuntimeError(f"workspace has no captured base manifest: {workspace}") from error

    def inherited_workspace_paths(self, workspace: Path) -> frozenset[str]:
        """Return actor files inherited from a parent attempt that must remain retained."""

        return frozenset(self._workspace_inherited_paths.get(workspace, set()))

    def release_workspace(self, workspace: Path) -> None:
        """Release manifest bookkeeping after an attempt workspace is removed."""

        self._workspace_manifests.pop(workspace, None)
        self._workspace_inherited_paths.pop(workspace, None)

    def run_once(
        self,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt:
        if trial.task_id != task.task.task_id:
            raise ValueError("planned trial task_id does not match the resolved task")
        if parent is not None and parent.trial_id != trial.trial_id:
            raise ValueError("parent attempt belongs to another trial")

        workspace = self._create_workspace(task=task, parent=parent)
        self._attempt_workspaces.append(workspace)
        return self._execute_in_workspace(
            task=task,
            trial=trial,
            workspace=workspace,
            attempt_id=attempt_id,
            parent_attempt_id=None if parent is None else parent.attempt_id,
            instruction=instruction,
        )

    def _run_again(
        self,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        *,
        attempt_id: str,
        parent: TaskAttempt,
        instruction: str,
    ) -> TaskAttempt:
        """Run one explicit reward-aware continuation in the parent's isolated workspace."""
        if parent.trial_id != trial.trial_id:
            raise ValueError("parent attempt belongs to another trial")
        return self._execute_in_workspace(
            task=task,
            trial=trial,
            workspace=parent.workspace,
            attempt_id=attempt_id,
            parent_attempt_id=parent.attempt_id,
            instruction=instruction,
        )

    def _execute_in_workspace(
        self,
        *,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        workspace: Path,
        attempt_id: str,
        parent_attempt_id: str | None,
        instruction: str | None,
    ) -> TaskAttempt:
        return execute_attempt(
            task=task,
            trial=trial,
            workspace=workspace,
            attempt_id=attempt_id,
            parent_attempt_id=parent_attempt_id,
            instruction=instruction,
            adapter_builder=self._adapter_builder,
            constitutional_model=self._constitutional_model,
            normalise=self._normalise,
        )

    def _create_workspace(self, *, task: ResolvedTaskInstance, parent: TaskAttempt | None) -> Path:
        if self._work_root is not None:
            self._work_root.mkdir(parents=True, exist_ok=True)
        if parent is None:
            workspace, manifest = materialize_base_workspace(
                task,
                work_root=self._work_root,
                agent_files=self._agent_files,
            )
            self._workspace_manifests[workspace] = manifest
            self._workspace_inherited_paths[workspace] = set()
            return workspace

        parent_base = self.base_workspace_manifest(parent.workspace)
        workspace, child_manifest, inherited = fork_attempt_workspace(
            parent.workspace,
            base_manifest=parent_base,
            inherited_paths=self.inherited_workspace_paths(parent.workspace),
            work_root=self._work_root,
        )
        self._workspace_manifests[workspace] = child_manifest
        self._workspace_inherited_paths[workspace] = set(inherited)
        return workspace


class ArtifactTrialAdapterError(RuntimeError):
    """Raised when a scheduled artifact trial cannot be bound or finalized safely."""


@dataclass(frozen=True, slots=True)
class ArtifactTrialExecution:
    """Portable result returned after one scheduler-owned artifact execution."""

    record: TrialRecord
    receipts: tuple[AttemptReceipt, ...]
    finalization: TrialFinalization

    @property
    def outcome(self) -> WorkerOutcome:
        return WorkerOutcome(
            terminal_state="succeeded" if self.record.execution_status is ExecutionStatus.COMPLETED else "failed",
            receipts=self.receipts,
            finalization=self.finalization,
        )


@dataclass
class _CandidateState:
    attempt: AttemptRecord
    submission_id: str
    started: datetime
    task_attempt: TaskAttempt | None = None
    failure_message: str | None = None
    output_references: tuple[ArtifactRef, ...] = ()


class ArtifactTrialAdapter:
    """Run one exact artifact trial through the existing local task runtime."""

    def __init__(
        self,
        *,
        evidence_store: EvidenceRunStore,
        operational_store: OperationalStore,
        plan: RunPlan,
        runtime: LocalTaskRuntime,
        tasks: Sequence[ResolvedTaskInstance],
        verify: bool = True,
        keep_workspaces: bool = False,
    ) -> None:
        self._evidence_store = evidence_store
        self._operational_store = operational_store
        self._plan = plan
        self._runtime = runtime
        self._tasks = self._index_tasks(tasks)
        self._verify = verify
        self._keep_workspaces = keep_workspaces

    def __call__(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> WorkerOutcome:
        """Execute one scheduler-dispatched work item and return its strict outcome."""

        return self.execute(work_item, attempt).outcome

    def worker(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> WorkerOutcome:
        """Return the strict scheduler outcome after one artifact execution."""

        return self(work_item, attempt)

    def execute(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> ArtifactTrialExecution:
        """Bind scheduler identities before invoking the existing artifact runtime."""

        stored = self._evidence_store.read_run(self._plan.run_identity)
        if stored.plan != self._plan:
            raise ArtifactTrialAdapterError("authoritative run plan does not match the persisted plan")
        trial = self._planned_trial(work_item)
        self._validate_attempt(work_item, attempt)
        task = self._tasks.get(trial.task_release.task_id)
        if task is None:
            raise ArtifactTrialAdapterError(
                f"planned artifact trial references an unresolved task: {trial.task_release.task_id}"
            )
        try:
            _validate_canonical_task_release(trial, task)
        except ValueError as error:
            raise ArtifactTrialAdapterError(str(error)) from error

        record_path = self._record_path(trial)
        finalization_path = self._finalization_path(trial)
        if record_path.exists() or finalization_path.exists():
            raise ArtifactTrialAdapterError(f"trial finalization already exists: {trial.trial_identity.id}")
        runtime_trial = _runtime_trial_for_planned_trial(trial, stored.spec)
        candidate_states: list[_CandidateState] = []
        recipe = self._bound_recipe(trial, work_item, attempt, candidate_states)
        try:
            record = run_trial(
                runtime=self._runtime,
                task=task,
                trial=runtime_trial,
                recipe=recipe,
                verify=self._verify,
                keep_workspaces=self._keep_workspaces,
                planned_trial_binding=_planned_trial_binding(trial, stored.spec),
                planned_run_spec=stored.spec,
                result_validator=_result_validator(trial),
            )
        except Exception as error:
            if candidate_states and candidate_states[-1].task_attempt is None:
                self._finish_candidate(candidate_states[-1], success=False, message=str(error))
            receipts = self._candidate_receipts(candidate_states, work_item, trial.agent_condition.identity)
            self._copy_candidate_artifacts(candidate_states, record_path.parent / "_artifacts")
            self._persist_receipts(receipts)
            raise
        self._copy_materialized_artifacts(record, record_path.parent / "_artifacts")
        selection_ref = next(
            (item.artifact for item in record.extension_refs if item.extension_kind == "attempt_selection"), None
        )
        selected_attempt_id = candidate_states[0].attempt.attempt_id
        verifier_receipt = None
        if selection_ref is not None:
            selection = AttemptSelectionEvidence.model_validate_json(
                ArtifactRepository(self._runtime.artifact_root).read_bytes(selection_ref)
            )
            if selection.selected_index is not None:
                selected_attempt_id = candidate_states[selection.selected_index].attempt.attempt_id
        verifier_ref = next(
            (item.artifact for item in record.extension_refs if item.extension_kind == "verifier_execution"), None
        )
        if verifier_ref is not None:
            verifier_receipt = VerifierExecutionReceipt.model_validate_json(
                ArtifactRepository(self._runtime.artifact_root).read_bytes(verifier_ref)
            )
        receipts = self._candidate_receipts(
            candidate_states,
            work_item,
            trial.agent_condition.identity,
            selected_attempt_id=selected_attempt_id,
            verifier_receipt=verifier_receipt,
        )
        self._copy_candidate_artifacts(candidate_states, record_path.parent / "_artifacts")
        try:
            write_trial_record_at(path=record_path, record=record)
        except DuplicateTrialRecordError as error:
            raise ArtifactTrialAdapterError(f"trial finalization already exists: {trial.trial_identity.id}") from error
        finalization = TrialFinalization(
            finalization_id=new_entity_id(EntityKind.RECEIPT),
            trial_id=trial.trial_id,
            attempt_id=validate_uuidv7(selected_attempt_id),
            record_version=1,
            trial_record_ref=PortableRelativePath(record_path.relative_to(self._evidence_store.root).as_posix()),
            published_at=record.completed_at or record.started_at,
            state=FinalizationState.CURRENT,
        )
        self._persist_receipts(receipts)
        try:
            self._persist_finalization(finalization, finalization_path)
        except DuplicateAppendOnlyFileError as error:
            raise ArtifactTrialAdapterError(f"trial finalization already exists: {trial.trial_identity.id}") from error
        return ArtifactTrialExecution(
            record=record,
            receipts=receipts,
            finalization=finalization,
        )

    @staticmethod
    def _index_tasks(tasks: Sequence[ResolvedTaskInstance]) -> dict[str, ResolvedTaskInstance]:
        indexed: dict[str, ResolvedTaskInstance] = {}
        for task in tasks:
            task_id = task.task.task_id
            if task_id in indexed:
                raise ArtifactTrialAdapterError(f"resolved tasks must have unique task ids: {task_id}")
            indexed[task_id] = task
        return indexed

    def _planned_trial(self, work_item: WorkItemRecord) -> CanonicalPlannedTrial:
        if work_item.run_id != str(self._plan.run_id) or work_item.plan_id != str(self._plan.plan_id):
            raise ArtifactTrialAdapterError("work item does not belong to the authoritative run plan")
        matches = [trial for trial in self._plan.trials if str(trial.trial_id) == work_item.trial_id]
        if len(matches) != 1:
            raise ArtifactTrialAdapterError(f"work item does not identify one planned trial: {work_item.trial_id}")
        trial = matches[0]
        if trial.execution_family != "artifact":
            raise ArtifactTrialAdapterError("scheduled work item is not an artifact trial")
        if trial.ordinal != work_item.ordinal:
            raise ArtifactTrialAdapterError("work item ordinal does not match the authoritative trial")
        if work_item.backend != trial.compute.backend:
            raise ArtifactTrialAdapterError("work item backend does not match the authoritative trial")
        return trial

    @staticmethod
    def _validate_attempt(work_item: WorkItemRecord, attempt: AttemptRecord) -> None:
        if work_item.state != "running":
            raise ArtifactTrialAdapterError("artifact execution requires a running scheduler work item")
        if attempt.work_id != work_item.work_id or attempt.trial_id != work_item.trial_id:
            raise ArtifactTrialAdapterError("scheduler attempt does not match the work item")
        if attempt.run_id != work_item.run_id:
            raise ArtifactTrialAdapterError("scheduler attempt does not match the work item run")
        if attempt.lease_id is None:
            raise ArtifactTrialAdapterError("artifact execution requires a lease-bound attempt")
        if attempt.state != "running":
            raise ArtifactTrialAdapterError("artifact execution requires a running scheduler attempt")

    def _bound_recipe(
        self,
        trial: CanonicalPlannedTrial,
        work_item: WorkItemRecord,
        scheduler_attempt: AttemptRecord,
        candidate_states: list[_CandidateState],
    ) -> AttemptRecipe:
        base_recipe = _recipe_for_planned_trial(trial)
        candidate_count = (
            1 if isinstance(trial.attempt_recipe, CanonicalSingleAttemptRecipe) else trial.attempt_recipe.candidates
        )

        def recipe(run_once: AttemptRunner) -> AttemptSelection:
            call_count = 0

            def bound_run_once(
                *,
                attempt_id: str,
                parent: TaskAttempt | None = None,
                instruction: str | None = None,
            ) -> TaskAttempt:
                nonlocal call_count
                if call_count >= candidate_count:
                    raise ArtifactTrialAdapterError("artifact attempt recipe created more candidates than planned")
                candidate_index = call_count + 1
                if candidate_index == 1:
                    candidate_attempt = scheduler_attempt
                    if candidate_attempt.candidate_index != 1 or candidate_attempt.retry_number != 0:
                        raise ArtifactTrialAdapterError("scheduler attempt must be candidate 1 with retry number 0")
                else:
                    candidate_attempt = self._operational_store.create_attempt_for_lease(
                        work_item.work_id,
                        trial_id=work_item.trial_id,
                        lease_id=cast(str, scheduler_attempt.lease_id),
                        candidate_index=candidate_index,
                        retry_number=0,
                        now=scheduler_attempt.started_at or scheduler_attempt.created_at,
                    )
                    candidate_attempt = self._operational_store.transition_attempt(
                        candidate_attempt.attempt_id,
                        state="running",
                        now=scheduler_attempt.started_at or scheduler_attempt.created_at,
                    )
                submission_id = str(new_entity_id(EntityKind.BACKEND_SUBMISSION))
                self._operational_store.record_backend_submission(
                    submission_id,
                    attempt_id=candidate_attempt.attempt_id,
                    backend=work_item.backend,
                    now=scheduler_attempt.started_at or scheduler_attempt.created_at,
                )
                self._operational_store.transition_backend_submission(
                    submission_id,
                    state="running",
                    now=scheduler_attempt.started_at or scheduler_attempt.created_at,
                )
                candidate_states.append(
                    _CandidateState(
                        candidate_attempt,
                        submission_id,
                        candidate_attempt.started_at or scheduler_attempt.started_at or candidate_attempt.created_at,
                    )
                )
                call_count += 1
                try:
                    task_attempt = run_once(
                        attempt_id=candidate_attempt.attempt_id, parent=parent, instruction=instruction
                    )
                except Exception as error:
                    self._finish_candidate(candidate_states[-1], success=False, message=str(error))
                    raise
                candidate_states[-1].task_attempt = task_attempt
                candidate_states[-1].output_references = self._publish_candidate_output(task_attempt)
                self._finish_candidate(
                    candidate_states[-1],
                    success=task_attempt.status is AgentOutputStatus.COMPLETED,
                    message=(
                        "candidate output was not completed"
                        if task_attempt.status is not AgentOutputStatus.COMPLETED
                        else None
                    ),
                )
                return task_attempt

            selection = base_recipe(bound_run_once)
            if call_count != candidate_count:
                raise ArtifactTrialAdapterError("artifact attempt recipe did not create its declared candidates")
            return selection

        return recipe

    def _finish_candidate(self, candidate: _CandidateState, *, success: bool, message: str | None = None) -> None:
        candidate.failure_message = message
        self._operational_store.transition_attempt(
            candidate.attempt.attempt_id, state="succeeded" if success else "failed"
        )
        self._operational_store.transition_backend_submission(
            candidate.submission_id, state="completed" if success else "failed"
        )

    def _publish_candidate_output(self, task_attempt: TaskAttempt) -> tuple[ArtifactRef, ...]:
        output_path = resolve_workspace_path(task_attempt.workspace, task_attempt.request.output_path)
        if not output_path.is_file():
            return ()
        media_type = "text/markdown" if output_path.suffix.lower() == ".md" else "application/octet-stream"
        reference = ArtifactRepository(self._runtime.artifact_root).publish_bytes(
            data=output_path.read_bytes(), media_type=media_type
        )
        return (reference,)

    def _candidate_receipts(
        self,
        candidates: Sequence[_CandidateState],
        work_item: WorkItemRecord,
        condition: EntityIdentity,
        *,
        selected_attempt_id: str | None = None,
        verifier_receipt: VerifierExecutionReceipt | None = None,
    ) -> tuple[AttemptReceipt, ...]:
        receipts = []
        for candidate in candidates:
            task_attempt = candidate.task_attempt
            succeeded = task_attempt is not None and task_attempt.status is AgentOutputStatus.COMPLETED
            failure = (
                None
                if succeeded
                else FailureClassification(
                    failure_class=FailureClass.BENCHMARK,
                    kind=FailureKind.TASK_FAILURE,
                    message=candidate.failure_message or "candidate execution failed",
                )
            )
            finished = datetime.now(UTC)
            receipts.append(
                AttemptReceipt(
                    receipt_id=new_entity_id(EntityKind.RECEIPT),
                    receipt_key=EntityKey(f"{work_item.work_key}/candidate-{candidate.attempt.candidate_index}"),
                    attempt_id=validate_uuidv7(candidate.attempt.attempt_id),
                    backend=work_item.backend,
                    submission_id=validate_uuidv7(candidate.submission_id),
                    requested_condition=condition,
                    started_at=candidate.started,
                    finished_at=finished,
                    process_status=AttemptProcessStatus.SUCCEEDED if succeeded else AttemptProcessStatus.FAILED,
                    cancellation_status=CancellationStatus.NOT_REQUESTED,
                    resource_usage=AttemptResourceUsage(
                        wall_seconds=0.0 if task_attempt is None else max(0.0, task_attempt.elapsed_seconds)
                    ),
                    output_references=candidate.output_references,
                    verifier_receipt=verifier_receipt if candidate.attempt.attempt_id == selected_attempt_id else None,
                    failure=failure,
                    reconciliation_status=ReconciliationState.NOT_REQUIRED,
                )
            )
        return tuple(receipts)

    def _record_path(self, trial: CanonicalPlannedTrial) -> Path:
        directory = self._evidence_store.run_directory(self._plan.run_identity)
        return directory / "trial-records" / f"{trial.trial_id}.json"

    def _finalization_path(self, trial: CanonicalPlannedTrial) -> Path:
        return self._evidence_store.run_directory(self._plan.run_identity) / "finalizations" / f"{trial.trial_id}.json"

    def _persist_receipts(self, receipts: Sequence[AttemptReceipt]) -> None:
        root = self._evidence_store.run_directory(self._plan.run_identity) / "receipts"
        root.mkdir(parents=True, exist_ok=True)
        for receipt in receipts:
            path = root / f"{receipt.receipt_id}.json"
            try:
                write_append_only_json_at(path=path, payload=receipt.model_dump_json(indent=2) + "\n")
            except DuplicateAppendOnlyFileError as error:
                raise ArtifactTrialAdapterError(f"attempt receipt already exists: {receipt.receipt_id}") from error

    @staticmethod
    def _persist_finalization(finalization: TrialFinalization, path: Path) -> None:
        write_append_only_json_at(path=path, payload=finalization.model_dump_json(indent=2) + "\n")

    def _copy_materialized_artifacts(self, record: TrialRecord, target_root: Path) -> None:
        source = ArtifactRepository(self._runtime.artifact_root)
        target = ArtifactRepository(target_root)
        references: dict[str, ArtifactRef] = {}
        if record.output is not None:
            for item in record.output.artifacts:
                references[item.artifact.artifact_id] = item.artifact
        references.update({item.artifact.artifact_id: item.artifact for item in record.extension_refs})
        references.update({item.artifact.artifact_id: item.artifact for item in record.authority_evidence})
        if record.provider_evidence is not None:
            references[record.provider_evidence.artifact_id] = record.provider_evidence
        for reference in references.values():
            target.publish_bytes(data=source.read_bytes(reference), media_type=reference.media_type)

    def _copy_candidate_artifacts(self, candidates: Sequence[_CandidateState], target_root: Path) -> None:
        source = ArtifactRepository(self._runtime.artifact_root)
        target = ArtifactRepository(target_root)
        references = {
            reference.artifact_id: reference for candidate in candidates for reference in candidate.output_references
        }
        for reference in references.values():
            target.publish_bytes(data=source.read_bytes(reference), media_type=reference.media_type)


def run_trial(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    recipe: AttemptRecipe,
    reviewer: ReviewerRunConfig | None = None,
    verify: bool = True,
    keep_workspaces: bool = False,
    selected_workspace_export: Path | None = None,
    planned_trial_binding: PlannedTrialBinding | None = None,
    planned_run_spec: ResolvedRunSpec | None = None,
    result_validator: Callable[[AdapterResult], None] | None = None,
) -> TrialRecord:
    """Run one tracked recipe, verify its selection, and return durable trial evidence."""

    attempts: list[TaskAttempt] = []
    attempt_ids: set[str] = set()
    snapshot_dir: Path | None = None
    started = time.monotonic()
    first_workspace_index = len(runtime.attempt_workspaces)

    def tracked_run_once(
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt:
        if not attempt_id.strip():
            raise ValueError("attempt_id must not be blank")
        if attempt_id in attempt_ids:
            raise ValueError(f"attempt_id must be unique within a trial: {attempt_id}")
        if parent is not None and all(parent is not item for item in attempts):
            raise ValueError("parent attempt was not created by this trial runner")
        attempt_ids.add(attempt_id)
        attempt = runtime.run_once(
            task,
            trial,
            attempt_id=attempt_id,
            parent=parent,
            instruction=instruction,
        )
        if result_validator is not None:
            result_validator(attempt.result)
        attempts.append(attempt)
        return attempt

    try:
        selection = recipe(tracked_run_once)
        selected = selection.attempt
        if selected is None:
            if not attempts:
                raise ValueError(f"attempt recipe did not create or select an attempt: {selection.reason}")
            representative = attempts[0]
            output_relative_path = (
                resolve_workspace_path(representative.workspace, task.task.verifier.expected_output_path)
                .relative_to(representative.workspace)
                .as_posix()
            )
            base_manifest = runtime.base_workspace_manifest(representative.workspace)
            final_manifest = capture_final_workspace_manifest(
                representative.workspace, base_manifest, output_relative_path
            )
            return build_failed_materialized_record(
                runtime=runtime,
                task=task,
                trial=trial,
                attempts=attempts,
                selection=selection,
                started=started,
                planned_trial_binding=planned_trial_binding,
                planned_run_spec=planned_run_spec,
                base_workspace_manifest=base_manifest,
                final_workspace_manifest=final_manifest,
                workspace_delta=build_workspace_delta(base_manifest, final_manifest),
                inherited_paths=runtime.inherited_workspace_paths(representative.workspace),
            )
        if all(selected is not item for item in attempts):
            raise ValueError("attempt recipe selected an untracked attempt")

        output_relative_path = (
            resolve_workspace_path(selected.workspace, task.task.verifier.expected_output_path)
            .relative_to(selected.workspace)
            .as_posix()
        )
        base_manifest = runtime.base_workspace_manifest(selected.workspace)
        final_manifest = capture_final_workspace_manifest(selected.workspace, base_manifest, output_relative_path)
        workspace_delta = build_workspace_delta(base_manifest, final_manifest)
        snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
        shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
        if selected_workspace_export is not None:
            export_selected_workspace(snapshot_dir, selected_workspace_export)
        evaluation, verification_seconds, verifier_receipt, evaluation_status = evaluate_selected_attempt(
            task=task,
            attempt=selected,
            verify=verify,
        )
        if reviewer is not None and reviewer.enabled:
            review_result = run_workspace_reviewer(
                task_dir=task.instance_dir,
                workspace_dir=selected.workspace,
                config=reviewer,
            )
            if review_result.status != "complete" and reviewer.fail_on_error:
                raise RuntimeError(f"workspace reviewer failed: {review_result.status}")
            evaluation = with_reviewer_summary(evaluation, selected.workspace)

        return build_materialized_record(
            runtime=runtime,
            task=task,
            trial=trial,
            selected=selected,
            attempts=attempts,
            evaluation=evaluation,
            started=started,
            verification_seconds=verification_seconds,
            actor_snapshot=snapshot_dir,
            evidence_workspace=selected.workspace,
            selection_evidence=selection.evidence,
            verifier_receipt=verifier_receipt,
            evaluation_status=evaluation_status,
            planned_trial_binding=planned_trial_binding,
            planned_run_spec=planned_run_spec,
            base_workspace_manifest=base_manifest,
            final_workspace_manifest=final_manifest,
            workspace_delta=workspace_delta,
            inherited_paths=runtime.inherited_workspace_paths(selected.workspace),
        )
    finally:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if not keep_workspaces:
            for workspace in runtime.attempt_workspaces[first_workspace_index:]:
                dispose_workspace(workspace)
                runtime.release_workspace(workspace)


def run_experiment(
    *,
    runtime: LocalTaskRuntime | ImportedExperimentRuntime,
    tasks: Sequence[ResolvedTaskInstance],
    trials: Sequence[PlannedTrial],
    recipe: AttemptRecipe | CanonicalAttemptRecipe,
    reviewer: ReviewerRunConfig | None = None,
    verify: bool = True,
    keep_workspaces: bool = False,
) -> list[TrialRecord]:
    """Apply one attempt recipe directly to every planned artifact-task trial."""

    if not isinstance(runtime, LocalTaskRuntime):
        if not isinstance(recipe, CanonicalSingleAttemptRecipe | BestOfAttemptRecipe):
            raise TypeError("imported experiment runtimes require a canonical attempt recipe")
        return runtime.run_experiment(
            tasks=tasks,
            trials=trials,
            recipe_spec=recipe,
            reviewer=reviewer,
            verify=verify,
        )

    selected_recipe = (
        build_attempt_recipe(recipe)
        if isinstance(recipe, CanonicalSingleAttemptRecipe | BestOfAttemptRecipe)
        else recipe
    )

    tasks_by_id: dict[str, ResolvedTaskInstance] = {}
    for task in tasks:
        task_id = task.task.task_id
        if task_id in tasks_by_id:
            raise ValueError(f"resolved tasks must have unique task ids: {task_id}")
        tasks_by_id[task_id] = task
        runtime.task_revision(task)

    records: list[TrialRecord] = []
    for trial in trials:
        selected_task = tasks_by_id.get(trial.task_id)
        if selected_task is None:
            raise ValueError(f"planned trial references an unresolved task: {trial.task_id}")
        records.append(
            run_trial(
                runtime=runtime,
                task=selected_task,
                trial=trial,
                recipe=selected_recipe,
                reviewer=reviewer,
                verify=verify,
                keep_workspaces=keep_workspaces,
            )
        )
    return records


def run_persisted_artifact_plan(
    *,
    store: EvidenceRunStore,
    run_identity: EntityIdentity,
    runtime: LocalTaskRuntime,
    tasks: Sequence[ResolvedTaskInstance],
    started_at: datetime,
    reviewer: ReviewerRunConfig | None = None,
    verify: bool = True,
    keep_workspaces: bool = False,
) -> list[TrialRecord]:
    """Execute the artifact subset of one persisted ready plan in ordinal order."""

    stored = store.read_run(run_identity)
    plan = stored.plan
    if plan is None or stored.state.state != "ready":
        raise ValueError("a persisted ready plan is required for local artifact execution")

    tasks_by_id: dict[str, ResolvedTaskInstance] = {}
    for task in tasks:
        if task.task.task_id in tasks_by_id:
            raise ValueError(f"resolved tasks must have unique task ids: {task.task.task_id}")
        tasks_by_id[task.task.task_id] = task

    artifact_trials = tuple(trial for trial in plan.trials if trial.execution_family == "artifact")
    if not artifact_trials:
        raise ValueError("persisted plan contains no artifact-family trials")
    for trial in artifact_trials:
        selected_task = tasks_by_id.get(trial.task_release.task_id)
        if selected_task is None:
            raise ValueError(f"planned artifact trial references an unresolved task: {trial.task_release.task_id}")
        _validate_canonical_task_release(trial, selected_task)

    store.start_run(run_identity, started_at=started_at)
    records: list[TrialRecord] = []
    for trial in artifact_trials:
        task = tasks_by_id[trial.task_release.task_id]
        _validate_canonical_task_release(trial, task)
        runtime_trial = _runtime_trial_for_planned_trial(trial, stored.spec)
        records.append(
            run_trial(
                runtime=runtime,
                task=task,
                trial=runtime_trial,
                recipe=_recipe_for_planned_trial(trial),
                reviewer=reviewer,
                verify=verify,
                keep_workspaces=keep_workspaces,
                planned_trial_binding=_planned_trial_binding(trial, stored.spec),
                planned_run_spec=stored.spec,
                result_validator=_result_validator(trial),
            )
        )
    return sorted(records, key=lambda record: _trial_ordinal(record, artifact_trials))


def _validate_canonical_task_release(trial: CanonicalPlannedTrial, task: ResolvedTaskInstance) -> None:
    reference = trial.task_release
    if task.task.identity != reference.task_identity:
        raise ValueError(f"task identity does not match planned release: {reference.task_id}")
    try:
        assert_task_snapshot_matches_directory(reference=reference, task_dir=task.instance_dir)
    except TaskSnapshotError as error:
        raise ValueError(f"task release does not match planned snapshot: {reference.task_id}") from error


def _runtime_trial_for_planned_trial(trial: CanonicalPlannedTrial, spec: ResolvedRunSpec) -> PlannedTrial:
    from aec_bench.contracts.experiment_manifest import AgentConfig

    condition = trial.agent_condition
    return PlannedTrial(
        trial_id=str(trial.trial_identity.id),
        experiment_id=str(spec.experiment_identity.id),
        task_id=trial.task_release.task_id,
        agent=AgentConfig(
            name=str(condition.identity.key),
            adapter=condition.adapter,
            model=condition.model,
            client=condition.client,
            parameters=condition.parameters,
            system_prompt=condition.system_prompt,
        ),
        compute=trial.compute,
        repetition=trial.repetition,
        extensions={str(extension.extension_kind): extension.value for extension in trial.extensions},
    )


def _recipe_for_planned_trial(trial: CanonicalPlannedTrial) -> AttemptRecipe:
    if isinstance(trial.attempt_recipe, CanonicalSingleAttemptRecipe):
        return single_attempt()
    if isinstance(trial.attempt_recipe, BestOfAttemptRecipe):
        return best_of(k=trial.attempt_recipe.candidates, selector=self_select())
    raise TypeError(f"unsupported canonical attempt recipe: {type(trial.attempt_recipe).__name__}")


def _planned_trial_binding(trial: CanonicalPlannedTrial, spec: ResolvedRunSpec) -> PlannedTrialBinding:
    return PlannedTrialBinding(
        schema_version=2,
        run_identity=spec.run_identity,
        trial_identity=trial.trial_identity,
        task_release=trial.task_release,
        agent_condition_identity=trial.agent_condition.identity,
        ordinal=trial.ordinal,
        repetition=trial.repetition,
        compute=trial.compute,
        family_release=trial.family_release,
        execution_family=trial.execution_family,
        evaluation_profile=trial.evaluation_profile,
        expected_authorities=spec.expected_authorities,
    )


def _result_validator(trial: CanonicalPlannedTrial) -> Callable[[AdapterResult], None]:
    def validate(result: AdapterResult) -> None:
        if result.adapter_name != trial.agent_condition.adapter:
            raise ValueError("adapter result does not match the planned agent condition")
        if result.resolved_model != trial.agent_condition.model:
            raise ValueError("resolved model does not match the planned agent condition")

    return validate


def _trial_ordinal(record: TrialRecord, trials: Sequence[CanonicalPlannedTrial]) -> int:
    for trial in trials:
        if str(trial.trial_identity.id) == record.trial_id:
            return trial.ordinal
    raise ValueError(f"record does not match a planned artifact trial: {record.trial_id}")


def run_trial_with_verifier_feedback(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    reviewer: ReviewerRunConfig | None = None,
    keep_workspace: bool = False,
    target_reward: float = DEFAULT_VERIFIER_RETRY_TARGET_REWARD,
) -> TrialRecord:
    """Run one optional reward-aware second pass in the first attempt workspace."""

    attempts: list[TaskAttempt] = []
    snapshot_dir: Path | None = None
    started = time.monotonic()
    first_workspace_index = len(runtime.attempt_workspaces)
    try:
        first = runtime.run_once(task, trial, attempt_id="attempt-0")
        attempts.append(first)
        output_relative_path = (
            resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path)
            .relative_to(first.workspace)
            .as_posix()
        )
        base_manifest = runtime.base_workspace_manifest(first.workspace)
        final_manifest = capture_final_workspace_manifest(first.workspace, base_manifest, output_relative_path)
        (
            initial_evaluation,
            first_verification_seconds,
            first_verifier_receipt,
            first_evaluation_status,
        ) = evaluate_selected_attempt(
            task=task,
            attempt=first,
            verify=True,
        )
        selected = first
        evaluation = initial_evaluation
        verification_seconds = first_verification_seconds

        if should_run_verifier_feedback_retry(
            first.workspace,
            reward=initial_evaluation.reward,
            target_reward=target_reward,
        ):
            retry_instruction = build_verifier_retry_instruction(
                workspace=first.workspace,
                output_path=resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path),
                base_instruction=first.request.instruction,
                reward=initial_evaluation.reward,
            )
            prepare_verifier_retry_workspace(
                workspace=first.workspace,
                output_path=resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path),
                attempt_name="attempt-01",
            )
            shutil.rmtree(first.workspace / "tests", ignore_errors=True)
            for evidence_path in (
                task.task.verifier.reward_path,
                task.task.verifier.details_path,
                "logs/verifier/feedback.md",
            ):
                if evidence_path is None:
                    continue
                resolve_workspace_path(first.workspace, evidence_path).unlink(missing_ok=True)

            selected = runtime._run_again(
                task,
                trial,
                attempt_id="attempt-1",
                parent=first,
                instruction=retry_instruction,
            )
            attempts.append(selected)
            final_manifest = capture_final_workspace_manifest(selected.workspace, base_manifest, output_relative_path)
            snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
            shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
            evaluation, second_verification_seconds, verifier_receipt, evaluation_status = evaluate_selected_attempt(
                task=task,
                attempt=selected,
                verify=True,
            )
            verification_seconds = (first_verification_seconds or 0.0) + (second_verification_seconds or 0.0)
            write_verifier_retry_summary(
                selected.workspace,
                {
                    "performed": True,
                    "initial_reward": initial_evaluation.reward,
                    "final_reward": evaluation.reward,
                    "retry_agent_seconds": selected.elapsed_seconds,
                    "retry_verifier_seconds": second_verification_seconds,
                },
            )
        else:
            snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
            shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
            verifier_receipt = first_verifier_receipt
            evaluation_status = first_evaluation_status

        if reviewer is not None and reviewer.enabled:
            review_result = run_workspace_reviewer(
                task_dir=task.instance_dir,
                workspace_dir=selected.workspace,
                config=reviewer,
            )
            if review_result.status != "complete" and reviewer.fail_on_error:
                raise RuntimeError(f"workspace reviewer failed: {review_result.status}")
            evaluation = with_reviewer_summary(evaluation, selected.workspace)

        return build_materialized_record(
            runtime=runtime,
            task=task,
            trial=trial,
            selected=selected,
            attempts=attempts,
            evaluation=evaluation,
            started=started,
            verification_seconds=verification_seconds,
            actor_snapshot=snapshot_dir,
            evidence_workspace=selected.workspace,
            verifier_receipt=verifier_receipt,
            evaluation_status=evaluation_status,
            base_workspace_manifest=base_manifest,
            final_workspace_manifest=final_manifest,
            workspace_delta=build_workspace_delta(base_manifest, final_manifest),
            inherited_paths=runtime.inherited_workspace_paths(selected.workspace),
        )
    finally:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if not keep_workspace:
            for workspace in runtime.attempt_workspaces[first_workspace_index:]:
                dispose_workspace(workspace)
                runtime.release_workspace(workspace)


__all__ = (
    "ArtifactTrialAdapter",
    "ArtifactTrialAdapterError",
    "ArtifactTrialExecution",
    "ImportedExperimentRuntime",
    "LocalTaskRuntime",
    "run_experiment",
    "run_persisted_artifact_plan",
    "run_trial",
    "run_trial_with_verifier_feedback",
)
