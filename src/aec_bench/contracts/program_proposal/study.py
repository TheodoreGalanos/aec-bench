# ABOUTME: Defines matched candidate evidence, paired comparisons, and complete optimization cycles.
# ABOUTME: Keeps evaluation coverage and selection invariants separate from proposal construction.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, FiniteFloat, field_validator, model_validator

from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef, validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal._canonical import (
    canonical_unique_models,
    canonical_unique_strings,
)
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.types import (
    CandidateEvidenceKind,
    OptimizationDisposition,
    OptimizationSplit,
    ProgramCandidateKind,
)
from aec_bench.contracts.validators import NonEmptyStr


class MatchedEvaluationCoordinate(LegacyContentAddressedModel):
    """One task-lineage-seed repetition shared by every candidate in a study."""

    schema_version: Literal["aecbench.matched-evaluation-coordinate.v2"] = "aecbench.matched-evaluation-coordinate.v2"
    coordinate_id: NonEmptyStr
    task_id: NonEmptyStr
    task_revision: NonEmptyStr
    split: OptimizationSplit
    review_lineage_id: NonEmptyStr
    seed: int = Field(ge=0)
    repetition: int = Field(ge=0)

    @field_validator("task_revision", "review_lineage_id")
    @classmethod
    def validate_snapshot_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class MatchedCandidateEvidenceRef(LegacyContentAddressedModel):
    """Evidence identity for one candidate evaluated on one matched coordinate."""

    schema_version: Literal["aecbench.matched-candidate-evidence-ref.v1"] = "aecbench.matched-candidate-evidence-ref.v1"
    evidence_id: NonEmptyStr
    candidate_id: NonEmptyStr
    coordinate_sha256: str
    kind: CandidateEvidenceKind
    trial_record_sha256: str | None
    evidence_complete: bool
    integrity_passed: bool

    @field_validator(
        "coordinate_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("trial_record_sha256")
    @classmethod
    def validate_optional_trial_record_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_evidence_shape(self) -> Self:
        if self.kind is CandidateEvidenceKind.TRIAL_RECORD and self.trial_record_sha256 is None:
            raise ValueError("trial-backed evidence requires a TrialRecord identity")
        if self.kind is not CandidateEvidenceKind.TRIAL_RECORD and self.trial_record_sha256 is not None:
            raise ValueError("non-trial evidence cannot bind a TrialRecord identity")
        return self


class ProgramCandidateStudy(LegacyContentAddressedModel):
    """Complete fixed-K/H0 matched evidence matrix for an incumbent and frozen proposals."""

    schema_version: Literal["aecbench.program-candidate-study.v1"] = "aecbench.program-candidate-study.v1"
    study_id: NonEmptyStr
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    proposal_freeze: ProposalFreeze
    aggregate_budget: HarnessBudget
    incumbent_candidate: ProgramCandidateRef
    coordinates: tuple[MatchedEvaluationCoordinate, ...] = Field(min_length=1)
    evidence_refs: tuple[MatchedCandidateEvidenceRef, ...] = Field(min_length=1)

    @field_validator("coordinates")
    @classmethod
    def canonicalize_coordinates(
        cls,
        value: tuple[MatchedEvaluationCoordinate, ...],
    ) -> tuple[MatchedEvaluationCoordinate, ...]:
        canonical = canonical_unique_models(
            value,
            identity="coordinate_id",
            label="matched coordinates",
        )
        semantic_identities = tuple(
            (
                coordinate.task_id,
                coordinate.task_revision,
                coordinate.split,
                coordinate.review_lineage_id,
                coordinate.seed,
                coordinate.repetition,
            )
            for coordinate in canonical
        )
        if len(semantic_identities) != len(set(semantic_identities)):
            raise ValueError("matched coordinate semantic identities must be unique")
        return canonical

    @field_validator("evidence_refs")
    @classmethod
    def canonicalize_evidence_refs(
        cls,
        value: tuple[MatchedCandidateEvidenceRef, ...],
    ) -> tuple[MatchedCandidateEvidenceRef, ...]:
        ids = [reference.evidence_id for reference in value]
        identities = [(reference.candidate_id, reference.coordinate_sha256) for reference in value]
        if len(ids) != len(set(ids)):
            raise ValueError("matched evidence ids must be unique")
        if len(identities) != len(set(identities)):
            raise ValueError("candidate-coordinate evidence pairs must be unique")
        return tuple(
            sorted(
                value,
                key=lambda reference: (
                    reference.candidate_id,
                    reference.coordinate_sha256,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_study_bindings(self) -> Self:
        _validate_study_harness_bindings(self)
        _validate_study_incumbent(self)
        _validate_study_coordinates(self)
        _validate_study_evidence_coverage(self)
        return self


class PairedCandidateComparison(LegacyContentAddressedModel):
    """Fail-closed comparison of one frozen proposal with the incumbent."""

    schema_version: Literal["aecbench.paired-candidate-comparison.v1"] = "aecbench.paired-candidate-comparison.v1"
    comparison_id: NonEmptyStr
    study_sha256: str
    incumbent_candidate: ProgramCandidateRef
    challenger_candidate: ProgramCandidateRef
    incumbent_evidence_refs: tuple[MatchedCandidateEvidenceRef, ...] = Field(min_length=1)
    challenger_evidence_refs: tuple[MatchedCandidateEvidenceRef, ...] = Field(min_length=1)
    coverage_complete: bool
    integrity_passed: bool
    utility_delta: FiniteFloat | None
    disposition: OptimizationDisposition
    selected_candidate_id: NonEmptyStr | None

    @field_validator("study_sha256")
    @classmethod
    def validate_study_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("incumbent_evidence_refs", "challenger_evidence_refs")
    @classmethod
    def canonicalize_evidence_refs(
        cls,
        value: tuple[MatchedCandidateEvidenceRef, ...],
    ) -> tuple[MatchedCandidateEvidenceRef, ...]:
        coordinates = [reference.coordinate_sha256 for reference in value]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("comparison evidence coordinates must be unique")
        return tuple(sorted(value, key=lambda reference: reference.coordinate_sha256))

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        _validate_comparison_candidate_roles(self)
        _validate_comparison_evidence_bindings(self)
        actual_coverage = _comparison_has_complete_coverage(self)
        actual_integrity = _comparison_has_passing_integrity(self)
        _validate_comparison_evidence_flags(
            self,
            actual_coverage=actual_coverage,
            actual_integrity=actual_integrity,
        )
        evidence_valid = self.coverage_complete and self.integrity_passed
        if self.disposition is OptimizationDisposition.EXPERIMENT_ERROR:
            _validate_experiment_error_comparison(self, evidence_valid=evidence_valid)
            return self
        _validate_non_error_comparison(self, evidence_valid=evidence_valid)
        _validate_comparison_selection(self)
        return self


class DecompositionOptimizationCycle(LegacyContentAddressedModel):
    """Complete frozen-candidate optimization cycle with no diagnostic-repair semantics."""

    schema_version: Literal["aecbench.decomposition-optimization-cycle.v1"] = (
        "aecbench.decomposition-optimization-cycle.v1"
    )
    cycle_id: NonEmptyStr
    study: ProgramCandidateStudy
    scheduled_candidate_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    completed_candidate_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    comparisons: tuple[PairedCandidateComparison, ...] = Field(min_length=1)
    cycle_complete: Literal[True]
    disposition: OptimizationDisposition
    selected_candidate_id: NonEmptyStr | None

    @field_validator("scheduled_candidate_ids", "completed_candidate_ids")
    @classmethod
    def canonicalize_candidate_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="cycle candidate ids")

    @field_validator("comparisons")
    @classmethod
    def canonicalize_comparisons(
        cls,
        value: tuple[PairedCandidateComparison, ...],
    ) -> tuple[PairedCandidateComparison, ...]:
        challenger_ids = [comparison.challenger_candidate.candidate_id for comparison in value]
        if len(challenger_ids) != len(set(challenger_ids)):
            raise ValueError("cycle comparisons must be unique by challenger")
        return tuple(
            sorted(
                value,
                key=lambda comparison: comparison.challenger_candidate.candidate_id,
            )
        )

    @model_validator(mode="after")
    def validate_complete_cycle(self) -> Self:
        frozen_ids = tuple(
            sorted(candidate.candidate_id for candidate in self.study.proposal_freeze.realized_candidates)
        )
        if self.scheduled_candidate_ids != frozen_ids or self.completed_candidate_ids != frozen_ids:
            raise ValueError("optimization cycle requires a complete frozen candidate schedule")
        comparison_ids = tuple(comparison.challenger_candidate.candidate_id for comparison in self.comparisons)
        if comparison_ids != frozen_ids:
            raise ValueError("optimization cycle requires one comparison for every frozen candidate")
        study_evidence = {reference.content_sha256 for reference in self.study.evidence_refs}
        for comparison in self.comparisons:
            if comparison.study_sha256 != self.study.content_sha256:
                raise ValueError("cycle comparison does not bind the exact study")
            comparison_evidence = {
                reference.content_sha256
                for reference in (
                    *comparison.incumbent_evidence_refs,
                    *comparison.challenger_evidence_refs,
                )
            }
            expected_evidence = {
                reference.content_sha256
                for reference in self.study.evidence_refs
                if reference.candidate_id
                in {
                    self.study.incumbent_candidate.candidate_id,
                    comparison.challenger_candidate.candidate_id,
                }
            }
            if comparison_evidence != expected_evidence or not comparison_evidence <= study_evidence:
                raise ValueError("cycle comparison does not use the exact matched study evidence")
        selected = [
            comparison
            for comparison in self.comparisons
            if comparison.disposition
            in {
                OptimizationDisposition.ACCEPT,
                OptimizationDisposition.DEVELOPMENT_SELECTED,
            }
        ]
        has_error = any(
            comparison.disposition is OptimizationDisposition.EXPERIMENT_ERROR for comparison in self.comparisons
        )
        has_abstention = any(
            comparison.disposition is OptimizationDisposition.ABSTAIN for comparison in self.comparisons
        )
        if self.disposition is OptimizationDisposition.EXPERIMENT_ERROR:
            valid = has_error and self.selected_candidate_id is None
        elif self.disposition in {
            OptimizationDisposition.ACCEPT,
            OptimizationDisposition.DEVELOPMENT_SELECTED,
        }:
            valid = (
                not has_error
                and len(selected) == 1
                and selected[0].disposition is self.disposition
                and self.selected_candidate_id == selected[0].challenger_candidate.candidate_id
            )
        elif self.disposition is OptimizationDisposition.ABSTAIN:
            valid = not has_error and not selected and has_abstention and self.selected_candidate_id is None
        else:
            valid = (
                not has_error
                and not selected
                and not has_abstention
                and self.selected_candidate_id == self.study.incumbent_candidate.candidate_id
            )
        if not valid:
            raise ValueError("cycle disposition does not match its complete comparison set")
        return self


def _validate_study_harness_bindings(study: ProgramCandidateStudy) -> None:
    fixed_harness = study.proposal_freeze.problem_view.fixed_harness
    if study.kernel_ref != fixed_harness.kernel_ref:
        raise ValueError("study kernel does not match the frozen H0 projection")
    if study.fixed_harness_ref != study.proposal_freeze.fixed_harness_ref:
        raise ValueError("study fixed H0 does not match the proposal freeze")
    if study.aggregate_budget != fixed_harness.aggregate_budget:
        raise ValueError("study aggregate budget does not match frozen H0")
    if study.evaluation_regime_ref != study.proposal_freeze.evaluation_regime_ref:
        raise ValueError("study evaluation regime does not match the proposal freeze")


def _validate_study_incumbent(study: ProgramCandidateStudy) -> None:
    if study.incumbent_candidate.kind is not ProgramCandidateKind.INCUMBENT:
        raise ValueError("study incumbent must have incumbent candidate kind")
    frozen_incumbent = study.proposal_freeze.incumbent_candidate
    if frozen_incumbent is not None and study.incumbent_candidate != frozen_incumbent:
        raise ValueError("study incumbent does not match the frozen incumbent")


def _validate_study_coordinates(study: ProgramCandidateStudy) -> None:
    view = study.proposal_freeze.problem_view
    for coordinate in study.coordinates:
        if coordinate.split is not study.proposal_freeze.split:
            raise ValueError("matched coordinate split does not match proposal freeze")
        if coordinate.task_id != view.task_id or coordinate.task_revision != view.task_revision:
            raise ValueError("matched coordinate task does not match problem view")
        if coordinate.review_lineage_id != study.proposal_freeze.selected_review_lineage_id:
            raise ValueError("matched coordinate review lineage does not match proposal freeze")


def _validate_study_evidence_coverage(study: ProgramCandidateStudy) -> None:
    candidate_ids = {
        study.incumbent_candidate.candidate_id,
        *(candidate.candidate_id for candidate in study.proposal_freeze.realized_candidates),
    }
    coordinate_hashes = {coordinate.content_sha256 for coordinate in study.coordinates}
    expected_pairs = {
        (candidate_id, coordinate_sha256) for candidate_id in candidate_ids for coordinate_sha256 in coordinate_hashes
    }
    actual_pairs = {(reference.candidate_id, reference.coordinate_sha256) for reference in study.evidence_refs}
    if actual_pairs != expected_pairs:
        raise ValueError("study requires exact candidate-coordinate coverage")


def _validate_comparison_candidate_roles(comparison: PairedCandidateComparison) -> None:
    if comparison.incumbent_candidate.kind is not ProgramCandidateKind.INCUMBENT:
        raise ValueError("comparison incumbent must have incumbent kind")
    if comparison.challenger_candidate.kind is not ProgramCandidateKind.PROPOSAL:
        raise ValueError("comparison challenger must have proposal kind")
    if comparison.incumbent_candidate.candidate_id == comparison.challenger_candidate.candidate_id:
        raise ValueError("comparison candidates must be distinct")


def _validate_comparison_evidence_bindings(comparison: PairedCandidateComparison) -> None:
    if any(
        reference.candidate_id != comparison.incumbent_candidate.candidate_id
        for reference in comparison.incumbent_evidence_refs
    ):
        raise ValueError("incumbent evidence does not bind the incumbent")
    if any(
        reference.candidate_id != comparison.challenger_candidate.candidate_id
        for reference in comparison.challenger_evidence_refs
    ):
        raise ValueError("challenger evidence does not bind the challenger")


def _comparison_evidence_refs(
    comparison: PairedCandidateComparison,
) -> tuple[MatchedCandidateEvidenceRef, ...]:
    return (
        *comparison.incumbent_evidence_refs,
        *comparison.challenger_evidence_refs,
    )


def _comparison_has_complete_coverage(
    comparison: PairedCandidateComparison,
) -> bool:
    incumbent_coordinates = {reference.coordinate_sha256 for reference in comparison.incumbent_evidence_refs}
    challenger_coordinates = {reference.coordinate_sha256 for reference in comparison.challenger_evidence_refs}
    return incumbent_coordinates == challenger_coordinates and all(
        reference.evidence_complete for reference in _comparison_evidence_refs(comparison)
    )


def _comparison_has_passing_integrity(
    comparison: PairedCandidateComparison,
) -> bool:
    return all(reference.integrity_passed for reference in _comparison_evidence_refs(comparison))


def _validate_comparison_evidence_flags(
    comparison: PairedCandidateComparison,
    *,
    actual_coverage: bool,
    actual_integrity: bool,
) -> None:
    if comparison.coverage_complete != actual_coverage:
        raise ValueError("coverage flag does not match paired evidence")
    if comparison.integrity_passed != actual_integrity:
        raise ValueError("integrity flag does not match paired evidence")


def _validate_experiment_error_comparison(
    comparison: PairedCandidateComparison,
    *,
    evidence_valid: bool,
) -> None:
    if evidence_valid or comparison.utility_delta is not None or comparison.selected_candidate_id is not None:
        raise ValueError("experiment_error requires incomplete coverage or failed integrity and no selection")


def _validate_non_error_comparison(
    comparison: PairedCandidateComparison,
    *,
    evidence_valid: bool,
) -> None:
    if not evidence_valid:
        raise ValueError("comparison disposition requires complete matched coverage and passing integrity")
    if comparison.utility_delta is None:
        raise ValueError("non-error comparison requires a utility delta")


def _validate_comparison_selection(comparison: PairedCandidateComparison) -> None:
    expected_selected = _expected_selected_candidate_id(comparison)
    if comparison.selected_candidate_id != expected_selected:
        raise ValueError(f"{comparison.disposition.value} disposition has an invalid selected candidate")


def _expected_selected_candidate_id(
    comparison: PairedCandidateComparison,
) -> str | None:
    if comparison.disposition in {
        OptimizationDisposition.ACCEPT,
        OptimizationDisposition.DEVELOPMENT_SELECTED,
    }:
        return comparison.challenger_candidate.candidate_id
    if comparison.disposition is OptimizationDisposition.REJECT:
        return comparison.incumbent_candidate.candidate_id
    return None
