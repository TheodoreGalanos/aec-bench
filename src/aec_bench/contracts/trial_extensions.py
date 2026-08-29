# ABOUTME: Defines typed optional provenance extensions used by current trial records.
# ABOUTME: Keeps lifecycle and study-specific evidence outside the shared TrialRecord envelope.

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.validators import (
    FrozenStrictModel,
    NonEmptyStr,
    StrictModel,
    ensure_non_empty_string,
    ensure_optional_non_empty_string,
)


class ArtifactReference(StrictModel):
    kind: NonEmptyStr
    path: NonEmptyStr
    sha256: NonEmptyStr
    media_type: NonEmptyStr

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
        return value


class VerifierOutputParseStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    MISSING = "missing"
    MALFORMED = "malformed"
    VALID = "valid"


class VerifierExecutionReceipt(FrozenStrictModel):
    """Record the process outcome and bounded evidence of one verifier execution."""

    receipt_id: UUID
    verifier_key: NonEmptyStr
    verifier_version: Annotated[int, Field(strict=True, gt=0)]
    started_at: datetime
    finished_at: datetime
    duration_seconds: NonNegativeFloat
    command_name: NonEmptyStr
    arguments: tuple[str, ...] = ()
    working_directory_role: Literal["trial_workspace"] = "trial_workspace"
    exit_code: int | None
    timed_out: bool
    cancelled: bool
    stdout_artifact: ArtifactReference | None = None
    stderr_artifact: ArtifactReference | None = None
    reward_artifact: ArtifactReference | None = None
    details_artifact: ArtifactReference | None = None
    output_parse_status: VerifierOutputParseStatus
    failure_kind: NonEmptyStr | None = None
    failure_message: str | None = None
    runtime_transform_version: Annotated[int, Field(strict=True, gt=0)]
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    @field_validator("receipt_id", mode="before")
    @classmethod
    def validate_receipt_id(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("failure_message")
    @classmethod
    def validate_failure_message(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)

    @model_validator(mode="after")
    def validate_timing_and_flags(self) -> "VerifierExecutionReceipt":
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError("verifier receipt timestamps must include a timezone")
        if self.finished_at < self.started_at:
            raise ValueError("verifier receipt finished_at must not precede started_at")
        if self.timed_out and self.cancelled:
            raise ValueError("verifier receipt cannot be timed out and cancelled")
        if self.duration_seconds and not isfinite(self.duration_seconds):
            raise ValueError("verifier receipt duration_seconds must be finite")
        return self

    @property
    def completed(self) -> bool:
        """Return true only when the process and reward contract both succeeded."""

        return (
            not self.timed_out
            and not self.cancelled
            and self.exit_code == 0
            and self.reward_artifact is not None
            and self.output_parse_status is VerifierOutputParseStatus.VALID
        )


class DerivationStepRecord(StrictModel):
    axis: NonEmptyStr
    value: NonEmptyStr
    parent_value: NonEmptyStr

    @model_validator(mode="after")
    def validate_change(self) -> "DerivationStepRecord":
        if self.value == self.parent_value:
            msg = "derivation step must change the parent value"
            raise ValueError(msg)
        return self


class AdaptationProvenance(StrictModel):
    family_id: NonEmptyStr
    seed_task_id: NonEmptyStr
    variation_key: NonEmptyStr
    variation: dict[str, str]
    derivation_lineage: list[DerivationStepRecord] = Field(default_factory=list)

    @field_validator("variation")
    @classmethod
    def validate_variation(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            msg = "variation must not be empty"
            raise ValueError(msg)
        for axis, axis_value in value.items():
            ensure_non_empty_string(axis)
            ensure_non_empty_string(axis_value)
        return value

    @model_validator(mode="after")
    def validate_lineage(self) -> "AdaptationProvenance":
        seen: set[str] = set()
        for step in self.derivation_lineage:
            if step.axis in seen:
                msg = "derivation_lineage axes must be unique"
                raise ValueError(msg)
            seen.add(step.axis)
            if step.axis not in self.variation:
                msg = "derivation_lineage axis must exist in variation"
                raise ValueError(msg)
            if self.variation[step.axis] != step.value:
                msg = "derivation_lineage value must match variation"
                raise ValueError(msg)
        return self


class LifecycleSessionRecord(StrictModel):
    session_id: NonEmptyStr
    checkpoint_ids: list[NonEmptyStr] = Field(default_factory=list)
    requested_adapter: NonEmptyStr | None = None
    adapter: NonEmptyStr
    resolved_model: NonEmptyStr
    execution_mode: Literal["persistent_context", "fresh_context"] | None = None
    memory_visibility_policy: (
        Literal[
            "persistent_context",
            "artifact_memory",
            "raw_evidence_only",
            "current_release_only",
        ]
        | None
    ) = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    status: Literal["completed", "failed", "partial"]
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    cache_read_tokens: NonNegativeInt = 0
    cache_write_tokens: NonNegativeInt = 0
    failure_kind: str | None = None
    provider_error: str | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)

    @field_validator("checkpoint_ids")
    @classmethod
    def validate_checkpoint_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("session checkpoint ids must be unique")
        return value


class LifecycleExecutionRecord(StrictModel):
    execution_mode: Literal["persistent_context", "fresh_context"]
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ]
    max_turns_per_session: PositiveInt
    status: Literal["completed", "failed", "partial"]
    sessions: list[LifecycleSessionRecord] = Field(default_factory=list)

    @field_validator("max_turns_per_session", mode="before")
    @classmethod
    def validate_strict_turn_limit(cls, value: object) -> object:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError("max_turns_per_session must be a positive integer")
        return value

    @model_validator(mode="after")
    def validate_session_consistency(self) -> "LifecycleExecutionRecord":
        if self.execution_mode == "persistent_context" and self.memory_visibility_policy != "persistent_context":
            raise ValueError("persistent lifecycle execution requires persistent_context visibility")
        if self.execution_mode == "fresh_context" and self.memory_visibility_policy == "persistent_context":
            raise ValueError("fresh lifecycle execution cannot use persistent_context visibility")
        resolved_models = {
            session.resolved_model for session in self.sessions if session.resolved_model != "unresolved"
        }
        if len(resolved_models) > 1:
            raise ValueError("resolved model must remain stable across lifecycle sessions")
        if len({session.adapter for session in self.sessions if session.adapter != "unresolved"}) > 1:
            raise ValueError("adapter must remain stable across lifecycle sessions")
        session_ids = [session.session_id for session in self.sessions]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("lifecycle session ids must be unique")
        if self.status == "completed" and (
            not self.sessions or any(session.status != "completed" for session in self.sessions)
        ):
            raise ValueError("completed lifecycle execution requires completed sessions")
        if any(
            session.execution_mode is not None and session.execution_mode != self.execution_mode
            for session in self.sessions
        ):
            raise ValueError("session execution mode must match lifecycle execution")
        if any(
            session.memory_visibility_policy is not None
            and session.memory_visibility_policy != self.memory_visibility_policy
            for session in self.sessions
        ):
            raise ValueError("session visibility policy must match lifecycle execution")
        return self


