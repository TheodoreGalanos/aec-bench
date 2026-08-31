# ABOUTME: Runs ordinary artifact-task attempts in isolated local workspaces.
# ABOUTME: Keeps one adapter execution separate from selection, verification, and persistence.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel

from aec_bench.adapters.base import Adapter, AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.canonical_refs import CanonicalRefSet, parse_canonical_refs
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
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
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trial_extensions import ArtifactReference, VerifierExecutionReceipt
from aec_bench.contracts.trial_record import (
    EvaluationStatus,
    ExecutionStatus,
    PlannedTrialBinding,
    TrialRecord,
)
from aec_bench.evaluation.normalisation import NormalisationResult, normalise_output
from aec_bench.evaluation.verifier_outcome import map_verifier_execution
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
from aec_bench.harness.artifact.recipes import (
    AttemptRecipe,
    AttemptRunner,
    best_of,
    build_attempt_recipe,
    self_select,
    single_attempt,
)
from aec_bench.harness.artifact.values import AttemptSelection, AttemptSelectionEvidence, TaskAttempt
from aec_bench.harness.compilation.task_snapshot import TaskSnapshotError, assert_task_snapshot_matches_directory
from aec_bench.harness.local_runtime import (
    cleanup_workspace,
    patch_workspace_paths,
    read_instruction,
    setup_workspace,
    stage_verifier_assets,
)
from aec_bench.harness.model_execution.llm_reviewer import ReviewerRunConfig, run_workspace_reviewer
from aec_bench.harness.trial_record_builder import build_trial_record
from aec_bench.harness.verifier_execution import (
    VERIFIER_PROTOCOL_VERSION,
    execute_verifier,
    localise_staged_verifier_paths,
)
from aec_bench.harness.workspace_evidence import (
    WorkspaceDelta,
    WorkspaceManifest,
    capture_workspace_manifest,
    compare_workspace_manifests,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.ledger.writer import (
    DuplicateAppendOnlyFileError,
    DuplicateTrialRecordError,
    materialize_trial_record,
    write_append_only_json_at,
    write_trial_record_at,
)
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.tasks.snapshot import build_task_snapshot_archive
from aec_bench.trajectory.writer import TrajectoryWriter
from aec_bench.trials import PlannedTrial

AdapterBuilder = Callable[..., Adapter]
_VERIFIER_RETRY_PROMPT = "verifier_retry_prompt.md"
_VERIFIER_RETRY_TARGET_REWARD = 1.0
_VERIFIER_RETRY_ARTIFACT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_VERIFIER_RETRY_EXCLUDED_PREFIXES = ("expected_", "input_", "prior_", "source_")


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
        request = self._build_request(task=task, trial=trial, workspace=workspace, instruction=instruction)
        adapter = self._build_adapter(trial=trial, workspace=workspace)
        started = time.monotonic()
        result = adapter.execute(request)
        elapsed_seconds = time.monotonic() - started

        output_path = resolve_workspace_path(workspace, task.task.verifier.expected_output_path)
        output_source = "adapter"
        if output_path.is_file() and output_path.read_text(encoding="utf-8", errors="replace").strip():
            output_source = "direct_write"
        elif result.raw_output_text:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.raw_output_text, encoding="utf-8")
            output_source = "raw_output"

        if self._normalise and output_path.is_file():
            refs = load_canonical_refs(task.instance_dir / "task.toml")
            if refs.refs:
                apply_normalisation(
                    output_path,
                    refs,
                    workspace / "normalisation_report.json",
                    committed_result=result,
                )
        validate_output_commit(
            result=result, output_path=output_path, expected_output_path=task.task.verifier.expected_output_path
        )
        _write_agent_result(
            workspace=workspace,
            requested_model=trial.agent.model,
            adapter_kind=trial.agent.adapter,
            result=result,
            output_source=output_source,
        )
        selector_visible_output = output_path.read_bytes() if output_path.is_file() else None
        output_reference = (
            ArtifactReference(
                kind="primary_output",
                path=request.output_path,
                sha256=hashlib.sha256(selector_visible_output).hexdigest(),
                media_type="application/octet-stream",
            )
            if selector_visible_output
            else None
        )
        return TaskAttempt(
            attempt_id=attempt_id,
            trial_id=trial.trial_id,
            parent_attempt_id=parent_attempt_id,
            workspace=workspace,
            request=request,
            result=result,
            elapsed_seconds=elapsed_seconds,
            selector_visible_output=selector_visible_output,
            output_reference=output_reference,
        )

    def _create_workspace(self, *, task: ResolvedTaskInstance, parent: TaskAttempt | None) -> Path:
        if self._work_root is not None:
            self._work_root.mkdir(parents=True, exist_ok=True)
        if parent is None:
            capture_workspace_manifest(task.instance_dir, include_checksums=False)
            workspace = Path(setup_workspace(str(task.instance_dir), work_root=self._work_root)).resolve()
            self._copy_agent_files(workspace)
            patch_workspace_paths(str(workspace))
            self._workspace_manifests[workspace] = capture_workspace_manifest(workspace)
            self._workspace_inherited_paths[workspace] = set()
            return workspace

        parent_base = self.base_workspace_manifest(parent.workspace)
        parent_snapshot = capture_workspace_manifest(parent.workspace)
        parent_delta = compare_workspace_manifests(parent_base, parent_snapshot)
        parent_roles: dict[str, Literal["task_input", "primary_output", "actor_output"]] = {
            str(item.relative_path): item.source_role for item in parent_base.files
        }
        parent_roles.update({str(item.relative_path): "actor_output" for item in parent_delta.changed_files})
        parent_manifest = capture_workspace_manifest(
            parent.workspace,
            source_roles=parent_roles,
            default_source_role="actor_output",
        )
        workspace = Path(tempfile.mkdtemp(prefix="aec-bench-local-", dir=self._work_root)).resolve()
        shutil.copytree(parent.workspace, workspace, dirs_exist_ok=True)
        shutil.rmtree(workspace / "tests", ignore_errors=True)
        shutil.rmtree(workspace / "logs" / "verifier", ignore_errors=True)
        patch_workspace_paths(str(workspace), source_workspace=str(parent.workspace))
        child_manifest = capture_workspace_manifest(
            workspace,
            source_roles=parent_roles,
            default_source_role="actor_output",
        )
        self._workspace_manifests[workspace] = child_manifest
        inherited_paths = self.inherited_workspace_paths(parent.workspace) | {
            str(item.relative_path) for item in parent_delta.changed_files
        }
        self._workspace_inherited_paths[workspace] = {
            str(item.relative_path)
            for item in child_manifest.files
            if item.source_role in {"actor_output", "primary_output"}
            and any(parent_item.relative_path == item.relative_path for parent_item in parent_manifest.files)
            and str(item.relative_path) in inherited_paths
        }
        return workspace

    def _copy_agent_files(self, workspace: Path) -> None:
        for logical_path, source in self._agent_files.items():
            destination = resolve_workspace_path(workspace, logical_path)
            if source.is_symlink():
                raise ValueError(f"agent configuration file must not be a symbolic link: {source}")
            if not source.is_file():
                raise FileNotFoundError(f"agent configuration file is missing: {source}")
            if source.stat().st_nlink != 1:
                raise ValueError(f"agent configuration file must not have shared inode state: {source}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _build_adapter(self, *, trial: PlannedTrial, workspace: Path) -> Adapter:
        builder = self._adapter_builder
        if builder is None:
            from aec_bench.adapters.local_registry import build_local_adapter

            builder = build_local_adapter
        trajectory_writer = TrajectoryWriter(path=str(workspace / "trajectory.jsonl"))
        return builder(
            adapter_kind=trial.agent.adapter,
            model_name=trial.agent.model,
            workspace=str(workspace),
            trajectory_writer=trajectory_writer,
            constitutional_model=self._constitutional_model,
        )

    def _build_request(
        self,
        *,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        workspace: Path,
        instruction: str | None,
    ) -> AdapterRequest:
        selected_instruction = instruction if instruction is not None else read_instruction(str(workspace))
        if not selected_instruction:
            raise ValueError("task workspace does not contain an instruction")
        system_prompt = trial.agent.system_prompt
        if trial.agent.system_prompt_file is not None:
            system_prompt = resolve_workspace_path(workspace, trial.agent.system_prompt_file).read_text(
                encoding="utf-8"
            )
        tools: list[ToolSpec] = []
        if trial.agent.adapter == "tool_loop":
            tools = [ToolSpec(name="bash", source="builtin", description="Execute a bash command in the workspace")]
        configuration = dict(trial.agent.parameters)
        timeout = trial.compute.timeout_override or task.task.timeout_seconds
        if trial.agent.adapter == "prime-agent":
            configuration["timeout_seconds"] = timeout
        elif trial.agent.adapter == "deepseek_harness":
            configuration["timeout_sec"] = timeout
        output_path = task.task.verifier.expected_output_path
        return AdapterRequest(
            instruction=selected_instruction,
            system_prompt=system_prompt,
            tools=tools,
            configuration=configuration,
            output_path=output_path,
            output_format="markdown" if Path(output_path).suffix.lower() == ".md" else "jsonl",
        )


def resolve_workspace_path(workspace: Path, configured_path: str) -> Path:
    """Resolve one configured artifact path below its attempt workspace."""

    path = Path(configured_path)
    if path.parts and path.parts[0] == "workspace":
        path = Path(*path.parts[1:])
    elif path.is_absolute() and path.parts[:2] == ("/", "workspace"):
        path = Path(*path.parts[2:])
    elif path.is_absolute() and path.parts[:2] == ("/", "logs"):
        path = Path(*path.parts[1:])
    elif path.is_absolute():
        raise ValueError("task output path must resolve inside the attempt workspace")
    candidate = (workspace / path).resolve()
    if candidate != workspace.resolve() and workspace.resolve() not in candidate.parents:
        raise ValueError("task output path must resolve inside the attempt workspace")
    return candidate


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


def load_canonical_refs(task_toml_path: Path) -> CanonicalRefSet:
    if not task_toml_path.exists():
        return CanonicalRefSet()
    import tomllib

    data = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
    return parse_canonical_refs(data.get("canonical_refs", {}))


def apply_normalisation(
    output_path: Path,
    refs: CanonicalRefSet,
    report_path: Path,
    *,
    committed_result: AdapterResult | None = None,
) -> NormalisationResult:
    text = output_path.read_text(encoding="utf-8")
    result = normalise_output(text, refs)
    if result.substitutions_count == 0:
        return result
    if committed_result is not None and committed_result.completion_commit is not None:
        raise ValueError("canonical-reference normalisation cannot change committed output bytes")
    output_path.write_text(result.normalised, encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "substitutions_count": result.substitutions_count,
                "audit_log": [
                    {
                        "matched_text": match.matched_text,
                        "canonical_value": match.canonical_value,
                        "distance": match.distance,
                        "count": match.count,
                    }
                    for match in result.audit_log
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def validate_output_commit(*, result: AdapterResult, output_path: Path, expected_output_path: str) -> None:
    attestation = result.completion_commit
    if attestation is None:
        return
    if attestation.output_path != expected_output_path:
        raise ValueError("output commit path does not match the task expected output path")
    content = output_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != attestation.output_sha256:
        raise ValueError("output commit SHA-256 does not match the attempt output")
    if len(content) != attestation.output_size_bytes:
        raise ValueError("output commit byte size does not match the attempt output")


def _write_agent_result(
    *,
    workspace: Path,
    requested_model: str,
    adapter_kind: str,
    result: AdapterResult,
    output_source: str,
) -> None:
    payload = {
        "status": result.agent_output.status.value,
        "model": requested_model,
        "resolved_model": result.resolved_model,
        "adapter": adapter_kind,
        "adapter_configuration": result.configuration_record,
        "model_calls": result.usage_model_calls,
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "cache_read_tokens": result.usage_cache_read_tokens,
        "cache_write_tokens": result.usage_cache_write_tokens,
        "turns_used": result.turns_used,
        "max_turns": result.max_turns,
        "failure_kind": result.failure_kind.value if result.failure_kind is not None else None,
        "provider_error": result.provider_error,
        "output_source": output_source,
    }
    (workspace / "agent_result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
            final_manifest = _capture_final_workspace_manifest(
                representative.workspace, base_manifest, output_relative_path
            )
            return _build_failed_materialized_record(
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
                workspace_delta=compare_workspace_manifests(base_manifest, final_manifest),
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
        final_manifest = _capture_final_workspace_manifest(selected.workspace, base_manifest, output_relative_path)
        workspace_delta = compare_workspace_manifests(base_manifest, final_manifest)
        snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
        shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
        if selected_workspace_export is not None:
            _export_selected_workspace(snapshot_dir, selected_workspace_export)
        evaluation, verification_seconds, verifier_receipt, evaluation_status = _evaluate_selected_attempt(
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
            evaluation = _with_reviewer_summary(evaluation, selected.workspace)

        return _build_materialized_record(
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
                cleanup_workspace(workspace)
                runtime.release_workspace(workspace)


def _export_selected_workspace(snapshot: Path, destination: Path) -> None:
    """Atomically export the exact actor snapshot before verification changes the workspace."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(f"selected workspace export destination must be empty: {destination}")
        destination.rmdir()
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        shutil.copytree(snapshot, staging, dirs_exist_ok=True)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


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
    target_reward: float = _VERIFIER_RETRY_TARGET_REWARD,
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
        final_manifest = _capture_final_workspace_manifest(first.workspace, base_manifest, output_relative_path)
        (
            initial_evaluation,
            first_verification_seconds,
            first_verifier_receipt,
            first_evaluation_status,
        ) = _evaluate_selected_attempt(
            task=task,
            attempt=first,
            verify=True,
        )
        selected = first
        evaluation = initial_evaluation
        verification_seconds = first_verification_seconds

        if _should_run_verifier_feedback_retry(
            first.workspace,
            reward=initial_evaluation.reward,
            target_reward=target_reward,
        ):
            retry_instruction = _build_verifier_retry_instruction(
                workspace=first.workspace,
                output_path=resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path),
                base_instruction=first.request.instruction,
                reward=initial_evaluation.reward,
            )
            _prepare_verifier_retry_workspace(
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
            final_manifest = _capture_final_workspace_manifest(selected.workspace, base_manifest, output_relative_path)
            snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
            shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
            evaluation, second_verification_seconds, verifier_receipt, evaluation_status = _evaluate_selected_attempt(
                task=task,
                attempt=selected,
                verify=True,
            )
            verification_seconds = (first_verification_seconds or 0.0) + (second_verification_seconds or 0.0)
            _write_verifier_retry_summary(
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
            evaluation = _with_reviewer_summary(evaluation, selected.workspace)

        return _build_materialized_record(
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
            workspace_delta=compare_workspace_manifests(base_manifest, final_manifest),
            inherited_paths=runtime.inherited_workspace_paths(selected.workspace),
        )
    finally:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if not keep_workspace:
            for workspace in runtime.attempt_workspaces[first_workspace_index:]:
                cleanup_workspace(workspace)
                runtime.release_workspace(workspace)


def _build_materialized_record(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    selected: TaskAttempt,
    attempts: list[TaskAttempt],
    evaluation: EvaluationResult,
    started: float,
    verification_seconds: float | None,
    actor_snapshot: Path,
    evidence_workspace: Path,
    selection_evidence: AttemptSelectionEvidence | None = None,
    verifier_receipt: VerifierExecutionReceipt | None = None,
    evaluation_status: EvaluationStatus | None = None,
    planned_trial_binding: PlannedTrialBinding | None = None,
    planned_run_spec: ResolvedRunSpec | None = None,
    base_workspace_manifest: WorkspaceManifest | None = None,
    final_workspace_manifest: WorkspaceManifest | None = None,
    workspace_delta: WorkspaceDelta | None = None,
    inherited_paths: frozenset[str] = frozenset(),
) -> TrialRecord:
    output_path = resolve_workspace_path(actor_snapshot, task.task.verifier.expected_output_path)
    record = build_trial_record(
        trial_id=trial.trial_id,
        experiment_id=(
            trial.experiment_id if planned_run_spec is None else str(planned_run_spec.experiment_identity.id)
        ),
        task=task.task,
        task_revision=runtime.task_revision(task),
        request=selected.request,
        result=_aggregate_attempt_usage(
            selected=selected.result,
            attempts=attempts,
            selection_evidence=selection_evidence,
        ),
        evaluation=evaluation,
        total_seconds=time.monotonic() - started,
        agent_seconds=sum(attempt.elapsed_seconds for attempt in attempts),
        verification_seconds=verification_seconds,
        runtime_image="local",
        compute_backend=trial.compute.backend,
        raw_output_path=str(output_path) if output_path.is_file() else None,
        conversation_path=_existing_path(actor_snapshot / "conversation.jsonl"),
        trajectory_path=_existing_path(actor_snapshot / "trajectory.jsonl"),
        attempt=1 if planned_trial_binding is not None else trial.repetition,
        extensions=_trial_extensions(trial, selection_evidence, verifier_receipt),
        evaluation_status=evaluation_status,
        planned_trial_binding=planned_trial_binding,
        run_id=None if planned_run_spec is None else str(planned_run_spec.run_identity.id),
        dataset=None if planned_run_spec is None else planned_run_spec.dataset,
        expected_authorities=() if planned_run_spec is None else planned_run_spec.expected_authorities,
        evaluation_regime=None if planned_run_spec is None else planned_run_spec.evaluation_regime,
    )
    if base_workspace_manifest is None or final_workspace_manifest is None or workspace_delta is None:
        raise ValueError("artifact record requires workspace manifests")
    _attach_workspace_delta(
        record=record,
        workspace=actor_snapshot,
        base_manifest=base_workspace_manifest,
        final_manifest=final_workspace_manifest,
        delta=workspace_delta,
        primary_output_path=task.task.verifier.expected_output_path,
        inherited_paths=inherited_paths,
    )
    _attach_post_execution_files(record=record, workspace=evidence_workspace)
    return materialize_trial_record(artifact_root=runtime.artifact_root, record=record)


def _build_failed_materialized_record(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    attempts: list[TaskAttempt],
    selection: AttemptSelection,
    started: float,
    planned_trial_binding: PlannedTrialBinding | None = None,
    planned_run_spec: ResolvedRunSpec | None = None,
    base_workspace_manifest: WorkspaceManifest | None = None,
    final_workspace_manifest: WorkspaceManifest | None = None,
    workspace_delta: WorkspaceDelta | None = None,
    inherited_paths: frozenset[str] = frozenset(),
) -> TrialRecord:
    representative = attempts[0]
    record = build_trial_record(
        trial_id=trial.trial_id,
        experiment_id=(
            trial.experiment_id if planned_run_spec is None else str(planned_run_spec.experiment_identity.id)
        ),
        task=task.task,
        task_revision=runtime.task_revision(task),
        request=representative.request,
        result=_aggregate_attempt_usage(
            selected=representative.result,
            attempts=attempts,
            selection_evidence=selection.evidence,
        ),
        evaluation=None,
        total_seconds=time.monotonic() - started,
        agent_seconds=sum(attempt.elapsed_seconds for attempt in attempts),
        verification_seconds=None,
        runtime_image="local",
        compute_backend=trial.compute.backend,
        attempt=1 if planned_trial_binding is not None else trial.repetition,
        extensions=_trial_extensions(trial, selection.evidence),
        execution_status_override=ExecutionStatus.FAILED,
        # A failed execution can still contain useful actor files and workspace
        # manifests. Keep a TrialOutput so those artifacts remain referenced.
        include_output=True,
        planned_trial_binding=planned_trial_binding,
        run_id=None if planned_run_spec is None else str(planned_run_spec.run_identity.id),
        dataset=None if planned_run_spec is None else planned_run_spec.dataset,
        expected_authorities=() if planned_run_spec is None else planned_run_spec.expected_authorities,
        evaluation_regime=None if planned_run_spec is None else planned_run_spec.evaluation_regime,
    )
    if base_workspace_manifest is None or final_workspace_manifest is None or workspace_delta is None:
        raise ValueError("failed artifact record requires workspace manifests")
    snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-failed-selected-", dir=runtime.artifact_root.parent))
    try:
        shutil.copytree(representative.workspace, snapshot_dir, dirs_exist_ok=True)
        _attach_workspace_delta(
            record=record,
            workspace=snapshot_dir,
            base_manifest=base_workspace_manifest,
            final_manifest=final_workspace_manifest,
            delta=workspace_delta,
            primary_output_path=task.task.verifier.expected_output_path,
            inherited_paths=inherited_paths,
        )
        return materialize_trial_record(artifact_root=runtime.artifact_root, record=record)
    finally:
        shutil.rmtree(snapshot_dir, ignore_errors=True)


def _trial_extensions(
    trial: PlannedTrial,
    selection_evidence: AttemptSelectionEvidence | None,
    verifier_receipt: VerifierExecutionReceipt | None = None,
) -> dict[str, BaseModel]:
    extensions = dict(trial.extensions)
    if selection_evidence is not None:
        if "attempt_selection" in extensions:
            raise ValueError("planned trial extension conflicts with attempt selection evidence")
        extensions["attempt_selection"] = selection_evidence
    if verifier_receipt is not None:
        if "verifier_execution" in extensions:
            raise ValueError("planned trial extension conflicts with verifier execution evidence")
        extensions["verifier_execution"] = verifier_receipt
    return extensions


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _should_run_verifier_feedback_retry(
    workspace: Path,
    *,
    reward: float | None,
    target_reward: float,
) -> bool:
    return reward is not None and reward < target_reward and (workspace / _VERIFIER_RETRY_PROMPT).is_file()


def _build_verifier_retry_instruction(
    *, workspace: Path, output_path: Path, base_instruction: str, reward: float
) -> str:
    verifier_dir = workspace / "logs" / "verifier"
    retry_instruction = _read_optional_text(workspace / "verifier_retry_instruction.md").strip()
    governing_instruction = retry_instruction or base_instruction.strip()
    parts = [
        governing_instruction,
        "---",
        "# Verifier Feedback Retry",
        _read_optional_text(workspace / _VERIFIER_RETRY_PROMPT).strip(),
        f"Previous verifier reward: `{reward:.4f}`.",
        "The previous output was:",
        "```markdown",
        _read_optional_text(output_path).strip(),
        "```",
    ]
    feedback = _read_optional_text(verifier_dir / "feedback.md").strip()
    details = _read_optional_text(verifier_dir / "details.json").strip()
    if feedback:
        parts.extend(("The verifier feedback was:", "```markdown", feedback, "```"))
    if details:
        parts.extend(("The verifier detail scores were:", "```json", details, "```"))
    parts.append(
        "Repair the workspace now. You may overwrite the required output and any required side-effect files. "
        "Do not merely describe files that should be written."
    )
    return "\n\n".join(part for part in parts if part)


def _is_verifier_retry_side_effect(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix == ".json"
        and not path.name.startswith(_VERIFIER_RETRY_EXCLUDED_PREFIXES)
        and path.name.endswith(_VERIFIER_RETRY_ARTIFACT_SUFFIXES)
    )


def _archive_verifier_retry_attempt(workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = workspace / "logs" / "verifier" / "attempts" / attempt_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "agent_result.json",
        "trajectory.jsonl",
        "conversation.jsonl",
        "prime-events.jsonl",
        "prime-stderr.log",
        "prime-run.json",
        "logs/verifier/reward.json",
        "logs/verifier/details.json",
        "logs/verifier/feedback.md",
    ):
        source = workspace / relative
        if source.is_file():
            shutil.copy2(source, archive_dir / source.name)
    if output_path.is_file():
        shutil.copy2(output_path, archive_dir / output_path.name)
    prime_sessions = workspace / "logs" / "prime" / "sessions"
    if prime_sessions.is_dir():
        shutil.copytree(prime_sessions, archive_dir / "prime-sessions", dirs_exist_ok=True)
    for source in sorted(workspace.iterdir()):
        if _is_verifier_retry_side_effect(source):
            artifact_dir = archive_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, artifact_dir / source.name)
    return archive_dir


def _prepare_verifier_retry_workspace(*, workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = _archive_verifier_retry_attempt(workspace, output_path, attempt_name)
    output_path.unlink(missing_ok=True)
    return archive_dir


def _write_verifier_retry_summary(workspace: Path, payload: Mapping[str, object]) -> None:
    retry_path = workspace / "logs" / "verifier" / "retry.json"
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _evaluate_selected_attempt(
    *, task: ResolvedTaskInstance, attempt: TaskAttempt, verify: bool
) -> tuple[EvaluationResult, float | None, VerifierExecutionReceipt | None, EvaluationStatus | None]:
    output_path = resolve_workspace_path(attempt.workspace, task.task.verifier.expected_output_path)
    verifier_seconds = None
    verifier_receipt = None
    reward_payload: dict[str, Any] | None = None
    details_payload: dict[str, Any] | None = None
    if verify:
        stage_verifier_assets(task.instance_dir, attempt.workspace)
        started = time.monotonic()
        transform_version = localise_staged_verifier_paths(
            workspace=attempt.workspace,
            verifier_root=attempt.workspace / "tests",
        )
        execution = execute_verifier(
            verifier_path=attempt.workspace / task.task.verifier.script,
            workspace=attempt.workspace,
            output_path=output_path,
            reward_path=resolve_workspace_path(attempt.workspace, task.task.verifier.reward_path),
            details_path=(
                None
                if task.task.verifier.details_path is None
                else resolve_workspace_path(attempt.workspace, task.task.verifier.details_path)
            ),
            verifier_key=f"{task.task.task_id}/verifier",
            verifier_version=VERIFIER_PROTOCOL_VERSION,
            runtime_transform_version=transform_version,
        )
        verifier_seconds = time.monotonic() - started
        verifier_receipt = execution.receipt
        reward_payload = execution.reward_payload
        details_payload = execution.details_payload
    verifier_completed = verifier_receipt is not None and verifier_receipt.completed
    output_present = output_path.is_file()
    valid_output = attempt.status is AgentOutputStatus.COMPLETED and output_present
    reward = 0.0
    breakdown = details_payload
    errors: list[str] = []
    if verifier_completed and reward_payload is not None:
        reward = float(reward_payload["reward"])
    elif not verify:
        errors.append("verification was disabled")
    elif verifier_receipt is not None:
        errors.append(verifier_receipt.failure_message or "verifier did not complete successfully")
    else:
        errors.append("verifier did not run")
    if not valid_output and reward != 0.0:
        errors.append("verifier reward was ignored because the selected attempt has no valid output")
        reward = 0.0
    evaluation = EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=valid_output,
            schema_valid=valid_output,
            verifier_completed=verifier_completed,
            errors=errors,
        ),
        breakdown=breakdown,
    )
    if verifier_receipt is not None:
        mapped = map_verifier_execution(
            receipt=verifier_receipt,
            evaluation=evaluation,
            expected_verifier_key=f"{task.task.task_id}/verifier",
            expected_verifier_version=VERIFIER_PROTOCOL_VERSION,
        )
        return mapped.evaluation, verifier_seconds, verifier_receipt, mapped.status
    return evaluation, verifier_seconds, verifier_receipt, None


def _with_reviewer_summary(evaluation: EvaluationResult, workspace: Path) -> EvaluationResult:
    summary_path = workspace / "logs" / "reviewer" / "summary.json"
    if not summary_path.is_file():
        return evaluation
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    breakdown = dict(evaluation.breakdown or {})
    breakdown["llm_reviewer"] = payload
    return evaluation.model_copy(update={"breakdown": breakdown})


def _capture_final_workspace_manifest(
    workspace: Path,
    base_manifest: WorkspaceManifest,
    primary_output_path: str,
) -> WorkspaceManifest:
    """Keep original source roles while marking new actor files explicitly."""

    roles: dict[str, Literal["task_input", "primary_output", "actor_output"]] = {
        str(item.relative_path): item.source_role for item in base_manifest.files
    }
    primary_relative = resolve_workspace_path(workspace, primary_output_path).relative_to(workspace).as_posix()
    roles[str(primary_relative)] = "primary_output"
    return capture_workspace_manifest(
        workspace,
        source_roles=roles,
        default_source_role="actor_output",
        bytes_copied=0,
    )


def _attach_workspace_delta(
    *,
    record: TrialRecord,
    workspace: Path,
    base_manifest: WorkspaceManifest,
    final_manifest: WorkspaceManifest,
    delta: WorkspaceDelta,
    primary_output_path: str,
    inherited_paths: frozenset[str] = frozenset(),
) -> None:
    """Retain declared outputs and meaningful actor changes, not unchanged inputs."""

    named_paths = {
        Path(value).resolve() for value, _media, _logical in record.pending_artifacts.values() if Path(value).is_file()
    }
    primary_relative = resolve_workspace_path(workspace, primary_output_path).relative_to(workspace).as_posix()
    retained_paths = {str(item.relative_path) for item in delta.changed_files}
    retained_paths.add(primary_relative)
    retained_paths.update(inherited_paths)
    for item in final_manifest.files:
        if item.file_type != "file" or str(item.relative_path) not in retained_paths:
            continue
        path = workspace / item.relative_path
        if path.resolve() in named_paths or item.size_bytes == 0:
            continue
        record.attach_artifact(
            f"output:workspace:{item.relative_path}",
            path,
            media_type="application/octet-stream",
            logical_path=item.relative_path,
            expected_sha256=item.sha256,
        )

    attached_bytes = sum(
        item.size_bytes
        for item in final_manifest.files
        if item.file_type == "file" and str(item.relative_path) in retained_paths and item.size_bytes > 0
    )
    final_manifest = final_manifest.model_copy(update={"bytes_attached": attached_bytes})
    manifest_dir = workspace / ".workspace-manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    files: tuple[tuple[str, BaseModel], ...] = (
        ("base.json", base_manifest),
        ("final.json", final_manifest),
        ("delta.json", delta),
    )
    for name, value in files:
        path = manifest_dir / name
        path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")
        record.attach_artifact(
            f"output:workspace-manifest:{name.removesuffix('.json')}",
            path,
            media_type="application/json",
            logical_path=f"workspace/{name}",
        )


def _attach_post_execution_files(*, record: TrialRecord, workspace: Path) -> None:
    for root in (workspace / "logs" / "verifier", workspace / "logs" / "reviewer"):
        if not root.is_dir():
            continue
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            if path.stat().st_size == 0:
                continue
            relative = path.relative_to(workspace).as_posix()
            record.attach_artifact(
                f"output:evidence:{relative}",
                path,
                media_type="application/octet-stream",
                logical_path=relative,
            )


def _existing_path(path: Path) -> str | None:
    return str(path) if path.is_file() else None


def _aggregate_attempt_usage(
    *,
    selected: AdapterResult,
    attempts: list[TaskAttempt],
    selection_evidence: AttemptSelectionEvidence | None = None,
) -> AdapterResult:
    usage_fields = (
        "usage_model_calls",
        "usage_input_tokens",
        "usage_output_tokens",
        "usage_cache_read_tokens",
        "usage_cache_write_tokens",
        "usage_advisor_calls",
        "usage_advisor_input_tokens",
        "usage_advisor_output_tokens",
    )
    updates: dict[str, int | None] = {}
    selector_usage = None if selection_evidence is None else selection_evidence.selector
    for field_name in usage_fields:
        values = [getattr(attempt.result, field_name) for attempt in attempts]
        selector_field = {
            "usage_model_calls": "model_calls",
            "usage_input_tokens": "input_tokens",
            "usage_output_tokens": "output_tokens",
            "usage_cache_read_tokens": "cache_read_tokens",
            "usage_cache_write_tokens": "cache_write_tokens",
        }.get(field_name)
        selector_value = (
            0 if selector_usage is None or selector_field is None else getattr(selector_usage, selector_field)
        )
        updates[field_name] = (
            None
            if all(value is None for value in values) and selector_value == 0
            else sum(value or 0 for value in values) + selector_value
        )
    adapter_replace = cast(Callable[..., AdapterResult], replace)
    return adapter_replace(selected, **updates)


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
