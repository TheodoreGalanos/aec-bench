# ABOUTME: Builds canonical artifact trial records from validated attempts and receipts.
# ABOUTME: Owns workspace evidence attachment, output retention, usage aggregation, and materialization.

from __future__ import annotations

import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, PlannedTrialBinding, TrialRecord
from aec_bench.harness.artifact.values import AttemptSelection, AttemptSelectionEvidence, TaskAttempt
from aec_bench.harness.artifact.workspace_port import resolve_workspace_path
from aec_bench.harness.trial_record_builder import build_trial_record
from aec_bench.harness.workspace_evidence import WorkspaceDelta, WorkspaceManifest
from aec_bench.ledger.writer import materialize_trial_record
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.trials import PlannedTrial


class RecordingRuntime(Protocol):
    @property
    def artifact_root(self) -> Path: ...

    def task_revision(self, task: ResolvedTaskInstance) -> str: ...


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
    for name, value in (("base.json", base_manifest), ("final.json", final_manifest), ("delta.json", delta)):
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


def build_materialized_record(
    *,
    runtime: RecordingRuntime,
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


def build_failed_materialized_record(
    *,
    runtime: RecordingRuntime,
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


__all__ = ("build_failed_materialized_record", "build_materialized_record")
