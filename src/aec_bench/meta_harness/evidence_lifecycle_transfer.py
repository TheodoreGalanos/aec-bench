# ABOUTME: Builds descriptive holdout-generalization summaries from immutable lifecycle records.
# ABOUTME: Enforces visibility, provenance integrity, and exact selected-condition identity without execution.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import NonNegativeInt, PositiveInt, ValidationError, field_validator, model_validator

from aec_bench.contracts.evaluation_result import ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import ArtifactReference, Completeness, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    canonical_evidence_lifecycle_spec_payload,
    evidence_request_catalog_payload,
    evidence_request_protocol_identity,
    validate_evidence_request_run_state,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleOperationCurrentSource,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    LifecycleExperimentManifest,
    LifecycleExperimentMetrics,
    lifecycle_experiment_metrics_payload,
)
from aec_bench.meta_harness.evidence_lifecycle_metrics import LifecycleSemanticMetrics
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    LifecycleVerificationResult,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    expected_evidence_request_run_artifact_paths,
    is_evidence_request_run_artifact_path,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_run_state,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.meta_harness.lifecycle_operation_snapshot import (
    expected_lifecycle_operation_run_artifact_paths,
    is_lifecycle_operation_run_artifact_path,
    validate_lifecycle_operation_snapshot,
    validate_lifecycle_operation_snapshot_payloads,
)
from aec_bench.meta_harness.lifecycle_operation_store import (
    resolve_lifecycle_operation_current_source,
    validate_lifecycle_operation_resolver_replay,
)
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceLifecycleSpec
from aec_bench.task_world_templates.lifecycles import lifecycle_package_variant


class LifecycleTransferRecordReference(StrictModel):
    experiment_id: NonEmptyStr
    trial_id: NonEmptyStr
    ledger_path: NonEmptyStr
    sha256: NonEmptyStr

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("ledger_path")
    @classmethod
    def validate_canonical_ledger_path(cls, value: str) -> str:
        if not _is_canonical_absolute_path(value):
            raise ValueError("lifecycle transfer ledger_path must be an absolute canonical path")
        return value


