# ABOUTME: Defines durable runtime records for evidence-lifecycle runs and checkpoints.
# ABOUTME: Models recovery lineage and reward-independent semantic diagnostics independently of task content.

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_metrics import LifecycleSemanticMetrics


class LifecycleRunStatus(StrEnum):
    AWAITING_EVIDENCE_RELEASE = "awaiting_evidence_release"
    AWAITING_CHECKPOINT_SUBMISSION = "awaiting_checkpoint_submission"
    COMPLETE = "complete"


class CheckpointRunStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUBMITTED = "submitted"


class CheckpointAttemptStatus(StrEnum):
    ACTIVE = "active"
    SUBMITTED = "submitted"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class LifecycleTransitionKind(StrEnum):
    BRANCH = "branch"
    EVIDENCE_REQUEST = "evidence_request"
    OPERATION = "operation"
    RELEASE = "release"
    SUBMIT = "submit"
    REVISIT = "revisit"


class EvidenceRequestOutcome(StrEnum):
    RELEASED = "released"
    ALREADY_RELEASED = "already_released"
    REJECTED = "rejected"


class EvidenceRequestRejection(StrEnum):
    INACTIVE_CHECKPOINT = "inactive_checkpoint"
    UNKNOWN_REQUEST = "unknown_request"
    PREREQUISITES_INCOMPLETE = "prerequisites_incomplete"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_SUPPORTED = "not_supported"


class LifecycleOperationOutcome(StrEnum):
    COMPLETED = "completed"
    ALREADY_CURRENT = "already_current"
    REJECTED = "rejected"


class LifecycleOperationDisposition(StrEnum):
    COMPUTED = "computed"
    REUSED = "reused"
    ACTIVATED = "activated"


class LifecycleOperationRejection(StrEnum):
    INACTIVE_CHECKPOINT = "inactive_checkpoint"
    UNKNOWN_OPERATION = "unknown_operation"
    PREREQUISITES_INCOMPLETE = "prerequisites_incomplete"
    STALE_VISIBLE_SOURCE = "stale_visible_source"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_SUPPORTED = "not_supported"


