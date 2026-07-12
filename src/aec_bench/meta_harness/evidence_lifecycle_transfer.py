# ABOUTME: Builds descriptive holdout-generalization summaries from immutable lifecycle records.
# ABOUTME: Enforces visibility, provenance integrity, and exact selected-condition identity without execution.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import NonNegativeInt, PositiveInt, ValidationError, field_validator, model_validator

from aec_bench.contracts.evaluation_result import ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import ArtifactReference, Completeness, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import LifecycleExperimentManifest
from aec_bench.meta_harness.evidence_lifecycle_metrics import LifecycleSemanticMetrics
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    LifecycleVerificationResult,
)


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
        except OSError:
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
    state_reference = _artifact_by_kind(record, "lifecycle_state")
    if verification_reference is None or state_reference is None or provenance.invocation_index is None:
        return ("snapshot_contract_missing",)
    try:
        manifest = _read_artifact_object(artifacts, provenance.invocation_manifest)
        invocation_index = _read_artifact_object(artifacts, provenance.invocation_index)
        verification = _read_artifact_object(artifacts, verification_reference)
        state = _read_artifact_object(artifacts, state_reference)
        manifest = LifecycleExperimentManifest.model_validate(manifest).model_dump(mode="json")
        verification_result = LifecycleVerificationResult.model_validate(verification)
        state_result = EvidenceLifecycleRunState.model_validate(state)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
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


def _artifact_by_kind(record: TrialRecord, kind: str) -> ArtifactReference | None:
    matches = [artifact for artifact in record.outputs.artifacts or () if artifact.kind == kind]
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