class LifecycleTransferCondition(StrictModel):
    model: NonEmptyStr
    adapter: NonEmptyStr
    runtime_dependency_sha256: NonEmptyStr
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    max_turns_per_session: PositiveInt

    @field_validator("runtime_dependency_sha256")
    @classmethod
    def validate_runtime_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("max_turns_per_session", mode="before")
    @classmethod
    def validate_strict_turn_limit(cls, value: object) -> object:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError("max_turns_per_session must be a positive integer")
        return value

    @model_validator(mode="after")
    def validate_mode_policy_pair(self) -> LifecycleTransferCondition:
        if (
            self.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
            and self.memory_visibility_policy is not LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("persistent_context execution requires persistent_context visibility")
        if (
            self.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT
            and self.memory_visibility_policy is LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("fresh_context execution cannot use persistent_context visibility")
        return self


class LifecycleTransferStudyDesign(StrictModel):
    interpretation: Literal["descriptive_holdout_generalization"]
    selection_basis: Literal["public_calibration"]
    causal_effects_supported: Literal[False]
    cross_run_learning_supported: Literal[False]


class LifecycleTransferEvaluationSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    study_design: LifecycleTransferStudyDesign
    selected_condition: LifecycleTransferCondition
    public_calibration_records: tuple[LifecycleTransferRecordReference, ...]
    holdout_target_records: tuple[LifecycleTransferRecordReference, ...]

    @field_validator("public_calibration_records", "holdout_target_records")
    @classmethod
    def validate_record_references(
        cls,
        value: tuple[LifecycleTransferRecordReference, ...],
    ) -> tuple[LifecycleTransferRecordReference, ...]:
        if not value:
            raise ValueError("lifecycle transfer record references must not be empty")
        if any(not _is_canonical_absolute_path(item.ledger_path) for item in value):
            raise ValueError("lifecycle transfer ledger_path must be an absolute canonical path")
        logical_identities = [_reference_logical_identity(item) for item in value]
        physical_identities = [_reference_physical_identity(item) for item in value]
        if len(logical_identities) != len(set(logical_identities)) or len(physical_identities) != len(
            set(physical_identities)
        ):
            raise ValueError("duplicate lifecycle transfer record reference")
        return tuple(sorted(value, key=_reference_sort_key))

    @model_validator(mode="after")
    def validate_disjoint_record_sets(self) -> LifecycleTransferEvaluationSpec:
        calibration_logical = {_reference_logical_identity(item) for item in self.public_calibration_records}
        target_logical = {_reference_logical_identity(item) for item in self.holdout_target_records}
        calibration_physical = {_reference_physical_identity(item) for item in self.public_calibration_records}
        target_physical = {_reference_physical_identity(item) for item in self.holdout_target_records}
        if calibration_logical & target_logical or calibration_physical & target_physical:
            raise ValueError("duplicate lifecycle transfer record reference across evidence sets")
        return self


class LifecycleTransferCalibrationResult(StrictModel):
    record: LifecycleTransferRecordReference
    status: Literal["supports_selected_condition", "not_supporting"]
    reasons: tuple[NonEmptyStr, ...] = ()


class LifecycleTransferTargetResult(StrictModel):
    record: LifecycleTransferRecordReference
    status: Literal["eligible", "not_evaluable"]
    reasons: tuple[NonEmptyStr, ...] = ()
    verifier_reward: float | None = None
    verifier_validity: ValidityCheck | None = None
    semantic_diagnostics: LifecycleSemanticMetrics | None = None
    diagnostic_reasons: tuple[NonEmptyStr, ...] = ()


class LifecycleTransferSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    evaluation_id: NonEmptyStr
    status: Literal["evaluated", "not_evaluable"]
    study_design: LifecycleTransferStudyDesign
    selected_condition: LifecycleTransferCondition
    calibration_record_count: NonNegativeInt
    calibration_support_count: NonNegativeInt
    target_record_count: NonNegativeInt
    eligible_target_count: NonNegativeInt
    mean_target_reward: float | None
    calibration_results: tuple[LifecycleTransferCalibrationResult, ...]
    target_results: tuple[LifecycleTransferTargetResult, ...]


@dataclass(frozen=True)
class _LoadedRecord:
    record: TrialRecord | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _LoadedArtifacts:
    content_by_path: dict[str, bytes]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _LifecycleSnapshot:
    package_content_by_relative: dict[str, bytes]
    run_content_by_relative: dict[str, bytes]
    lifecycle_variant: dict[str, object]


def build_lifecycle_transfer_evaluation(
    spec: LifecycleTransferEvaluationSpec,
) -> LifecycleTransferSummary:
    """Describe holdout performance under one condition supported by public calibration evidence."""
    spec = LifecycleTransferEvaluationSpec.model_validate(spec.model_dump(mode="json"))
    calibration_loaded = [(_reference, _load_record(_reference)) for _reference in spec.public_calibration_records]
    calibration_results: list[LifecycleTransferCalibrationResult] = []
    supporting_records: list[TrialRecord] = []
    calibration_packages: set[str] = set()
    for reference, loaded in calibration_loaded:
        reasons = list(loaded.reasons)
        if loaded.record is not None:
            provenance = loaded.record.lifecycle_provenance
            if not loaded.reasons and provenance is not None:
                calibration_packages.add(provenance.package_sha256)
            reasons.extend(_record_eligibility_reasons(loaded.record, expected_visibility=Visibility.PUBLIC))
            reasons.extend(_condition_mismatch_reasons(loaded.record, spec.selected_condition))
        normalized_reasons = _unique_reasons(reasons)
        if not normalized_reasons and loaded.record is not None:
            supporting_records.append(loaded.record)
        calibration_results.append(
            LifecycleTransferCalibrationResult(
                record=reference,
                status="supports_selected_condition" if not normalized_reasons else "not_supporting",
                reasons=normalized_reasons,
            )
        )

    target_results: list[LifecycleTransferTargetResult] = []
    eligible_rewards: list[float] = []
    for reference in spec.holdout_target_records:
        loaded = _load_record(reference)
        reasons = list(loaded.reasons)
        semantic_diagnostics: LifecycleSemanticMetrics | None = None
        diagnostic_reasons: tuple[str, ...] = ()
        if loaded.record is not None:
            reasons.extend(_record_eligibility_reasons(loaded.record, expected_visibility=Visibility.HOLDOUT))
            reasons.extend(_condition_mismatch_reasons(loaded.record, spec.selected_condition))
            if not supporting_records:
                reasons.append("no_public_calibration_support")
            provenance = loaded.record.lifecycle_provenance
            if provenance is not None and provenance.package_sha256 in calibration_packages:
                reasons.append("target_package_matches_calibration")
            semantic_diagnostics, diagnostic_reasons = _semantic_diagnostics(loaded.record)
        elif not supporting_records:
            reasons.append("no_public_calibration_support")
        normalized_reasons = _unique_reasons(reasons)
        eligible = not normalized_reasons and loaded.record is not None
        reward = loaded.record.evaluation.reward if eligible and loaded.record is not None else None
        if reward is not None:
            eligible_rewards.append(reward)
        target_results.append(
            LifecycleTransferTargetResult(
                record=reference,
                status="eligible" if eligible else "not_evaluable",
                reasons=normalized_reasons,
                verifier_reward=reward,
                verifier_validity=(
                    loaded.record.evaluation.validity if eligible and loaded.record is not None else None
                ),
                semantic_diagnostics=semantic_diagnostics if eligible else None,
                diagnostic_reasons=diagnostic_reasons,
            )
        )

    return LifecycleTransferSummary(
        evaluation_id=f"lifecycle-transfer-{_canonical_sha256(spec.model_dump(mode='json'))}",
        status="evaluated" if eligible_rewards else "not_evaluable",
        study_design=spec.study_design,
        selected_condition=spec.selected_condition,
        calibration_record_count=len(calibration_results),
        calibration_support_count=len(supporting_records),
        target_record_count=len(target_results),
        eligible_target_count=len(eligible_rewards),
        mean_target_reward=(sum(eligible_rewards) / len(eligible_rewards) if eligible_rewards else None),
        calibration_results=tuple(calibration_results),
        target_results=tuple(target_results),
    )


def _load_record(reference: LifecycleTransferRecordReference) -> _LoadedRecord:
    path = Path(reference.ledger_path)
    reasons: list[str] = []
    try:
        path = path.resolve()
    except OSError:
        return _LoadedRecord(record=None, reasons=("record_path_unresolvable",))
    if path.parent.name != reference.experiment_id or path.name != f"{reference.trial_id}.json":
        reasons.append("record_path_not_canonical")
    try:
        record_bytes = path.read_bytes()
    except FileNotFoundError:
        reasons.append("record_missing")
        return _LoadedRecord(record=None, reasons=_unique_reasons(reasons))
    except OSError:
        reasons.append("record_unreadable")
        return _LoadedRecord(record=None, reasons=_unique_reasons(reasons))
    if hashlib.sha256(record_bytes).hexdigest() != reference.sha256:
        reasons.append("record_sha256_mismatch")
        return _LoadedRecord(record=None, reasons=_unique_reasons(reasons))
    try:
        record = TrialRecord.model_validate_json(record_bytes)
    except (ValidationError, ValueError):
        reasons.append("record_invalid")
        return _LoadedRecord(record=None, reasons=_unique_reasons(reasons))
    if record.experiment_id != reference.experiment_id or record.trial_id != reference.trial_id:
        reasons.append("record_identity_mismatch")
    ledger_root = path.parent.parent
    loaded_artifacts = _load_artifacts(record, ledger_root=ledger_root)
    reasons.extend(loaded_artifacts.reasons)
    if not loaded_artifacts.reasons:
        reasons.extend(_snapshot_record_reasons(record, artifacts=loaded_artifacts.content_by_path))
    return _LoadedRecord(record=record, reasons=_unique_reasons(reasons))


def _load_artifacts(record: TrialRecord, *, ledger_root: Path) -> _LoadedArtifacts:
    artifacts = record.outputs.artifacts
    if not artifacts:
        return _LoadedArtifacts(content_by_path={}, reasons=("immutable_snapshot_missing",))
    reasons: list[str] = []
    content_by_path: dict[str, bytes] = {}
    seen: set[str] = set()
    root = ledger_root.resolve()
    for artifact in artifacts:
        if artifact.path in seen:
            reasons.append("duplicate_artifact_reference")
            continue
        seen.add(artifact.path)
        relative = Path(artifact.path)
        if relative.is_absolute() or ".." in relative.parts:
            reasons.append("artifact_path_escapes_ledger")
            continue
        try:
            path = (root / relative).resolve()
        except (OSError, ValueError):
            reasons.append("artifact_unresolvable")
            continue
        try:
            path.relative_to(root)
        except ValueError:
            reasons.append("artifact_path_escapes_ledger")
            continue
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            reasons.append("artifact_missing")
            continue
        except OSError:
            reasons.append("artifact_unreadable")
            continue
        if hashlib.sha256(content).hexdigest() != artifact.sha256:
            reasons.append("artifact_sha256_mismatch")
            continue
        content_by_path[artifact.path] = content
    return _LoadedArtifacts(content_by_path=content_by_path, reasons=_unique_reasons(reasons))


def _snapshot_record_reasons(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
) -> tuple[str, ...]:
    provenance = record.lifecycle_provenance
    execution = record.lifecycle_execution
    if provenance is None or execution is None:
        return ()
    verification_reference = _artifact_by_kind(record, "lifecycle_verification")
    metrics_reference = _artifact_by_kind(record, "lifecycle_metrics")
    state_reference = _artifact_by_kind(record, "lifecycle_state")
    lifecycle_spec_reference = _artifact_by_suffix(record, "/package/lifecycle.json")
    if verification_reference is None or state_reference is None or provenance.invocation_index is None:
        return ("snapshot_contract_missing",)
    try:
        manifest = _read_artifact_object(artifacts, provenance.invocation_manifest)
        invocation_index = _read_artifact_object(artifacts, provenance.invocation_index)
        verification = _read_artifact_object(artifacts, verification_reference)
        state = _read_artifact_object(artifacts, state_reference)
        if _v3_state_contains_evidence_request_fields(state):
            return ("snapshot_contract_invalid",)
        manifest = LifecycleExperimentManifest.model_validate(manifest).model_dump(mode="json")
        verification_result = LifecycleVerificationResult.model_validate(verification)
        state_result = EvidenceLifecycleRunState.model_validate(state)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EvidenceLifecycleError):
        return ("snapshot_contract_invalid",)

    metrics_result: LifecycleExperimentMetrics | None = None
    lifecycle_spec_result: EvidenceLifecycleSpec | None = None
    if state_result.schema_version in {"4", "5"}:
        if metrics_reference is None or lifecycle_spec_reference is None:
            return ("snapshot_contract_missing",)
        try:
            metrics = _read_artifact_object(artifacts, metrics_reference)
            lifecycle_spec = _read_artifact_object(artifacts, lifecycle_spec_reference)
            metrics_result = LifecycleExperimentMetrics.model_validate(metrics)
            lifecycle_spec_result = EvidenceLifecycleSpec.model_validate(lifecycle_spec)
            validate_evidence_request_run_state(state_result, lifecycle_spec_result)
            if state_result.schema_version == "5":
                validate_lifecycle_operation_run_state(state_result, lifecycle_spec_result)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EvidenceLifecycleError):
            return ("snapshot_contract_invalid",)

    lifecycle = manifest.get("lifecycle")
    repository = manifest.get("repository")
    environment = manifest.get("environment")
    verifier = manifest.get("verifier")
    model = manifest.get("model")
    execution_snapshot = manifest.get("execution")
    outputs = manifest.get("outputs")
    snapshot_sections = (lifecycle, repository, environment, verifier, model, execution_snapshot, outputs)
    if not all(isinstance(item, dict) for item in snapshot_sections):
        return ("snapshot_contract_invalid",)
    assert isinstance(lifecycle, dict)
    assert isinstance(repository, dict)
    assert isinstance(environment, dict)
    assert isinstance(verifier, dict)
    assert isinstance(model, dict)
    assert isinstance(execution_snapshot, dict)
    assert isinstance(outputs, dict)
    runtime = environment.get("runtime_provenance")
    variant = lifecycle.get("variant")
    declared_artifacts = outputs.get("artifacts")
    if not isinstance(runtime, dict) or not isinstance(variant, dict) or not isinstance(declared_artifacts, dict):
        return ("snapshot_contract_invalid",)
    lifecycle_snapshot: _LifecycleSnapshot | None = None
    if state_result.schema_version == "5":
        assert lifecycle_spec_result is not None
        try:
            lifecycle_snapshot = _validate_v5_snapshot_reconciliation(
                record,
                artifacts=artifacts,
                state=state_result,
                spec=lifecycle_spec_result,
                manifest=manifest,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EvidenceLifecycleError):
            return ("snapshot_contract_invalid",)
    manifest_sweep = manifest.get("sweep")
    index_sweep = invocation_index.get("sweep")
    if not isinstance(manifest_sweep, dict) or not isinstance(index_sweep, dict):
        return ("snapshot_contract_invalid",)
    if (
        invocation_index.get("manifest_sha256") != provenance.invocation_manifest.sha256
        or outputs.get("verification.json") != verification_reference.sha256
        or declared_artifacts.get("verification.json") != verification_reference.sha256
        or declared_artifacts.get("state.json") != state_reference.sha256
        or manifest_sweep != index_sweep
        or manifest_sweep.get("sweep_experiment_id") != record.experiment_id
        or manifest_sweep.get("planned_trial_id") != record.trial_id
    ):
        return ("snapshot_record_mismatch",)
    if metrics_reference is not None and (
        outputs.get("metrics.json") != metrics_reference.sha256
        or declared_artifacts.get("metrics.json") != metrics_reference.sha256
    ):
        return ("snapshot_record_mismatch",)
    try:
        runtime_distributions = _string_tuple(runtime.get("distributions"))
        resolved_models = tuple(sorted(_string_tuple(model.get("resolved_models"))))
        resolved_adapters = tuple(sorted(_string_tuple(model.get("resolved_adapters"))))
    except ValueError:
        return ("snapshot_contract_invalid",)
    snapshot_turn_limit = execution_snapshot.get("max_turns_per_session")
    snapshot_session_count = execution_snapshot.get("session_count")
    if not _is_strict_positive_int(snapshot_turn_limit) or not _is_non_negative_int(snapshot_session_count):
        return ("snapshot_contract_invalid",)
    if snapshot_session_count != len(execution.sessions):
        return ("snapshot_record_mismatch",)

    state_checkpoint_ids = {checkpoint.checkpoint_id for checkpoint in state_result.checkpoint_runs}
    session_checkpoint_ids = {
        checkpoint_id for session in execution.sessions for checkpoint_id in session.checkpoint_ids
    }
    if (
        verification_result.lifecycle_id != provenance.lifecycle_id
        or (verification_result.template_id is not None and verification_result.template_id != record.task.task_id)
        or state_result.lifecycle_id != provenance.lifecycle_id
        or state_result.world_id != provenance.world_id
        or state_result.lifecycle_spec_sha256 != provenance.spec_sha256
        or state_result.package_sha256 != provenance.package_sha256
        or state_checkpoint_ids != session_checkpoint_ids
    ):
        return ("snapshot_record_mismatch",)

    if state_result.schema_version in {"4", "5"}:
        assert lifecycle_spec_result is not None
        assert metrics_result is not None
        evidence_request_reasons = _evidence_request_snapshot_reasons(
            record,
            artifacts=artifacts,
            state=state_result,
            spec=lifecycle_spec_result,
            manifest=manifest,
            metrics=metrics_result,
            snapshot=lifecycle_snapshot,
        )
        if evidence_request_reasons:
            return evidence_request_reasons
    if state_result.schema_version == "5":
        assert lifecycle_spec_result is not None
        assert metrics_result is not None
        assert lifecycle_snapshot is not None
        operation_reasons = _lifecycle_operation_snapshot_reasons(
            record,
            artifacts=artifacts,
            state=state_result,
            spec=lifecycle_spec_result,
            manifest=manifest,
            metrics=metrics_result,
            snapshot=lifecycle_snapshot,
        )
        if operation_reasons:
            return operation_reasons

    output_structurally_valid = state_result.status.value == "complete"
    verifier_completed = verification_result.overall != "incomplete"
    expected_validity = ValidityCheck(
        output_parseable=output_structurally_valid,
        schema_valid=output_structurally_valid and verifier_completed,
        verifier_completed=verifier_completed,
        errors=_verification_failures(verification_result),
    )
    expected_completeness = (
        Completeness.COMPLETE
        if (
            record.outputs.artifacts
            and execution.sessions
            and all(session.resolved_model != "unresolved" for session in execution.sessions)
            and all(session.adapter != "unresolved" for session in execution.sessions)
            and repository.get("repository_kind", "git") == "git"
            and not bool(repository.get("dirty"))
        )
        else Completeness.PARTIAL
    )

    record_visibility = record.task.visibility.value if record.task.visibility is not None else None
    snapshot_visibility = variant.get("visibility")
    if record.task.visibility is None and "visibility" not in record.task.model_fields_set:
        snapshot_visibility = None
    expected_values = {
        "task_revision": lifecycle.get("package_sha256"),
        "visibility": snapshot_visibility,
        "lifecycle_id": lifecycle.get("lifecycle_id"),
        "world_id": lifecycle.get("world_id"),
        "spec_sha256": lifecycle.get("spec_sha256"),
        "package_sha256": lifecycle.get("package_sha256"),
        "repository_commit": repository.get("commit"),
        "repository_kind": repository.get("repository_kind", "git"),
        "repository_dirty": bool(repository.get("dirty")),
        "repository_dirty_digest": repository.get("dirty_digest"),
        "runtime_provider": runtime.get("provider"),
        "runtime_distributions": runtime_distributions,
        "runtime_dependency_sha256": runtime.get("dependency_inventory_sha256"),
        "verifier_qualified_name": verifier.get("qualified_name"),
        "verifier_source_sha256": verifier.get("source_sha256"),
        "resolved_models": resolved_models,
        "resolved_adapters": resolved_adapters,
        "execution_mode": execution_snapshot.get("mode"),
        "memory_visibility_policy": execution_snapshot.get("memory_visibility_policy"),
        "max_turns_per_session": snapshot_turn_limit,
        "execution_status": execution_snapshot.get("status"),
        "reward": verification_result.reward,
        "validity": expected_validity.model_dump(mode="json"),
        "completeness": expected_completeness.value,
    }
    actual_values = {
        "task_revision": record.task.task_revision,
        "visibility": record_visibility,
        "lifecycle_id": provenance.lifecycle_id,
        "world_id": provenance.world_id,
        "spec_sha256": provenance.spec_sha256,
        "package_sha256": provenance.package_sha256,
        "repository_commit": provenance.repository_commit,
        "repository_kind": provenance.repository_kind,
        "repository_dirty": provenance.repository_dirty,
        "repository_dirty_digest": provenance.repository_dirty_digest,
        "runtime_provider": provenance.runtime_provider,
        "runtime_distributions": provenance.runtime_distributions,
        "runtime_dependency_sha256": provenance.runtime_dependency_sha256,
        "verifier_qualified_name": provenance.verifier_qualified_name,
        "verifier_source_sha256": provenance.verifier_source_sha256,
        "resolved_models": (record.agent.model,),
        "resolved_adapters": (record.agent.adapter,),
        "execution_mode": execution.execution_mode,
        "memory_visibility_policy": execution.memory_visibility_policy,
        "max_turns_per_session": execution.max_turns_per_session,
        "execution_status": execution.status,
        "reward": record.evaluation.reward,
        "validity": record.evaluation.validity.model_dump(mode="json"),
        "completeness": record.completeness.value,
    }
    if expected_values != actual_values:
        return ("snapshot_record_mismatch",)
    breakdown = record.evaluation.breakdown if isinstance(record.evaluation.breakdown, dict) else {}
    verification_gates = {gate_id: gate.model_dump(mode="json") for gate_id, gate in verification_result.gates.items()}
    if breakdown.get("lifecycle_gates") != verification_gates:
        return ("snapshot_record_mismatch",)
    semantic_metrics = (
        verification_result.semantic_metrics.model_dump(mode="json")
        if verification_result.semantic_metrics is not None
        else None
    )
    if breakdown.get("semantic_transition") != semantic_metrics:
        return ("snapshot_record_mismatch",)
    return ()


