# ABOUTME: Executes assured motif selections on holdout factorials and derives evidence from real trials.
# ABOUTME: Separates dispatch assurance from non-authoritative evaluation.

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Literal, Self

from pydantic import Field, FiniteFloat, NonNegativeFloat, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.applicability import profile_task_applicability
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.factorial_analysis import (
    FactorialAnalysis,
    FactorialOutcome,
    analyse_factorial,
)
from aec_bench.meta_harness.factorial_candidates import (
    FactorialCandidateFactoryRequest,
    MaterializedFactorialCandidate,
    build_factorial_candidate_reference,
    materialize_factorial_candidates,
)
from aec_bench.meta_harness.factorial_plan import (
    FactorialCandidateReference,
    FactorialCell,
    FactorialPlan,
    FactorialStudyManifest,
    FactorialTrial,
)
from aec_bench.meta_harness.factorial_study import (
    FactorialStudyExecution,
    FactorialTrialExecution,
    execute_factorial_study,
    validate_factorial_record_lineage,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.motif_assurance import (
    MotifAssuranceBoundary,
    MotifAssuranceSnapshot,
)
from aec_bench.meta_harness.motif_learning import (
    GovernedMotifTransferPlan,
    MotifTransferPlan,
    MotifTransferPromotionReport,
    MotifTransferResult,
    release_governed_motif_transfer_plan,
)
from aec_bench.meta_harness.motifs import (
    HarnessProgramMotif,
    MotifLibrary,
    MotifPromotionDecision,
    MotifPromotionPolicy,
    MotifStatus,
    TransferEvidenceReference,
    decide_motif_promotion,
    resolve_motif_selection,
)
from aec_bench.tasks.registry import TaskRegistry


class MotifTransferTrialEvidence(FrozenStrictModel):
    """One planned holdout factorial trial and its exact verified TrialRecord artifacts."""

    trial: FactorialTrial
    execution_seed: int
    candidate_reference: FactorialCandidateReference
    bundle_sha256: str
    candidate_manifest: ArtifactReference
    trial_record_ids: tuple[NonEmptyStr, ...]
    trial_records: tuple[ArtifactReference, ...]
    mean_reward: FiniteFloat
    validity_rate: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: NonNegativeFloat
    cost_evidence_complete: Literal[True] = True

    @field_validator("bundle_sha256")
    @classmethod
    def validate_bundle_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial_identity(self) -> Self:
        if self.candidate_reference != self.trial.candidate:
            raise ValueError("transfer trial evidence does not match its planned candidate")
        if not self.trial_records or len(self.trial_records) != len(self.trial_record_ids):
            raise ValueError("transfer trial evidence requires one artifact per TrialRecord")
        if len(set(self.trial_record_ids)) != len(self.trial_record_ids):
            raise ValueError("transfer trial evidence contains duplicate TrialRecord ids")
        return self


class MotifTransferEvaluationReport(ContentAddressedModel):
    """Content-addressed holdout study from which transfer evidence is mechanically derived."""

    schema_version: Literal["aecbench.motif-transfer-evaluation.v1"] = "aecbench.motif-transfer-evaluation.v1"
    conclusion: Literal["frozen_motif_transfer"] = "frozen_motif_transfer"
    transfer_plan_sha256: str
    transfer_plan: MotifTransferPlan
    frozen_archive_sha256: str
    selected_motif_sha256: str
    manifest: FactorialStudyManifest
    plan: FactorialPlan
    plan_artifact: ArtifactReference
    trials: tuple[MotifTransferTrialEvidence, ...]
    analysis: FactorialAnalysis
    analysis_sha256: str
    motif_ids: tuple[NonEmptyStr, ...]
    world_lineage_ids: tuple[NonEmptyStr, ...]
    trial_count: PositiveInt
    record_count: PositiveInt
    validity_rate: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: NonNegativeFloat
    cost_evidence_complete: Literal[True] = True
    transfer_evidence: TransferEvidenceReference

    @field_validator(
        "transfer_plan_sha256",
        "frozen_archive_sha256",
        "selected_motif_sha256",
        "analysis_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("world_lineage_ids")
    @classmethod
    def canonicalize_world_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ordered = tuple(sorted(set(value)))
        if not ordered:
            raise ValueError("transfer evaluation requires at least one holdout world lineage")
        return ordered

    @field_validator("motif_ids")
    @classmethod
    def canonicalize_motif_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ordered = tuple(sorted(set(value)))
        if not ordered:
            raise ValueError("transfer evaluation requires selected motif ancestry")
        for motif_id in ordered:
            validate_sha256(motif_id)
        return ordered

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        _validate_transfer_report_bindings(self)
        _validate_transfer_report_counts(self)
        _validate_transfer_report_aggregates(self)
        _validate_transfer_evidence_reference(self)
        return self


def _validate_transfer_report_bindings(report: MotifTransferEvaluationReport) -> None:
    if report.transfer_plan.content_sha256 != report.transfer_plan_sha256:
        raise ValueError("transfer evaluation does not bind its frozen transfer plan")
    if report.transfer_plan.frozen_archive_sha256 != report.frozen_archive_sha256:
        raise ValueError("transfer evaluation archive does not match its transfer plan")
    if report.transfer_plan.selection_decision.selected_motif_sha256 != report.selected_motif_sha256:
        raise ValueError("transfer evaluation motif does not match its selection decision")
    if report.selected_motif_sha256 not in report.motif_ids:
        raise ValueError("transfer evaluation ancestry does not contain its selected motif")
    if report.plan.plan_sha256 != report.analysis.plan_sha256:
        raise ValueError("transfer analysis does not bind its factorial plan")
    if report.plan.manifest_sha256 != canonical_content_sha256(report.manifest.model_dump(mode="json")):
        raise ValueError("transfer factorial plan does not bind its manifest")
    if report.analysis_sha256 != canonical_content_sha256(report.analysis.model_dump(mode="json")):
        raise ValueError("transfer analysis hash does not bind its full analysis")


def _validate_transfer_report_counts(report: MotifTransferEvaluationReport) -> None:
    if report.trial_count != len(report.trials) or report.trial_count != report.plan.trial_count:
        raise ValueError("transfer report does not cover every planned factorial trial")
    if tuple(item.trial for item in report.trials) != report.plan.trials:
        raise ValueError("transfer trial evidence does not preserve exact plan order")
    if report.record_count != sum(len(item.trial_records) for item in report.trials):
        raise ValueError("transfer report record count does not match its artifacts")


def _validate_transfer_report_aggregates(report: MotifTransferEvaluationReport) -> None:
    derived_validity_rate = (
        sum(item.validity_rate * len(item.trial_record_ids) for item in report.trials) / report.record_count
    )
    if not math.isclose(
        report.validity_rate,
        derived_validity_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer report validity does not match its trial evidence")
    if not math.isclose(
        float(report.estimated_cost_usd),
        sum(float(item.estimated_cost_usd) for item in report.trials),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer report cost does not match its trial evidence")


def _validate_transfer_evidence_reference(report: MotifTransferEvaluationReport) -> None:
    if (
        report.transfer_evidence.evaluation_sha256 != report.analysis_sha256
        or report.transfer_evidence.world_lineage_ids != report.world_lineage_ids
        or not math.isclose(
            float(report.transfer_evidence.validity_rate),
            report.validity_rate,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or not math.isclose(
            float(report.transfer_evidence.estimated_cost_usd),
            float(report.estimated_cost_usd),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        raise ValueError("transfer reference does not match the executed holdout evidence")


@dataclass(frozen=True)
class MotifTransferRuntimeResult:
    """Executed holdout evaluation and its immutable evidence finalization result."""

    evaluation: MotifTransferEvaluationReport
    finalization: MotifTransferResult


def execute_motif_transfer(
    *,
    frozen_library: MotifLibrary,
    plan: GovernedMotifTransferPlan,
    current_snapshot: MotifAssuranceSnapshot,
    authority_ledger: AuthorityLedger,
    policy: MotifPromotionPolicy,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    policy_id: str,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    randomization_seed: int,
    executor: HarborCommandExecutor | None = None,
    confidence_level: float = 0.95,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: int = 42,
) -> MotifTransferRuntimeResult:
    """Run one assured selection and retain accepted transfer evidence as non-authoritative."""

    library = MotifLibrary.model_validate(frozen_library.model_dump(mode="python"))
    source_plan = release_governed_motif_transfer_plan(
        plan=plan,
        frozen_library=library,
        current_snapshot=current_snapshot,
        authority_ledger=authority_ledger,
        boundary=MotifAssuranceBoundary.DISPATCH,
    )
    evaluation = _execute_motif_transfer_evaluation(
        library=library,
        source_plan=source_plan,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        policy_id=policy_id,
        harness_generator_sha256=harness_generator_sha256,
        program_generator_sha256=program_generator_sha256,
        randomization_seed=randomization_seed,
        executor=executor,
        confidence_level=confidence_level,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )
    finalization = finalize_motif_transfer(
        frozen_library=library,
        evaluation=evaluation,
        policy=policy,
    )
    return MotifTransferRuntimeResult(evaluation=evaluation, finalization=finalization)


def _execute_motif_transfer_evaluation(
    *,
    library: MotifLibrary,
    source_plan: MotifTransferPlan,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    policy_id: str,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    randomization_seed: int,
    executor: HarborCommandExecutor | None,
    confidence_level: float,
    bootstrap_replicates: int,
    bootstrap_seed: int,
) -> MotifTransferEvaluationReport:
    """Execute and verify the holdout factorial for one assured released plan."""

    if library.archive_sha256 != source_plan.frozen_archive_sha256:
        raise ValueError("transfer runtime requires the exact frozen selection archive")
    motif_ids = _selected_motif_lineage_ids(
        library,
        source_plan.selection_decision.selected_motif_sha256,
    )
    request = source_plan.instantiation.factorial_request
    validate_holdout_task_visibility(
        task_refs=request.task_refs,
        tasks_root=workflow.tasks_root,
    )
    materialized = materialize_factorial_candidates(
        request,
        registry=registry,
        tasks_root=workflow.tasks_root,
    )
    current_applicability = profile_task_applicability(
        task_refs=request.task_refs,
        tasks_root=workflow.tasks_root,
        registry=registry,
    )
    if current_applicability != source_plan.target_applicability:
        raise ValueError("holdout applicability changed after pre-execution motif selection")

    manifest = FactorialStudyManifest(
        experiment_id=request.experiment_id,
        randomization_seed=randomization_seed,
        repetitions=request.repetitions,
        candidate_sets=(materialized.references,),
    )
    execution = execute_factorial_study(
        candidates=materialized,
        manifest=manifest,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        policy_id=policy_id,
        harness_generator_sha256=harness_generator_sha256,
        program_generator_sha256=program_generator_sha256,
        split="holdout",
        motif_ids=motif_ids,
        executor=executor,
        confidence_level=confidence_level,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )
    evaluation = _build_transfer_evaluation(source_plan, execution, motif_ids=motif_ids)
    verify_motif_transfer_evaluation(evaluation, frozen_library=library)
    return evaluation


def validate_holdout_task_visibility(*, task_refs: tuple[str, ...], tasks_root: Path) -> None:
    """Fail before transfer execution unless every selected task declares holdout visibility."""
    task_registry = TaskRegistry(tasks_root=Path(tasks_root))
    task_registry.reload()
    invalid = tuple(
        task_id
        for task_id in task_refs
        if (task := task_registry.get(task_id)) is None or task.visibility is not Visibility.HOLDOUT
    )
    if invalid:
        raise ValueError("transfer target tasks must be declared holdout: " + ", ".join(invalid))


def finalize_motif_transfer(
    *,
    frozen_library: MotifLibrary,
    evaluation: MotifTransferEvaluationReport,
    policy: MotifPromotionPolicy,
) -> MotifTransferResult:
    """Evaluate verified transfer evidence without claiming an authority-bearing status."""

    library, source, plan, selected, enriched, decision = _prepare_motif_transfer_finalization(
        frozen_library=frozen_library,
        evaluation=evaluation,
        policy=policy,
    )
    return _build_motif_transfer_result(
        library=library,
        source=source,
        plan=plan,
        selected=selected,
        enriched=enriched,
        decision=decision,
        final=enriched,
    )


def _prepare_motif_transfer_finalization(
    *,
    frozen_library: MotifLibrary,
    evaluation: MotifTransferEvaluationReport,
    policy: MotifPromotionPolicy,
) -> tuple[
    MotifLibrary,
    MotifTransferEvaluationReport,
    MotifTransferPlan,
    HarnessProgramMotif,
    HarnessProgramMotif,
    MotifPromotionDecision,
]:
    """Verify transfer evidence and derive the immutable reusable evidence record and decision."""

    library = MotifLibrary.model_validate(frozen_library.model_dump(mode="python"))
    source = MotifTransferEvaluationReport.model_validate(evaluation.model_dump(mode="python"))
    verify_motif_transfer_evaluation(source, frozen_library=library)
    plan = source.transfer_plan

    transfer = _derive_transfer_evidence(
        analysis=source.analysis,
        world_lineage_ids=source.world_lineage_ids,
        validity_rate=source.validity_rate,
        estimated_cost_usd=float(source.estimated_cost_usd),
    )
    if not transfer.selected_before_holdout or not transfer.archive_frozen:
        raise ValueError("transfer evidence must come after frozen pre-holdout selection")
    if transfer.world_lineage_ids != plan.target_applicability.world_lineage_ids:
        raise ValueError("transfer evidence does not match the attested target world lineages")
    selected = resolve_motif_selection(
        library,
        plan.selection_request,
        plan.selection_decision,
    )
    if selected is None or selected.status is not MotifStatus.REUSABLE:
        raise ValueError("transfer promotion requires one selected reusable motif")

    enriched = HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=selected.kernel_abi_sha256,
        hx_template=selected.hx_template,
        px_template=selected.px_template,
        applicability=selected.applicability,
        descriptor=selected.descriptor,
        accepted_repair_refs=selected.accepted_repair_refs,
        factorial_evidence_refs=selected.factorial_evidence_refs,
        quality_evidence_refs=selected.quality_evidence_refs,
        transfer_evidence_refs=(*selected.transfer_evidence_refs, transfer),
        parent_motif_sha256=selected.motif_sha256,
    )
    decision = decide_motif_promotion(enriched, MotifStatus.TRANSFER_VALIDATED, policy)
    return library, source, plan, selected, enriched, decision


def _build_motif_transfer_result(
    *,
    library: MotifLibrary,
    source: MotifTransferEvaluationReport,
    plan: MotifTransferPlan,
    selected: HarnessProgramMotif,
    enriched: HarnessProgramMotif,
    decision: MotifPromotionDecision,
    final: HarnessProgramMotif,
) -> MotifTransferResult:
    """Build the published v1 report from an explicitly chosen authority outcome."""

    archive = library.add(enriched).add(final)
    report = MotifTransferPromotionReport(
        transfer_plan_sha256=plan.content_sha256,
        transfer_evaluation_sha256=source.content_sha256,
        input_archive_sha256=library.archive_sha256,
        selected_motif_sha256=selected.motif_sha256,
        transfer_evidence=source.transfer_evidence,
        evidence_motif_sha256=enriched.motif_sha256,
        promotion_decision=decision,
        final_motif_sha256=final.motif_sha256,
        final_status=final.status,
        output_archive_sha256=archive.archive_sha256,
    )
    return MotifTransferResult(motif=final, library=archive, report=report)


def verify_motif_transfer_evaluation(
    report: MotifTransferEvaluationReport,
    *,
    frozen_library: MotifLibrary,
) -> None:
    """Recompute effects and fail closed if any plan or TrialRecord artifact has changed."""
    source = MotifTransferEvaluationReport.model_validate(report.model_dump(mode="python"))
    library = MotifLibrary.model_validate(frozen_library.model_dump(mode="python"))
    request = _verify_transfer_evaluation_basis(source=source, library=library)
    verified_trials = tuple(
        _verify_transfer_trial(source=source, trial=trial, request=request) for trial in source.trials
    )
    _verify_transfer_evaluation_summary(source=source, verified_trials=verified_trials)


def _verify_transfer_evaluation_basis(
    *,
    source: MotifTransferEvaluationReport,
    library: MotifLibrary,
) -> FactorialCandidateFactoryRequest:
    if library.archive_sha256 != source.frozen_archive_sha256:
        raise ValueError("transfer verification requires the exact frozen selection archive")
    expected_motif_ids = _selected_motif_lineage_ids(
        library,
        source.selected_motif_sha256,
    )
    if source.motif_ids != expected_motif_ids:
        raise ValueError("transfer evaluation motif ancestry does not match the frozen archive")
    _verify_artifact(source.plan_artifact)
    try:
        plan_payload = json.loads(Path(source.plan_artifact.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid transfer factorial plan artifact") from error
    if plan_payload.get("plan") != source.plan.model_dump(mode="json"):
        raise ValueError("transfer plan artifact does not contain the reported factorial plan")
    request = source.transfer_plan.instantiation.factorial_request
    if plan_payload.get("execution_seeds") != list(request.seeds):
        raise ValueError("transfer plan artifact does not contain the preregistered seed schedule")
    if (
        source.manifest.experiment_id != request.experiment_id
        or source.manifest.repetitions != request.repetitions
        or len(source.manifest.candidate_sets) != 1
        or source.manifest.candidate_sets[0].world_id != request.world_id
    ):
        raise ValueError("transfer factorial manifest does not match the selected target request")
    return request


@dataclass(frozen=True)
class _VerifiedTransferTrial:
    outcome: FactorialOutcome
    cost: float
    valid_records: int
    record_count: int
    lineages: frozenset[str]


def _verify_transfer_trial(
    *,
    source: MotifTransferEvaluationReport,
    trial: MotifTransferTrialEvidence,
    request: FactorialCandidateFactoryRequest,
) -> _VerifiedTransferTrial:
    candidate, bundle = _load_verified_transfer_candidate(
        source=source,
        trial=trial,
        request=request,
    )
    records = _load_verified_transfer_records(trial=trial, bundle=bundle)
    costs, lineages = _verify_transfer_record_lineage(
        source=source,
        trial=trial,
        candidate=candidate,
        records=records,
    )
    mean_reward = fmean(record.evaluation.reward for record in records)
    if not math.isclose(mean_reward, float(trial.mean_reward), rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("transfer trial reward does not match its TrialRecords")
    valid_records = sum(_valid(record) for record in records)
    validity_rate = valid_records / len(records)
    if not math.isclose(
        validity_rate,
        trial.validity_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer trial validity does not match its TrialRecords")
    trial_cost = sum(costs)
    if not math.isclose(
        trial_cost,
        float(trial.estimated_cost_usd),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer trial cost does not match its TrialRecords")
    return _VerifiedTransferTrial(
        outcome=FactorialOutcome(trial_id=trial.trial.trial_id, value=mean_reward),
        cost=trial_cost,
        valid_records=valid_records,
        record_count=len(records),
        lineages=frozenset(lineages),
    )


def _load_verified_transfer_candidate(
    *,
    source: MotifTransferEvaluationReport,
    trial: MotifTransferTrialEvidence,
    request: FactorialCandidateFactoryRequest,
) -> tuple[MaterializedFactorialCandidate, RunBundle]:
    _verify_artifact(trial.candidate_manifest)
    bundle = _load_candidate_bundle(trial.candidate_manifest)
    if bundle.content_sha256 != trial.bundle_sha256:
        raise ValueError("transfer candidate manifest does not match its reported bundle")
    expected_reference = build_factorial_candidate_reference(
        request=request,
        cell=trial.trial.cell,
        bundle=bundle,
    )
    if expected_reference != trial.candidate_reference:
        raise ValueError("transfer candidate identity does not match its source factors")
    expected_seed = request.seeds[trial.trial.repetition - 1]
    if trial.execution_seed != expected_seed:
        raise ValueError("transfer trial seed does not match its preregistered repetition")
    snapshot_sha256 = canonical_content_sha256([snapshot.model_dump(mode="json") for snapshot in bundle.task_snapshots])
    if snapshot_sha256 != source.transfer_plan.target_applicability.source_snapshot_sha256:
        raise ValueError("transfer candidate snapshots do not match pre-execution applicability")
    candidate = MaterializedFactorialCandidate(
        cell=trial.trial.cell,
        reference=trial.candidate_reference,
        bundle=bundle,
    )
    return candidate, bundle


def _load_verified_transfer_records(
    *,
    trial: MotifTransferTrialEvidence,
    bundle: RunBundle,
) -> tuple[TrialRecord, ...]:
    records: list[TrialRecord] = []
    for artifact in trial.trial_records:
        _verify_artifact(artifact)
        try:
            records.append(TrialRecord.model_validate_json(Path(artifact.path).read_text(encoding="utf-8")))
        except Exception as error:
            raise ValueError(f"invalid transfer TrialRecord artifact: {artifact.path}") from error
    if tuple(record.trial_id for record in records) != trial.trial_record_ids:
        raise ValueError("transfer TrialRecord ids do not match the evaluation report")
    if len(records) != len(bundle.harbor.task_refs) or {record.task.task_id for record in records} != set(
        bundle.harbor.task_refs
    ):
        raise ValueError("transfer TrialRecords do not exactly cover their compiled tasks")
    if any(not record.evaluation.validity.verifier_completed for record in records):
        raise ValueError("transfer TrialRecord verifier evidence is incomplete")
    return tuple(records)


def _verify_transfer_record_lineage(
    *,
    source: MotifTransferEvaluationReport,
    trial: MotifTransferTrialEvidence,
    candidate: MaterializedFactorialCandidate,
    records: tuple[TrialRecord, ...],
) -> tuple[list[float], set[str]]:
    costs: list[float] = []
    lineages: set[str] = set()
    for record in records:
        if record.cost is None or record.cost.estimated_cost_usd is None:
            raise ValueError("transfer promotion requires complete known cost evidence")
        costs.append(float(record.cost.estimated_cost_usd))
        try:
            validate_factorial_record_lineage(
                record=record,
                trial=trial.trial,
                candidate=candidate,
                execution_seed=trial.execution_seed,
                plan_artifact=source.plan_artifact,
            )
        except ValueError as error:
            raise ValueError("transfer TrialRecord lineage does not match its planned trial") from error
        provenance = record.meta_harness_provenance
        assert provenance is not None
        if provenance.split != "holdout":
            raise ValueError("transfer TrialRecord lineage must use the holdout split")
        if provenance.motif_ids != source.motif_ids:
            raise ValueError("transfer TrialRecord motif ancestry does not match the evaluation report")
        if record.outputs.artifacts is None or trial.candidate_manifest not in record.outputs.artifacts:
            raise ValueError("transfer TrialRecord does not bind its candidate manifest")
        lineages.add(provenance.world_package_sha256)
    return costs, lineages


def _verify_transfer_evaluation_summary(
    *,
    source: MotifTransferEvaluationReport,
    verified_trials: tuple[_VerifiedTransferTrial, ...],
) -> None:
    interval = source.analysis.joint_incremental_uplift.interval
    recomputed = analyse_factorial(
        source.plan,
        [trial.outcome for trial in verified_trials],
        confidence_level=interval.confidence_level,
        bootstrap_replicates=interval.replicates,
        bootstrap_seed=interval.seed,
    )
    if recomputed != source.analysis:
        raise ValueError("transfer factorial analysis does not match the reported TrialRecords")
    lineages = {lineage for trial in verified_trials for lineage in trial.lineages}
    if tuple(sorted(lineages)) != source.world_lineage_ids:
        raise ValueError("transfer world lineages do not match the reported TrialRecords")
    total_records = sum(trial.record_count for trial in verified_trials)
    total_valid = sum(trial.valid_records for trial in verified_trials)
    validity_rate = total_valid / total_records
    if not math.isclose(
        validity_rate,
        source.validity_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer validity does not match the reported TrialRecords")
    total_cost = sum(trial.cost for trial in verified_trials)
    if not math.isclose(
        total_cost,
        float(source.estimated_cost_usd),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("transfer total cost does not match the reported TrialRecords")
    derived_transfer = _derive_transfer_evidence(
        analysis=recomputed,
        world_lineage_ids=tuple(sorted(lineages)),
        validity_rate=validity_rate,
        estimated_cost_usd=total_cost,
    )
    if source.transfer_evidence != derived_transfer:
        raise ValueError("transfer report does not contain its derived transfer evidence")


def _build_transfer_evaluation(
    plan: MotifTransferPlan,
    execution: FactorialStudyExecution,
    *,
    motif_ids: tuple[str, ...],
) -> MotifTransferEvaluationReport:
    trials = tuple(_trial_evidence(item) for item in execution.trial_executions)
    records = tuple(record for item in execution.trial_executions for record in item.records)
    lineages = tuple(
        sorted(
            {
                provenance.world_package_sha256
                for record in records
                if (provenance := record.meta_harness_provenance) is not None
            }
        )
    )
    if lineages != plan.target_applicability.world_lineage_ids:
        raise ValueError("executed holdout lineages do not match the pre-selection applicability attestation")
    analysis = execution.analysis
    analysis_sha256 = canonical_content_sha256(analysis.model_dump(mode="json"))
    estimated_cost = sum(float(item.estimated_cost_usd) for item in trials)
    validity_rate = sum(_valid(record) for record in records) / len(records)
    transfer = _derive_transfer_evidence(
        analysis=analysis,
        world_lineage_ids=lineages,
        validity_rate=validity_rate,
        estimated_cost_usd=estimated_cost,
    )
    selected_motif_sha256 = plan.selection_decision.selected_motif_sha256
    if selected_motif_sha256 is None:
        raise ValueError("transfer plan has no selected motif")
    return MotifTransferEvaluationReport(
        transfer_plan_sha256=plan.content_sha256,
        transfer_plan=plan,
        frozen_archive_sha256=plan.frozen_archive_sha256,
        selected_motif_sha256=selected_motif_sha256,
        manifest=execution.manifest,
        plan=execution.plan,
        plan_artifact=execution.plan_artifact.reference,
        trials=trials,
        analysis=analysis,
        analysis_sha256=analysis_sha256,
        motif_ids=motif_ids,
        world_lineage_ids=lineages,
        trial_count=len(trials),
        record_count=len(records),
        validity_rate=validity_rate,
        estimated_cost_usd=estimated_cost,
        cost_evidence_complete=True,
        transfer_evidence=transfer,
    )


def _trial_evidence(execution: FactorialTrialExecution) -> MotifTransferTrialEvidence:
    records = execution.records
    costs: list[float] = []
    for record in records:
        if record.cost is None or record.cost.estimated_cost_usd is None:
            raise ValueError("transfer promotion requires complete known cost evidence")
        costs.append(float(record.cost.estimated_cost_usd))
    artifacts = tuple(
        _artifact(path)
        for invocation in execution.execution.harbor_invocations
        for path in invocation.imported_trial_paths
    )
    if len(artifacts) != len(records):
        raise ValueError("transfer trial artifact count does not match imported TrialRecords")
    valid = sum(_valid(record) for record in records)
    provenances = tuple(record.meta_harness_provenance for record in records)
    if any(provenance is None for provenance in provenances):
        raise ValueError("transfer TrialRecords require meta-harness provenance")
    bundle_sha256s = {provenance.bundle_sha256 for provenance in provenances if provenance is not None}
    if len(bundle_sha256s) != 1:
        raise ValueError("transfer trial records do not share one candidate bundle")
    return MotifTransferTrialEvidence(
        trial=execution.trial,
        execution_seed=execution.execution_seed,
        candidate_reference=execution.candidate_reference,
        bundle_sha256=next(iter(bundle_sha256s)),
        candidate_manifest=execution.execution.candidate_manifest.reference,
        trial_record_ids=tuple(record.trial_id for record in records),
        trial_records=artifacts,
        mean_reward=fmean(record.evaluation.reward for record in records),
        validity_rate=valid / len(records),
        estimated_cost_usd=sum(costs),
        cost_evidence_complete=True,
    )


def _selected_motif_lineage_ids(
    library: MotifLibrary,
    selected_motif_sha256: str | None,
) -> tuple[str, ...]:
    if selected_motif_sha256 is None:
        raise ValueError("transfer selection does not identify a motif")
    motifs_by_id = {motif.motif_sha256: motif for motif in library.motifs}
    lineage: set[str] = set()
    current_id: str | None = selected_motif_sha256
    while current_id is not None:
        if current_id in lineage:
            raise ValueError("transfer motif ancestry contains a cycle")
        current = motifs_by_id.get(current_id)
        if current is None:
            raise ValueError("transfer motif ancestry is incomplete in the frozen archive")
        lineage.add(current_id)
        current_id = current.parent_motif_sha256
    return tuple(sorted(lineage))


def _derive_transfer_evidence(
    *,
    analysis: FactorialAnalysis,
    world_lineage_ids: tuple[str, ...],
    validity_rate: float,
    estimated_cost_usd: float,
) -> TransferEvidenceReference:
    return TransferEvidenceReference.create(
        evaluation_sha256=canonical_content_sha256(analysis.model_dump(mode="json")),
        world_lineage_ids=world_lineage_ids,
        split="holdout",
        objective_reward=float(analysis.cell_means[FactorialCell.HX_PX]),
        validity_rate=validity_rate,
        joint_uplift=float(analysis.joint_uplift.estimate),
        joint_incremental_uplift=float(analysis.joint_incremental_uplift.estimate),
        joint_incremental_uplift_lower_bound=float(analysis.joint_incremental_uplift.interval.lower),
        estimated_cost_usd=estimated_cost_usd,
        selected_before_holdout=True,
        archive_frozen=True,
    )


def _artifact(path: Path) -> ArtifactReference:
    source = Path(path)
    return ArtifactReference(
        kind="trial-record",
        path=str(source),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        media_type="application/json",
    )


def _load_candidate_bundle(reference: ArtifactReference) -> RunBundle:
    try:
        payload = json.loads(Path(reference.path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "aecbench.meta-harness-candidate.v1":
            raise ValueError("candidate manifest schema is invalid")
        return RunBundle.model_validate(payload.get("bundle"))
    except Exception as error:
        raise ValueError(f"invalid transfer candidate manifest: {reference.path}") from error


def _verify_artifact(reference: ArtifactReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"artifact digest mismatch: {reference.path}")


def _valid(record: TrialRecord) -> bool:
    validity = record.evaluation.validity
    return validity.output_parseable and validity.schema_valid and validity.verifier_completed
