# ABOUTME: Defines typed private evidence and manifest contracts for sealed lifecycle audits.
# ABOUTME: Keeps holdout schemas independent from snapshot orchestration and TrialRecord publication.

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_calibration import FrozenLifecycleCondition
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    canonical_sha256,
    validate_relative_path,
)


class LifecycleHoldoutSessionEvidence(StrictModel):
    """Capture one normalized adapter session without weakening the host record schema."""

    checkpoint_id: str | None = None
    checkpoint_ids: tuple[NonEmptyStr, ...] = ()
    status: NonEmptyStr
    model: NonEmptyStr
    adapter: NonEmptyStr
    adapter_name: NonEmptyStr
    resolved_model: NonEmptyStr
    configuration_record: dict[str, Any] = Field(default_factory=dict)
    session_mode: Literal["persistent", "fresh"]
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ]
    session_id: NonEmptyStr
    max_turns: PositiveInt
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    cache_read_tokens: NonNegativeInt = 0
    cache_write_tokens: NonNegativeInt = 0
    failure_kind: str | None = None
    provider_error: str | None = None

    @field_validator("checkpoint_ids")
    @classmethod
    def validate_checkpoint_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("holdout session checkpoint ids must be unique")
        return value


class LifecycleHoldoutAgentTotals(StrictModel):
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cache_read_tokens: NonNegativeInt
    cache_write_tokens: NonNegativeInt
    failures: NonNegativeInt


class LifecycleHoldoutRuntimeEvidence(StrictModel):
    provider: NonEmptyStr
    distributions: tuple[NonEmptyStr, ...]
    dependency_sha256: NonEmptyStr
    python_version: NonEmptyStr

    @field_validator("dependency_sha256")
    @classmethod
    def validate_dependency_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("distributions")
    @classmethod
    def validate_distributions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("holdout runtime distributions must be non-empty, sorted, and unique")
        return value


class LifecycleHoldoutInteractionEvidence(StrictModel):
    protocol: Literal["lifecycle_operation"]
    protocol_sha256: NonEmptyStr
    tool_schema: tuple[dict[str, Any], ...]
    tool_schema_sha256: NonEmptyStr

    @field_validator("protocol_sha256", "tool_schema_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleHoldoutAgentEvidence(StrictModel):
    """Bind the normalized host evidence to the selected public condition."""

    schema_version: Literal["1"] = "1"
    model: NonEmptyStr
    adapter: NonEmptyStr
    resolved_adapters: tuple[NonEmptyStr, ...]
    execution_mode: Literal["persistent_context", "fresh_context"]
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ]
    max_turns_per_session: PositiveInt
    status: NonEmptyStr
    sessions: tuple[LifecycleHoldoutSessionEvidence, ...]
    totals: LifecycleHoldoutAgentTotals
    runtime: LifecycleHoldoutRuntimeEvidence
    interaction: LifecycleHoldoutInteractionEvidence

    @field_validator("resolved_adapters")
    @classmethod
    def validate_resolved_adapters(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("holdout resolved adapters must be non-empty, sorted, and unique")
        return value

    @field_validator("sessions")
    @classmethod
    def validate_sessions(
        cls,
        value: tuple[LifecycleHoldoutSessionEvidence, ...],
    ) -> tuple[LifecycleHoldoutSessionEvidence, ...]:
        if not value:
            raise ValueError("holdout agent evidence requires at least one session")
        session_ids = [session.session_id for session in value]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("holdout session ids must be unique")
        return value


class LifecycleHoldoutAuditManifest(StrictModel):
    """Describe the complete private snapshot without creating a public disclosure surface."""

    schema_version: Literal["1"] = "1"
    audit_manifest_sha256: NonEmptyStr
    experiment_id: NonEmptyStr
    trial_id: NonEmptyStr
    created_at: NonEmptyStr
    calibration_freeze_sha256: NonEmptyStr
    target_freeze_sha256: NonEmptyStr
    target_commitment_sha256: NonEmptyStr
    claim_sha256: NonEmptyStr
    run_start_sha256: NonEmptyStr
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    package_tree_sha256: NonEmptyStr
    run_tree_sha256: NonEmptyStr
    python_version: NonEmptyStr
    repository: dict[str, Any]
    selected_condition: FrozenLifecycleCondition
    agent_evidence: LifecycleHoldoutAgentEvidence
    verification: dict[str, Any]
    package_files: dict[str, NonEmptyStr]
    run_files: dict[str, NonEmptyStr]

    @field_validator(
        "audit_manifest_sha256",
        "calibration_freeze_sha256",
        "target_freeze_sha256",
        "target_commitment_sha256",
        "claim_sha256",
        "run_start_sha256",
        "lifecycle_spec_sha256",
        "package_sha256",
        "package_tree_sha256",
        "run_tree_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("package_files", "run_files")
    @classmethod
    def validate_file_inventory(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("holdout snapshot file inventory must not be empty")
        for relative, digest in value.items():
            validate_relative_path(relative)
            ArtifactReference.validate_sha256(digest)
        return value

    @model_validator(mode="after")
    def validate_manifest_hash(self) -> LifecycleHoldoutAuditManifest:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"audit_manifest_sha256"}))
        if self.audit_manifest_sha256 != expected:
            raise ValueError("holdout audit manifest hash does not bind its canonical payload")
        return self


def holdout_record_status(status: str) -> Literal["completed", "failed", "partial"]:
    if status in {"completed", "ok"}:
        return "completed"
    if status == "partial":
        return "partial"
    return "failed"


def holdout_verification_failures(verification: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    gates = verification.get("gates")
    if not isinstance(gates, dict):
        return ["verification gates are malformed"]
    for gate_id, gate in gates.items():
        if not isinstance(gate, dict):
            failures.append(f"{gate_id}:malformed")
            continue
        for failure in gate.get("failures", []):
            failures.append(f"{gate_id}:{failure}")
    return failures
