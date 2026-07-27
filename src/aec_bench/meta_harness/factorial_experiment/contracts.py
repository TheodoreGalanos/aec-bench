# ABOUTME: Defines immutable contracts for preregistered fixed-K factorial experiments.
# ABOUTME: Preserves historical schema identifiers and validates exact evidence and plan bindings.

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, FiniteFloat, NonNegativeFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    KernelRef,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.applicability import MotifApplicabilityAttestation
from aec_bench.meta_harness.factorial_analysis import FactorialAnalysis
from aec_bench.meta_harness.factorial_candidates import FactorialCandidateFactoryRequest
from aec_bench.meta_harness.factorial_plan import (
    FactorialCandidateReference,
    FactorialCell,
    FactorialPlan,
    FactorialStudyManifest,
    FactorialTrial,
)
from aec_bench.meta_harness.harness_budget import HarnessBudgetObservation

from .artifact_io import _sha256_path

FactorialExperimentSplit = Literal["discovery", "calibration"]


class FactorialExperimentSpec(ContentAddressedModel):
    """Strict, immutable inputs and preregistered candidate references for one stage-zero run."""

    schema_version: Literal["aecbench.meta-harness-stage-zero-spec.v2"] = "aecbench.meta-harness-stage-zero-spec.v2"
    conclusion: Literal["candidate_search"] = "candidate_search"
    policy_id: NonEmptyStr
    split: FactorialExperimentSplit
    harness_generator_sha256: str
    program_generator_sha256: str
    candidate_requests: tuple[FactorialCandidateFactoryRequest, ...]
    applicability: MotifApplicabilityAttestation
    study_manifest: FactorialStudyManifest
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
        value: tuple[FactorialCandidateFactoryRequest, ...],
    ) -> tuple[FactorialCandidateFactoryRequest, ...]:
        if not value:
            raise ValueError("stage-zero requires at least one candidate factory request")
        ordered = tuple(sorted(value, key=lambda request: request.world_id))
        world_ids = [request.world_id for request in ordered]
        if len(world_ids) != len(set(world_ids)):
            raise ValueError("stage-zero candidate request world ids must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_preregistration(self) -> Self:
        requests_by_world = {request.world_id: request for request in self.candidate_requests}
        manifest_by_world = {
            candidate_set.world_id: candidate_set for candidate_set in self.study_manifest.candidate_sets
        }
        if set(requests_by_world) != set(manifest_by_world):
            raise ValueError("stage-zero requests and preregistered manifest must cover the exact same worlds")
        if {request.experiment_id for request in self.candidate_requests} != {self.study_manifest.experiment_id}:
            raise ValueError("stage-zero requests must share the preregistered experiment identity")
        if {request.repetitions for request in self.candidate_requests} != {self.study_manifest.repetitions}:
            raise ValueError("stage-zero requests must share the preregistered repetition count")
        if len({request.kernel_ref for request in self.candidate_requests}) != 1:
            raise ValueError("stage-zero requests must share one fixed kernel")
        kernel_ref = self.candidate_requests[0].kernel_ref
        if self.applicability.kernel_ref != kernel_ref:
            raise ValueError("stage-zero applicability must use the preregistered fixed kernel")
        task_refs = tuple(sorted({task_ref for request in self.candidate_requests for task_ref in request.task_refs}))
        projected_task_refs = tuple(projection.snapshot.task_id for projection in self.applicability.projections)
        if projected_task_refs != task_refs:
            raise ValueError("stage-zero applicability must cover the exact preregistered task set")
        return self


class FactorialExperimentCellEvidence(FrozenStrictModel):
    """One exact factorial cell, executable bundle identity, and candidate-manifest artifact."""

    cell: FactorialCell
    candidate_reference: FactorialCandidateReference
    bundle_sha256: str
    compiled_harness_sha256: str
    compiled_program_sha256: str
    candidate_manifest: ArtifactReference

    @field_validator("bundle_sha256", "compiled_harness_sha256", "compiled_program_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_cell_identity(self) -> Self:
        if self.candidate_reference.cell is not self.cell:
            raise ValueError("stage-zero cell evidence does not match its candidate reference")
        if self.candidate_reference.harness_sha256 != self.compiled_harness_sha256:
            raise ValueError("stage-zero cell evidence does not match its compiled harness")
        return self


class FactorialExperimentCandidateSetEvidence(FrozenStrictModel):
    """Source factor templates, task/world snapshots, and all four compiled candidates."""

    world_id: NonEmptyStr
    request: FactorialCandidateFactoryRequest
    task_snapshots: tuple[TaskSnapshotRef, ...]
    cells: tuple[FactorialExperimentCellEvidence, ...]

    @field_validator("cells")
    @classmethod
    def canonicalize_cells(
        cls,
        value: tuple[FactorialExperimentCellEvidence, ...],
    ) -> tuple[FactorialExperimentCellEvidence, ...]:
        order = {cell: index for index, cell in enumerate(FactorialCell)}
        return tuple(sorted(value, key=lambda item: order[item.cell]))

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        if self.request.world_id != self.world_id:
            raise ValueError("stage-zero candidate request does not match its world")
        if len(self.cells) != len(FactorialCell) or {item.cell for item in self.cells} != set(FactorialCell):
            raise ValueError("stage-zero candidate evidence requires all four factorial cells")
        if tuple(snapshot.task_id for snapshot in self.task_snapshots) != self.request.task_refs:
            raise ValueError("stage-zero task snapshots must exactly match the candidate request")
        if any(item.candidate_reference.world_id != self.world_id for item in self.cells):
            raise ValueError("stage-zero candidate cells must match their candidate world")
        return self


class FactorialExperimentTrialEvidence(FrozenStrictModel):
    """One planned factorial trial with exact imported records and observable resource evidence."""

    trial: FactorialTrial
    execution_seed: int
    candidate_reference: FactorialCandidateReference
    bundle_sha256: str
    trial_record_ids: tuple[NonEmptyStr, ...]
    trial_records: tuple[ArtifactReference, ...]
    budget: HarnessBudgetObservation
    mean_reward: FiniteFloat
    validity_rate: float = Field(ge=0.0, le=1.0)
    observed_tokens: NonNegativeInt
    token_evidence_complete: Literal[True]
    estimated_cost_usd: NonNegativeFloat
    cost_evidence_complete: Literal[True]

    @field_validator("bundle_sha256")
    @classmethod
    def validate_bundle_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial_evidence(self) -> Self:
        if self.candidate_reference != self.trial.candidate:
            raise ValueError("stage-zero trial evidence does not match its planned candidate")
        if not self.trial_records or len(self.trial_records) != len(self.trial_record_ids):
            raise ValueError("stage-zero trial evidence requires one artifact per TrialRecord")
        if len(set(self.trial_record_ids)) != len(self.trial_record_ids):
            raise ValueError("stage-zero trial evidence contains duplicate TrialRecord ids")
        if self.budget.status != "within_budget":
            raise ValueError("stage-zero trial evidence contains a breached harness budget")
        if not self.budget.token_evidence_complete or not self.budget.cost_evidence_complete:
            raise ValueError("stage-zero requires complete token and cost evidence")
        if self.observed_tokens != self.budget.observed_tokens:
            raise ValueError("stage-zero trial token evidence does not match its budget observation")
        if not math.isclose(
            float(self.estimated_cost_usd),
            float(self.budget.observed_cost_usd),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("stage-zero trial cost evidence does not match its budget observation")
        return self


class FactorialExperimentReport(ContentAddressedModel):
    """Complete content-addressed stage-zero report; never represents harness learning."""

    schema_version: Literal["aecbench.meta-harness-stage-zero-report.v2"] = "aecbench.meta-harness-stage-zero-report.v2"
    conclusion: Literal["candidate_search"] = "candidate_search"
    spec_sha256: str
    spec_artifact: ArtifactReference
    kernel_ref: KernelRef
    applicability: MotifApplicabilityAttestation
    split: FactorialExperimentSplit
    manifest: FactorialStudyManifest
    plan: FactorialPlan
    plan_artifact: ArtifactReference
    candidates: tuple[FactorialExperimentCandidateSetEvidence, ...]
    trials: tuple[FactorialExperimentTrialEvidence, ...]
    analysis: FactorialAnalysis
    analysis_sha256: str
    world_lineage_ids: tuple[NonEmptyStr, ...]
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

    @field_validator("world_lineage_ids")
    @classmethod
    def canonicalize_world_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        ordered = tuple(sorted(set(value)))
        if not ordered:
            raise ValueError("stage-zero report requires at least one world lineage")
        return ordered

    @field_validator("candidates")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[FactorialExperimentCandidateSetEvidence, ...],
    ) -> tuple[FactorialExperimentCandidateSetEvidence, ...]:
        return tuple(sorted(value, key=lambda candidate: candidate.world_id))

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
    report: FactorialExperimentReport,
) -> None:
    if report.plan.manifest_sha256 != canonical_content_sha256(
        report.manifest.model_dump(mode="json"),
    ):
        raise ValueError("stage-zero report plan does not bind its manifest")
    if report.applicability.kernel_ref != report.kernel_ref:
        raise ValueError(
            "stage-zero report applicability does not bind its fixed kernel",
        )
    if report.applicability.world_lineage_ids != report.world_lineage_ids:
        raise ValueError(
            "stage-zero report applicability does not bind its world lineages",
        )
    if report.plan.plan_sha256 != report.analysis.plan_sha256:
        raise ValueError("stage-zero report analysis does not bind its plan")
    if report.analysis_sha256 != canonical_content_sha256(
        report.analysis.model_dump(mode="json"),
    ):
        raise ValueError(
            "stage-zero report analysis_sha256 does not bind its analysis",
        )
    if report.plan_artifact.sha256 != _sha256_path(
        Path(report.plan_artifact.path),
    ):
        raise ValueError("stage-zero report plan artifact digest mismatch")


def _validate_report_candidate_bindings(
    report: FactorialExperimentReport,
) -> dict[str, FactorialExperimentCellEvidence]:
    requests = tuple(candidate.request for candidate in report.candidates)
    manifest_by_world = {candidate_set.world_id: candidate_set for candidate_set in report.manifest.candidate_sets}
    if tuple(request.world_id for request in requests) != tuple(
        manifest_by_world,
    ):
        raise ValueError(
            "stage-zero report candidates must exactly cover the manifest worlds",
        )
    cells_by_reference: dict[str, FactorialExperimentCellEvidence] = {}
    for candidate in report.candidates:
        references = tuple(item.candidate_reference for item in candidate.cells)
        if references != manifest_by_world[candidate.world_id].candidates:
            raise ValueError(
                "stage-zero candidate evidence does not bind preregistered references",
            )
        if candidate.request.kernel_ref != report.kernel_ref:
            raise ValueError(
                "stage-zero candidate evidence does not use the report kernel",
            )
        cells_by_reference.update(
            {item.candidate_reference.reference_sha256: item for item in candidate.cells},
        )
    return cells_by_reference


def _validate_report_trial_bindings(
    report: FactorialExperimentReport,
    *,
    cells_by_reference: dict[str, FactorialExperimentCellEvidence],
) -> None:
    if report.trial_count != len(report.trials) or report.trial_count != report.plan.trial_count:
        raise ValueError(
            "stage-zero report requires exact planned trial coverage",
        )
    if tuple(item.trial for item in report.trials) != report.plan.trials:
        raise ValueError(
            "stage-zero report trials must preserve exact plan order",
        )
    for trial in report.trials:
        cell = cells_by_reference.get(
            trial.candidate_reference.reference_sha256,
        )
        if cell is None or cell.bundle_sha256 != trial.bundle_sha256:
            raise ValueError(
                "stage-zero trial evidence does not bind its executable candidate",
            )


def _validate_report_resource_aggregates(
    report: FactorialExperimentReport,
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
            "stage-zero report validity does not match trial evidence",
        )
    if any(not item.token_evidence_complete or not item.cost_evidence_complete for item in report.trials):
        raise ValueError(
            "stage-zero report requires complete token and cost evidence",
        )
    if report.observed_tokens != sum(item.observed_tokens for item in report.trials):
        raise ValueError(
            "stage-zero report token total does not match trial evidence",
        )
    if not math.isclose(
        float(report.estimated_cost_usd),
        sum(float(item.estimated_cost_usd) for item in report.trials),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "stage-zero report cost total does not match trial evidence",
        )


@dataclass(frozen=True)
class FactorialExperimentRunResult:
    """Persisted stage-zero report and its content-addressed location."""

    report: FactorialExperimentReport
    path: Path