def _v3_state_contains_evidence_request_fields(state: dict[str, object]) -> bool:
    if state.get("schema_version") != "3":
        return False
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        return False
    forbidden = {
        "evidence_request_budget",
        "evidence_request_budget_remaining",
        "evidence_request_actions",
    }
    return any(isinstance(checkpoint, dict) and not forbidden.isdisjoint(checkpoint) for checkpoint in checkpoint_runs)


def _validate_v5_snapshot_reconciliation(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    manifest: dict[str, object],
) -> _LifecycleSnapshot:
    provenance = record.lifecycle_provenance
    if provenance is None or record.outputs.artifacts is None:
        raise ValueError("v5 lifecycle snapshot provenance is missing")
    state_reference = _artifact_by_kind(record, "lifecycle_state")
    metrics_reference = _artifact_by_kind(record, "lifecycle_metrics")
    verification_reference = _artifact_by_kind(record, "lifecycle_verification")
    seal_reference = _artifact_by_kind(record, "lifecycle_invocation_seal")
    metadata_references = (
        state_reference,
        metrics_reference,
        verification_reference,
        seal_reference,
        provenance.invocation_index,
        provenance.ablation_manifest,
        provenance.ablation_plan,
    )
    if any(reference is None for reference in metadata_references):
        raise ValueError("v5 lifecycle snapshot metadata is incomplete")
    assert state_reference is not None
    assert metrics_reference is not None
    assert verification_reference is not None
    assert seal_reference is not None
    assert provenance.invocation_index is not None
    assert provenance.ablation_manifest is not None
    assert provenance.ablation_plan is not None

    state_path = _canonical_snapshot_path(state_reference.path)
    if state_path.parts[-2:] != ("run", "state.json") or len(state_path.parts) < 3:
        raise ValueError("v5 lifecycle state does not identify one canonical snapshot prefix")
    snapshot_prefix = PurePosixPath(*state_path.parts[:-2])
    package_root = snapshot_prefix / "package"
    run_root = snapshot_prefix / "run"

    lifecycle = manifest.get("lifecycle")
    outputs = manifest.get("outputs")
    experiment_id = manifest.get("experiment_id")
    if not isinstance(lifecycle, dict) or not isinstance(outputs, dict) or not isinstance(experiment_id, str):
        raise ValueError("v5 lifecycle manifest sections are invalid")
    experiment_component = PurePosixPath(experiment_id)
    if experiment_component.parts != (experiment_id,) or experiment_id in {"", ".", ".."}:
        raise ValueError("v5 lifecycle experiment identity is not one canonical path component")
    package_hashes = _validated_snapshot_hash_map(lifecycle.get("package_files"), label="package")
    run_hashes = _validated_snapshot_hash_map(outputs.get("artifacts"), label="run")
    variant = lifecycle.get("variant")
    if not isinstance(variant, dict):
        raise ValueError("v5 lifecycle manifest variant is invalid")
    if any("experiments" in PurePosixPath(relative).parts for relative in run_hashes):
        raise ValueError("v5 lifecycle run artifact map overlaps canonical snapshot metadata")
    manifest_lifecycle_id = lifecycle.get("lifecycle_id")
    manifest_world_id = lifecycle.get("world_id")
    if not (
        isinstance(manifest_lifecycle_id, str)
        and spec.lifecycle_id == state.lifecycle_id == manifest_lifecycle_id == provenance.lifecycle_id
    ):
        raise ValueError("v5 lifecycle semantic identity does not match across the snapshot")
    if not (
        isinstance(manifest_world_id, str)
        and spec.world_id == state.world_id == manifest_world_id == provenance.world_id
    ):
        raise ValueError("v5 lifecycle world identity does not match across the snapshot")

    canonical_experiment_root = run_root / "experiments" / experiment_id
    canonical_metadata_paths = {
        "manifest": canonical_experiment_root / "experiment-manifest.json",
        "metrics": canonical_experiment_root / "metrics.json",
        "verification": canonical_experiment_root / "verification.json",
        "seal": canonical_experiment_root / "index-entry.json",
        "index": snapshot_prefix / "experiment-index.jsonl",
        "ablation_manifest": snapshot_prefix / "sweep" / "manifest.json",
        "ablation_plan": snapshot_prefix / "sweep" / "plan.json",
    }
    expected_metadata_references = {
        "manifest": provenance.invocation_manifest,
        "seal": seal_reference,
        "index": provenance.invocation_index,
        "ablation_manifest": provenance.ablation_manifest,
        "ablation_plan": provenance.ablation_plan,
    }
    for name, reference in expected_metadata_references.items():
        if _canonical_snapshot_path(reference.path) != canonical_metadata_paths[name]:
            raise ValueError(f"v5 lifecycle {name} reference is outside the canonical snapshot layout")

    actual_by_path: dict[PurePosixPath, ArtifactReference] = {}
    for reference in record.outputs.artifacts:
        path = _canonical_snapshot_path(reference.path)
        if path in actual_by_path:
            raise ValueError("v5 lifecycle snapshot contains duplicate canonical artifact paths")
        actual_by_path[path] = reference
    expected_hashes: dict[PurePosixPath, str] = {
        **{package_root / relative: digest for relative, digest in package_hashes.items()},
        **{run_root / relative: digest for relative, digest in run_hashes.items()},
        canonical_metadata_paths["manifest"]: provenance.invocation_manifest.sha256,
        canonical_metadata_paths["metrics"]: run_hashes.get("metrics.json", ""),
        canonical_metadata_paths["verification"]: run_hashes.get("verification.json", ""),
        canonical_metadata_paths["seal"]: seal_reference.sha256,
        canonical_metadata_paths["index"]: provenance.invocation_index.sha256,
        canonical_metadata_paths["ablation_manifest"]: provenance.ablation_manifest.sha256,
        canonical_metadata_paths["ablation_plan"]: provenance.ablation_plan.sha256,
    }
    if (
        not expected_hashes[canonical_metadata_paths["metrics"]]
        or not expected_hashes[canonical_metadata_paths["verification"]]
    ):
        raise ValueError("v5 lifecycle manifest omits canonical metrics or verification")
    if set(actual_by_path) != set(expected_hashes):
        raise ValueError("v5 lifecycle snapshot inventory does not match its canonical manifest")
    if any(actual_by_path[path].sha256 != digest for path, digest in expected_hashes.items()):
        raise ValueError("v5 lifecycle snapshot artifact hashes do not match its canonical manifest")
    for name, reference in expected_metadata_references.items():
        if actual_by_path[canonical_metadata_paths[name]] != reference:
            raise ValueError(f"v5 lifecycle {name} reference does not match record provenance")
    if actual_by_path[state_path] != state_reference:
        raise ValueError("v5 lifecycle state reference does not match the canonical run map")
    if actual_by_path[run_root / "metrics.json"] != metrics_reference:
        raise ValueError("v5 lifecycle metrics reference does not match the canonical run map")
    if actual_by_path[run_root / "verification.json"] != verification_reference:
        raise ValueError("v5 lifecycle verification reference does not match the canonical run map")

    package_content = _snapshot_content_map(
        artifacts,
        references=actual_by_path,
        root=package_root,
        declared=package_hashes,
    )
    run_content = _snapshot_content_map(
        artifacts,
        references=actual_by_path,
        root=run_root,
        declared=run_hashes,
    )
    template_content = package_content.get("template.json")
    if template_content is None:
        raise ValueError("v5 lifecycle package template is missing")
    template = CompositeTaskWorldTemplate.model_validate_json(template_content)
    if template.template_id != record.task.task_id:
        raise ValueError("v5 lifecycle package template does not match the TrialRecord task")
    if template.evidence_lifecycle != spec:
        raise ValueError("v5 lifecycle package template and lifecycle contract disagree")
    _validate_v5_canonical_metadata(
        record,
        artifacts=artifacts,
        references=actual_by_path,
        paths=canonical_metadata_paths,
        manifest=manifest,
        lifecycle_variant=variant,
        state=state,
    )
    computed_package_sha256 = _package_content_sha256(package_content)
    computed_spec_sha256 = _canonical_sha256(canonical_evidence_lifecycle_spec_payload(spec))
    manifest_package_sha256 = lifecycle.get("package_sha256")
    manifest_spec_sha256 = lifecycle.get("spec_sha256")
    if not isinstance(manifest_package_sha256, str) or not isinstance(manifest_spec_sha256, str):
        raise ValueError("v5 lifecycle manifest identities are invalid")
    if not (state.package_sha256 == manifest_package_sha256 == provenance.package_sha256 == computed_package_sha256):
        raise ValueError("v5 lifecycle package identity does not match its snapshotted bytes")
    if not (state.lifecycle_spec_sha256 == manifest_spec_sha256 == provenance.spec_sha256 == computed_spec_sha256):
        raise ValueError("v5 lifecycle spec identity does not match its canonical contract")
    lifecycle_content = package_content.get("lifecycle.json")
    if lifecycle_content is None or EvidenceLifecycleSpec.model_validate_json(lifecycle_content) != spec:
        raise ValueError("v5 lifecycle package contract does not match the validated spec")
    return _LifecycleSnapshot(
        package_content_by_relative=package_content,
        run_content_by_relative=run_content,
        lifecycle_variant=dict(variant),
    )


