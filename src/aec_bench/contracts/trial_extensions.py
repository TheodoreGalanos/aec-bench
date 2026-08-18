# ABOUTME: Defines typed optional provenance extensions used by current trial records.
# ABOUTME: Keeps lifecycle and study-specific evidence outside the shared TrialRecord envelope.

from typing import Any, Literal

from pydantic import (
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_non_empty_string


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
        "repository_dirty_digest",
        "runtime_dependency_sha256",
        "verifier_source_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

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
    kernel_id: NonEmptyStr
    kernel_sha256: NonEmptyStr
    harness_id: NonEmptyStr
    harness_sha256: NonEmptyStr
    program_id: NonEmptyStr
    program_sha256: NonEmptyStr
    bundle_id: NonEmptyStr
    bundle_sha256: NonEmptyStr
    parent_bundle_id: NonEmptyStr | None = None
    review_sidecar_sha256: NonEmptyStr
    declared_surface_sha256: NonEmptyStr
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
    candidate_manifest: ArtifactReference
    harness_program_plan: ArtifactReference | None = None
    repair_decision: ArtifactReference | None = None
    motif_ids: tuple[NonEmptyStr, ...] = ()
    evaluation_plan_ref: EvaluationPlanRef | None = None
    proposal_session: ProposalSessionTrialProvenance | None = None

    @field_validator(
        "kernel_sha256",
        "harness_sha256",
        "program_sha256",
        "bundle_sha256",
        "review_sidecar_sha256",
        "declared_surface_sha256",
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
