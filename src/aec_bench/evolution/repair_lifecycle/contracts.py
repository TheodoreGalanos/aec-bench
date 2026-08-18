# ABOUTME: Defines immutable evidence and lineage contracts for verifier-guided Hx-or-px repair.
# ABOUTME: Enforces pairing, reward coverage, execution recovery, and terminal-result invariants.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import (
    CompiledExecutionProgram,
    ExecutionProgram,
    ExecutionProgramRef,
    ProgramLimits,
    ProgramNode,
)
from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessInstanceRef,
)
from aec_bench.contracts.harness_kernel import FrozenStrictModel, validate_sha256
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.paired_repair import (
    PairedRepairAttempt,
    RepairAcceptancePolicy,
    RepairDecision,
    RepairTrialOutcome,
)


class RepairOwner(StrEnum):
    """Only mutable surfaces that verifier-guided repair may own."""

    HARNESS = "harness"
    PROGRAM = "program"


class RepairFailureDomain(StrEnum):
    """Evidence-attributed failure domain, including surfaces outside repair authority."""

    HARNESS = "harness"
    PROGRAM = "program"
    TASK_WORLD = "task_world"
    VERIFIER = "verifier"
    RUNTIME = "runtime"
    UNDETERMINED = "undetermined"


class RepairLoopStage(StrEnum):
    """Closed lifecycle stages used by fail-closed diagnostics."""

    PROPOSE = "propose"
    COMPILE = "compile"
    RUN = "run"
    VERIFY = "verify"
    DIAGNOSE = "diagnose"
    PATCH = "patch"
    ACCEPT = "accept"


class RepairLoopStatus(StrEnum):
    """Terminal outcomes of one bounded repair attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHILD_EVIDENCE_INCOMPLETE = "child_evidence_incomplete"
    RECOVERED_UNSCORED = "recovered_unscored"
    RECOVERY_FAILED = "recovery_failed"
    NO_REPAIR_REQUIRED = "no_repair_required"
    NO_APPLICABLE_REPAIR = "no_applicable_repair"


class RepairRewardCoverage(StrEnum):
    """How much of the preregistered verifier-reward matrix a run produced."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"