def _validate_v5_canonical_metadata(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
    references: dict[PurePosixPath, ArtifactReference],
    paths: dict[str, PurePosixPath],
    manifest: dict[str, object],
    lifecycle_variant: dict[str, object],
    state: EvidenceLifecycleRunState,
) -> None:
    provenance = record.lifecycle_provenance
    execution = record.lifecycle_execution
    manifest_experiment_id = manifest.get("experiment_id")
    manifest_sweep = manifest.get("sweep")
    if provenance is None or execution is None or not isinstance(manifest_experiment_id, str):
        raise ValueError("v5 lifecycle canonical metadata lacks record provenance")
    if not isinstance(manifest_sweep, dict):
        raise ValueError("v5 lifecycle canonical metadata lacks sweep identity")

    seal = _snapshot_object_at(artifacts, references=references, path=paths["seal"])
    shared_index = _snapshot_object_at(artifacts, references=references, path=paths["index"])
    expected_shared_manifest_path = f"run/experiments/{manifest_experiment_id}/experiment-manifest.json"
    if shared_index.get("manifest_path") != expected_shared_manifest_path:
        raise ValueError("v5 lifecycle shared index has a noncanonical manifest path")
    normalized_index = dict(shared_index)
    normalized_index["manifest_path"] = "experiment-manifest.json"
    if seal != normalized_index:
        raise ValueError("v5 lifecycle invocation seal and shared index disagree")
    if (
        shared_index.get("experiment_id") != manifest_experiment_id
        or shared_index.get("manifest_sha256") != provenance.invocation_manifest.sha256
        or shared_index.get("sweep") != manifest_sweep
    ):
        raise ValueError("v5 lifecycle invocation index does not bind its canonical manifest")

    ablation_manifest = LifecycleAblationManifest.model_validate(
        _snapshot_object_at(artifacts, references=references, path=paths["ablation_manifest"])
    )
    ablation_plan = LifecycleAblationPlan.model_validate(
        _snapshot_object_at(artifacts, references=references, path=paths["ablation_plan"])
    )
    canonical_ablation_manifest_sha256 = _canonical_sha256(ablation_manifest.model_dump(mode="json"))
    sweep_experiment_id = manifest_sweep.get("sweep_experiment_id")
    planned_trial_id = manifest_sweep.get("planned_trial_id")
    if not (
        ablation_manifest.experiment_id == ablation_plan.experiment_id == sweep_experiment_id == record.experiment_id
    ):
        raise ValueError("v5 lifecycle sweep experiment identity does not match the TrialRecord")
    if (
        ablation_plan.manifest_sha256 != canonical_ablation_manifest_sha256
        or ablation_plan.study_design != ablation_manifest.study_design
        or manifest_sweep.get("plan_sha256") != ablation_plan.plan_sha256
    ):
        raise ValueError("v5 lifecycle sweep plan does not bind its canonical manifest")
    selected = [trial for trial in ablation_plan.trials if trial.trial_id == planned_trial_id]
    if len(selected) != 1 or planned_trial_id != record.trial_id:
        raise ValueError("v5 lifecycle sweep does not select the TrialRecord trial")
    trial = selected[0]
    variant_id = lifecycle_variant.get("variant_id")
    adaptation = lifecycle_variant.get("adaptation")
    expected_condition_id = f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}"
    if (
        ablation_manifest.lifecycle_template_id != record.task.task_id
        or trial.variant_id != variant_id
        or trial.variant_id not in ablation_manifest.variants
        or trial.adaptation.model_dump(mode="json") != adaptation
        or trial.lifecycle_id != state.lifecycle_id
        or trial.world_id != state.world_id
        or trial.spec_sha256 != state.lifecycle_spec_sha256
        or trial.package_sha256 != state.package_sha256
        or trial.agent.adapter != record.agent.adapter
        or trial.agent.model != record.agent.model
        or trial.max_turns_per_session != execution.max_turns_per_session
        or trial.execution_mode.value != execution.execution_mode
        or trial.memory_visibility_policy.value != execution.memory_visibility_policy
        or trial.runtime_provenance.adapter != record.agent.adapter
        or trial.runtime_provenance.provider != provenance.runtime_provider
        or trial.runtime_provenance.distributions != provenance.runtime_distributions
        or trial.runtime_provenance.dependency_inventory_sha256 != provenance.runtime_dependency_sha256
        or manifest_sweep.get("condition_id") != expected_condition_id
        or manifest_sweep.get("repetition") != trial.repetition
        or trial.repetition > ablation_manifest.repetitions
    ):
        raise ValueError("v5 lifecycle selected sweep trial does not match recorded execution")
    if trial.agent not in ablation_manifest.agents or not any(
        condition.execution_mode == trial.execution_mode
        and condition.memory_visibility_policy == trial.memory_visibility_policy
        for condition in ablation_manifest.conditions
    ):
        raise ValueError("v5 lifecycle selected sweep trial is absent from its manifest")
    ledger_path = Path(trial.ledger_path)
    if ledger_path.name != f"{trial.trial_id}.json" or ledger_path.parent.name != record.experiment_id:
        raise ValueError("v5 lifecycle selected sweep trial has a noncanonical ledger path")


