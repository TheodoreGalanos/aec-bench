# ABOUTME: Executes the bounded verifier-guided repair lifecycle over injected trusted boundaries.
# ABOUTME: Enforces exact pairing, lineage, mutation ownership, fresh evidence, and fail-closed diagnostics.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Never

from aec_bench.contracts.harness_instance import TaskSourceBindingConfig
from aec_bench.evolution.paired_repair import (
    PairedRepairAttempt,
    RepairDecision,
    RepairMutationScope,
    decide_repair,
)

from .contracts import (
    CompiledRepairCandidate,
    RepairCandidate,
    RepairDiagnosis,
    RepairExecutionRecoveryAttempt,
    RepairExecutionRecoveryDecision,
    RepairExecutionStatus,
    RepairLoopDiagnostic,
    RepairLoopError,
    RepairLoopRequest,
    RepairLoopResult,
    RepairLoopStage,
    RepairLoopStatus,
    RepairOwner,
    RepairPairingSpec,
    RepairPatchRequest,
    RepairRewardCoverage,
    RepairRunResult,
    VerifiedRepairRun,
)

ProposalGenerator = Callable[[RepairLoopRequest], RepairCandidate]
CandidateCompiler = Callable[[RepairCandidate, RepairPairingSpec], CompiledRepairCandidate]
CandidateRunner = Callable[[CompiledRepairCandidate, RepairPairingSpec], RepairRunResult]
CandidateVerifier = Callable[[CompiledRepairCandidate, RepairRunResult], VerifiedRepairRun]
FailureDiagnoser = Callable[[CompiledRepairCandidate, VerifiedRepairRun], RepairDiagnosis]
CandidatePatcher = Callable[[RepairPatchRequest], RepairCandidate]


@dataclass(frozen=True)
class RepairLoopDependencies:
    """Trusted execution boundaries injected into the closed orchestration kernel."""

    generator: ProposalGenerator
    compiler: CandidateCompiler
    runner: CandidateRunner
    verifier: CandidateVerifier
    diagnoser: FailureDiagnoser
    harness_patcher: CandidatePatcher
    program_patcher: CandidatePatcher


