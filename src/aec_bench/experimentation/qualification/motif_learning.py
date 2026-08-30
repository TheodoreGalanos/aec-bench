# ABOUTME: Converts verified harness-program and paired-repair evidence into typed Hx/px motif evaluations.
# ABOUTME: Separates non-authoritative recommendations, governed selection, and historical replay.

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.execution_program import (
    ActionNode,
    BranchNode,
    ExecutionProgramRef,
    FanoutNode,
    JoinNode,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    ContextBindingConfig,
    HarnessInstanceRef,
    HarnessSpec,
    TaskSourceBindingConfig,
    ToolBindingConfig,
)
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
    kernel_abi_commitment,
    validate_sha256,
)
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.paired_repair import RepairTrialOutcome, decide_repair
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairLoopStatus,
    RepairProgramTemplate,
)
from aec_bench.experimentation.governance.applicability import (
    MotifApplicabilityAttestation,
    profile_task_applicability,
)
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.motif_assurance import (
    AssuredMotifSelectionRecord,
    MotifAssuranceAuthorityError,
    MotifAssuranceBoundary,
    MotifAssuranceSnapshot,
    assert_assured_motif_selection_current,
)
from aec_bench.experimentation.governance.motifs import (
    HarnessProgramEvidenceReference,
    HarnessProgramMotif,
    MotifLibrary,
    MotifPromotionDecision,
    MotifPromotionPolicy,
    MotifSelectionDecision,
    MotifSelectionRequest,
    MotifStatus,
    MotifStructuralDescriptor,
    PairedRepairEvidenceReference,
    QualityEvidenceReference,
    TransferEvidenceReference,
    apply_motif_promotion,
    decide_motif_promotion,
    resolve_motif_selection,
    select_motif,
)
from aec_bench.experimentation.qualification.harness_program_study import (
    HarnessProgramStudyReport,
    harness_program_study_evidence,
    verify_harness_program_study_report,
)
from aec_bench.experimentation.qualification.harness_program_study.candidates import ProgramFactorTemplate
from aec_bench.experimentation.qualification.harness_program_study.plan import HarnessProgramCell
from aec_bench.experimentation.qualification.motif_materialization import (
    InstantiatedMotifFactors,
    MotifHarnessProgramInstantiationRequest,
    encode_harness_motif_template,
    encode_program_motif_template,
    instantiate_selected_motif_factors,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    RepairAttemptPlan,
    RepairRuntimeExecution,
    RepairTerminalRecord,
    StoredRepairArtifact,
)
from aec_bench.harness.compilation import compile_execution_program, compile_harness_instance
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry

SelectionSplit = Literal["discovery", "calibration"]