def _snapshot_object_at(
    artifacts: dict[str, bytes],
    *,
    references: dict[PurePosixPath, ArtifactReference],
    path: PurePosixPath,
) -> dict[str, object]:
    reference = references[path]
    content = artifacts.get(reference.path)
    if content is None:
        raise ValueError("v5 lifecycle canonical metadata bytes are missing")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("v5 lifecycle canonical metadata must contain a JSON object")
    return payload


def _canonical_snapshot_path(raw_path: str) -> PurePosixPath:
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw_path or path == PurePosixPath("."):
        raise ValueError("lifecycle snapshot artifact path is not canonical")
    return path


def _validated_snapshot_hash_map(value: object, *, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"v5 lifecycle manifest {label} artifact map is missing")
    validated: dict[str, str] = {}
    for raw_relative, digest in value.items():
        if not isinstance(raw_relative, str) or not isinstance(digest, str):
            raise ValueError(f"v5 lifecycle manifest {label} artifact map is invalid")
        relative = _canonical_snapshot_path(raw_relative)
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"v5 lifecycle manifest {label} artifact hash is invalid")
        validated[relative.as_posix()] = digest
    if len(validated) != len(value):
        raise ValueError(f"v5 lifecycle manifest {label} artifact paths are ambiguous")
    return validated