class RepairExecutionStatus(StrEnum):
    """Seed-level terminal state used independently of verifier reward."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


class RepairPairingSpec(FrozenStrictModel):
    """Exact task, seed, budget, and repetition identity for both paired arms."""

    split: Literal["discovery", "repair_gate", "calibration", "holdout"]
    task_ids: tuple[NonEmptyStr, ...]
    seeds: tuple[int, ...]
    budget: HarnessBudget
    repetitions: PositiveInt

    @model_validator(mode="after")
    def validate_pairing(self) -> Self:
        if self.split == "holdout":
            raise ValueError("holdout tasks cannot participate in repair")
        if not self.task_ids:
            raise ValueError("repair pairing requires at least one task")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("repair pairing task ids must be unique")
        if len(self.seeds) != self.repetitions:
            raise ValueError("repair pairing requires exactly one seed per repetition")
        if len(self.seeds) != len(set(self.seeds)):
            raise ValueError("repair pairing seeds must be unique")
        return self


class RepairProgramTemplate(FrozenStrictModel):
    """Harness-independent px source rebound to each freshly compiled Hx."""

    program_id: NonEmptyStr
    version: NonEmptyStr
    nodes: tuple[ProgramNode, ...]
    limits: ProgramLimits = Field(default_factory=ProgramLimits)

    def bind(self, harness_ref: HarnessInstanceRef) -> ExecutionProgram:
        """Bind this px source to one exact compiled Hx reference."""
        return ExecutionProgram(
            program_id=self.program_id,
            version=self.version,
            harness_ref=harness_ref,
            nodes=self.nodes,
            limits=self.limits,
        )


class RepairCandidate(FrozenStrictModel):
    """Proposed Hx and px sources with explicit parent/child iteration lineage."""

    candidate_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr | None
    iteration: NonNegativeInt
    harness_request: HarnessCompileRequest
    program_template: RepairProgramTemplate


class CompiledRepairCandidate(FrozenStrictModel):
    """Candidate resolved into exact Hx, px, and executable RunBundle contracts."""

    candidate_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr | None
    iteration: NonNegativeInt
    harness: CompiledHarnessInstance
    program: CompiledExecutionProgram
    bundle: RunBundle

    @model_validator(mode="after")
    def validate_compiled_identity(self) -> Self:
        if self.bundle.harness != self.harness:
            raise ValueError("compiled repair bundle must contain the candidate harness")
        if self.bundle.program != self.program:
            raise ValueError("compiled repair bundle must contain the candidate program")
        return self


class RepairRunResult(FrozenStrictModel):
    """Unscored execution artifact returned by the injected trusted runner."""

    run_id: NonEmptyStr
    candidate_id: NonEmptyStr
    pairing: RepairPairingSpec
    artifact_sha256: str

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class RepairRunObservation(FrozenStrictModel):
    """One seed-pinned verifier outcome within an exact paired run."""

    seed: int
    outcome: RepairTrialOutcome


class RepairExecutionObservation(FrozenStrictModel):
    """One seed-pinned execution result that never invents a verifier reward."""

    repetition: PositiveInt
    seed: int
    status: RepairExecutionStatus
    error_code: NonEmptyStr | None = None
    failed_node_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_failure_evidence(self) -> Self:
        if self.status is RepairExecutionStatus.SUCCEEDED and (
            self.error_code is not None or self.failed_node_id is not None
        ):
            raise ValueError("successful execution observations cannot contain failure evidence")
        if self.status is RepairExecutionStatus.FAILED and self.error_code is None:
            raise ValueError("failed execution observations require an error code")
        return self


class VerifiedRepairRun(FrozenStrictModel):
    """Fresh verifier evidence pinned to one run and compiled candidate identity."""

    verification_id: NonEmptyStr
    run_id: NonEmptyStr
    candidate_id: NonEmptyStr
    harness_ref: HarnessInstanceRef
    program_ref: ExecutionProgramRef
    run_artifact_sha256: str
    pairing: RepairPairingSpec
    passed: bool
    reward_coverage: RepairRewardCoverage = RepairRewardCoverage.COMPLETE
    observations: tuple[RepairRunObservation, ...] = ()
    execution_observations: tuple[RepairExecutionObservation, ...] = ()
    diagnostics: tuple[NonEmptyStr, ...] = ()

    @field_validator("run_artifact_sha256")
    @classmethod
    def validate_identity_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_observations(self) -> Self:
        _validate_reward_observation_identity(self)
        expected_coordinates = _expected_reward_coordinates(self.pairing)
        actual_coordinates = _actual_reward_coordinates(self)
        _validate_reward_coordinates(self, expected=expected_coordinates, actual=actual_coordinates)
        _validate_reward_coverage(self, expected=expected_coordinates, actual=actual_coordinates)
        _validate_execution_observations(self)
        _validate_passing_run(self)
        return self


RewardCoordinate = tuple[str, int, int]


def _validate_reward_observation_identity(run: VerifiedRepairRun) -> None:
    if any(observation.outcome.candidate_id != run.candidate_id for observation in run.observations):
        raise ValueError("verified outcomes must identify the verified candidate")
    if any(observation.outcome.split != run.pairing.split for observation in run.observations):
        raise ValueError("verified outcomes must use the exact repair split")
    block_ids = [observation.outcome.block_id for observation in run.observations]
    if len(block_ids) != len(set(block_ids)):
        raise ValueError("verified repair outcomes must use unique blocks")


def _expected_reward_coordinates(pairing: RepairPairingSpec) -> set[RewardCoordinate]:
    return {
        (task_id, repetition, seed)
        for task_id in pairing.task_ids
        for repetition, seed in enumerate(pairing.seeds, start=1)
    }


def _actual_reward_coordinates(run: VerifiedRepairRun) -> set[RewardCoordinate]:
    return {
        (
            observation.outcome.task_world_id,
            observation.outcome.repetition,
            observation.seed,
        )
        for observation in run.observations
    }


def _validate_reward_coordinates(
    run: VerifiedRepairRun,
    *,
    expected: set[RewardCoordinate],
    actual: set[RewardCoordinate],
) -> None:
    if len(actual) != len(run.observations):
        raise ValueError("verified repair outcomes must use unique task, repetition, and seed coordinates")
    if not actual.issubset(expected):
        raise ValueError("verified outcomes must use only preregistered task, repetition, and seed coordinates")


def _validate_reward_coverage(
    run: VerifiedRepairRun,
    *,
    expected: set[RewardCoordinate],
    actual: set[RewardCoordinate],
) -> None:
    if run.reward_coverage is RepairRewardCoverage.COMPLETE:
        if actual != expected or len(run.observations) != len(expected):
            raise ValueError("verified outcomes must cover every exact task, repetition, and seed")
        return
    if run.reward_coverage is RepairRewardCoverage.PARTIAL:
        if not actual or actual == expected:
            raise ValueError("partial reward coverage requires a non-empty strict subset of verified outcomes")
        return
    if run.observations:
        raise ValueError("no reward coverage cannot contain verified outcomes")


def _validate_execution_observations(run: VerifiedRepairRun) -> None:
    expected = set(enumerate(run.pairing.seeds, start=1))
    actual = {(observation.repetition, observation.seed) for observation in run.execution_observations}
    if len(actual) != len(run.execution_observations):
        raise ValueError("repair execution observations must use unique repetition and seed coordinates")
    if run.execution_observations and actual != expected:
        raise ValueError("repair execution observations must cover every exact repetition and seed")
    if run.reward_coverage is not RepairRewardCoverage.COMPLETE and actual != expected:
        raise ValueError("incomplete reward coverage requires exact execution observations")


def _validate_passing_run(run: VerifiedRepairRun) -> None:
    if run.passed and run.reward_coverage is not RepairRewardCoverage.COMPLETE:
        raise ValueError("a passing repair run requires complete verifier reward coverage")
    if run.passed and any(
        observation.status is not RepairExecutionStatus.SUCCEEDED for observation in run.execution_observations
    ):
        raise ValueError("a passing repair run cannot contain unsuccessful execution observations")


class RepairExecutionRecoveryAttempt(FrozenStrictModel):
    """Matched parent-child execution evidence used only when parent rewards are incomplete."""

    attempt_id: NonEmptyStr
    iteration: PositiveInt
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    parent_run_id: NonEmptyStr
    child_run_id: NonEmptyStr
    pairing: RepairPairingSpec
    parent_executions: tuple[RepairExecutionObservation, ...] = Field(min_length=1)
    child_executions: tuple[RepairExecutionObservation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_matched_executions(self) -> Self:
        if self.parent_candidate_id == self.child_candidate_id:
            raise ValueError("execution recovery child must differ from its parent")
        expected = set(enumerate(self.pairing.seeds, start=1))
        parent_coordinates = {(item.repetition, item.seed) for item in self.parent_executions}
        child_coordinates = {(item.repetition, item.seed) for item in self.child_executions}
        if (
            len(parent_coordinates) != len(self.parent_executions)
            or len(child_coordinates) != len(self.child_executions)
            or parent_coordinates != expected
            or child_coordinates != expected
        ):
            raise ValueError("execution recovery requires exact matched repetition and seed observations")
        if all(item.status is RepairExecutionStatus.SUCCEEDED for item in self.parent_executions):
            raise ValueError("execution recovery requires at least one unsuccessful parent execution")
        return self


class RepairExecutionRecoveryDecision(FrozenStrictModel):
    """Execution-only recovery result that deliberately makes no reward-improvement claim."""

    attempt_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    recovered: bool
    reasons: tuple[NonEmptyStr, ...]
    paired_execution_count: PositiveInt
    parent_failed_count: PositiveInt
    child_succeeded_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_recovery_decision(self) -> Self:
        if self.recovered == bool(self.reasons):
            raise ValueError("execution recovery is successful exactly when no rejection reasons remain")
        if self.child_succeeded_count > self.paired_execution_count:
            raise ValueError("successful child execution count cannot exceed paired execution count")
        return self


class RepairDiagnosis(FrozenStrictModel):
    """Evidence-derived attribution, which may deliberately name no mutable owner."""

    candidate_id: NonEmptyStr
    run_id: NonEmptyStr
    failure_domain: RepairFailureDomain
    owner: RepairOwner | None
    code: NonEmptyStr
    message: NonEmptyStr
    evidence_codes: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_failure_domain(self) -> Self:
        expected_owner = {
            RepairFailureDomain.HARNESS: RepairOwner.HARNESS,
            RepairFailureDomain.PROGRAM: RepairOwner.PROGRAM,
        }.get(self.failure_domain)
        if self.owner is not None and self.owner is not expected_owner:
            raise ValueError("repair owner must agree with its evidence-attributed failure domain")
        if len(self.evidence_codes) != len(set(self.evidence_codes)):
            raise ValueError("repair diagnosis evidence codes must be unique")
        return self


class RepairPatchRequest(FrozenStrictModel):
    """Typed child-lineage request supplied to the selected trusted patcher."""

    parent: RepairCandidate
    diagnosis: RepairDiagnosis
    child_candidate_id: NonEmptyStr
    iteration: PositiveInt


class RepairLoopRequest(FrozenStrictModel):
    """One bounded repair attempt with expected identities and acceptance policy."""

    loop_id: NonEmptyStr
    attempt_id: NonEmptyStr
    iteration: PositiveInt
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    pairing: RepairPairingSpec
    acceptance_policy: RepairAcceptancePolicy

    @model_validator(mode="after")
    def validate_candidate_ids(self) -> Self:
        if self.parent_candidate_id == self.child_candidate_id:
            raise ValueError("repair child candidate must differ from its parent")
        return self


class RepairLoopResult(FrozenStrictModel):
    """Typed terminal record for scored repair, unscored recovery, or abstention."""

    loop_id: NonEmptyStr
    attempt_id: NonEmptyStr
    iteration: PositiveInt
    status: RepairLoopStatus
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr | None = None
    parent_verification: VerifiedRepairRun
    child_verification: VerifiedRepairRun | None = None
    diagnosis: RepairDiagnosis | None = None
    attempt: PairedRepairAttempt | None = None
    decision: RepairDecision | None = None
    recovery_attempt: RepairExecutionRecoveryAttempt | None = None
    recovery_decision: RepairExecutionRecoveryDecision | None = None

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> Self:
        _validate_status_evidence(self)
        _validate_verification_identities(self)
        _validate_paired_attempt_lineage(self)
        _validate_recovery_attempt_lineage(self)
        _validate_recovery_decision_lineage(self)
        return self


def _validate_status_evidence(result: RepairLoopResult) -> None:
    if result.status is RepairLoopStatus.NO_REPAIR_REQUIRED:
        _validate_no_repair_result(result)
        return
    if result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR:
        _validate_no_applicable_repair_result(result)
        return
    if result.status in {RepairLoopStatus.ACCEPTED, RepairLoopStatus.REJECTED}:
        _validate_scored_repair_result(result)
        return
    if result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE:
        _validate_incomplete_child_result(result)
        return
    _validate_execution_recovery_result(result)


def _child_fields(result: RepairLoopResult) -> tuple[str | None, VerifiedRepairRun | None]:
    return result.child_candidate_id, result.child_verification


def _reward_fields(result: RepairLoopResult) -> tuple[PairedRepairAttempt | None, RepairDecision | None]:
    return result.attempt, result.decision


def _recovery_fields(
    result: RepairLoopResult,
) -> tuple[RepairExecutionRecoveryAttempt | None, RepairExecutionRecoveryDecision | None]:
    return result.recovery_attempt, result.recovery_decision


def _validate_no_repair_result(result: RepairLoopResult) -> None:
    evidence = (*_child_fields(result), *_reward_fields(result), *_recovery_fields(result))
    if result.diagnosis is not None or any(field is not None for field in evidence):
        raise ValueError("no-repair result cannot contain child repair evidence")


def _validate_no_applicable_repair_result(result: RepairLoopResult) -> None:
    if result.diagnosis is None or result.diagnosis.owner is not None:
        raise ValueError("no-applicable-repair result requires an unowned diagnosis")
    evidence = (*_child_fields(result), *_reward_fields(result), *_recovery_fields(result))
    if any(field is not None for field in evidence):
        raise ValueError("no-applicable-repair result cannot contain child repair evidence")


def _validate_scored_repair_result(result: RepairLoopResult) -> None:
    if (
        result.diagnosis is None
        or result.diagnosis.owner is None
        or any(field is None for field in _child_fields(result))
    ):
        raise ValueError("scored repair result requires child and mutable diagnosis evidence")
    if any(field is None for field in _reward_fields(result)) or any(
        field is not None for field in _recovery_fields(result)
    ):
        raise ValueError("scored repair result requires only a paired reward attempt and decision")
    assert result.child_verification is not None
    assert result.attempt is not None
    assert result.decision is not None
    _validate_scored_reward_evidence(result)
    _validate_scored_decision(result)


def _validate_scored_reward_evidence(result: RepairLoopResult) -> None:
    assert result.child_verification is not None
    assert result.attempt is not None
    if (
        result.parent_verification.reward_coverage is not RepairRewardCoverage.COMPLETE
        or result.child_verification.reward_coverage is not RepairRewardCoverage.COMPLETE
    ):
        raise ValueError("scored repair result requires complete reward coverage for parent and child")
    parent_outcomes = tuple(observation.outcome for observation in result.parent_verification.observations)
    child_outcomes = tuple(observation.outcome for observation in result.child_verification.observations)
    if result.attempt.parent_outcomes != parent_outcomes:
        raise ValueError("scored repair parent outcomes must equal parent verification observations")
    if result.attempt.child_outcomes != child_outcomes:
        raise ValueError("scored repair child outcomes must equal child verification observations")


def _validate_scored_decision(result: RepairLoopResult) -> None:
    assert result.child_verification is not None
    assert result.decision is not None
    if (result.status is RepairLoopStatus.ACCEPTED) != result.decision.accepted:
        raise ValueError("repair result status must match its acceptance decision")
    if result.status is RepairLoopStatus.ACCEPTED and not result.child_verification.passed:
        raise ValueError("accepted scored repair requires a passing child verification")


def _validate_incomplete_child_result(result: RepairLoopResult) -> None:
    if (
        result.diagnosis is None
        or result.diagnosis.owner is None
        or any(field is None for field in _child_fields(result))
    ):
        raise ValueError("incomplete-child result requires child and mutable diagnosis evidence")
    if any(field is not None for field in (*_reward_fields(result), *_recovery_fields(result))):
        raise ValueError("incomplete-child result cannot contain a scored or recovery decision")
    assert result.child_verification is not None
    if result.parent_verification.reward_coverage is not RepairRewardCoverage.COMPLETE:
        raise ValueError("incomplete-child result requires complete parent reward coverage")
    if result.child_verification.reward_coverage is RepairRewardCoverage.COMPLETE:
        raise ValueError("incomplete-child result requires incomplete child reward coverage")


def _validate_execution_recovery_result(result: RepairLoopResult) -> None:
    if (
        result.diagnosis is None
        or result.diagnosis.owner is not RepairOwner.PROGRAM
        or any(field is None for field in _child_fields(result))
    ):
        raise ValueError("execution recovery requires child and program-owned diagnosis evidence")
    if any(field is not None for field in _reward_fields(result)) or any(
        field is None for field in _recovery_fields(result)
    ):
        raise ValueError("execution recovery requires only a recovery attempt and decision")
    assert result.child_verification is not None
    assert result.recovery_attempt is not None
    assert result.recovery_decision is not None
    _validate_recovery_evidence(result)
    _validate_recovery_status(result)


def _validate_recovery_evidence(result: RepairLoopResult) -> None:
    assert result.child_verification is not None
    assert result.recovery_attempt is not None
    if result.parent_verification.reward_coverage is RepairRewardCoverage.COMPLETE:
        raise ValueError("execution recovery requires incomplete parent reward coverage")
    if result.recovery_attempt.parent_executions != result.parent_verification.execution_observations:
        raise ValueError("recovery parent executions must equal parent verification execution observations")
    if result.recovery_attempt.child_executions != result.child_verification.execution_observations:
        raise ValueError("recovery child executions must equal child verification execution observations")


def _validate_recovery_status(result: RepairLoopResult) -> None:
    assert result.child_verification is not None
    assert result.recovery_attempt is not None
    assert result.recovery_decision is not None
    if (result.status is RepairLoopStatus.RECOVERED_UNSCORED) != result.recovery_decision.recovered:
        raise ValueError("repair result status must match its execution recovery decision")
    if result.status is not RepairLoopStatus.RECOVERED_UNSCORED:
        return
    if (
        result.child_verification.reward_coverage is not RepairRewardCoverage.COMPLETE
        or not result.child_verification.passed
    ):
        raise ValueError("recovered-unscored result requires a complete passing child verification")
    if any(
        observation.status is not RepairExecutionStatus.SUCCEEDED
        for observation in result.recovery_attempt.child_executions
    ):
        raise ValueError("recovered-unscored result requires every child execution to succeed")


def _validate_verification_identities(result: RepairLoopResult) -> None:
    if result.parent_verification.candidate_id != result.parent_candidate_id:
        raise ValueError("repair result parent verification must identify the parent candidate")
    if result.child_verification is not None and result.child_candidate_id != result.child_verification.candidate_id:
        raise ValueError("repair result child verification must identify the child candidate")


def _validate_paired_attempt_lineage(result: RepairLoopResult) -> None:
    if result.attempt is not None and (
        result.attempt.attempt_id != result.attempt_id
        or result.attempt.iteration != result.iteration
        or result.attempt.parent_candidate_id != result.parent_candidate_id
        or result.attempt.child_candidate_id != result.child_candidate_id
    ):
        raise ValueError("repair result paired attempt must preserve loop lineage")


def _validate_recovery_attempt_lineage(result: RepairLoopResult) -> None:
    if result.recovery_attempt is not None and (
        result.recovery_attempt.attempt_id != result.attempt_id
        or result.recovery_attempt.iteration != result.iteration
        or result.recovery_attempt.parent_candidate_id != result.parent_candidate_id
        or result.recovery_attempt.child_candidate_id != result.child_candidate_id
        or result.recovery_attempt.parent_run_id != result.parent_verification.run_id
        or result.child_verification is None
        or result.recovery_attempt.child_run_id != result.child_verification.run_id
    ):
        raise ValueError("repair result execution recovery attempt must preserve loop lineage")


def _validate_recovery_decision_lineage(result: RepairLoopResult) -> None:
    if result.recovery_decision is not None and (
        result.recovery_decision.attempt_id != result.attempt_id
        or result.recovery_decision.parent_candidate_id != result.parent_candidate_id
        or result.recovery_decision.child_candidate_id != result.child_candidate_id
    ):
        raise ValueError("repair result execution recovery decision must preserve loop lineage")


class RepairLoopDiagnostic(FrozenStrictModel):
    """Stable fail-closed diagnostic for dependency or invariant failures."""

    stage: RepairLoopStage
    code: NonEmptyStr
    message: NonEmptyStr
    candidate_id: NonEmptyStr | None = None


class RepairLoopError(RuntimeError):
    """Raised whenever a repair dependency or closed invariant fails."""

    def __init__(self, diagnostic: RepairLoopDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)