class AcceptedRepairEvidence(ContentAddressedModel):
    """Accepted paired-repair evidence pinned to its persisted terminal artifact and child Hx/px."""

    schema_version: Literal["aecbench.accepted-repair-evidence.v1"] = "aecbench.accepted-repair-evidence.v1"
    terminal: ArtifactReference
    decision_sha256: str
    parent_candidate_id: NonEmptyStr
    parent_harness_ref: HarnessInstanceRef
    parent_program_ref: ExecutionProgramRef
    child_candidate_id: NonEmptyStr
    child_harness_ref: HarnessInstanceRef
    child_program_ref: ExecutionProgramRef
    references: tuple[PairedRepairEvidenceReference, ...] = Field(min_length=1)

    @field_validator(
        "decision_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if any(not reference.accepted for reference in self.references):
            raise ValueError("accepted repair evidence may contain only accepted references")
        if any(reference.decision_sha256 != self.decision_sha256 for reference in self.references):
            raise ValueError("accepted repair references must bind one exact decision")
        return self


class MotifLearningReport(ContentAddressedModel):
    """Causal audit record for candidate creation and every attempted promotion edge."""

    schema_version: Literal["aecbench.motif-learning-report.v3"] = "aecbench.motif-learning-report.v3"
    conclusion: Literal["motif_learning"] = "motif_learning"
    source_stage_report_sha256: str
    child_calibration_report_sha256: str
    repair_terminal: ArtifactReference
    applicability: MotifApplicabilityAttestation
    calibration_applicability: MotifApplicabilityAttestation
    harness_program_evidence: HarnessProgramEvidenceReference
    quality_evidence: QualityEvidenceReference
    repair_evidence: AcceptedRepairEvidence
    policy: MotifPromotionPolicy
    input_archive_sha256: str
    candidate_motif_sha256: str
    motif_lineage_sha256s: tuple[str, ...]
    promotion_decisions: tuple[MotifPromotionDecision, ...]
    final_motif_sha256: str
    final_status: MotifStatus
    output_archive_sha256: str

    @field_validator(
        "source_stage_report_sha256",
        "child_calibration_report_sha256",
        "input_archive_sha256",
        "candidate_motif_sha256",
        "final_motif_sha256",
        "output_archive_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("motif_lineage_sha256s")
    @classmethod
    def validate_lineage_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("motif learning report requires a motif lineage")
        for address in value:
            validate_sha256(address)
        return value


@dataclass(frozen=True)
class MotifLearningResult:
    """In-memory learned motif, immutable archive, and persisted-ready causal report."""

    candidate: HarnessProgramMotif
    motif: HarnessProgramMotif
    library: MotifLibrary
    report: MotifLearningReport


class MotifTransferPlan(ContentAddressedModel):
    """Frozen pre-holdout selection and target-specific Hx/px materialization plan."""

    schema_version: Literal["aecbench.motif-transfer-plan.v1"] = "aecbench.motif-transfer-plan.v1"
    selected_before_holdout: Literal[True] = True
    frozen_archive_sha256: str
    target_applicability: MotifApplicabilityAttestation
    selection_request: MotifSelectionRequest
    selection_decision: MotifSelectionDecision
    instantiation: InstantiatedMotifFactors

    @field_validator("frozen_archive_sha256")
    @classmethod
    def validate_archive_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_selection_lineage(self) -> Self:
        if self.selection_request.archive_sha256 != self.frozen_archive_sha256:
            raise ValueError("transfer plan selection request does not bind its frozen archive")
        if self.selection_request.applicability != self.target_applicability.descriptor:
            raise ValueError("transfer plan selection does not bind its target applicability")
        if self.selection_request.target_review_lineage_ids != self.target_applicability.review_lineage_ids:
            raise ValueError("transfer plan selection does not bind its target review lineages")
        if self.selection_decision.request_sha256 != self.selection_request.request_sha256:
            raise ValueError("transfer plan decision does not bind its selection request")
        if self.instantiation.selection_decision_sha256 != self.selection_decision.decision_sha256:
            raise ValueError("transfer plan materialization does not bind its selection decision")
        if self.target_applicability.kernel_ref != self.instantiation.harness_program_request.kernel_ref:
            raise ValueError("transfer plan applicability does not use the target fixed kernel")
        return self


class GovernedMotifTransferPlan(ContentAddressedModel):
    """Selection-time assurance bound to one exact transfer plan."""

    schema_version: Literal["aecbench.governed-motif-transfer-plan.v2"] = "aecbench.governed-motif-transfer-plan.v2"
    transfer_plan_sha256: str
    transfer_plan: MotifTransferPlan
    assured_selection_sha256: str
    assured_selection: AssuredMotifSelectionRecord

    @field_validator("transfer_plan_sha256", "assured_selection_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_assured_selection(self) -> Self:
        if self.transfer_plan.content_sha256 != self.transfer_plan_sha256:
            raise ValueError("governed transfer plan does not bind its exact plan")
        if self.assured_selection.content_sha256 != self.assured_selection_sha256:
            raise ValueError("governed transfer plan does not bind its exact assured selection")
        if (
            self.transfer_plan.selection_request != self.assured_selection.selection_request
            or self.transfer_plan.selection_decision != self.assured_selection.selection_decision
        ):
            raise ValueError("governed transfer plan and assured selection disagree")
        if self.transfer_plan.instantiation.selected_motif_sha256 != self.assured_selection.selected_motif_sha256:
            raise ValueError("governed transfer plan binds the wrong selected motif")
        return self

    @classmethod
    def create(
        cls,
        *,
        transfer_plan: MotifTransferPlan,
        assured_selection: AssuredMotifSelectionRecord,
    ) -> GovernedMotifTransferPlan:
        """Create the assurance-bearing plan for one exact transfer plan."""
        selected_plan = MotifTransferPlan.model_validate(transfer_plan.model_dump(mode="python"))
        assured = AssuredMotifSelectionRecord.model_validate(assured_selection.model_dump(mode="python"))
        return cls(
            transfer_plan_sha256=selected_plan.content_sha256,
            transfer_plan=selected_plan,
            assured_selection_sha256=assured.content_sha256,
            assured_selection=assured,
        )


class MotifTransferPromotionReport(ContentAddressedModel):
    """Auditable holdout evidence and governed transfer-promotion outcome."""

    schema_version: Literal["aecbench.motif-transfer-promotion-report.v1"] = (
        "aecbench.motif-transfer-promotion-report.v1"
    )
    conclusion: Literal["transfer_evaluation"] = "transfer_evaluation"
    selected_before_holdout: Literal[True] = True
    transfer_plan_sha256: str
    transfer_evaluation_sha256: str
    input_archive_sha256: str
    selected_motif_sha256: str
    transfer_evidence: TransferEvidenceReference
    evidence_motif_sha256: str
    promotion_decision: MotifPromotionDecision
    final_motif_sha256: str
    final_status: MotifStatus
    output_archive_sha256: str

    @field_validator(
        "transfer_plan_sha256",
        "transfer_evaluation_sha256",
        "input_archive_sha256",
        "selected_motif_sha256",
        "evidence_motif_sha256",
        "final_motif_sha256",
        "output_archive_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


@dataclass(frozen=True)
class MotifTransferResult:
    """Transfer-enriched motif, immutable archive, and persisted-ready promotion report."""

    motif: HarnessProgramMotif
    library: MotifLibrary
    report: MotifTransferPromotionReport


def attest_harness_program_study_applicability(
    report: HarnessProgramStudyReport,
) -> MotifApplicabilityAttestation:
    """Return the kernel-derived applicability preregistered before harness-program-study execution."""
    verify_harness_program_study_report(report)
    return report.applicability


def attest_task_snapshots_applicability(
    *,
    task_refs: tuple[str, ...],
    tasks_root: Path,
    registry: KernelRuntimeRegistry,
) -> MotifApplicabilityAttestation:
    """Profile exact target tasks through the allowlisted fixed-K profiler before selection."""
    return profile_task_applicability(
        task_refs=task_refs,
        tasks_root=tasks_root,
        registry=registry,
    )


def derive_motif_solution_descriptor(
    spec: HarnessSpec,
    program: ProgramFactorTemplate,
) -> MotifStructuralDescriptor:
    """Derive solution coordinates from actual typed Hx/px structure, never caller labels."""
    source_spec = HarnessSpec.model_validate(spec.model_dump(mode="python"))
    source_program = ProgramFactorTemplate.model_validate(program.model_dump(mode="python"))
    nodes = source_program.nodes
    has_fanout = any(isinstance(node, FanoutNode) for node in nodes)
    has_join = any(isinstance(node, JoinNode) for node in nodes)
    has_branch = any(isinstance(node, BranchNode) for node in nodes)
    recursive = source_spec.recursion_policy.enabled or any(
        getattr(node, "recursion", None) is not None for node in nodes
    )
    if has_fanout and has_branch:
        decomposition = "fanout_branch"
    elif has_fanout:
        decomposition = "fanout"
    elif has_branch:
        decomposition = "branch"
    elif sum(isinstance(node, ActionNode | VerifyNode) for node in nodes) > 1:
        decomposition = "staged"
    else:
        decomposition = "monolithic"
    if recursive:
        decomposition = f"recursive_{decomposition}"

    if has_fanout and has_join:
        orchestration = "fanout_join"
    elif has_fanout:
        orchestration = "bounded_parallel"
    elif has_branch:
        orchestration = "conditional"
    else:
        orchestration = "serial"

    operation_ids = {node.operation_id for node in nodes if isinstance(node, ActionNode | FanoutNode | VerifyNode)}
    tool_ids = {
        tool_id
        for binding in source_spec.bindings
        if isinstance(binding.configuration, ToolBindingConfig)
        for tool_id in binding.configuration.tool_ids
    }
    tool_surface = tuple(sorted(operation_ids | tool_ids))
    fanout_parallelism = [node.max_parallelism for node in nodes if isinstance(node, FanoutNode)]
    maximum_parallelism = (
        min(source_program.limits.max_parallelism, max(fanout_parallelism)) if fanout_parallelism else 1
    )
    has_context = any(isinstance(binding.configuration, ContextBindingConfig) for binding in source_spec.bindings)
    state_mode: Literal["stateless", "ephemeral", "persistent"] = (
        "ephemeral" if has_context or recursive or has_fanout or has_join or has_branch else "stateless"
    )
    return MotifStructuralDescriptor(
        decomposition_pattern=decomposition,
        orchestration_pattern=orchestration,
        decomposition_depth=_program_depth(source_program),
        maximum_parallelism=maximum_parallelism,
        tool_surface=tool_surface,
        state_mode=state_mode,
    )


def capture_accepted_repair_evidence(
    execution: RepairRuntimeExecution,
) -> AcceptedRepairEvidence:
    """Verify and adapt one accepted paired repair without accepting pre-mutation scores."""
    _validate_accepted_repair_result(execution)
    attempt_plan, terminal = _load_repair_capture_artifacts(execution)
    _validate_repair_capture_artifact_chain(
        execution=execution,
        attempt_plan=attempt_plan,
        terminal=terminal,
    )
    result = execution.result
    assert result.decision is not None
    assert result.child_verification is not None
    assert result.attempt is not None
    assert result.child_candidate_id is not None
    decision_sha256 = canonical_json_sha256(result.decision.model_dump(mode="json"))
    references = _build_paired_repair_references(
        execution=execution,
        decision_sha256=decision_sha256,
    )
    return AcceptedRepairEvidence(
        terminal=execution.terminal.reference,
        decision_sha256=decision_sha256,
        parent_candidate_id=result.parent_candidate_id,
        parent_harness_ref=result.parent_verification.harness_ref,
        parent_program_ref=result.parent_verification.program_ref,
        child_candidate_id=result.child_candidate_id,
        child_harness_ref=result.child_verification.harness_ref,
        child_program_ref=result.child_verification.program_ref,
        references=references,
    )


def _validate_accepted_repair_result(execution: RepairRuntimeExecution) -> None:
    result = execution.result
    if result.status is not RepairLoopStatus.ACCEPTED or result.decision is None or not result.decision.accepted:
        raise ValueError("motif learning requires an accepted paired repair result")
    if result.child_verification is None or result.attempt is None or result.child_candidate_id is None:
        raise ValueError("accepted paired repair is missing child verification evidence")


def _load_repair_capture_artifacts(
    execution: RepairRuntimeExecution,
) -> tuple[RepairAttemptPlan, RepairTerminalRecord]:
    attempt_plan_path = _verify_stored_repair_artifact(execution.attempt_plan, label="attempt plan")
    attempt_plan = RepairAttemptPlan.model_validate_json(attempt_plan_path.read_text(encoding="utf-8"))
    terminal_path = _verify_stored_repair_artifact(execution.terminal, label="repair terminal")
    terminal = RepairTerminalRecord.model_validate_json(terminal_path.read_text(encoding="utf-8"))
    return attempt_plan, terminal


def _validate_repair_capture_artifact_chain(
    *,
    execution: RepairRuntimeExecution,
    attempt_plan: RepairAttemptPlan,
    terminal: RepairTerminalRecord,
) -> None:
    result = execution.result
    assert result.attempt is not None
    assert result.decision is not None
    assert result.child_verification is not None
    if terminal.attempt_plan_sha256 != execution.attempt_plan.reference.sha256:
        raise ValueError("repair terminal does not reference the supplied attempt plan")
    if terminal.result != result:
        raise ValueError("repair terminal artifact does not contain the supplied paired repair result")
    if terminal.repair_run_spec != attempt_plan.repair_run_spec:
        raise ValueError("repair terminal and attempt plan do not bind the same repair run spec")
    if terminal.evidence_use_policy != attempt_plan.evidence_use_policy:
        raise ValueError("repair terminal and attempt plan do not bind the same evidence-use policy")
    if not terminal.evidence_use_policy.motif_evidence_eligible:
        raise ValueError("repair evidence-use policy does not permit motif evidence capture")
    request = attempt_plan.request
    if (
        request.loop_id != result.loop_id
        or request.attempt_id != result.attempt_id
        or request.iteration != result.iteration
        or request.parent_candidate_id != result.parent_candidate_id
        or request.child_candidate_id != result.child_candidate_id
        or attempt_plan.parent.candidate_id != result.parent_candidate_id
        or request.pairing != result.parent_verification.pairing
        or request.pairing != result.child_verification.pairing
    ):
        raise ValueError("repair attempt plan request/result lineage does not match")
    recomputed_decision = decide_repair(result.attempt, request.acceptance_policy)
    if recomputed_decision != result.decision:
        raise ValueError("accepted repair decision does not match the attempt plan acceptance policy")


def _build_paired_repair_references(
    *,
    execution: RepairRuntimeExecution,
    decision_sha256: str,
) -> tuple[PairedRepairEvidenceReference, ...]:
    result = execution.result
    assert result.attempt is not None
    assert result.decision is not None
    child_by_lineage: dict[str, list[RepairTrialOutcome]] = defaultdict(list)
    parent_by_lineage: dict[str, list[RepairTrialOutcome]] = defaultdict(list)
    for outcome in result.attempt.child_outcomes:
        child_by_lineage[outcome.review_lineage_sha256].append(outcome)
    for outcome in result.attempt.parent_outcomes:
        parent_by_lineage[outcome.review_lineage_sha256].append(outcome)
    if set(child_by_lineage) != set(parent_by_lineage):
        raise ValueError("accepted repair review lineages are not exactly paired")

    references: list[PairedRepairEvidenceReference] = []
    for review_lineage_sha256 in sorted(child_by_lineage):
        child = tuple(child_by_lineage[review_lineage_sha256])
        parent = tuple(parent_by_lineage[review_lineage_sha256])
        split_values = {outcome.split for outcome in (*parent, *child)}
        if len(split_values) != 1:
            raise ValueError("accepted repair review evidence mixes evaluation splits")
        costs = tuple(outcome.cost for outcome in (*parent, *child))
        if any(cost is None for cost in costs):
            raise ValueError("accepted repair evidence requires complete cost evidence")
        validity_rate = sum(outcome.valid and outcome.complete for outcome in child) / len(child)
        references.append(
            PairedRepairEvidenceReference.create(
                attempt_id=result.attempt_id,
                decision_sha256=decision_sha256,
                review_lineage_id=review_lineage_sha256,
                split=next(iter(split_values)),
                accepted=True,
                mean_reward_delta=result.decision.mean_reward_delta,
                validity_rate=validity_rate,
                estimated_cost_usd=sum(float(cost) for cost in costs if cost is not None),
            )
        )
    return tuple(references)


def learn_and_promote_motif(
    *,
    source_stage_report: HarnessProgramStudyReport,
    child_calibration_report: HarnessProgramStudyReport,
    repair_execution: RepairRuntimeExecution,
    repaired_candidate: RepairCandidate,
    policy: MotifPromotionPolicy,
    registry: KernelRuntimeRegistry,
    library: MotifLibrary,
) -> MotifLearningResult:
    """Evaluate motif evidence and stop before any authority-bearing reusable promotion."""

    return _evaluate_motif_learning(
        source_stage_report=source_stage_report,
        child_calibration_report=child_calibration_report,
        repair_execution=repair_execution,
        repaired_candidate=repaired_candidate,
        policy=policy,
        registry=registry,
        library=library,
    )


def _evaluate_motif_learning(
    *,
    source_stage_report: HarnessProgramStudyReport,
    child_calibration_report: HarnessProgramStudyReport,
    repair_execution: RepairRuntimeExecution,
    repaired_candidate: RepairCandidate,
    policy: MotifPromotionPolicy,
    registry: KernelRuntimeRegistry,
    library: MotifLibrary,
) -> MotifLearningResult:
    """Build one causal motif evaluation without granting protected status."""

    source_library, attestation, calibration_attestation = _validate_motif_learning_reports(
        source_stage_report=source_stage_report,
        child_calibration_report=child_calibration_report,
        library=library,
    )
    repair = capture_accepted_repair_evidence(repair_execution)
    candidate, harness_program_evidence, quality = _build_motif_candidate(
        source_stage_report=source_stage_report,
        child_calibration_report=child_calibration_report,
        repaired_candidate=repaired_candidate,
        repair=repair,
        registry=registry,
    )
    archive, current, lineage, decisions = _evaluate_motif_promotion_lineage(
        source_library=source_library,
        candidate=candidate,
        policy=policy,
    )
    report = MotifLearningReport(
        source_stage_report_sha256=source_stage_report.content_sha256,
        child_calibration_report_sha256=child_calibration_report.content_sha256,
        repair_terminal=repair.terminal,
        applicability=attestation,
        calibration_applicability=calibration_attestation,
        harness_program_evidence=harness_program_evidence,
        quality_evidence=quality,
        repair_evidence=repair,
        policy=policy,
        input_archive_sha256=source_library.archive_sha256,
        candidate_motif_sha256=candidate.motif_sha256,
        motif_lineage_sha256s=lineage,
        promotion_decisions=decisions,
        final_motif_sha256=current.motif_sha256,
        final_status=current.status,
        output_archive_sha256=archive.archive_sha256,
    )
    return MotifLearningResult(candidate=candidate, motif=current, library=archive, report=report)


def _validate_motif_learning_reports(
    *,
    source_stage_report: HarnessProgramStudyReport,
    child_calibration_report: HarnessProgramStudyReport,
    library: MotifLibrary,
) -> tuple[MotifLibrary, MotifApplicabilityAttestation, MotifApplicabilityAttestation]:
    verify_harness_program_study_report(source_stage_report)
    verify_harness_program_study_report(child_calibration_report)
    source_library = MotifLibrary.model_validate(library.model_dump(mode="python"))
    attestation = source_stage_report.applicability
    calibration_attestation = child_calibration_report.applicability
    if source_stage_report.split != "discovery":
        raise ValueError("motif learning source evidence must use the discovery split")
    if child_calibration_report.split != "calibration":
        raise ValueError("motif learning child evidence must use the calibration split")
    if attestation.review_lineage_ids != source_stage_report.review_lineage_ids:
        raise ValueError("applicability attestation does not cover the source harness-program-study review lineages")
    if calibration_attestation.review_lineage_ids != child_calibration_report.review_lineage_ids:
        raise ValueError("child applicability does not cover its calibration review lineages")
    if calibration_attestation.descriptor != attestation.descriptor:
        raise ValueError("child calibration must use the source applicability bucket")
    if set(calibration_attestation.review_lineage_ids).intersection(attestation.review_lineage_ids):
        raise ValueError("child calibration review lineages must be independent from source evidence")
    return source_library, attestation, calibration_attestation


def _build_motif_candidate(
    *,
    source_stage_report: HarnessProgramStudyReport,
    child_calibration_report: HarnessProgramStudyReport,
    repaired_candidate: RepairCandidate,
    repair: AcceptedRepairEvidence,
    registry: KernelRuntimeRegistry,
) -> tuple[HarnessProgramMotif, HarnessProgramEvidenceReference, QualityEvidenceReference]:
    if any(reference.split != "repair_gate" for reference in repair.references):
        raise ValueError("motif learning repair evidence must use the repair_gate split")
    _validate_repaired_candidate(
        repaired_candidate=repaired_candidate,
        repair=repair,
        stage_report=source_stage_report,
        registry=registry,
    )
    program_factor = _program_factor(repaired_candidate.program_template)
    calibrated_spec = _calibrated_harness_spec(child_calibration_report)
    _validate_calibrated_harness_rebinding(
        source=repaired_candidate.harness_request.spec,
        calibrated=calibrated_spec,
    )
    hx_template = encode_harness_motif_template(calibrated_spec)
    px_template = encode_program_motif_template(program_factor)
    harness_program_evidence = harness_program_study_evidence(child_calibration_report)
    calibration_subject = (
        harness_program_evidence.subject_hx_template_sha256,
        harness_program_evidence.subject_px_template_sha256,
    )
    if calibration_subject != (hx_template.template_sha256, px_template.template_sha256):
        raise ValueError("child calibration evidence subject does not match the repaired candidate Hx/px")
    quality = _stage_quality_evidence(child_calibration_report, harness_program_evidence=harness_program_evidence)
    attestation = source_stage_report.applicability
    candidate = HarnessProgramMotif.create(
        status=MotifStatus.CANDIDATE,
        kernel_abi_sha256=kernel_abi_commitment(source_stage_report.kernel_ref),
        hx_template=hx_template,
        px_template=px_template,
        applicability=attestation.descriptor,
        descriptor=derive_motif_solution_descriptor(
            calibrated_spec,
            program_factor,
        ),
        accepted_repair_refs=repair.references,
        harness_program_evidence_refs=(harness_program_evidence,),
        quality_evidence_refs=(quality,),
    )
    return candidate, harness_program_evidence, quality


def _evaluate_motif_promotion_lineage(
    *,
    source_library: MotifLibrary,
    candidate: HarnessProgramMotif,
    policy: MotifPromotionPolicy,
) -> tuple[
    MotifLibrary,
    HarnessProgramMotif,
    tuple[str, ...],
    tuple[MotifPromotionDecision, ...],
]:
    archive = source_library.add(candidate)
    current = candidate
    lineage = [candidate.motif_sha256]
    decisions: list[MotifPromotionDecision] = []
    for target in (MotifStatus.PROVISIONAL, MotifStatus.REUSABLE):
        decision = decide_motif_promotion(current, target, policy)
        decisions.append(decision)
        if not decision.accepted:
            break
        if decision.target_status is MotifStatus.REUSABLE:
            break
        current = apply_motif_promotion(current, decision, policy)
        archive = archive.add(current)
        lineage.append(current.motif_sha256)
    return archive, current, tuple(lineage), tuple(decisions)


def select_and_materialize_motif(
    *,
    library: MotifLibrary,
    applicability: MotifApplicabilityAttestation,
    selection_split: SelectionSplit,
    request: MotifHarnessProgramInstantiationRequest,
) -> MotifTransferPlan:
    """Reject unassured reusable-motif materialization at the active dispatch surface."""

    del library, applicability, selection_split, request
    raise MotifAssuranceAuthorityError(
        "reusable motif materialization requires governed assurance; use select_and_materialize_assured_motif"
    )


def _select_and_materialize_motif(
    *,
    library: MotifLibrary,
    applicability: MotifApplicabilityAttestation,
    selection_split: SelectionSplit,
    request: MotifHarnessProgramInstantiationRequest,
) -> MotifTransferPlan:
    """Select and materialize after the caller has established assurance."""

    frozen_library = MotifLibrary.model_validate(library.model_dump(mode="python"))
    target = MotifApplicabilityAttestation.model_validate(applicability.model_dump(mode="python"))
    selection_request = MotifSelectionRequest.create(
        archive_sha256=frozen_library.archive_sha256,
        archive_frozen=True,
        kernel_abi_sha256=kernel_abi_commitment(request.kernel_ref),
        applicability=target.descriptor,
        selection_split=selection_split,
        target_review_lineage_ids=target.review_lineage_ids,
    )
    decision = select_motif(frozen_library, selection_request)
    instantiation = instantiate_selected_motif_factors(
        library=frozen_library,
        selection_request=selection_request,
        selection_decision=decision,
        request=request,
    )
    return MotifTransferPlan(
        frozen_archive_sha256=frozen_library.archive_sha256,
        target_applicability=target,
        selection_request=selection_request,
        selection_decision=decision,
        instantiation=instantiation,
    )


def select_and_materialize_assured_motif(
    *,
    library: MotifLibrary,
    applicability: MotifApplicabilityAttestation,
    selection_split: SelectionSplit,
    request: MotifHarnessProgramInstantiationRequest,
    assurance_snapshot: MotifAssuranceSnapshot,
) -> GovernedMotifTransferPlan:
    """Materialize a plan and freeze its active assurance in the same selection record."""
    frozen_library = MotifLibrary.model_validate(library.model_dump(mode="python"))
    transfer_plan = _select_and_materialize_motif(
        library=frozen_library,
        applicability=applicability,
        selection_split=selection_split,
        request=request,
    )
    selected = resolve_motif_selection(
        frozen_library,
        transfer_plan.selection_request,
        transfer_plan.selection_decision,
    )
    if selected is None:
        raise ValueError("assured motif transfer selection did not select a motif")
    assured = AssuredMotifSelectionRecord.create(
        selection_request=transfer_plan.selection_request,
        selection_decision=transfer_plan.selection_decision,
        selected_motif=selected,
        snapshot=assurance_snapshot,
    )
    return GovernedMotifTransferPlan.create(
        transfer_plan=transfer_plan,
        assured_selection=assured,
    )


def release_governed_motif_transfer_plan(
    *,
    plan: GovernedMotifTransferPlan,
    frozen_library: MotifLibrary,
    current_snapshot: MotifAssuranceSnapshot,
    authority_ledger: AuthorityLedger,
    boundary: MotifAssuranceBoundary,
) -> MotifTransferPlan:
    """Release a plan only after an immediate dispatch or promotion assurance recheck."""
    governed = GovernedMotifTransferPlan.model_validate(plan.model_dump(mode="python"))
    library = MotifLibrary.model_validate(frozen_library.model_dump(mode="python"))
    released_plan = governed.transfer_plan
    if library.archive_sha256 != released_plan.frozen_archive_sha256:
        raise ValueError("governed transfer requires the exact frozen selection archive")
    selected = resolve_motif_selection(
        library,
        released_plan.selection_request,
        released_plan.selection_decision,
    )
    if selected is None:
        raise ValueError("governed transfer selection did not select a motif")
    if (
        selected.motif_sha256 != governed.assured_selection.selected_motif_sha256
        or selected.motif_sha256 != released_plan.instantiation.selected_motif_sha256
    ):
        raise ValueError("governed transfer resolved the wrong selected motif")
    assert_assured_motif_selection_current(
        governed.assured_selection,
        selected,
        current_snapshot,
        authority_ledger=authority_ledger,
        boundary=boundary,
    )
    return released_plan


def write_motif_audit_report(
    report: MotifLearningReport | MotifTransferPromotionReport,
    *,
    artifacts_root: Path,
) -> ArtifactReference:
    """Persist a canonical report below its model content address and return a byte digest."""
    normalized = report.__class__.model_validate(report.model_dump(mode="python"))
    filename = (
        "motif-learning-report.json"
        if isinstance(normalized, MotifLearningReport)
        else "motif-transfer-promotion-report.json"
    )
    encoded = (json.dumps(normalized.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    path = Path(artifacts_root) / normalized.content_sha256 / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("motif report path already contains different content")
    if not path.exists():
        path.write_bytes(encoded)
    return ArtifactReference(
        kind=filename.removesuffix(".json"),
        path=str(path),
        sha256=hashlib.sha256(encoded).hexdigest(),
        media_type="application/json",
    )


def _program_depth(program: ProgramFactorTemplate) -> int:
    depths: dict[str, int] = {}
    for node in program.nodes:
        depths[node.node_id] = 0 if not node.depends_on else 1 + max(depths[parent] for parent in node.depends_on)
    return max(depths.values(), default=0)


def _program_factor(template: RepairProgramTemplate) -> ProgramFactorTemplate:
    return ProgramFactorTemplate(
        factor_id=template.program_id,
        version=template.version,
        nodes=template.nodes,
        limits=template.limits,
    )


def _calibrated_harness_spec(
    report: HarnessProgramStudyReport,
) -> HarnessSpec:
    specs = tuple(candidate.request.learned_harness_spec for candidate in report.candidates)
    if not specs or any(spec != specs[0] for spec in specs[1:]):
        raise ValueError("child calibration mixes learned harness specs")
    return specs[0]


def _validate_calibrated_harness_rebinding(
    *,
    source: HarnessSpec,
    calibrated: HarnessSpec,
) -> None:
    calibrated_task_sources = [
        binding.configuration
        for binding in calibrated.bindings
        if isinstance(binding.configuration, TaskSourceBindingConfig)
    ]
    if len(calibrated_task_sources) != 1:
        raise ValueError("child calibration harness requires exactly one task-source binding")
    rebound_bindings = []
    source_task_source_count = 0
    for binding in source.bindings:
        configuration = binding.configuration
        if isinstance(configuration, TaskSourceBindingConfig):
            source_task_source_count += 1
            configuration = TaskSourceBindingConfig(task_refs=calibrated_task_sources[0].task_refs)
        rebound_bindings.append(binding.model_copy(update={"configuration": configuration}))
    if source_task_source_count != 1:
        raise ValueError("repaired harness requires exactly one task-source binding")
    rebound = HarnessSpec(
        summary=source.summary,
        contracts=source.contracts,
        budget=source.budget,
        recursion_policy=source.recursion_policy,
        bindings=tuple(rebound_bindings),
    )
    if rebound != calibrated:
        raise ValueError("child calibration may rebind only the repaired harness task-source slot")


def _validate_repaired_candidate(
    *,
    repaired_candidate: RepairCandidate,
    repair: AcceptedRepairEvidence,
    stage_report: HarnessProgramStudyReport,
    registry: KernelRuntimeRegistry,
) -> None:
    candidate = RepairCandidate.model_validate(repaired_candidate.model_dump(mode="python"))
    if candidate.candidate_id != repair.child_candidate_id:
        raise ValueError("repaired candidate does not identify the accepted repair child")
    if candidate.parent_candidate_id != repair.parent_candidate_id:
        raise ValueError("repaired candidate does not bind the harness-program-study repair parent")
    if candidate.harness_request.kernel_ref != registry.manifest.ref:
        raise ValueError("repaired candidate does not target the installed fixed kernel")
    harness = compile_harness_instance(candidate.harness_request, registry=registry)
    program = compile_execution_program(
        candidate.program_template.bind(harness.ref),
        harness=harness,
        registry=registry,
    )
    if harness.ref != repair.child_harness_ref or program.ref != repair.child_program_ref:
        raise ValueError("repaired candidate sources do not compile to the accepted child Hx/px")
    parent_cells = [
        cell
        for evidence in stage_report.candidates
        for cell in evidence.cells
        if cell.cell is HarnessProgramCell.HX_PX
        and cell.compiled_harness_ref == repair.parent_harness_ref
        and cell.compiled_program_ref == repair.parent_program_ref
    ]
    if not parent_cells:
        raise ValueError("accepted repair parent does not match a harness-program-study learned Hx/px candidate")


def _stage_quality_evidence(
    report: HarnessProgramStudyReport,
    *,
    harness_program_evidence: HarnessProgramEvidenceReference,
) -> QualityEvidenceReference:
    if not report.cost_evidence_complete:
        raise ValueError("harness-program-study quality evidence requires complete cost coverage")
    joint_trials = tuple(item for item in report.trials if item.trial.cell is HarnessProgramCell.HX_PX)
    if not joint_trials:
        raise ValueError("harness-program-study report contains no joint Hx/px trials")
    if any(not item.cost_evidence_complete for item in joint_trials):
        raise ValueError("harness-program-study joint Hx/px evidence has unknown cost")
    evaluation_payload = {
        "schema_version": "aecbench.motif-quality-evaluation.v1",
        "analysis_sha256": report.analysis_sha256,
        "trials": [
            {
                "trial_id": item.trial.trial_id,
                "mean_reward": item.mean_reward,
                "validity_rate": item.validity_rate,
            }
            for item in joint_trials
        ],
    }
    return QualityEvidenceReference.create(
        evaluation_sha256=canonical_json_sha256(evaluation_payload),
        subject_hx_template_sha256=harness_program_evidence.subject_hx_template_sha256,
        subject_px_template_sha256=harness_program_evidence.subject_px_template_sha256,
        review_lineage_ids=report.review_lineage_ids,
        split=report.split,
        objective_reward=fmean(float(item.mean_reward) for item in joint_trials),
        validity_rate=min(float(item.validity_rate) for item in joint_trials),
        estimated_cost_usd=sum(float(item.estimated_cost_usd) for item in joint_trials),
        holdout_accessed_during_selection=False,
        included_in_harness_program_reference_sha256=harness_program_evidence.reference_sha256,
    )


def _verify_artifact(reference: ArtifactReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"artifact digest mismatch: {reference.path}")


def _verify_stored_repair_artifact(artifact: StoredRepairArtifact, *, label: str) -> Path:
    referenced_path = Path(artifact.reference.path)
    if artifact.path != referenced_path:
        raise ValueError(f"{label} path does not match its artifact reference")
    _verify_artifact(artifact.reference)
    return referenced_path