def run_repair_loop(
    request: RepairLoopRequest,
    *,
    dependencies: RepairLoopDependencies,
) -> RepairLoopResult:
    """Execute one propose-compile-run-verify-repair-paired-rerun lifecycle."""
    if request.pairing.split == "holdout":
        _fail(
            stage=RepairLoopStage.PROPOSE,
            code="holdout_repair_prohibited",
            message="holdout tasks cannot participate in repair",
        )

    parent = _invoke(
        stage=RepairLoopStage.PROPOSE,
        code="proposal_failed",
        callback=lambda: RepairCandidate.model_validate(dependencies.generator(request)),
    )
    _validate_parent_candidate(parent, request)
    _validate_source_pairing(parent, request.pairing, stage=RepairLoopStage.PROPOSE)

    compiled_parent = _compile_candidate(parent, request.pairing, dependencies)
    parent_run = _run_candidate(compiled_parent, request.pairing, dependencies)
    parent_verification = _verify_candidate(compiled_parent, parent_run, request.pairing, dependencies)
    if parent_verification.passed:
        return RepairLoopResult(
            loop_id=request.loop_id,
            attempt_id=request.attempt_id,
            iteration=request.iteration,
            status=RepairLoopStatus.NO_REPAIR_REQUIRED,
            parent_candidate_id=parent.candidate_id,
            parent_verification=parent_verification,
        )

    diagnosis = _invoke(
        stage=RepairLoopStage.DIAGNOSE,
        code="diagnosis_failed",
        candidate_id=parent.candidate_id,
        callback=lambda: RepairDiagnosis.model_validate(dependencies.diagnoser(compiled_parent, parent_verification)),
    )
    if diagnosis.candidate_id != parent.candidate_id or diagnosis.run_id != parent_run.run_id:
        _fail(
            stage=RepairLoopStage.DIAGNOSE,
            code="diagnosis_lineage_mismatch",
            message="diagnosis must identify the verified parent run",
            candidate_id=parent.candidate_id,
        )
    if diagnosis.owner is None:
        return RepairLoopResult(
            loop_id=request.loop_id,
            attempt_id=request.attempt_id,
            iteration=request.iteration,
            status=RepairLoopStatus.NO_APPLICABLE_REPAIR,
            parent_candidate_id=parent.candidate_id,
            parent_verification=parent_verification,
            diagnosis=diagnosis,
        )
    if (
        parent_verification.reward_coverage is not RepairRewardCoverage.COMPLETE
        and diagnosis.owner is not RepairOwner.PROGRAM
    ):
        _fail(
            stage=RepairLoopStage.DIAGNOSE,
            code="incomplete_reward_repair_requires_program_owner",
            message="incomplete parent rewards can enter only the program execution-recovery path",
            candidate_id=parent.candidate_id,
        )

    patch_request = RepairPatchRequest(
        parent=parent,
        diagnosis=diagnosis,
        child_candidate_id=request.child_candidate_id,
        iteration=request.iteration,
    )
    patcher = dependencies.harness_patcher if diagnosis.owner is RepairOwner.HARNESS else dependencies.program_patcher
    child = _invoke(
        stage=RepairLoopStage.PATCH,
        code="patch_failed",
        candidate_id=parent.candidate_id,
        callback=lambda: RepairCandidate.model_validate(patcher(patch_request)),
    )
    _validate_child_candidate(parent=parent, child=child, request=request, owner=diagnosis.owner)
    _validate_source_pairing(child, request.pairing, stage=RepairLoopStage.PATCH)

    compiled_child = _compile_candidate(child, request.pairing, dependencies)
    child_run = _run_candidate(compiled_child, request.pairing, dependencies)
    if child_run.run_id == parent_run.run_id:
        _fail(
            stage=RepairLoopStage.RUN,
            code="pre_mutation_run_reused",
            message="post-mutation candidate requires a fresh paired run",
            candidate_id=child.candidate_id,
        )
    child_verification = _verify_candidate(compiled_child, child_run, request.pairing, dependencies)

    if parent_verification.reward_coverage is not RepairRewardCoverage.COMPLETE:
        recovery_attempt = _invoke(
            stage=RepairLoopStage.ACCEPT,
            code="paired_execution_evidence_invalid",
            candidate_id=child.candidate_id,
            callback=lambda: RepairExecutionRecoveryAttempt(
                attempt_id=request.attempt_id,
                iteration=request.iteration,
                parent_candidate_id=parent.candidate_id,
                child_candidate_id=child.candidate_id,
                parent_run_id=parent_verification.run_id,
                child_run_id=child_verification.run_id,
                pairing=request.pairing,
                parent_executions=parent_verification.execution_observations,
                child_executions=child_verification.execution_observations,
            ),
        )
        recovery_decision = _decide_execution_recovery(
            recovery_attempt,
            child_verification=child_verification,
        )
        recovery_status = (
            RepairLoopStatus.RECOVERED_UNSCORED if recovery_decision.recovered else RepairLoopStatus.RECOVERY_FAILED
        )
        return RepairLoopResult(
            loop_id=request.loop_id,
            attempt_id=request.attempt_id,
            iteration=request.iteration,
            status=recovery_status,
            parent_candidate_id=parent.candidate_id,
            child_candidate_id=child.candidate_id,
            parent_verification=parent_verification,
            child_verification=child_verification,
            diagnosis=diagnosis,
            recovery_attempt=recovery_attempt,
            recovery_decision=recovery_decision,
        )

    if child_verification.reward_coverage is not RepairRewardCoverage.COMPLETE:
        return RepairLoopResult(
            loop_id=request.loop_id,
            attempt_id=request.attempt_id,
            iteration=request.iteration,
            status=RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE,
            parent_candidate_id=parent.candidate_id,
            child_candidate_id=child.candidate_id,
            parent_verification=parent_verification,
            child_verification=child_verification,
            diagnosis=diagnosis,
        )

    attempt = _invoke(
        stage=RepairLoopStage.ACCEPT,
        code="paired_evidence_invalid",
        candidate_id=child.candidate_id,
        callback=lambda: PairedRepairAttempt(
            attempt_id=request.attempt_id,
            iteration=request.iteration,
            mutation_scope=(
                RepairMutationScope.HARNESS if diagnosis.owner is RepairOwner.HARNESS else RepairMutationScope.PROGRAM
            ),
            parent_candidate_id=parent.candidate_id,
            child_candidate_id=child.candidate_id,
            parent_outcomes=tuple(observation.outcome for observation in parent_verification.observations),
            child_outcomes=tuple(observation.outcome for observation in child_verification.observations),
        ),
    )
    decision = decide_repair(attempt, request.acceptance_policy)
    if not child_verification.passed and decision.accepted:
        decision = RepairDecision.model_validate(
            {
                **decision.model_dump(mode="json"),
                "accepted": False,
                "reasons": (*decision.reasons, "child_verifier_failed"),
            }
        )
    status = RepairLoopStatus.ACCEPTED if decision.accepted else RepairLoopStatus.REJECTED
    return RepairLoopResult(
        loop_id=request.loop_id,
        attempt_id=request.attempt_id,
        iteration=request.iteration,
        status=status,
        parent_candidate_id=parent.candidate_id,
        child_candidate_id=child.candidate_id,
        parent_verification=parent_verification,
        child_verification=child_verification,
        diagnosis=diagnosis,
        attempt=attempt,
        decision=decision,
    )


