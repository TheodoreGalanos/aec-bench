# ABOUTME: Defines immutable contracts for preregistered fixed-K harness-program studies.
# ABOUTME: Validates exact evidence and plan bindings for the four treatment combinations.

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, FiniteFloat, NonNegativeFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.applicability import MotifApplicabilityAttestation
from aec_bench.experimentation.qualification.harness_program_study.analysis import HarnessProgramAnalysis
from aec_bench.experimentation.qualification.harness_program_study.candidates import HarnessProgramCandidateRequest
from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCandidateReference,
    HarnessProgramCell,
    HarnessProgramPlan,
    HarnessProgramStudyManifest,
    HarnessProgramTrial,
)
from aec_bench.harness.budget import HarnessBudgetObservation

from .artifact_io import _sha256_path

HarnessProgramStudySplit = Literal["discovery", "calibration"]


class HarnessProgramStudySpec(LegacyContentAddressedModel):
    """Strict, immutable inputs and preregistered candidate references for one harness-program-study run."""

    schema_version: Literal["aecbench.harness-program-study-spec.v1"] = "aecbench.harness-program-study-spec.v1"
    conclusion: Literal["candidate_search"] = "candidate_search"
    policy_id: NonEmptyStr
    split: HarnessProgramStudySplit
    harness_generator_sha256: str
    program_generator_sha256: str
    candidate_requests: tuple[HarnessProgramCandidateRequest, ...]
    applicability: MotifApplicabilityAttestation
    study_manifest: HarnessProgramStudyManifest
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    bootstrap_replicates: PositiveInt = 2_000
    bootstrap_seed: int = 42

    @field_validator("harness_generator_sha256", "program_generator_sha256")
    @classmethod
    def validate_generator_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidate_requests")
    @classmethod
    def canonicalize_requests(
        cls,
        value: tuple[HarnessProgramCandidateRequest, ...],
    ) -> tuple[HarnessProgramCandidateRequest, ...]:
        if not value:
            raise ValueError("harness-program-study requires at least one candidate factory request")
        ordered = tuple(sorted(value, key=lambda request: request.task_set_id))
        task_set_ids = [request.task_set_id for request in ordered]
        if len(task_set_ids) != len(set(task_set_ids)):
            raise ValueError("harness-program-study candidate request task-set ids must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_preregistration(self) -> Self:
        requests_by_task_set = {request.task_set_id: request for request in self.candidate_requests}
        manifest_by_task_set = {
            candidate_set.task_set_id: candidate_set for candidate_set in self.study_manifest.candidate_sets
        }
        if set(requests_by_task_set) != set(manifest_by_task_set):
            raise ValueError("harness-program-study requests and preregistered manifest must cover the same task sets")
        if {request.experiment_id for request in self.candidate_requests} != {self.study_manifest.experiment_id}:
            raise ValueError("harness-program-study requests must share the preregistered experiment identity")
        if {request.repetitions for request in self.candidate_requests} != {self.study_manifest.repetitions}:
            raise ValueError("harness-program-study requests must share the preregistered repetition count")
        if len({request.kernel_ref for request in self.candidate_requests}) != 1:
            raise ValueError("harness-program-study requests must share one fixed kernel")
        kernel_ref = self.candidate_requests[0].kernel_ref
        if self.applicability.kernel_ref != kernel_ref:
            raise ValueError("harness-program-study applicability must use the preregistered fixed kernel")
        task_refs = tuple(sorted({task_ref for request in self.candidate_requests for task_ref in request.task_refs}))
        projected_task_refs = tuple(projection.snapshot.task_id for projection in self.applicability.projections)
        if projected_task_refs != task_refs:
            raise ValueError("harness-program-study applicability must cover the exact preregistered task set")
        return self


class HarnessProgramStudyCellEvidence(FrozenStrictModel):
    """One exact harness-program cell and its executable plan relationships."""

    cell: HarnessProgramCell
    candidate_reference: HarnessProgramCandidateReference
    bundle_id: NonEmptyStr
    compiled_harness_ref: HarnessInstanceRef
    compiled_program_ref: ExecutionProgramRef

    @model_validator(mode="after")
    def validate_cell_identity(self) -> Self:
        if self.candidate_reference.cell is not self.cell:
            raise ValueError("harness-program-study cell evidence does not match its candidate reference")
        if self.candidate_reference.harness_ref != self.compiled_harness_ref:
            raise ValueError("harness-program-study cell evidence does not match its compiled harness")
        return self


class HarnessProgramStudyCandidateSetEvidence(FrozenStrictModel):
    """Source factor templates, task-review snapshots, and all four compiled candidates."""

    task_set_id: NonEmptyStr
    request: HarnessProgramCandidateRequest
    task_snapshots: tuple[TaskSnapshotRef, ...]
    cells: tuple[HarnessProgramStudyCellEvidence, ...]

    @field_validator("cells")
    @classmethod
    def canonicalize_cells(
        cls,
        value: tuple[HarnessProgramStudyCellEvidence, ...],
    ) -> tuple[HarnessProgramStudyCellEvidence, ...]:
        order = {cell: index for index, cell in enumerate(HarnessProgramCell)}
        return tuple(sorted(value, key=lambda item: order[item.cell]))

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        if self.request.task_set_id != self.task_set_id:
            raise ValueError("harness-program-study candidate request does not match its task set")
        if len(self.cells) != len(HarnessProgramCell) or {item.cell for item in self.cells} != set(HarnessProgramCell):
            raise ValueError("harness-program-study candidate evidence requires all four harness-program cells")
        if tuple(snapshot.task_id for snapshot in self.task_snapshots) != self.request.task_refs:
            raise ValueError("harness-program-study task snapshots must exactly match the candidate request")
        if any(item.candidate_reference.task_set_id != self.task_set_id for item in self.cells):
            raise ValueError("harness-program-study candidate cells must match their candidate task set")
        return self


class HarnessProgramStudyTrialEvidence(FrozenStrictModel):
    """One planned harness-program trial with exact imported records and observable resource evidence."""

    trial: HarnessProgramTrial
    execution_seed: int
    candidate_reference: HarnessProgramCandidateReference
    bundle_id: NonEmptyStr
    trial_record_ids: tuple[NonEmptyStr, ...]
    trial_records: tuple[ArtifactReference, ...]
    budget: HarnessBudgetObservation
    mean_reward: FiniteFloat
    validity_rate: float = Field(ge=0.0, le=1.0)
    observed_tokens: NonNegativeInt
    token_evidence_complete: Literal[True]
    estimated_cost_usd: NonNegativeFloat
    cost_evidence_complete: Literal[True]

    @model_validator(mode="after")
    def validate_trial_evidence(self) -> Self:
        if self.candidate_reference != self.trial.candidate:
            raise ValueError("harness-program-study trial evidence does not match its planned candidate")
        if not self.trial_records or len(self.trial_records) != len(self.trial_record_ids):
            raise ValueError("harness-program-study trial evidence requires one artifact per TrialRecord")
        if len(set(self.trial_record_ids)) != len(self.trial_record_ids):
            raise ValueError("harness-program-study trial evidence contains duplicate TrialRecord ids")
        if self.budget.status != "within_budget":
            raise ValueError("harness-program-study trial evidence contains a breached harness budget")
        if not self.budget.token_evidence_complete or not self.budget.cost_evidence_complete:
            raise ValueError("harness-program-study requires complete token and cost evidence")
        if self.observed_tokens != self.budget.observed_tokens:
            raise ValueError("harness-program-study trial token evidence does not match its budget observation")
        if not math.isclose(
            float(self.estimated_cost_usd),
            float(self.budget.observed_cost_usd),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("harness-program-study trial cost evidence does not match its budget observation")
        return self


class HarnessProgramStudyReport(LegacyContentAddressedModel):
    """Complete content-addressed harness-program-study report; never represents harness learning."""

    schema_version: Literal["aecbench.harness-program-study-report.v1"] = "aecbench.harness-program-study-report.v1"
    conclusion: Literal["candidate_search"] = "candidate_search"
    spec_sha256: str
    spec_artifact: ArtifactReference
    kernel_ref: KernelRef
    applicability: MotifApplicabilityAttestation
    split: HarnessProgramStudySplit
    manifest: HarnessProgramStudyManifest
    plan: HarnessProgramPlan
    plan_artifact: ArtifactReference
    candidates: tuple[HarnessProgramStudyCandidateSetEvidence, ...]
    trials: tuple[HarnessProgramStudyTrialEvidence, ...]
    analysis: HarnessProgramAnalysis
    analysis_sha256: str
    review_lineage_ids: tuple[NonEmptyStr, ...]
    trial_count: PositiveInt
    validity_rate: float = Field(ge=0.0, le=1.0)
    observed_tokens: NonNegativeInt
    token_evidence_complete: Literal[True]
    estimated_cost_usd: NonNegativeFloat
    cost_evidence_complete: Literal[True]

    @field_validator("spec_sha256", "analysis_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("review_lineage_ids")
    @classmethod
    def canonicalize_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ordered = tuple(sorted(set(value)))
        if not ordered:
            raise ValueError("harness-program-study report requires at least one review lineage")
        return ordered

    @field_validator("candidates")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[HarnessProgramStudyCandidateSetEvidence, ...],
    ) -> tuple[HarnessProgramStudyCandidateSetEvidence, ...]:
        return tuple(sorted(value, key=lambda candidate: candidate.task_set_id))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        _validate_report_plan_bindings(self)
        cells_by_reference = _validate_report_candidate_bindings(self)
        _validate_report_trial_bindings(
            self,
            cells_by_reference=cells_by_reference,
        )
        _validate_report_resource_aggregates(self)
        return self


def _validate_report_plan_bindings(
    report: HarnessProgramStudyReport,
) -> None:
    if report.plan.manifest_sha256 != canonical_json_sha256(
        report.manifest.model_dump(mode="json"),
    ):
        raise ValueError("harness-program-study report plan does not bind its manifest")
    if report.applicability.kernel_ref != report.kernel_ref:
        raise ValueError(
            "harness-program-study report applicability does not bind its fixed kernel",
        )
    if report.applicability.review_lineage_ids != report.review_lineage_ids:
        raise ValueError(
            "harness-program-study report applicability does not bind its review lineages",
        )
    if report.plan.plan_sha256 != report.analysis.plan_sha256:
        raise ValueError("harness-program-study report analysis does not bind its plan")
    if report.analysis_sha256 != canonical_json_sha256(
        report.analysis.model_dump(mode="json"),
    ):
        raise ValueError(
            "harness-program-study report analysis_sha256 does not bind its analysis",
        )
    if report.plan_artifact.sha256 != _sha256_path(
        Path(report.plan_artifact.path),
    ):
        raise ValueError("harness-program-study report plan artifact digest mismatch")


def _validate_report_candidate_bindings(
    report: HarnessProgramStudyReport,
) -> dict[str, HarnessProgramStudyCellEvidence]:
    requests = tuple(candidate.request for candidate in report.candidates)
    manifest_by_task_set = {
        candidate_set.task_set_id: candidate_set for candidate_set in report.manifest.candidate_sets
    }
    if tuple(request.task_set_id for request in requests) != tuple(
        manifest_by_task_set,
    ):
        raise ValueError(
            "harness-program-study report candidates must exactly cover the manifest task sets",
        )
    cells_by_reference: dict[str, HarnessProgramStudyCellEvidence] = {}
    for candidate in report.candidates:
        references = tuple(item.candidate_reference for item in candidate.cells)
        if references != manifest_by_task_set[candidate.task_set_id].candidates:
            raise ValueError(
                "harness-program-study candidate evidence does not bind preregistered references",
            )
        if candidate.request.kernel_ref != report.kernel_ref:
            raise ValueError(
                "harness-program-study candidate evidence does not use the report kernel",
            )
        cells_by_reference.update(
            {item.candidate_reference.reference_sha256: item for item in candidate.cells},
        )
    return cells_by_reference


def _validate_report_trial_bindings(
    report: HarnessProgramStudyReport,
    *,
    cells_by_reference: dict[str, HarnessProgramStudyCellEvidence],
) -> None:
    if report.trial_count != len(report.trials) or report.trial_count != report.plan.trial_count:
        raise ValueError(
            "harness-program-study report requires exact planned trial coverage",
        )
    if tuple(item.trial for item in report.trials) != report.plan.trials:
        raise ValueError(
            "harness-program-study report trials must preserve exact plan order",
        )
    for trial in report.trials:
        cell = cells_by_reference.get(
            trial.candidate_reference.reference_sha256,
        )
        if cell is None or cell.bundle_id != trial.bundle_id:
            raise ValueError(
                "harness-program-study trial evidence does not bind its executable candidate",
            )


def _validate_report_resource_aggregates(
    report: HarnessProgramStudyReport,
) -> None:
    record_count = sum(len(item.trial_record_ids) for item in report.trials)
    derived_validity_rate = (
        sum(item.validity_rate * len(item.trial_record_ids) for item in report.trials) / record_count
    )
    if not math.isclose(
        report.validity_rate,
        derived_validity_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "harness-program-study report validity does not match trial evidence",
        )
    if any(not item.token_evidence_complete or not item.cost_evidence_complete for item in report.trials):
        raise ValueError(
            "harness-program-study report requires complete token and cost evidence",
        )
    if report.observed_tokens != sum(item.observed_tokens for item in report.trials):
        raise ValueError(
            "harness-program-study report token total does not match trial evidence",
        )
    if not math.isclose(
        float(report.estimated_cost_usd),
        sum(float(item.estimated_cost_usd) for item in report.trials),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "harness-program-study report cost total does not match trial evidence",
        )


@dataclass(frozen=True)
class HarnessProgramStudyRunResult:
    """Persisted harness-program-study report and its content-addressed location."""

    report: HarnessProgramStudyReport
    path: Path
