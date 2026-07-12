# ABOUTME: Contract models for append-only trial provenance in the aec-bench Python implementation.
# ABOUTME: Defines nested execution, input, output, timing, and completeness for replayable records.

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.agent_output import AgentOutput
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_non_empty_string


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class TaskReference(StrictModel):
    task_id: NonEmptyStr
    task_revision: NonEmptyStr
    visibility: Visibility | None = None


class AgentReference(StrictModel):
    adapter: NonEmptyStr
    model: NonEmptyStr
    adapter_revision: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class EnvironmentSnapshot(StrictModel):
    runtime_image: NonEmptyStr
    compute_backend: NonEmptyStr
    tool_versions: dict[str, str] | None = None


class FileReference(StrictModel):
    path: NonEmptyStr
    hash: NonEmptyStr
    source: str | None = None


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


class InputRecord(StrictModel):
    instruction: NonEmptyStr
    system_prompt: str | None = None
    input_files: list[FileReference] | None = None


class OutputRecord(StrictModel):
    agent_output: AgentOutput | None = None
    raw_output_path: str | None = None
    conversation_path: str | None = None
    trajectory_path: str | None = None
    agent_result: dict[str, Any] | None = None
    artifacts: list[ArtifactReference] | None = None


class TimingRecord(StrictModel):
    total_seconds: NonNegativeFloat
    agent_seconds: NonNegativeFloat | None = None
    setup_seconds: NonNegativeFloat | None = None
    verification_seconds: NonNegativeFloat | None = None


class CostRecord(StrictModel):
    tokens_in: NonNegativeInt | None = None
    tokens_out: NonNegativeInt | None = None
    cache_read_tokens: NonNegativeInt | None = None
    cache_write_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None
    advisor_calls: NonNegativeInt | None = None
    advisor_input_tokens: NonNegativeInt | None = None
    advisor_output_tokens: NonNegativeInt | None = None


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
    world_id: NonEmptyStr
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
    calibration_freeze: ArtifactReference | None = None
    sealed_target_freeze: ArtifactReference | None = None
    sealed_audit_claim: ArtifactReference | None = None
    sealed_audit_manifest: ArtifactReference | None = None

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


class TrialRecord(StrictModel):
    trial_id: NonEmptyStr
    experiment_id: NonEmptyStr
    dataset_id: str | None = None  # "name@version" or None for inline runs
    timestamp: datetime
    task: TaskReference
    agent: AgentReference
    environment: EnvironmentSnapshot
    inputs: InputRecord
    outputs: OutputRecord
    evaluation: EvaluationResult
    timing: TimingRecord
    cost: CostRecord | None = None
    adaptation: AdaptationProvenance | None = None
    lifecycle_execution: LifecycleExecutionRecord | None = None
    lifecycle_provenance: LifecycleTrialProvenance | None = None
    completeness: Completeness

    @model_validator(mode="after")
    def validate_completeness(self) -> "TrialRecord":
        if self.completeness is Completeness.COMPLETE:
            missing = []
            if self.agent.adapter_revision is None:
                missing.append("agent.adapter_revision")
            if self.environment.tool_versions is None:
                missing.append("environment.tool_versions")
            if self.inputs.input_files is None:
                missing.append("inputs.input_files")
            if self.lifecycle_execution is not None or self.lifecycle_provenance is not None:
                if self.lifecycle_execution is None:
                    missing.append("lifecycle_execution")
                if self.lifecycle_provenance is None:
                    missing.append("lifecycle_provenance")
                if self.lifecycle_provenance is not None and self.lifecycle_provenance.repository_dirty:
                    missing.append("lifecycle_provenance.clean_repository")
                if self.lifecycle_provenance is not None:
                    public_fields = (
                        "invocation_index",
                        "ablation_manifest",
                        "ablation_plan",
                    )
                    holdout_fields = (
                        "calibration_freeze",
                        "sealed_target_freeze",
                        "sealed_audit_claim",
                        "sealed_audit_manifest",
                    )
                    required_fields: tuple[str, ...]
                    forbidden_fields: tuple[str, ...]
                    if self.task.visibility is Visibility.HOLDOUT:
                        required_fields = holdout_fields
                        forbidden_fields = public_fields
                    else:
                        required_fields = public_fields
                        forbidden_fields = holdout_fields
                    for field in required_fields:
                        if getattr(self.lifecycle_provenance, field) is None:
                            missing.append(f"lifecycle_provenance.{field}")
                    for field in forbidden_fields:
                        if getattr(self.lifecycle_provenance, field) is not None:
                            missing.append(f"lifecycle_provenance.forbidden_{field}")
                if self.lifecycle_execution is not None and not self.lifecycle_execution.sessions:
                    missing.append("lifecycle_execution.sessions")
                if self.lifecycle_execution is not None and any(
                    not session.artifacts for session in self.lifecycle_execution.sessions
                ):
                    missing.append("lifecycle_execution.sessions.artifacts")
                if self.lifecycle_execution is not None and any(
                    session.resolved_model == "unresolved" for session in self.lifecycle_execution.sessions
                ):
                    missing.append("lifecycle_execution.sessions.resolved_model")
                if self.lifecycle_execution is not None and any(
                    session.adapter == "unresolved" for session in self.lifecycle_execution.sessions
                ):
                    missing.append("lifecycle_execution.sessions.adapter")
                if not self.outputs.artifacts:
                    missing.append("outputs.artifacts")
            if missing:
                msg = f"complete trial record missing provenance fields: {', '.join(missing)}"
                raise ValueError(msg)
        if (self.lifecycle_execution is None) != (self.lifecycle_provenance is None):
            raise ValueError("lifecycle execution and provenance must be provided together")
        if self.lifecycle_execution is not None:
            resolved_models = {
                session.resolved_model
                for session in self.lifecycle_execution.sessions
                if session.resolved_model != "unresolved"
            }
            adapters = {
                session.adapter for session in self.lifecycle_execution.sessions if session.adapter != "unresolved"
            }
            if resolved_models and resolved_models != {self.agent.model}:
                raise ValueError("agent model must match the lifecycle resolved model")
            if adapters and adapters != {self.agent.adapter}:
                raise ValueError("agent adapter must match lifecycle sessions")
            if self.outputs.artifacts and self.lifecycle_provenance is not None:
                bound_artifacts = (
                    self.lifecycle_provenance.invocation_manifest,
                    self.lifecycle_provenance.invocation_index,
                    self.lifecycle_provenance.ablation_manifest,
                    self.lifecycle_provenance.ablation_plan,
                    self.lifecycle_provenance.calibration_freeze,
                    self.lifecycle_provenance.sealed_target_freeze,
                    self.lifecycle_provenance.sealed_audit_claim,
                    self.lifecycle_provenance.sealed_audit_manifest,
                )
                if any(artifact is not None and artifact not in self.outputs.artifacts for artifact in bound_artifacts):
                    raise ValueError("lifecycle provenance must be included in output artifacts")
        return self