def _decide_execution_recovery(
    attempt: RepairExecutionRecoveryAttempt,
    *,
    child_verification: VerifiedRepairRun,
) -> RepairExecutionRecoveryDecision:
    reasons: list[str] = []
    if child_verification.reward_coverage is not RepairRewardCoverage.COMPLETE:
        reasons.append("child_reward_coverage_incomplete")
    if not child_verification.passed:
        reasons.append("child_verifier_failed")
    child_succeeded_count = sum(
        observation.status is RepairExecutionStatus.SUCCEEDED for observation in attempt.child_executions
    )
    if child_succeeded_count != len(attempt.child_executions):
        reasons.append("child_execution_incomplete")
    parent_failed_count = sum(
        observation.status is not RepairExecutionStatus.SUCCEEDED for observation in attempt.parent_executions
    )
    return RepairExecutionRecoveryDecision(
        attempt_id=attempt.attempt_id,
        parent_candidate_id=attempt.parent_candidate_id,
        child_candidate_id=attempt.child_candidate_id,
        recovered=not reasons,
        reasons=tuple(reasons),
        paired_execution_count=len(attempt.parent_executions),
        parent_failed_count=parent_failed_count,
        child_succeeded_count=child_succeeded_count,
    )


def _compile_candidate(
    candidate: RepairCandidate,
    pairing: RepairPairingSpec,
    dependencies: RepairLoopDependencies,
) -> CompiledRepairCandidate:
    compiled = _invoke(
        stage=RepairLoopStage.COMPILE,
        code="compile_failed",
        candidate_id=candidate.candidate_id,
        callback=lambda: CompiledRepairCandidate.model_validate(dependencies.compiler(candidate, pairing)),
    )
    if (
        compiled.candidate_id != candidate.candidate_id
        or compiled.parent_candidate_id != candidate.parent_candidate_id
        or compiled.iteration != candidate.iteration
    ):
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_candidate_lineage_mismatch",
            message="compiled candidate must preserve source candidate lineage",
            candidate_id=candidate.candidate_id,
        )
    if compiled.harness.source_recipe_sha256 != candidate.harness_request.recipe.content_sha256:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_harness_source_mismatch",
            message="compiled harness must derive from the candidate Hx recipe",
            candidate_id=candidate.candidate_id,
        )
    expected_program = candidate.program_template.bind(compiled.harness.ref)
    if compiled.program.source_program_sha256 != expected_program.content_sha256:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_program_source_mismatch",
            message="compiled program must derive from the candidate px template",
            candidate_id=candidate.candidate_id,
        )
    if compiled.harness.kernel_ref != candidate.harness_request.kernel_ref:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_kernel_mismatch",
            message="compiled candidate must preserve the proposed fixed kernel",
            candidate_id=candidate.candidate_id,
        )
    if compiled.harness.budget != pairing.budget:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_budget_mismatch",
            message="compiled candidate budget must match the exact paired budget",
            candidate_id=candidate.candidate_id,
        )
    if compiled.bundle.harbor.task_refs != pairing.task_ids:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_tasks_mismatch",
            message="compiled candidate tasks must match the exact paired tasks",
            candidate_id=candidate.candidate_id,
        )
    if compiled.bundle.harbor.repetitions != pairing.repetitions:
        _fail(
            stage=RepairLoopStage.COMPILE,
            code="compiled_repetitions_mismatch",
            message="compiled candidate repetitions must match the exact paired repetitions",
            candidate_id=candidate.candidate_id,
        )
    return compiled