class LifecycleOperationArtifact(StrictModel):
    path: NonEmptyStr
    workspace_path: str | None = None
    sha256: NonEmptyStr

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("operation artifact sha256 must contain 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def validate_paths(self) -> LifecycleOperationArtifact:
        canonical = PurePosixPath(self.path)
        if canonical.is_absolute() or ".." in canonical.parts or canonical.parts[:1] != ("lifecycle_operations",):
            raise ValueError("operation artifact path must stay under lifecycle_operations/")
        if self.workspace_path is not None:
            workspace = PurePosixPath(self.workspace_path)
            if workspace.is_absolute() or ".." in workspace.parts or workspace.parts[:1] != ("inbox",):
                raise ValueError("operation workspace path must stay under inbox/")
        return self


class LifecycleOperationActionRecord(StrictModel):
    action_id: NonEmptyStr
    sequence: PositiveInt
    checkpoint_id: NonEmptyStr
    requested_checkpoint_id: NonEmptyStr
    operation_id: NonEmptyStr
    operation_kind: NonEmptyStr
    reason: NonEmptyStr
    session_id: NonEmptyStr
    attempt_id: NonEmptyStr
    outcome: LifecycleOperationOutcome
    rejection: LifecycleOperationRejection | None = None
    disposition: LifecycleOperationDisposition | None = None
    visible_source_state_before_sha256: NonEmptyStr
    visible_source_state_after_sha256: NonEmptyStr
    physical_source_state_before_sha256: NonEmptyStr
    physical_source_state_after_sha256: NonEmptyStr
    input_projection_sha256: NonEmptyStr
    request_sha256: NonEmptyStr
    result_manifest_sha256: str | None = None
    prerequisite_action_ids: tuple[NonEmptyStr, ...] = ()
    retained_from_action_id: str | None = None
    pre_action_state_sha256: NonEmptyStr
    post_action_state_sha256: NonEmptyStr
    artifacts: tuple[LifecycleOperationArtifact, ...] = ()
    budget_before: NonNegativeInt
    budget_consumed: Literal[0, 1]
    budget_after: NonNegativeInt
    inherited_from_parent: bool = False

    @field_validator(
        "visible_source_state_before_sha256",
        "visible_source_state_after_sha256",
        "physical_source_state_before_sha256",
        "physical_source_state_after_sha256",
        "input_projection_sha256",
        "request_sha256",
        "result_manifest_sha256",
        "pre_action_state_sha256",
        "post_action_state_sha256",
    )
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError("operation sha256 must contain 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def validate_outcome_and_budget(self) -> LifecycleOperationActionRecord:
        artifact_paths = [artifact.path for artifact in self.artifacts]
        if len(artifact_paths) != len(set(artifact_paths)):
            raise ValueError("operation artifact path values must be unique")
        workspace_paths = [
            artifact.workspace_path for artifact in self.artifacts if artifact.workspace_path is not None
        ]
        if len(workspace_paths) != len(set(workspace_paths)):
            raise ValueError("operation workspace path values must be unique")
        if self.budget_after != self.budget_before - self.budget_consumed:
            raise ValueError("operation budget arithmetic is inconsistent")
        if self.outcome == LifecycleOperationOutcome.COMPLETED:
            if (
                self.requested_checkpoint_id != self.checkpoint_id
                or self.rejection is not None
                or self.disposition
                not in {
                    LifecycleOperationDisposition.COMPUTED,
                    LifecycleOperationDisposition.ACTIVATED,
                }
                or self.budget_consumed != 1
                or self.result_manifest_sha256 is None
                or not self.artifacts
                or self.retained_from_action_id is not None
            ):
                raise ValueError("completed operation must consume budget and bind computed artifacts")
        elif self.outcome == LifecycleOperationOutcome.ALREADY_CURRENT:
            if (
                self.requested_checkpoint_id != self.checkpoint_id
                or self.rejection is not None
                or self.disposition != LifecycleOperationDisposition.REUSED
                or self.budget_consumed != 0
                or self.result_manifest_sha256 is not None
                or not self.artifacts
                or self.retained_from_action_id is None
            ):
                raise ValueError("already-current operation must reuse one prior result without budget")
        elif (
            self.rejection is None
            or self.disposition is not None
            or self.budget_consumed != 0
            or self.result_manifest_sha256 is not None
            or self.artifacts
            or self.retained_from_action_id is not None
        ):
            raise ValueError("rejected operation must record only its typed rejection")
        return self


class ReleasedEvidenceArtifact(StrictModel):
    path: NonEmptyStr
    workspace_path: NonEmptyStr
    sha256: NonEmptyStr

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def validate_paths(self) -> ReleasedEvidenceArtifact:
        canonical = PurePosixPath(self.path)
        workspace = PurePosixPath(self.workspace_path)
        if canonical.is_absolute() or ".." in canonical.parts or canonical.parts[:1] != ("evidence_requests",):
            raise ValueError("released evidence artifact path must stay under evidence_requests/")
        if workspace.is_absolute() or ".." in workspace.parts or workspace.parts[:1] != ("inbox",):
            raise ValueError("released evidence workspace path must stay under inbox/")
        return self


class EvidenceRequestActionRecord(StrictModel):
    action_id: NonEmptyStr
    sequence: PositiveInt
    checkpoint_id: NonEmptyStr
    requested_checkpoint_id: NonEmptyStr
    request_id: NonEmptyStr
    reason: NonEmptyStr
    session_id: NonEmptyStr
    attempt_id: NonEmptyStr
    outcome: EvidenceRequestOutcome
    rejection: EvidenceRequestRejection | None = None
    pre_action_state_sha256: NonEmptyStr
    post_action_state_sha256: NonEmptyStr
    released_artifacts: tuple[ReleasedEvidenceArtifact, ...] = ()
    budget_before: NonNegativeInt
    budget_consumed: Literal[0, 1]
    budget_after: NonNegativeInt
    inherited_from_parent: bool = False

    @field_validator("pre_action_state_sha256", "post_action_state_sha256")
    @classmethod
    def validate_state_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("action state sha256 must contain 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def validate_outcome_and_budget(self) -> EvidenceRequestActionRecord:
        if self.budget_after != self.budget_before - self.budget_consumed:
            raise ValueError("evidence request budget arithmetic is inconsistent")
        if self.outcome == EvidenceRequestOutcome.RELEASED:
            if (
                self.requested_checkpoint_id != self.checkpoint_id
                or self.rejection is not None
                or self.budget_consumed != 1
                or not self.released_artifacts
            ):
                raise ValueError("released evidence request must consume budget and record artifacts")
        elif self.outcome == EvidenceRequestOutcome.ALREADY_RELEASED:
            if (
                self.requested_checkpoint_id != self.checkpoint_id
                or self.rejection is not None
                or self.budget_consumed != 0
                or not self.released_artifacts
            ):
                raise ValueError("already-released evidence request must preserve its artifacts")
        elif self.rejection is None or self.budget_consumed != 0 or self.released_artifacts:
            raise ValueError("rejected evidence request must record only its rejection")
        return self


class CheckpointAttemptRecord(StrictModel):
    attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    sequence: PositiveInt
    execution_mode: NonEmptyStr
    status: CheckpointAttemptStatus
    resumed_from_attempt_id: str | None = None
    failure_kind: str | None = None
    episode_request_sha256: str | None = None
    inherited_from_parent: bool = False

    @field_validator("episode_request_sha256")
    @classmethod
    def validate_episode_request_hash(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError("episode_request_sha256 must contain 64 lowercase hexadecimal characters")
        return value


class CheckpointRunRecord(StrictModel):
    checkpoint_id: NonEmptyStr
    status: CheckpointRunStatus = CheckpointRunStatus.PENDING
    released_files: list[str] = Field(default_factory=list)
    submission_path: str | None = None
    submission_sha256: str | None = None
    attempts: list[CheckpointAttemptRecord] = Field(default_factory=list)
    evidence_request_budget: NonNegativeInt = 0
    evidence_request_budget_remaining: NonNegativeInt = 0
    evidence_request_actions: list[EvidenceRequestActionRecord] = Field(default_factory=list)
    operation_budget: NonNegativeInt = 0
    operation_budget_remaining: NonNegativeInt = 0
    operation_actions: list[LifecycleOperationActionRecord] = Field(default_factory=list)
    inherited_from_parent: bool = False

    @model_validator(mode="after")
    def validate_submission_and_attempt_state(self) -> CheckpointRunRecord:
        if self.status == CheckpointRunStatus.SUBMITTED:
            if self.submission_path is None or self.submission_sha256 is None:
                raise ValueError("submitted checkpoint requires submission path and sha256")
        active_attempts = [attempt for attempt in self.attempts if attempt.status == CheckpointAttemptStatus.ACTIVE]
        if len(active_attempts) > 1:
            raise ValueError("checkpoint cannot have multiple active attempts")
        sequences = [attempt.sequence for attempt in self.attempts]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("checkpoint attempt sequences must be contiguous")
        if self.evidence_request_budget_remaining > self.evidence_request_budget:
            raise ValueError("remaining evidence request budget cannot exceed its initial budget")
        remaining = self.evidence_request_budget
        for action in self.evidence_request_actions:
            if action.checkpoint_id != self.checkpoint_id:
                raise ValueError("evidence request action checkpoint must match its run record")
            if action.budget_before != remaining:
                raise ValueError("evidence request action budget chain is inconsistent")
            remaining = action.budget_after
        if remaining != self.evidence_request_budget_remaining:
            raise ValueError("remaining evidence request budget must match the action history")
        if self.operation_budget_remaining > self.operation_budget:
            raise ValueError("remaining operation budget cannot exceed its initial budget")
        operation_remaining = self.operation_budget
        for operation_action in self.operation_actions:
            if operation_action.checkpoint_id != self.checkpoint_id:
                raise ValueError("operation action checkpoint must match its run record")
            if operation_action.budget_before != operation_remaining:
                raise ValueError("operation action budget chain is inconsistent")
            operation_remaining = operation_action.budget_after
        if operation_remaining != self.operation_budget_remaining:
            raise ValueError("remaining operation budget must match the action history")
        return self

    @property
    def active_attempt(self) -> CheckpointAttemptRecord | None:
        return next(
            (attempt for attempt in reversed(self.attempts) if attempt.status == CheckpointAttemptStatus.ACTIVE),
            None,
        )

    @property
    def last_attempt(self) -> CheckpointAttemptRecord | None:
        return self.attempts[-1] if self.attempts else None


class CheckpointRevisitRecord(StrictModel):
    revisit_id: NonEmptyStr
    checkpoint_id: NonEmptyStr
    requested_from_checkpoint_id: str | None = None
    reason: NonEmptyStr


class LifecycleTransitionRecord(StrictModel):
    transition_id: NonEmptyStr
    kind: LifecycleTransitionKind
    from_checkpoint_id: str | None = None
    to_checkpoint_id: str | None = None
    reason: NonEmptyStr


class LifecycleBranchRecord(StrictModel):
    branch_id: NonEmptyStr
    parent_run_dir: NonEmptyStr
    branched_from_checkpoint_id: NonEmptyStr
    parent_submission_sha256: NonEmptyStr
    parent_action_state_sha256: str | None = None
    reason: NonEmptyStr

    @field_validator("parent_action_state_sha256")
    @classmethod
    def validate_parent_action_state_sha256(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError("parent action state sha256 must contain 64 lowercase hexadecimal characters")
        return value


class EvidenceLifecycleRunState(StrictModel):
    schema_version: Literal["3", "4", "5"] = "4"
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    run_authorization_sha256: str | None = None
    status: LifecycleRunStatus = LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    active_checkpoint_id: str | None = None
    checkpoint_runs: list[CheckpointRunRecord]
    revisits: list[CheckpointRevisitRecord] = Field(default_factory=list)
    transitions: list[LifecycleTransitionRecord] = Field(default_factory=list)
    branch: LifecycleBranchRecord | None = None

    @field_validator("run_authorization_sha256")
    @classmethod
    def validate_run_authorization_sha256(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError("run authorization sha256 must contain 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def validate_run_state(self) -> EvidenceLifecycleRunState:
        checkpoint_ids = [checkpoint.checkpoint_id for checkpoint in self.checkpoint_runs]
        if len(checkpoint_ids) != len(set(checkpoint_ids)):
            raise ValueError("lifecycle state checkpoint ids must be unique")
        active = [checkpoint for checkpoint in self.checkpoint_runs if checkpoint.status == CheckpointRunStatus.ACTIVE]
        if self.status == LifecycleRunStatus.COMPLETE:
            if self.active_checkpoint_id is not None or active:
                raise ValueError("complete lifecycle cannot have an active checkpoint")
            if any(checkpoint.status != CheckpointRunStatus.SUBMITTED for checkpoint in self.checkpoint_runs):
                raise ValueError("complete lifecycle requires every checkpoint to be submitted")
        elif self.status == LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION:
            if self.active_checkpoint_id is None or len(active) != 1:
                raise ValueError("awaiting submission requires exactly one active checkpoint")
            if active[0].checkpoint_id != self.active_checkpoint_id:
                raise ValueError("active checkpoint id must match the active checkpoint record")
        elif self.active_checkpoint_id is not None or active:
            raise ValueError("awaiting evidence release cannot have an active checkpoint")

        order = {
            CheckpointRunStatus.SUBMITTED: 0,
            CheckpointRunStatus.ACTIVE: 1,
            CheckpointRunStatus.PENDING: 2,
        }
        phases = [order[checkpoint.status] for checkpoint in self.checkpoint_runs]
        if phases != sorted(phases):
            raise ValueError("checkpoint statuses must follow submitted, active, then pending order")
        if self.branch is not None and self.branch.branched_from_checkpoint_id not in checkpoint_ids:
            raise ValueError("branch checkpoint must exist in lifecycle state")
        if (
            self.schema_version in {"4", "5"}
            and self.branch is not None
            and self.branch.parent_action_state_sha256 is None
        ):
            raise ValueError(f"v{self.schema_version} branch state requires a parent action state sha256")
        operation_actions = [action for checkpoint in self.checkpoint_runs for action in checkpoint.operation_actions]
        if self.schema_version in {"3", "4"} and (
            operation_actions
            or any(
                checkpoint.operation_budget or checkpoint.operation_budget_remaining
                for checkpoint in self.checkpoint_runs
            )
        ):
            raise ValueError(f"v{self.schema_version} lifecycle state cannot contain operation state")
        for expected_sequence, action in enumerate(operation_actions, start=1):
            expected_action_id = f"operation-{expected_sequence:06d}"
            if action.sequence != expected_sequence or action.action_id != expected_action_id:
                raise ValueError("operation action identities must be contiguous and globally ordered across the run")
        actions = [action for checkpoint in self.checkpoint_runs for action in checkpoint.evidence_request_actions]
        for expected_sequence, evidence_action in enumerate(actions, start=1):
            expected_action_id = f"evidence-request-{expected_sequence:06d}"
            if evidence_action.sequence != expected_sequence or evidence_action.action_id != expected_action_id:
                raise ValueError(
                    "evidence request action identities must be contiguous and globally ordered across the run"
                )
        return self

    def checkpoint(self, checkpoint_id: str) -> CheckpointRunRecord:
        for checkpoint in self.checkpoint_runs:
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        raise KeyError(checkpoint_id)


class LifecycleGateResult(StrictModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    failures: list[str] = Field(default_factory=list)


class LifecycleVerificationResult(StrictModel):
    template_id: str | None = None
    lifecycle_id: NonEmptyStr
    overall: Literal["pass", "fail", "incomplete"]
    passed: bool
    reward: float = Field(ge=0.0, le=1.0)
    gates: dict[str, LifecycleGateResult] = Field(min_length=1)
    semantic_metrics: LifecycleSemanticMetrics | None = None

    @model_validator(mode="after")
    def validate_outcome_consistency(self) -> LifecycleVerificationResult:
        gates_pass = all(gate.passed for gate in self.gates.values())
        if self.passed != (self.overall == "pass"):
            raise ValueError("passed must agree with overall")
        if self.passed != gates_pass:
            raise ValueError("passed must agree with verifier gates")
        return self
