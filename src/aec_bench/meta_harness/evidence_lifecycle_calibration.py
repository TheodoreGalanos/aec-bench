# ABOUTME: Selects one lifecycle condition exclusively from immutable public calibration evidence.
# ABOUTME: Publishes a deterministic write-once freeze before any sealed holdout audit is allowed.

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, cast

from pydantic import Field, FiniteFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import ArtifactReference, Completeness, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationTrial,
    LifecycleCalibrationSelectionPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
    validate_captured_lifecycle_operation_interaction,
    validate_historical_lifecycle_ablation_record,
)
from aec_bench.task_world_templates.lifecycles import sealed_lifecycle_mount_active

__all__ = [
    "FrozenLifecycleCondition",
    "LifecycleCalibrationCandidateResult",
    "LifecycleCalibrationFreeze",
    "LifecycleCalibrationPlannedCondition",
    "LifecycleCalibrationRecordReference",
    "LifecycleCalibrationSpendEnvelope",
    "build_lifecycle_calibration_freeze",
    "write_lifecycle_calibration_freeze",
]

_PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0.0)]
_VerifierReward = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]


class LifecycleCalibrationRecordReference(StrictModel):
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
    def validate_canonical_path(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute() or str(path.resolve()) != value:
            raise ValueError("calibration ledger path must be absolute and canonical")
        return value


@dataclass(frozen=True)
class _LoadedCalibrationRecord:
    trial: LifecycleAblationTrial
    record: TrialRecord
    reference: LifecycleCalibrationRecordReference


class LifecycleCalibrationPlannedCondition(StrictModel):
    requested_model: NonEmptyStr
    requested_adapter: NonEmptyStr
    runtime_provider: NonEmptyStr
    runtime_distributions: tuple[NonEmptyStr, ...]
    runtime_dependency_sha256: NonEmptyStr
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    max_turns_per_session: PositiveInt

    @field_validator("runtime_dependency_sha256")
    @classmethod
    def validate_runtime_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("runtime_distributions")
    @classmethod
    def validate_runtime_distributions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("runtime distributions must be non-empty, sorted, and unique")
        return value

    @model_validator(mode="after")
    def validate_mode_policy_pair(self) -> LifecycleCalibrationPlannedCondition:
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


class FrozenLifecycleCondition(LifecycleCalibrationPlannedCondition):
    resolved_model: NonEmptyStr
    resolved_adapter: NonEmptyStr
    interaction_protocol: Literal["lifecycle_operation"]
    interaction_protocol_sha256: NonEmptyStr
    tool_schema_sha256: NonEmptyStr

    @field_validator("interaction_protocol_sha256", "tool_schema_sha256")
    @classmethod
    def validate_interaction_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleCalibrationCandidateResult(StrictModel):
    candidate_id: NonEmptyStr
    planned_condition: LifecycleCalibrationPlannedCondition
    status: Literal["eligible", "ineligible"]
    reasons: tuple[NonEmptyStr, ...] = ()
    planned_trials: PositiveInt
    completed_records: NonNegativeInt
    mean_verifier_reward: _VerifierReward | None = None
    frozen_condition: FrozenLifecycleCondition | None = None
    records: tuple[LifecycleCalibrationRecordReference, ...]

    @model_validator(mode="after")
    def validate_status_payload(self) -> LifecycleCalibrationCandidateResult:
        expected_id = f"condition-{_canonical_sha256(self.planned_condition.model_dump(mode='json'))}"
        if self.candidate_id != expected_id:
            raise ValueError("calibration candidate id does not bind its planned condition")
        if self.planned_trials != len(self.records):
            raise ValueError("calibration candidate record count does not match its planned trials")
        if tuple(sorted(self.records, key=_reference_sort_key)) != self.records:
            raise ValueError("calibration candidate record references must use canonical order")
        record_keys = [_reference_sort_key(record) for record in self.records]
        if len(record_keys) != len(set(record_keys)):
            raise ValueError("calibration candidate contains duplicate record references")
        if self.status == "eligible":
            if self.reasons or self.mean_verifier_reward is None or self.frozen_condition is None:
                raise ValueError("eligible calibration candidate is missing selection evidence")
            if self.completed_records != self.planned_trials:
                raise ValueError("eligible calibration candidate requires every planned record")
            frozen_planned = LifecycleCalibrationPlannedCondition.model_validate(
                {
                    field: getattr(self.frozen_condition, field)
                    for field in LifecycleCalibrationPlannedCondition.model_fields
                }
            )
            if frozen_planned != self.planned_condition:
                raise ValueError("eligible frozen condition does not match its planned condition")
        elif self.mean_verifier_reward is not None or self.frozen_condition is not None or not self.reasons:
            raise ValueError("ineligible calibration candidate payload is inconsistent")
        return self


class LifecycleCalibrationSpendEnvelope(StrictModel):
    planned_trials: PositiveInt
    estimated_cost_per_trial_usd: _PositiveFiniteFloat
    planned_estimated_cost_usd: _PositiveFiniteFloat
    max_estimated_cost_usd: _PositiveFiniteFloat

    @model_validator(mode="after")
    def validate_envelope(self) -> LifecycleCalibrationSpendEnvelope:
        expected = float(self.estimated_cost_per_trial_usd) * self.planned_trials
        if float(self.planned_estimated_cost_usd) != expected:
            raise ValueError("planned calibration cost does not match the preregistered estimate")
        if float(self.planned_estimated_cost_usd) > float(self.max_estimated_cost_usd):
            raise ValueError("planned calibration cost exceeds the preregistered maximum")
        return self


class LifecycleCalibrationFreeze(StrictModel):
    schema_version: Literal["1"] = "1"
    freeze_sha256: NonEmptyStr
    experiment_id: NonEmptyStr
    manifest_sha256: NonEmptyStr
    plan_sha256: NonEmptyStr
    selection_policy: LifecycleCalibrationSelectionPolicy
    spend_envelope: LifecycleCalibrationSpendEnvelope
    selected_candidate_id: NonEmptyStr
    selected_condition: FrozenLifecycleCondition
    selected_mean_verifier_reward: _VerifierReward
    public_calibration_records: tuple[LifecycleCalibrationRecordReference, ...]
    candidates: tuple[LifecycleCalibrationCandidateResult, ...]

    @field_validator("freeze_sha256", "manifest_sha256", "plan_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_freeze(self) -> LifecycleCalibrationFreeze:
        if not self.public_calibration_records or not self.candidates:
            raise ValueError("calibration freeze requires public records and candidates")
        if tuple(sorted(self.public_calibration_records, key=_reference_sort_key)) != self.public_calibration_records:
            raise ValueError("calibration record references must use canonical order")
        logical_records = [(item.experiment_id, item.trial_id) for item in self.public_calibration_records]
        physical_records = [(item.ledger_path, item.sha256) for item in self.public_calibration_records]
        if len(logical_records) != len(set(logical_records)) or len(physical_records) != len(set(physical_records)):
            raise ValueError("calibration freeze contains duplicate record references")
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("calibration candidate ids must be unique")
        if tuple(sorted(self.candidates, key=lambda item: item.candidate_id)) != self.candidates:
            raise ValueError("calibration candidates must use canonical order")
        candidate_record_keys = [
            _reference_sort_key(record) for candidate in self.candidates for record in candidate.records
        ]
        public_record_keys = [_reference_sort_key(record) for record in self.public_calibration_records]
        if len(candidate_record_keys) != len(set(candidate_record_keys)) or set(candidate_record_keys) != set(
            public_record_keys
        ):
            raise ValueError("calibration candidate records must form an exact record partition")
        if self.spend_envelope.planned_trials != len(self.public_calibration_records):
            raise ValueError("calibration spend envelope must cover every public record")
        if any(record.experiment_id != self.experiment_id for record in self.public_calibration_records):
            raise ValueError("calibration record experiment ids must match the freeze")
        eligible = [item for item in self.candidates if item.status == "eligible"]
        if not eligible:
            raise ValueError("calibration freeze requires an eligible candidate")
        expected_winner = min(
            eligible,
            key=lambda item: (-cast(float, item.mean_verifier_reward), item.candidate_id),
        )
        if self.selected_candidate_id != expected_winner.candidate_id:
            raise ValueError("calibration selected candidate does not match the recomputed winner")
        selected = expected_winner
        if (
            selected.frozen_condition != self.selected_condition
            or selected.mean_verifier_reward != self.selected_mean_verifier_reward
        ):
            raise ValueError("selected calibration evidence does not match the chosen candidate")
        expected_hash = _canonical_sha256(self.model_dump(mode="json", exclude={"freeze_sha256"}))
        if self.freeze_sha256 != expected_hash:
            raise ValueError("freeze_sha256 must bind the canonical calibration freeze")
        return self


def build_lifecycle_calibration_freeze(
    manifest: LifecycleAblationManifest,
) -> LifecycleCalibrationFreeze:
    """Choose one exact condition using only a complete immutable public campaign."""
    if sealed_lifecycle_mount_active():
        raise ValueError("calibration condition cannot be frozen while a sealed holdout is mounted")
    manifest = LifecycleAblationManifest.model_validate(manifest.model_dump(mode="json"))
    policy = manifest.selection_policy
    if policy is None:
        raise ValueError("calibration selection policy was not preregistered")
    paths = _trial_record_paths(manifest)
    if not paths:
        raise ValueError("public calibration campaign is incomplete: no immutable TrialRecords found")
    first_record, first_reference = _read_record_once(paths[0])
    historical_manifest, plan = _load_historical_sweep_contract(manifest, first_record)
    records = _load_complete_campaign(
        historical_manifest,
        plan,
        preloaded={paths[0].resolve(): (first_record, first_reference)},
    )
    candidates = _candidate_results(historical_manifest, plan, records)
    eligible = [item for item in candidates if item.status == "eligible"]
    if not eligible:
        raise ValueError("public calibration campaign has no eligible condition")
    selected = min(
        eligible,
        key=lambda item: (-cast(float, item.mean_verifier_reward), item.candidate_id),
    )
    assert selected.frozen_condition is not None
    assert selected.mean_verifier_reward is not None
    assert manifest.estimated_cost_per_trial_usd is not None
    assert manifest.limits.max_estimated_cost_usd is not None
    assert plan.planned_estimated_cost_usd is not None
    spend_envelope = LifecycleCalibrationSpendEnvelope(
        planned_trials=plan.trial_count,
        estimated_cost_per_trial_usd=float(manifest.estimated_cost_per_trial_usd),
        planned_estimated_cost_usd=float(plan.planned_estimated_cost_usd),
        max_estimated_cost_usd=float(manifest.limits.max_estimated_cost_usd),
    )
    references = tuple(sorted((loaded.reference for loaded in records), key=_reference_sort_key))
    payload = {
        "schema_version": "1",
        "experiment_id": historical_manifest.experiment_id,
        "manifest_sha256": plan.manifest_sha256,
        "plan_sha256": plan.plan_sha256,
        "selection_policy": policy.model_dump(mode="json"),
        "spend_envelope": spend_envelope.model_dump(mode="json"),
        "selected_candidate_id": selected.candidate_id,
        "selected_condition": selected.frozen_condition.model_dump(mode="json"),
        "selected_mean_verifier_reward": selected.mean_verifier_reward,
        "public_calibration_records": [item.model_dump(mode="json") for item in references],
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    return LifecycleCalibrationFreeze.model_validate(
        {
            **payload,
            "freeze_sha256": _canonical_sha256(payload),
        }
    )


def write_lifecycle_calibration_freeze(
    manifest: LifecycleAblationManifest,
    output_path: Path,
) -> Path:
    """Publish one deterministic freeze without replacing prior bytes."""
    freeze = build_lifecycle_calibration_freeze(manifest)
    destination = Path(output_path)
    content = (json.dumps(freeze.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")
    if destination.exists() or destination.is_symlink():
        _validate_existing_freeze(destination, content)
        return destination
    mkdir_durable(destination.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            _validate_existing_freeze(destination, content)
        else:
            fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _load_complete_campaign(
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    *,
    preloaded: dict[Path, tuple[TrialRecord, LifecycleCalibrationRecordReference]],
) -> list[_LoadedCalibrationRecord]:
    expected_by_path: dict[Path, LifecycleAblationTrial] = {}
    for trial in plan.trials:
        path = Path(trial.ledger_path)
        if not path.is_absolute() or path.resolve() != path:
            raise ValueError("public calibration plan contains a non-canonical TrialRecord path")
        expected_by_path[path] = trial
    experiment_root = Path(manifest.ledger_root) / manifest.experiment_id
    actual_paths = {
        path
        for path in experiment_root.rglob("*.json")
        if not any(part.startswith("_") for part in path.relative_to(experiment_root).parts)
    }
    if any(path.is_symlink() or path.resolve() != path for path in actual_paths):
        raise ValueError("public calibration TrialRecord path is not canonical")
    expected_paths = set(expected_by_path)
    missing = expected_paths - actual_paths
    if missing:
        raise ValueError(
            f"public calibration campaign is incomplete: {len(missing)} of {plan.trial_count} planned records missing"
        )
    unexpected = actual_paths - expected_paths
    if unexpected:
        raise ValueError("public calibration ledger contains records outside the preregistered plan")
    loaded: list[_LoadedCalibrationRecord] = []
    for path, trial in sorted(expected_by_path.items(), key=lambda item: item[1].trial_id):
        record, reference = preloaded.get(path) or _read_record_once(path)
        if reference.experiment_id != record.experiment_id or reference.trial_id != record.trial_id:
            raise ValueError("public calibration record reference does not bind its TrialRecord")
        validate_historical_lifecycle_ablation_record(record, manifest, plan, trial)
        loaded.append(_LoadedCalibrationRecord(trial=trial, record=record, reference=reference))
    return loaded


def _candidate_results(
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    records: list[_LoadedCalibrationRecord],
) -> tuple[LifecycleCalibrationCandidateResult, ...]:
    del plan
    grouped: dict[str, list[_LoadedCalibrationRecord]] = defaultdict(list)
    planned_by_id: dict[str, LifecycleCalibrationPlannedCondition] = {}
    for loaded in records:
        planned = _planned_condition(loaded.trial)
        candidate_id = f"condition-{_canonical_sha256(planned.model_dump(mode='json'))}"
        planned_by_id[candidate_id] = planned
        grouped[candidate_id].append(loaded)

    expected_cells = {
        (variant_id, repetition)
        for variant_id in manifest.variants
        for repetition in range(1, manifest.repetitions + 1)
    }
    results: list[LifecycleCalibrationCandidateResult] = []
    for candidate_id in sorted(grouped):
        group = grouped[candidate_id]
        reasons: list[str] = []
        cells = {(loaded.trial.variant_id, loaded.trial.repetition) for loaded in group}
        if cells != expected_cells or len(group) != len(expected_cells):
            reasons.append("planned_candidate_coverage_mismatch")
        completed = 0
        resolved_models: set[str] = set()
        resolved_adapters: set[str] = set()
        protocol_hashes: set[str] = set()
        tool_schema_hashes: set[str] = set()
        rewards: list[float] = []
        for loaded in group:
            trial = loaded.trial
            record = loaded.record
            if record.task.visibility is not Visibility.PUBLIC:
                reasons.append("record_not_explicitly_public")
            if record.completeness is not Completeness.COMPLETE:
                reasons.append("record_incomplete")
            execution = record.lifecycle_execution
            provenance = record.lifecycle_provenance
            if execution is None or execution.status != "completed":
                reasons.append("execution_not_completed")
            if not record.evaluation.validity.verifier_completed:
                reasons.append("verifier_incomplete")
            if (
                record.task.visibility is Visibility.PUBLIC
                and record.completeness is Completeness.COMPLETE
                and execution is not None
                and execution.status == "completed"
                and record.evaluation.validity.verifier_completed
            ):
                completed += 1
            if record.agent.model == "unresolved":
                reasons.append("resolved_model_unavailable")
            else:
                resolved_models.add(record.agent.model)
            if record.agent.adapter == "unresolved":
                reasons.append("resolved_adapter_unavailable")
            else:
                resolved_adapters.add(record.agent.adapter)
            if record.agent.adapter != trial.agent.adapter:
                reasons.append("resolved_adapter_mismatch")
            if provenance is None:
                reasons.append("runtime_provenance_missing")
            else:
                expected_runtime = trial.runtime_provenance
                if (
                    provenance.runtime_provider != expected_runtime.provider
                    or provenance.runtime_distributions != expected_runtime.distributions
                    or provenance.runtime_dependency_sha256 != expected_runtime.dependency_inventory_sha256
                ):
                    reasons.append("runtime_provenance_mismatch")
            interaction = _operation_interaction_identity(manifest, record)
            if interaction is None:
                reasons.append("lifecycle_operation_protocol_missing")
            else:
                protocol_hashes.add(interaction[0])
                tool_schema_hashes.add(interaction[1])
            rewards.append(record.evaluation.reward)
        if len(resolved_models) != 1:
            reasons.append("resolved_model_not_stable")
        if len(resolved_adapters) != 1:
            reasons.append("resolved_adapter_not_stable")
        if len(protocol_hashes) != 1:
            reasons.append("interaction_protocol_not_stable")
        if len(tool_schema_hashes) != 1:
            reasons.append("tool_schema_not_stable")
        normalized_reasons = tuple(sorted(set(reasons)))
        frozen: FrozenLifecycleCondition | None = None
        mean_reward: float | None = None
        if not normalized_reasons:
            planned = planned_by_id[candidate_id]
            frozen = FrozenLifecycleCondition(
                **planned.model_dump(mode="python"),
                resolved_model=next(iter(resolved_models)),
                resolved_adapter=next(iter(resolved_adapters)),
                interaction_protocol="lifecycle_operation",
                interaction_protocol_sha256=next(iter(protocol_hashes)),
                tool_schema_sha256=next(iter(tool_schema_hashes)),
            )
            mean_reward = sum(rewards) / len(rewards)
        references = tuple(sorted((loaded.reference for loaded in group), key=_reference_sort_key))
        results.append(
            LifecycleCalibrationCandidateResult(
                candidate_id=candidate_id,
                planned_condition=planned_by_id[candidate_id],
                status="eligible" if frozen is not None else "ineligible",
                reasons=normalized_reasons,
                planned_trials=len(group),
                completed_records=completed,
                mean_verifier_reward=mean_reward,
                frozen_condition=frozen,
                records=references,
            )
        )
    return tuple(results)


def _planned_condition(trial: LifecycleAblationTrial) -> LifecycleCalibrationPlannedCondition:
    return LifecycleCalibrationPlannedCondition(
        requested_model=trial.agent.model,
        requested_adapter=trial.agent.adapter,
        runtime_provider=trial.runtime_provenance.provider,
        runtime_distributions=trial.runtime_provenance.distributions,
        runtime_dependency_sha256=trial.runtime_provenance.dependency_inventory_sha256,
        execution_mode=trial.execution_mode,
        memory_visibility_policy=trial.memory_visibility_policy,
        max_turns_per_session=trial.max_turns_per_session,
    )


def _operation_interaction_identity(
    manifest: LifecycleAblationManifest,
    record: TrialRecord,
) -> tuple[str, str] | None:
    provenance = record.lifecycle_provenance
    if provenance is None:
        return None
    invocation = _read_artifact_json(
        Path(manifest.ledger_root),
        provenance.invocation_manifest,
        expected_kind="lifecycle_manifest",
    )
    interaction = invocation.get("interaction")
    if not isinstance(interaction, dict):
        return None
    protocol = interaction.get("lifecycle_operation_protocol")
    tool_schema = interaction.get("tool_schema")
    if not isinstance(protocol, dict) or not isinstance(tool_schema, list):
        return None
    return validate_captured_lifecycle_operation_interaction(protocol, tool_schema)


def _load_historical_sweep_contract(
    requested_manifest: LifecycleAblationManifest,
    record: TrialRecord,
) -> tuple[LifecycleAblationManifest, LifecycleAblationPlan]:
    provenance = record.lifecycle_provenance
    if provenance is None or provenance.ablation_manifest is None or provenance.ablation_plan is None:
        raise ValueError("historical TrialRecord is missing snapshotted ablation contract references")
    manifest_payload = _read_artifact_json(
        Path(requested_manifest.ledger_root),
        provenance.ablation_manifest,
        expected_kind="lifecycle_ablation_manifest",
    )
    plan_payload = _read_artifact_json(
        Path(requested_manifest.ledger_root),
        provenance.ablation_plan,
        expected_kind="lifecycle_ablation_plan",
    )
    historical_manifest = LifecycleAblationManifest.model_validate(manifest_payload)
    plan = LifecycleAblationPlan.model_validate(plan_payload)
    if historical_manifest != requested_manifest:
        raise ValueError("requested calibration manifest does not match the snapshotted historical manifest")
    manifest_sha256 = _canonical_sha256(historical_manifest.model_dump(mode="json"))
    if plan.experiment_id != historical_manifest.experiment_id or plan.manifest_sha256 != manifest_sha256:
        raise ValueError("snapshotted historical plan does not bind the calibration manifest")
    return historical_manifest, plan


def _read_artifact_json(
    ledger_root: Path,
    reference: ArtifactReference,
    *,
    expected_kind: str,
) -> dict[str, Any]:
    if reference.kind != expected_kind:
        raise ValueError(f"calibration artifact kind must be {expected_kind}")
    relative = PurePosixPath(reference.path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in reference.path:
        raise ValueError("calibration artifact path is unsafe")
    root = ledger_root.resolve()
    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("calibration artifact escapes the ledger root") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError("calibration artifact hash does not match its TrialRecord")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != reference.sha256:
        raise ValueError("calibration artifact hash does not match its TrialRecord")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("calibration artifact must contain a JSON object")
    return cast(dict[str, Any], payload)


def _read_record_once(path: Path) -> tuple[TrialRecord, LifecycleCalibrationRecordReference]:
    candidate = Path(path)
    if (
        candidate.is_symlink()
        or not candidate.is_file()
        or not candidate.is_absolute()
        or candidate.resolve() != candidate
    ):
        raise ValueError("public calibration TrialRecord path is not canonical")
    content = candidate.read_bytes()
    record = TrialRecord.model_validate_json(content)
    return record, LifecycleCalibrationRecordReference(
        experiment_id=record.experiment_id,
        trial_id=record.trial_id,
        ledger_path=str(candidate),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _trial_record_paths(manifest: LifecycleAblationManifest) -> list[Path]:
    experiment_root = Path(manifest.ledger_root) / manifest.experiment_id
    if not experiment_root.exists():
        return []
    if experiment_root.is_symlink() or not experiment_root.is_dir():
        raise ValueError("public calibration experiment ledger root is not canonical")
    return sorted(
        path
        for path in experiment_root.rglob("*.json")
        if not any(part.startswith("_") for part in path.relative_to(experiment_root).parts)
    )


def _reference_sort_key(reference: LifecycleCalibrationRecordReference) -> tuple[str, str, str, str]:
    return reference.experiment_id, reference.trial_id, reference.ledger_path, reference.sha256


def _validate_existing_freeze(path: Path, expected: bytes) -> None:
    if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
        raise ValueError("calibration freeze already exists with different content")
    LifecycleCalibrationFreeze.model_validate_json(expected)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