def _run_candidate(
    candidate: CompiledRepairCandidate,
    pairing: RepairPairingSpec,
    dependencies: RepairLoopDependencies,
) -> RepairRunResult:
    run = _invoke(
        stage=RepairLoopStage.RUN,
        code="run_failed",
        candidate_id=candidate.candidate_id,
        callback=lambda: RepairRunResult.model_validate(dependencies.runner(candidate, pairing)),
    )
    if run.candidate_id != candidate.candidate_id:
        _fail(
            stage=RepairLoopStage.RUN,
            code="run_candidate_mismatch",
            message="runner result must identify the compiled candidate",
            candidate_id=candidate.candidate_id,
        )
    if run.pairing != pairing:
        _fail(
            stage=RepairLoopStage.RUN,
            code="run_pairing_mismatch",
            message="runner must preserve exact tasks, seeds, budget, and repetitions",
            candidate_id=candidate.candidate_id,
        )
    return run


def _verify_candidate(
    candidate: CompiledRepairCandidate,
    run: RepairRunResult,
    pairing: RepairPairingSpec,
    dependencies: RepairLoopDependencies,
) -> VerifiedRepairRun:
    verification = _invoke(
        stage=RepairLoopStage.VERIFY,
        code="verification_failed",
        candidate_id=candidate.candidate_id,
        callback=lambda: VerifiedRepairRun.model_validate(dependencies.verifier(candidate, run)),
    )
    if verification.candidate_id != candidate.candidate_id:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_candidate_mismatch",
            message="verification must identify the current compiled candidate",
            candidate_id=candidate.candidate_id,
        )
    if verification.run_id != run.run_id:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_run_mismatch",
            message="verification must derive from the current fresh run",
            candidate_id=candidate.candidate_id,
        )
    if verification.pairing != pairing:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_pairing_mismatch",
            message="verification must preserve the exact paired run identity",
            candidate_id=candidate.candidate_id,
        )
    if verification.harness_sha256 != candidate.harness.content_sha256:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_harness_mismatch",
            message="verification must identify the current compiled harness",
            candidate_id=candidate.candidate_id,
        )
    if verification.program_sha256 != candidate.program.content_sha256:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_program_mismatch",
            message="verification must identify the current compiled program",
            candidate_id=candidate.candidate_id,
        )
    if verification.run_artifact_sha256 != run.artifact_sha256:
        _fail(
            stage=RepairLoopStage.VERIFY,
            code="verification_artifact_mismatch",
            message="verification must derive from the current run artifact",
            candidate_id=candidate.candidate_id,
        )
    return verification


def _validate_parent_candidate(parent: RepairCandidate, request: RepairLoopRequest) -> None:
    if parent.candidate_id != request.parent_candidate_id:
        _fail(
            stage=RepairLoopStage.PROPOSE,
            code="parent_candidate_id_mismatch",
            message="generator must return the requested parent candidate",
        )
    if parent.iteration != request.iteration - 1:
        _fail(
            stage=RepairLoopStage.PROPOSE,
            code="parent_iteration_mismatch",
            message="parent candidate iteration must immediately precede the repair iteration",
            candidate_id=parent.candidate_id,
        )


