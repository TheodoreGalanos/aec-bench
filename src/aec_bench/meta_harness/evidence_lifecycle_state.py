# ABOUTME: Defines durable runtime records for evidence-lifecycle runs and checkpoints.
# ABOUTME: Models recovery lineage and reward-independent semantic diagnostics independently of task content.

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, PositiveInt, model_validator

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
    RELEASE = "release"
    SUBMIT = "submit"
    REVISIT = "revisit"


class CheckpointAttemptRecord(StrictModel):
    attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    sequence: PositiveInt
    execution_mode: NonEmptyStr
    status: CheckpointAttemptStatus
    resumed_from_attempt_id: str | None = None
    failure_kind: str | None = None


class CheckpointRunRecord(StrictModel):
    checkpoint_id: NonEmptyStr
    status: CheckpointRunStatus = CheckpointRunStatus.PENDING
    released_files: list[str] = Field(default_factory=list)
    submission_path: str | None = None
    submission_sha256: str | None = None
    attempts: list[CheckpointAttemptRecord] = Field(default_factory=list)
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
    reason: NonEmptyStr


class EvidenceLifecycleRunState(StrictModel):
    schema_version: Literal["3"] = "3"
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    status: LifecycleRunStatus = LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    active_checkpoint_id: str | None = None
    checkpoint_runs: list[CheckpointRunRecord]
    revisits: list[CheckpointRevisitRecord] = Field(default_factory=list)
    transitions: list[LifecycleTransitionRecord] = Field(default_factory=list)
    branch: LifecycleBranchRecord | None = None

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