class LifecycleTrialProvenance(StrictModel):
    lifecycle_id: NonEmptyStr
    spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    executable_artifact_sha256: NonEmptyStr | None = None
    operation_protocol_sha256: NonEmptyStr | None = None
    variant_id: NonEmptyStr | None = None
    repository_commit: NonEmptyStr
    repository_kind: Literal["git", "source_tree"] = "git"
    repository_dirty: bool
    repository_dirty_digest: NonEmptyStr
    runtime_provider: NonEmptyStr
    runtime_distributions: tuple[NonEmptyStr, ...]
    runtime_dependency_sha256: NonEmptyStr
    verifier_qualified_name: NonEmptyStr
    verifier_source_sha256: NonEmptyStr
    invocation_manifest: ArtifactReference
    invocation_index: ArtifactReference | None = None
    ablation_manifest: ArtifactReference | None = None
    ablation_plan: ArtifactReference | None = None

    @field_validator(
        "spec_sha256",
        "package_sha256",
        "executable_artifact_sha256",
        "operation_protocol_sha256",
        "repository_dirty_digest",
        "runtime_dependency_sha256",
        "verifier_source_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else ArtifactReference.validate_sha256(value)

    @field_validator("runtime_distributions")
    @classmethod
    def validate_runtime_distributions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("runtime dependency distributions are required")
        if tuple(sorted(set(value))) != value:
            raise ValueError("runtime dependency distributions must be sorted and unique")
        return value


class ProposalSessionTrialProvenance(StrictModel):
    """Pre-import proposal-session evidence bound to exactly one TrialRecord."""

    session_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_artifact_sha256: NonEmptyStr
    proposal_graph_sha256: NonEmptyStr
    compilation_sha256: NonEmptyStr
    session_plan_sha256: NonEmptyStr
    session_receipt: ArtifactReference
    cleanup_receipt: ArtifactReference
    task_package_manifest: ArtifactReference
    runtime_archive_manifest: ArtifactReference
    expected_trial_records: Literal[1]
    trial_ordinal: Literal[1]

    @field_validator(
        "candidate_artifact_sha256",
        "proposal_graph_sha256",
        "compilation_sha256",
        "session_plan_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @property
    def bound_artifacts(self) -> tuple[ArtifactReference, ...]:
        """Return the complete pre-import proposal evidence set."""
        return (
            self.session_receipt,
            self.cleanup_receipt,
            self.task_package_manifest,
            self.runtime_archive_manifest,
        )


class MetaHarnessTrialProvenance(StrictModel):
    run_id: NonEmptyStr
    policy_id: NonEmptyStr
    plan_run_id: NonEmptyStr
    kernel_id: NonEmptyStr
    harness_id: NonEmptyStr
    program_id: NonEmptyStr
    parent_plan_run_id: NonEmptyStr | None = None
    harness_generator_sha256: NonEmptyStr
    program_generator_sha256: NonEmptyStr
    split: Literal["discovery", "repair_gate", "calibration", "holdout"]
    repetition: PositiveInt
    execution_seed: int | None = None
    execution_seed_semantics: Literal["paired_repetition_label_only"] = "paired_repetition_label_only"
    harness_program_cell: Literal["h0_p0", "hx_p0", "h0_px", "hx_px"] | None = None
    paired_block_id: NonEmptyStr | None = None
    repair_attempt_id: NonEmptyStr | None = None
    repair_iteration: NonNegativeInt | None = None
    harness_program_plan: ArtifactReference | None = None
    repair_decision: ArtifactReference | None = None
    motif_ids: tuple[NonEmptyStr, ...] = ()
    evaluation_regime_ref: EvaluationRegimeRef | None = None
    proposal_session: ProposalSessionTrialProvenance | None = None

    @field_validator(
        "harness_generator_sha256",
        "program_generator_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("motif_ids")
    @classmethod
    def validate_motif_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("motif ids must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_study_lineage(self) -> "MetaHarnessTrialProvenance":
        harness_program_fields = (self.harness_program_cell, self.paired_block_id, self.harness_program_plan)
        if any(item is not None for item in harness_program_fields) and not all(
            item is not None for item in harness_program_fields
        ):
            raise ValueError("harness-program cell, paired block, and plan must be provided together")
        repair_fields = (self.repair_attempt_id, self.repair_iteration, self.repair_decision)
        if any(item is not None for item in repair_fields) and not all(item is not None for item in repair_fields):
            raise ValueError("repair attempt, iteration, and decision must be provided together")
        if self.split == "holdout" and any(item is not None for item in repair_fields):
            raise ValueError("holdout meta-harness trials cannot contain repair provenance")
        return self