def _validate_child_candidate(
    *,
    parent: RepairCandidate,
    child: RepairCandidate,
    request: RepairLoopRequest,
    owner: RepairOwner,
) -> None:
    if child.candidate_id != request.child_candidate_id:
        _fail(
            stage=RepairLoopStage.PATCH,
            code="child_candidate_id_mismatch",
            message="patcher must return the requested child candidate",
            candidate_id=parent.candidate_id,
        )
    if child.parent_candidate_id != parent.candidate_id:
        _fail(
            stage=RepairLoopStage.PATCH,
            code="child_parent_id_mismatch",
            message="repair child must preserve its exact parent candidate id",
            candidate_id=child.candidate_id,
        )
    if child.iteration != request.iteration:
        _fail(
            stage=RepairLoopStage.PATCH,
            code="child_iteration_mismatch",
            message="repair child must preserve the requested repair iteration",
            candidate_id=child.candidate_id,
        )
    if child.harness_request.kernel_ref != parent.harness_request.kernel_ref:
        _fail(
            stage=RepairLoopStage.PATCH,
            code="fixed_kernel_mutated",
            message="repair cannot mutate the fixed kernel reference",
            candidate_id=child.candidate_id,
        )
    if owner is RepairOwner.HARNESS:
        if child.program_template != parent.program_template:
            _fail(
                stage=RepairLoopStage.PATCH,
                code="non_owned_program_mutated",
                message="harness-owned repair cannot mutate px",
                candidate_id=child.candidate_id,
            )
        if child.harness_request == parent.harness_request:
            _fail(
                stage=RepairLoopStage.PATCH,
                code="owned_harness_not_mutated",
                message="harness-owned repair must change Hx",
                candidate_id=child.candidate_id,
            )
    else:
        if child.harness_request != parent.harness_request:
            _fail(
                stage=RepairLoopStage.PATCH,
                code="non_owned_harness_mutated",
                message="program-owned repair cannot mutate Hx",
                candidate_id=child.candidate_id,
            )
        if child.program_template == parent.program_template:
            _fail(
                stage=RepairLoopStage.PATCH,
                code="owned_program_not_mutated",
                message="program-owned repair must change px",
                candidate_id=child.candidate_id,
            )


def _validate_source_pairing(
    candidate: RepairCandidate,
    pairing: RepairPairingSpec,
    *,
    stage: RepairLoopStage,
) -> None:
    if candidate.harness_request.recipe.budget != pairing.budget:
        _fail(
            stage=stage,
            code="source_budget_mismatch",
            message="candidate Hx budget must match the exact paired budget",
            candidate_id=candidate.candidate_id,
        )
    task_configurations = [
        binding.configuration
        for binding in candidate.harness_request.recipe.bindings
        if isinstance(binding.configuration, TaskSourceBindingConfig)
    ]
    if len(task_configurations) != 1 or task_configurations[0].task_refs != pairing.task_ids:
        _fail(
            stage=stage,
            code="source_tasks_mismatch",
            message="candidate Hx tasks must match the exact paired tasks",
            candidate_id=candidate.candidate_id,
        )


def _invoke[ResultT](
    *,
    stage: RepairLoopStage,
    code: str,
    callback: Callable[[], ResultT],
    candidate_id: str | None = None,
) -> ResultT:
    try:
        return callback()
    except RepairLoopError:
        raise
    except Exception as exc:
        message = str(exc).strip() or type(exc).__name__
        raise RepairLoopError(
            RepairLoopDiagnostic(
                stage=stage,
                code=code,
                message=message,
                candidate_id=candidate_id,
            )
        ) from exc


def _fail(
    *,
    stage: RepairLoopStage,
    code: str,
    message: str,
    candidate_id: str | None = None,
) -> Never:
    raise RepairLoopError(
        RepairLoopDiagnostic(
            stage=stage,
            code=code,
            message=message,
            candidate_id=candidate_id,
        )
    )
