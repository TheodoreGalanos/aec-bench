# ABOUTME: Defines the typed host-to-environment contract for evidence-lifecycle episodes.
# ABOUTME: Keeps execution identity and usage separate from task-owned verification and reward.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    LifecycleRunStatus,
    ReleasedEvidenceArtifact,
)


class LifecycleExecutionMode(StrEnum):
    PERSISTENT_CONTEXT = "persistent_context"
    FRESH_CONTEXT = "fresh_context"


class LifecycleVisibilityPolicy(StrEnum):
    """Host-controlled model visibility over the durable lifecycle workspace."""

    PERSISTENT_CONTEXT = "persistent_context"
    ARTIFACT_MEMORY = "artifact_memory"
    RAW_EVIDENCE_ONLY = "raw_evidence_only"
    CURRENT_RELEASE_ONLY = "current_release_only"


class LifecycleEpisodeEnvironmentFailure(RuntimeError):
    """Carry an environment-owned failure classification across the host boundary."""

    def __init__(self, failure_kind: str, message: str) -> None:
        if not failure_kind.strip():
            raise ValueError("failure_kind must not be blank")
        super().__init__(message)
        self.failure_kind = failure_kind


class LifecycleCompletedCheckpoint(StrictModel):
    checkpoint_id: NonEmptyStr
    submission_path: NonEmptyStr
    submission_sha256: NonEmptyStr
    released_files: tuple[NonEmptyStr, ...] = ()

    @field_validator("submission_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleEvidenceRequestOption(StrictModel):
    request_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    prerequisite_request_ids: tuple[NonEmptyStr, ...] = ()
    status: Literal[
        "available",
        "released",
        "budget_exhausted",
        "prerequisites_incomplete",
    ]


class LifecycleEvidenceRequestCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    checkpoint_id: NonEmptyStr
    request_budget: NonNegativeInt
    remaining_budget: NonNegativeInt
    requests: tuple[LifecycleEvidenceRequestOption, ...] = ()

    @model_validator(mode="after")
    def validate_budget_and_ids(self) -> LifecycleEvidenceRequestCatalog:
        if self.remaining_budget > self.request_budget:
            raise ValueError("remaining evidence request budget cannot exceed its initial budget")
        request_ids = [request.request_id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("episode evidence request ids must be unique")
        return self


class LifecycleEpisodeContext(StrictModel):
    """Validated host state available before an episode attempt is opened."""

    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    status: LifecycleRunStatus
    active_checkpoint_id: NonEmptyStr
    checkpoint_id: NonEmptyStr
    title: NonEmptyStr
    workspace: NonEmptyStr
    run_dir: NonEmptyStr
    instruction: NonEmptyStr
    instruction_path: NonEmptyStr
    submission_path: NonEmptyStr
    released_files: tuple[NonEmptyStr, ...] = ()
    evidence_request_catalog: LifecycleEvidenceRequestCatalog | None = None
    released_evidence_artifacts: tuple[ReleasedEvidenceArtifact, ...] = ()
    completed_checkpoints: tuple[LifecycleCompletedCheckpoint, ...] = ()
    checkpoint_runs: tuple[CheckpointRunRecord, ...]

    @field_validator("lifecycle_spec_sha256", "package_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_active_checkpoint(self) -> LifecycleEpisodeContext:
        if self.status is not LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION:
            raise ValueError("episode context requires a checkpoint awaiting submission")
        if self.active_checkpoint_id != self.checkpoint_id:
            raise ValueError("episode checkpoint must match the active checkpoint")
        if not any(item.checkpoint_id == self.checkpoint_id for item in self.checkpoint_runs):
            raise ValueError("episode checkpoint must exist in checkpoint_runs")
        return self

    @classmethod
    def from_runtime_context(
        cls,
        payload: dict[str, Any],
        *,
        visibility_policy: LifecycleVisibilityPolicy | str,
    ) -> LifecycleEpisodeContext:
        """Select the stable episode fields and hash-bind every visible requested artifact."""
        policy = LifecycleVisibilityPolicy(visibility_policy)
        checkpoint_runs = tuple(payload["checkpoint_runs"])
        active_checkpoint = next(item for item in checkpoint_runs if item["checkpoint_id"] == payload["checkpoint_id"])
        visible_checkpoint_runs = (
            (active_checkpoint,) if policy is LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY else checkpoint_runs
        )
        released_evidence_artifacts = tuple(
            artifact
            for checkpoint in visible_checkpoint_runs
            for action in checkpoint.get("evidence_request_actions", ())
            if action.get("outcome") == "released"
            for artifact in action.get("released_artifacts", ())
        )
        return cls(
            lifecycle_id=payload["lifecycle_id"],
            world_id=payload["world_id"],
            lifecycle_spec_sha256=payload["lifecycle_spec_sha256"],
            package_sha256=payload["package_sha256"],
            status=payload["status"],
            active_checkpoint_id=payload["active_checkpoint_id"],
            checkpoint_id=payload["checkpoint_id"],
            title=payload["title"],
            workspace=payload["workspace"],
            run_dir=payload["run_dir"],
            instruction=payload["instruction"],
            instruction_path=payload["instruction_path"],
            submission_path=payload["submission_path"],
            released_files=tuple(payload.get("released_files", ())),
            evidence_request_catalog=payload.get("evidence_request_catalog"),
            released_evidence_artifacts=released_evidence_artifacts,
            completed_checkpoints=tuple(payload.get("completed_checkpoints", ())),
            checkpoint_runs=checkpoint_runs,
        )

    @property
    def completed_checkpoint_ids(self) -> tuple[str, ...]:
        return tuple(item.checkpoint_id for item in self.completed_checkpoints)


class LifecycleEpisodeRequest(StrictModel):
    """Host-authored execution request for one lifecycle environment call."""

    schema_version: Literal["1", "2"] = "2"
    episode_id: NonEmptyStr
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    checkpoint_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    requested_adapter: NonEmptyStr
    requested_model: NonEmptyStr
    max_turns_per_session: PositiveInt
    title: NonEmptyStr
    instruction: NonEmptyStr
    workspace: NonEmptyStr
    run_dir: NonEmptyStr
    instruction_path: NonEmptyStr
    submission_path: NonEmptyStr
    released_files: tuple[NonEmptyStr, ...] = ()
    evidence_request_catalog: LifecycleEvidenceRequestCatalog | None = None
    released_evidence_artifacts: tuple[ReleasedEvidenceArtifact, ...] = ()
    completed_checkpoint_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("lifecycle_spec_sha256", "package_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_execution_boundary(self) -> LifecycleEpisodeRequest:
        _validate_mode_visibility(self.execution_mode, self.memory_visibility_policy)
        if len(set(self.checkpoint_ids)) != len(self.checkpoint_ids):
            raise ValueError("episode checkpoint ids must be unique")
        if self.checkpoint_id not in self.checkpoint_ids:
            raise ValueError("active checkpoint must belong to the episode")
        if self.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT and self.checkpoint_ids != (self.checkpoint_id,):
            raise ValueError("fresh_context episode must own exactly one checkpoint")
        if self.checkpoint_id in self.completed_checkpoint_ids:
            raise ValueError("active checkpoint cannot already be completed")
        if len(set(self.completed_checkpoint_ids)) != len(self.completed_checkpoint_ids):
            raise ValueError("completed checkpoint ids must be unique")
        if len(set(self.released_files)) != len(self.released_files):
            raise ValueError("released files must be unique")
        if self.evidence_request_catalog is not None:
            if self.evidence_request_catalog.checkpoint_id != self.checkpoint_id:
                raise ValueError("evidence request catalogue must match the active checkpoint")
        artifact_paths = [artifact.path for artifact in self.released_evidence_artifacts]
        if len(artifact_paths) != len(set(artifact_paths)):
            raise ValueError("released evidence artifact paths must be unique")
        return self


class LifecycleEpisodeUsage(StrictModel):
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    cache_read_tokens: NonNegativeInt = 0
    cache_write_tokens: NonNegativeInt = 0


class LifecycleEpisodeResult(StrictModel):
    """Verifier-independent result returned by one lifecycle environment call."""

    schema_version: Literal["1"] = "1"
    episode_id: NonEmptyStr
    attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    status: Literal["completed", "failed"]
    requested_adapter: NonEmptyStr
    requested_model: NonEmptyStr
    max_turns_per_session: PositiveInt
    adapter: NonEmptyStr
    resolved_model: NonEmptyStr
    configuration: dict[str, Any] = Field(default_factory=dict)
    usage: LifecycleEpisodeUsage = Field(default_factory=LifecycleEpisodeUsage)
    failure_kind: NonEmptyStr | None = None
    provider_error: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_result(self) -> LifecycleEpisodeResult:
        _validate_mode_visibility(self.execution_mode, self.memory_visibility_policy)
        if len(set(self.checkpoint_ids)) != len(self.checkpoint_ids):
            raise ValueError("episode checkpoint ids must be unique")
        if self.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT and len(self.checkpoint_ids) != 1:
            raise ValueError("fresh_context result must own exactly one checkpoint")
        if self.status == "completed" and (self.failure_kind is not None or self.provider_error is not None):
            raise ValueError("completed episode cannot declare a failure")
        if self.status == "failed" and self.failure_kind is None:
            raise ValueError("failed episode requires failure_kind")
        return self


@runtime_checkable
class LifecycleEpisodeEnvironment(Protocol):
    """Provider-neutral environment executed after host attempt allocation."""

    @property
    def execution_mode(self) -> LifecycleExecutionMode: ...

    @property
    def memory_visibility_policy(self) -> LifecycleVisibilityPolicy: ...

    @property
    def requested_adapter(self) -> str: ...

    @property
    def requested_model(self) -> str: ...

    @property
    def max_turns_per_session(self) -> int: ...

    def recover(self, context: LifecycleEpisodeContext) -> None:
        """Seal or reject interrupted environment-owned artifacts before a retry."""
        ...

    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        """Durably create environment-owned attempt artifacts before host publication."""
        ...

    def record_failure(
        self,
        request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        """Reconcile environment-owned artifacts with a host-rejected attempt."""
        ...

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        """Execute one episode without reading or writing verifier outcomes."""
        ...


@dataclass(frozen=True)
class InProcessLifecycleEpisodeEnvironment:
    """Run a typed deterministic or application-owned episode function in process."""

    executor: Callable[[LifecycleEpisodeRequest], LifecycleEpisodeResult]
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def __post_init__(self) -> None:
        _validate_mode_visibility(self.execution_mode, self.memory_visibility_policy)

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        return LifecycleEpisodeResult.model_validate(self.executor(request))


def validate_episode_result_identity(
    request: LifecycleEpisodeRequest,
    result: LifecycleEpisodeResult,
) -> None:
    """Fail when an environment returns identity not allocated by the host."""
    expected = (
        request.episode_id,
        request.attempt_id,
        request.session_id,
        request.checkpoint_ids,
        request.execution_mode,
        request.memory_visibility_policy,
        request.requested_adapter,
        request.requested_model,
        request.max_turns_per_session,
    )
    actual = (
        result.episode_id,
        result.attempt_id,
        result.session_id,
        result.checkpoint_ids,
        result.execution_mode,
        result.memory_visibility_policy,
        result.requested_adapter,
        result.requested_model,
        result.max_turns_per_session,
    )
    if actual != expected:
        raise ValueError("episode result identity does not match request")


def _validate_mode_visibility(
    execution_mode: LifecycleExecutionMode,
    visibility_policy: LifecycleVisibilityPolicy,
) -> None:
    if (
        execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
        and visibility_policy is not LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
    ):
        raise ValueError("persistent_context execution requires persistent_context visibility")
    if (
        execution_mode is LifecycleExecutionMode.FRESH_CONTEXT
        and visibility_policy is LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
    ):
        raise ValueError("fresh_context execution cannot use persistent_context visibility")