def _snapshot_content_map(
    artifacts: dict[str, bytes],
    *,
    references: dict[PurePosixPath, ArtifactReference],
    root: PurePosixPath,
    declared: dict[str, str],
) -> dict[str, bytes]:
    content_by_relative: dict[str, bytes] = {}
    for relative in declared:
        path = root / relative
        reference = references[path]
        content = artifacts.get(reference.path)
        if content is None:
            raise ValueError("v5 lifecycle snapshot artifact bytes are missing")
        content_by_relative[relative] = content
    return content_by_relative


def _package_content_sha256(content_by_relative: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, content in sorted(content_by_relative.items()):
        encoded_relative = relative.encode("utf-8")
        digest.update(len(encoded_relative).to_bytes(8, "big"))
        digest.update(encoded_relative)
        digest.update(content)
    return digest.hexdigest()


def _validate_lifecycle_operation_resolver_snapshot_replay(
    snapshot: _LifecycleSnapshot,
    *,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    with TemporaryDirectory(prefix="aec-bench-lifecycle-transfer-") as temporary_root:
        root = Path(temporary_root)
        package_dir = root / "package"
        run_dir = root / "run"
        _materialize_snapshot_content(package_dir, snapshot.package_content_by_relative)
        _materialize_snapshot_content(run_dir, snapshot.run_content_by_relative)
        if lifecycle_package_variant(package_dir) != snapshot.lifecycle_variant:
            raise ValueError("v5 lifecycle package variant does not match its canonical manifest")
        source = resolve_lifecycle_operation_current_source(package_dir, run_dir, state)
        expected_current_source = LifecycleOperationCurrentSource(
            revision_id=source.revision_id,
            physical_source_state_sha256=source.physical_source_state_sha256,
            visible_source_state_sha256=source.visible_source_state_sha256,
            source_state=source.source_state,
        )
        validate_lifecycle_operation_snapshot(
            run_dir,
            state,
            spec,
            expected_current_source=expected_current_source,
        )
        validate_lifecycle_operation_resolver_replay(package_dir, run_dir, state, spec)


def _materialize_snapshot_content(root: Path, content_by_relative: dict[str, bytes]) -> None:
    for relative, content in sorted(content_by_relative.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _evidence_request_snapshot_reasons(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    manifest: dict[str, object],
    metrics: LifecycleExperimentMetrics,
    snapshot: _LifecycleSnapshot | None = None,
) -> tuple[str, ...]:
    actions = [action for checkpoint in state.checkpoint_runs for action in checkpoint.evidence_request_actions]
    action_capable = any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints)
    interaction = manifest.get("interaction")
    if not isinstance(interaction, dict):
        return ("snapshot_contract_invalid",)
    if not action_capable:
        return ("snapshot_contract_invalid",) if actions else ()
    evidence_request_paths = (
        frozenset(
            relative for relative in snapshot.run_content_by_relative if is_evidence_request_run_artifact_path(relative)
        )
        if snapshot is not None
        else _record_evidence_request_run_artifact_paths(record)
    )
    if evidence_request_paths != expected_evidence_request_run_artifact_paths(state, spec):
        return ("snapshot_contract_invalid",)

    protocol = interaction.get("evidence_request_protocol")
    tool_schema = interaction.get("tool_schema")
    if not isinstance(protocol, dict) or not isinstance(tool_schema, list):
        return ("snapshot_contract_invalid",)
    expected_protocol = evidence_request_protocol_identity()
    encoded_tool_schema = json.dumps(
        tool_schema,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        protocol.get("schema_version") != expected_protocol["schema_version"]
        or protocol.get("sha256") != expected_protocol["sha256"]
        or protocol.get("tool_schema_sha256") != hashlib.sha256(encoded_tool_schema).hexdigest()
        or not any(isinstance(tool, dict) and tool.get("name") == "request_evidence" for tool in tool_schema)
    ):
        return ("snapshot_contract_invalid",)

    expected_metrics = {
        "evidence_request_calls": len(actions),
        "accepted_evidence_requests": sum(action.outcome.value == "released" for action in actions),
        "already_released_evidence_requests": sum(action.outcome.value == "already_released" for action in actions),
        "rejected_evidence_requests": sum(action.outcome.value == "rejected" for action in actions),
        "evidence_request_budget_consumed": sum(action.budget_consumed for action in actions),
        "evidence_request_artifacts_released": sum(
            len(action.released_artifacts) for action in actions if action.outcome.value == "released"
        ),
    }
    metrics_payload = lifecycle_experiment_metrics_payload(metrics)
    if any(metrics_payload.get(field) != value for field, value in expected_metrics.items()):
        return ("snapshot_record_mismatch",)
    breakdown = record.evaluation.breakdown if isinstance(record.evaluation.breakdown, dict) else {}
    operational = dict(metrics_payload)
    operational.pop("semantic_transition", None)
    if breakdown.get("operational_metrics") != operational:
        return ("snapshot_record_mismatch",)

    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    for checkpoint in state.checkpoint_runs:
        expected_catalog = evidence_request_catalog_payload(
            checkpoint_specs[checkpoint.checkpoint_id],
            checkpoint,
        )
        catalog_relative = f"workspace/checkpoints/{checkpoint.checkpoint_id}/evidence-requests.json"
        catalog_content = _run_artifact_content(
            record,
            artifacts=artifacts,
            relative=catalog_relative,
            snapshot=snapshot,
        )
        catalog_was_released = expected_catalog is not None and checkpoint.status.value != "pending"
        if not catalog_was_released:
            if catalog_content is not None:
                return ("snapshot_contract_invalid",)
        else:
            try:
                actual_catalog = json.loads(catalog_content.decode("utf-8")) if catalog_content else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                return ("snapshot_contract_invalid",)
            if actual_catalog != expected_catalog:
                return ("snapshot_contract_invalid",)

        for action in checkpoint.evidence_request_actions:
            action_content = _run_artifact_content(
                record,
                artifacts=artifacts,
                relative=f"evidence_requests/{action.action_id}/action.json",
                snapshot=snapshot,
            )
            committed_content = _run_artifact_content(
                record,
                artifacts=artifacts,
                relative=f"evidence_requests/{action.action_id}/committed.json",
                snapshot=snapshot,
            )
            try:
                persisted_action = json.loads(action_content.decode("utf-8")) if action_content else None
                committed = json.loads(committed_content.decode("utf-8")) if committed_content else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                return ("snapshot_contract_invalid",)
            if persisted_action != action.model_dump(mode="json") or committed != {
                "action_id": action.action_id,
                "status": "committed",
            }:
                return ("snapshot_contract_invalid",)
            for artifact in action.released_artifacts:
                canonical = _run_artifact_content(
                    record,
                    artifacts=artifacts,
                    relative=artifact.path,
                    snapshot=snapshot,
                )
                projection = _run_artifact_content(
                    record,
                    artifacts=artifacts,
                    relative=f"workspace/{artifact.workspace_path}",
                    snapshot=snapshot,
                )
                if (
                    canonical is None
                    or projection is None
                    or hashlib.sha256(canonical).hexdigest() != artifact.sha256
                    or hashlib.sha256(projection).hexdigest() != artifact.sha256
                ):
                    return ("snapshot_contract_invalid",)
    return ()


def _record_evidence_request_run_artifact_paths(record: TrialRecord) -> frozenset[str]:
    paths: set[str] = set()
    for artifact in record.outputs.artifacts or ():
        normalized = f"/{artifact.path.lstrip('/')}"
        marker = "/run/"
        if marker not in normalized:
            continue
        relative = normalized.rsplit(marker, maxsplit=1)[1]
        if is_evidence_request_run_artifact_path(relative):
            paths.add(relative)
    return frozenset(paths)


def _lifecycle_operation_snapshot_reasons(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    manifest: dict[str, object],
    metrics: LifecycleExperimentMetrics,
    snapshot: _LifecycleSnapshot,
) -> tuple[str, ...]:
    actions = [action for checkpoint in state.checkpoint_runs for action in checkpoint.operation_actions]
    action_capable = any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints)
    interaction = manifest.get("interaction")
    if not isinstance(interaction, dict) or not action_capable:
        return ("snapshot_contract_invalid",)
    operation_paths = frozenset(
        relative for relative in snapshot.run_content_by_relative if is_lifecycle_operation_run_artifact_path(relative)
    )
    if operation_paths != expected_lifecycle_operation_run_artifact_paths(state, spec):
        return ("snapshot_contract_invalid",)

    protocol = interaction.get("lifecycle_operation_protocol")
    tool_schema = interaction.get("tool_schema")
    if not isinstance(protocol, dict) or not isinstance(tool_schema, list):
        return ("snapshot_contract_invalid",)
    expected_protocol = lifecycle_operation_protocol_identity()
    encoded_tool_schema = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        validate_lifecycle_operation_tool_schema(tool_schema)
    except EvidenceLifecycleError:
        return ("snapshot_contract_invalid",)
    if (
        protocol.get("schema_version") != expected_protocol["schema_version"]
        or protocol.get("sha256") != expected_protocol["sha256"]
        or protocol.get("tool") != expected_protocol["tool"]
        or protocol.get("tool_schema_sha256") != hashlib.sha256(encoded_tool_schema).hexdigest()
    ):
        return ("snapshot_contract_invalid",)

    expected_metrics = {
        "operation_calls": len(actions),
        "completed_operations": sum(action.outcome.value == "completed" for action in actions),
        "already_current_operations": sum(action.outcome.value == "already_current" for action in actions),
        "rejected_operations": sum(action.outcome.value == "rejected" for action in actions),
        "operation_budget_consumed": sum(action.budget_consumed for action in actions),
        "operation_artifacts_produced": sum(
            len(action.artifacts) for action in actions if action.outcome.value == "completed"
        ),
    }
    metrics_payload = lifecycle_experiment_metrics_payload(metrics)
    if metrics.schema_version != "3" or any(
        metrics_payload.get(field) != value for field, value in expected_metrics.items()
    ):
        return ("snapshot_record_mismatch",)
    breakdown = record.evaluation.breakdown if isinstance(record.evaluation.breakdown, dict) else {}
    operational = dict(metrics_payload)
    operational.pop("semantic_transition", None)
    if breakdown.get("operational_metrics") != operational:
        return ("snapshot_record_mismatch",)

    try:
        validate_lifecycle_operation_snapshot_payloads(
            state=state,
            spec=spec,
            artifact_paths=operation_paths,
            read_artifact=lambda relative: _run_artifact_content(
                record,
                artifacts=artifacts,
                relative=relative,
                snapshot=snapshot,
            ),
        )
        _validate_lifecycle_operation_resolver_snapshot_replay(
            snapshot,
            state=state,
            spec=spec,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EvidenceLifecycleError):
        return ("snapshot_contract_invalid",)
    return ()


def _run_artifact_content(
    record: TrialRecord,
    *,
    artifacts: dict[str, bytes],
    relative: str,
    snapshot: _LifecycleSnapshot | None = None,
) -> bytes | None:
    if snapshot is not None:
        return snapshot.run_content_by_relative.get(relative)
    suffix = f"/run/{relative}"
    matches = [artifact for artifact in record.outputs.artifacts or () if artifact.path.endswith(suffix)]
    if len(matches) != 1:
        return None
    return artifacts.get(matches[0].path)


def _artifact_by_kind(record: TrialRecord, kind: str) -> ArtifactReference | None:
    matches = [artifact for artifact in record.outputs.artifacts or () if artifact.kind == kind]
    return matches[0] if len(matches) == 1 else None


def _artifact_by_suffix(record: TrialRecord, suffix: str) -> ArtifactReference | None:
    matches = [artifact for artifact in record.outputs.artifacts or () if artifact.path.endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def _read_artifact_object(artifacts: dict[str, bytes], artifact: ArtifactReference) -> dict[str, object]:
    content = artifacts.get(artifact.path)
    if content is None:
        raise ValueError("snapshot artifact bytes are unavailable")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("snapshot artifact must contain a JSON object")
    return payload


def _record_eligibility_reasons(record: TrialRecord, *, expected_visibility: Visibility) -> tuple[str, ...]:
    reasons: list[str] = []
    if record.task.visibility is None:
        reasons.append("missing_task_visibility")
    elif record.task.visibility is not expected_visibility:
        reasons.append("calibration_not_public" if expected_visibility is Visibility.PUBLIC else "target_not_holdout")
    if record.completeness is not Completeness.COMPLETE:
        reasons.append("record_incomplete")
    if not record.evaluation.validity.verifier_completed:
        reasons.append("verifier_incomplete")
    if record.lifecycle_execution is None:
        reasons.append("missing_lifecycle_execution")
    if record.lifecycle_provenance is None:
        reasons.append("missing_lifecycle_provenance")
    return _unique_reasons(reasons)


def _condition_mismatch_reasons(
    record: TrialRecord,
    expected: LifecycleTransferCondition,
) -> tuple[str, ...]:
    execution = record.lifecycle_execution
    provenance = record.lifecycle_provenance
    if execution is None or provenance is None:
        return ()
    actual = {
        "model": record.agent.model,
        "adapter": record.agent.adapter,
        "runtime_dependency_sha256": provenance.runtime_dependency_sha256,
        "execution_mode": execution.execution_mode,
        "memory_visibility_policy": execution.memory_visibility_policy,
        "max_turns_per_session": execution.max_turns_per_session,
    }
    expected_values = expected.model_dump(mode="json")
    reason_by_field = {
        "model": "model_mismatch",
        "adapter": "adapter_mismatch",
        "runtime_dependency_sha256": "runtime_dependency_mismatch",
        "execution_mode": "execution_mode_mismatch",
        "memory_visibility_policy": "memory_visibility_policy_mismatch",
        "max_turns_per_session": "max_turns_per_session_mismatch",
    }
    reasons = [reason_by_field[field] for field, value in actual.items() if value != expected_values[field]]
    return _unique_reasons(reasons)


def _semantic_diagnostics(record: TrialRecord) -> tuple[LifecycleSemanticMetrics | None, tuple[str, ...]]:
    breakdown = record.evaluation.breakdown
    semantic = breakdown.get("semantic_transition") if isinstance(breakdown, dict) else None
    if semantic is None:
        return None, ()
    try:
        return LifecycleSemanticMetrics.model_validate(semantic), ()
    except ValidationError:
        return None, ("invalid_semantic_transition_metrics",)


def _reference_logical_identity(reference: LifecycleTransferRecordReference) -> tuple[str, str]:
    return reference.experiment_id, reference.trial_id


def _reference_physical_identity(reference: LifecycleTransferRecordReference) -> str:
    return str(Path(reference.ledger_path).resolve())


def _reference_sort_key(reference: LifecycleTransferRecordReference) -> tuple[str, str, str, str]:
    return reference.experiment_id, reference.trial_id, reference.ledger_path, reference.sha256


def _unique_reasons(reasons: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(reasons)))


def _is_canonical_absolute_path(value: str) -> bool:
    path = Path(value)
    try:
        return path.is_absolute() and path == path.resolve()
    except OSError:
        return False


def _is_strict_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _verification_failures(verification: LifecycleVerificationResult) -> list[str]:
    return [f"{gate_id}:{failure}" for gate_id, gate in verification.gates.items() for failure in gate.failures]


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or any(not isinstance(item, str) for item in value):
        raise ValueError("snapshot field must be a string sequence")
    return tuple(value)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
