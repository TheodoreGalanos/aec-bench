# ABOUTME: Builds evidence-blind proposal schedules and fail-closed proposal studies.
# ABOUTME: Derives deterministic candidate selection only from exactly bound evaluation outcomes.

from __future__ import annotations

import json
from statistics import fmean
from typing import Literal, Self

from pydantic import Field, FiniteFloat, field_validator, model_validator

from aec_bench.contracts.evaluation_outcome import (
    EvaluationDisposition,
    EvaluationOutcome,
)
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import (
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.study import (
    DecompositionOptimizationCycle,
    MatchedCandidateEvidenceRef,
    MatchedEvaluationCoordinate,
    PairedCandidateComparison,
    ProgramCandidateStudy,
)
from aec_bench.contracts.program_proposal.types import (
    CandidateEvidenceKind,
    OptimizationDisposition,
    OptimizationSplit,
    ProgramCandidateKind,
)
from aec_bench.contracts.validators import NonEmptyStr


class OptimizationExperimentError(ValueError):
    """Fail-closed protocol error raised before any ungrounded utility is interpreted."""

    disposition = OptimizationDisposition.EXPERIMENT_ERROR


class CandidateExecutionAssignment(LegacyContentAddressedModel):
    """One immutable candidate-coordinate execution assignment."""

    schema_version: Literal["aecbench.candidate-execution-assignment.v1"] = "aecbench.candidate-execution-assignment.v1"
    candidate: ProgramCandidateRef
    coordinate: MatchedEvaluationCoordinate


class DecompositionExecutionSchedule(LegacyContentAddressedModel):
    """Complete outcome-blind execution matrix for an incumbent and frozen proposals."""

    schema_version: Literal["aecbench.decomposition-execution-schedule.v1"] = (
        "aecbench.decomposition-execution-schedule.v1"
    )
    schedule_id: NonEmptyStr
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    proposal_freeze: ProposalFreeze
    aggregate_budget: HarnessBudget
    incumbent_candidate: ProgramCandidateRef
    coordinates: tuple[MatchedEvaluationCoordinate, ...] = Field(min_length=1)
    assignments: tuple[CandidateExecutionAssignment, ...] = Field(min_length=1)

    @field_validator("coordinates")
    @classmethod
    def canonicalize_coordinates(
        cls,
        value: tuple[MatchedEvaluationCoordinate, ...],
    ) -> tuple[MatchedEvaluationCoordinate, ...]:
        coordinate_ids = tuple(coordinate.coordinate_id for coordinate in value)
        coordinate_hashes = tuple(coordinate.content_sha256 for coordinate in value)
        if len(coordinate_ids) != len(set(coordinate_ids)):
            raise ValueError("schedule coordinate ids must be unique")
        if len(coordinate_hashes) != len(set(coordinate_hashes)):
            raise ValueError("schedule coordinate identities must be unique")
        semantic_identities = tuple(
            (
                coordinate.task_id,
                coordinate.task_revision,
                coordinate.split,
                coordinate.review_lineage_id,
                coordinate.seed,
                coordinate.repetition,
            )
            for coordinate in value
        )
        if len(semantic_identities) != len(set(semantic_identities)):
            raise ValueError("schedule coordinate semantic identities must be unique")
        return tuple(sorted(value, key=lambda coordinate: coordinate.coordinate_id))

    @field_validator("assignments")
    @classmethod
    def canonicalize_assignments(
        cls,
        value: tuple[CandidateExecutionAssignment, ...],
    ) -> tuple[CandidateExecutionAssignment, ...]:
        pairs = tuple(
            (
                assignment.candidate.content_sha256,
                assignment.coordinate.content_sha256,
            )
            for assignment in value
        )
        if len(pairs) != len(set(pairs)):
            raise ValueError("schedule candidate-coordinate assignments must be unique")
        return tuple(
            sorted(
                value,
                key=lambda assignment: (
                    assignment.candidate.candidate_id,
                    assignment.coordinate.coordinate_id,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_schedule_bindings(self) -> Self:
        _validate_schedule_authority_bindings(self)
        candidates = _validate_schedule_candidates(self)
        _validate_schedule_coordinates(self)
        _validate_schedule_cross_product(self, candidates=candidates)
        return self


def _validate_schedule_authority_bindings(
    schedule: DecompositionExecutionSchedule,
) -> None:
    projection = schedule.proposal_freeze.problem_view.fixed_harness
    if schedule.kernel_ref != projection.kernel_ref:
        raise ValueError("schedule kernel does not match the frozen H0 projection")
    if schedule.fixed_harness_ref != schedule.proposal_freeze.fixed_harness_ref:
        raise ValueError("schedule fixed H0 does not match the proposal freeze")
    if schedule.evaluation_regime_ref != schedule.proposal_freeze.evaluation_regime_ref:
        raise ValueError("schedule evaluation regime does not match the proposal freeze")
    if schedule.aggregate_budget != projection.aggregate_budget:
        raise ValueError("schedule aggregate budget does not match frozen H0")


def _validate_schedule_candidates(
    schedule: DecompositionExecutionSchedule,
) -> tuple[ProgramCandidateRef, ...]:
    if schedule.incumbent_candidate.kind is not ProgramCandidateKind.INCUMBENT:
        raise ValueError("schedule incumbent must have incumbent candidate kind")
    if (
        schedule.proposal_freeze.incumbent_candidate is not None
        and schedule.incumbent_candidate != schedule.proposal_freeze.incumbent_candidate
    ):
        raise ValueError("schedule incumbent does not match the frozen incumbent")
    candidates = (
        schedule.incumbent_candidate,
        *schedule.proposal_freeze.realized_candidates,
    )
    candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("schedule candidate ids must be unique")
    return candidates


def _validate_schedule_coordinates(schedule: DecompositionExecutionSchedule) -> None:
    view = schedule.proposal_freeze.problem_view
    for coordinate in schedule.coordinates:
        if coordinate.split is not schedule.proposal_freeze.split:
            raise ValueError("schedule coordinate split does not match proposal freeze")
        if coordinate.task_id != view.task_id or coordinate.task_revision != view.task_revision:
            raise ValueError("schedule coordinate task does not match problem view")
        if coordinate.review_lineage_id != schedule.proposal_freeze.selected_review_lineage_id:
            raise ValueError("schedule coordinate review lineage does not match proposal freeze")


def _validate_schedule_cross_product(
    schedule: DecompositionExecutionSchedule,
    *,
    candidates: tuple[ProgramCandidateRef, ...],
) -> None:
    expected_pairs = {
        (candidate.content_sha256, coordinate.content_sha256)
        for candidate in candidates
        for coordinate in schedule.coordinates
    }
    actual_pairs = {
        (
            assignment.candidate.content_sha256,
            assignment.coordinate.content_sha256,
        )
        for assignment in schedule.assignments
    }
    if actual_pairs != expected_pairs:
        raise ValueError("schedule requires the exact incumbent-and-proposal coordinate cross product")


class EvidenceOutcomeBinding(LegacyContentAddressedModel):
    """Exact resolution of one study evidence reference to its typed outcome."""

    schema_version: Literal["aecbench.evidence-outcome-binding.v1"] = "aecbench.evidence-outcome-binding.v1"
    evidence_id: NonEmptyStr
    evidence_sha256: str
    outcome: EvaluationOutcome

    @field_validator("evidence_sha256")
    @classmethod
    def validate_evidence_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class FrozenSelectionRule(LegacyContentAddressedModel):
    """Preregistered deterministic rule for selecting at most one proposal."""

    schema_version: Literal["aecbench.frozen-selection-rule.v1"] = "aecbench.frozen-selection-rule.v1"
    rule_id: NonEmptyStr
    minimum_utility_delta: FiniteFloat = Field(ge=0.0, le=1.0)
    candidate_tie_break: Literal["candidate_id_ascending"] = "candidate_id_ascending"


class DevelopmentSelectionRegime(LegacyContentAddressedModel):
    """Exact Vdev critic and frozen rule allowed to select an optimization candidate."""

    schema_version: Literal["aecbench.development-selection-regime.v1"] = "aecbench.development-selection-regime.v1"
    evaluation_regime_ref: EvaluationRegimeRef
    development_critic: CriticRef
    selection_rule_sha256: str
    split: Literal[OptimizationSplit.DEVELOPMENT] = OptimizationSplit.DEVELOPMENT

    @field_validator("selection_rule_sha256")
    @classmethod
    def validate_selection_rule_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_development_binding(self) -> Self:
        if self.development_critic.role is not CriticRole.DEVELOPMENT:
            raise ValueError("development selection requires a development critic")
        if self.development_critic.regime != self.evaluation_regime_ref:
            raise ValueError("development critic differs from the evaluation regime")
        return self


class DecompositionOptimizationResult(LegacyContentAddressedModel):
    """Internal exact cycle result nested inside the current development selection."""

    schedule: DecompositionExecutionSchedule
    selection_rule: FrozenSelectionRule
    outcome_bindings: tuple[EvidenceOutcomeBinding, ...] = Field(min_length=1)
    cycle: DecompositionOptimizationCycle

    @field_validator("outcome_bindings")
    @classmethod
    def canonicalize_outcome_bindings(
        cls,
        value: tuple[EvidenceOutcomeBinding, ...],
    ) -> tuple[EvidenceOutcomeBinding, ...]:
        evidence_ids = tuple(binding.evidence_id for binding in value)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("outcome evidence ids must be unique")
        return tuple(sorted(value, key=lambda binding: binding.evidence_id))

    @model_validator(mode="after")
    def validate_exact_result(self) -> Self:
        _validate_study_against_schedule(self.schedule, self.cycle.study)
        _validate_selection_rule(
            self.cycle.study,
            self.selection_rule,
            error_type=ValueError,
        )
        outcomes = _resolve_exact_outcomes(
            self.cycle.study,
            self.outcome_bindings,
            error_type=ValueError,
        )
        expected = _derive_cycle(
            cycle_id=self.cycle.cycle_id,
            study=self.cycle.study,
            outcomes=outcomes,
            selection_rule=self.selection_rule,
            selected_disposition=_selection_disposition_for_cycle(self.cycle),
        )
        if expected.content_sha256 != self.cycle.content_sha256:
            raise ValueError("optimization cycle does not match the exact outcomes and frozen selection rule")
        return self


class DevelopmentSelectionResult(LegacyContentAddressedModel):
    """Vdev-only selection artifact that cannot authorize acceptance or promotion."""

    schema_version: Literal["aecbench.development-selection-result.v1"] = "aecbench.development-selection-result.v1"
    selection_regime: DevelopmentSelectionRegime
    optimization_result: DecompositionOptimizationResult
    promotion_eligible: Literal[False] = False

    @property
    def cycle(self) -> DecompositionOptimizationCycle:
        """Expose the selected cycle without changing the serialized envelope."""
        return self.optimization_result.cycle

    @model_validator(mode="after")
    def validate_development_selection(self) -> Self:
        result = self.optimization_result
        if result.schedule.evaluation_regime_ref != self.selection_regime.evaluation_regime_ref:
            raise ValueError("development selection does not bind the exact evaluation regime")
        if result.selection_rule.content_sha256 != self.selection_regime.selection_rule_sha256:
            raise ValueError("development selection does not bind the exact frozen selection rule")
        if result.schedule.proposal_freeze.split is not self.selection_regime.split:
            raise ValueError("development selection requires the development split")
        if result.cycle.disposition is OptimizationDisposition.ACCEPT or any(
            comparison.disposition is OptimizationDisposition.ACCEPT for comparison in result.cycle.comparisons
        ):
            raise ValueError("development selection cannot carry acceptance dispositions")
        return self


def build_decomposition_execution_schedule(
    *,
    schedule_id: str,
    proposal_freeze: ProposalFreeze,
    incumbent_candidate: ProgramCandidateRef,
    coordinates: tuple[MatchedEvaluationCoordinate, ...],
    kernel_ref: KernelRef,
    fixed_harness_ref: HarnessInstanceRef,
    evaluation_regime_ref: EvaluationRegimeRef,
    aggregate_budget: HarnessBudget,
) -> DecompositionExecutionSchedule:
    """Freeze the full execution matrix without accepting validity, score, or outcome input."""
    candidates = (
        incumbent_candidate,
        *proposal_freeze.realized_candidates,
    )
    assignments = tuple(
        CandidateExecutionAssignment(candidate=candidate, coordinate=coordinate)
        for candidate in candidates
        for coordinate in coordinates
    )
    return DecompositionExecutionSchedule(
        schedule_id=schedule_id,
        kernel_ref=kernel_ref,
        fixed_harness_ref=fixed_harness_ref,
        evaluation_regime_ref=evaluation_regime_ref,
        proposal_freeze=proposal_freeze,
        aggregate_budget=aggregate_budget,
        incumbent_candidate=incumbent_candidate,
        coordinates=coordinates,
        assignments=assignments,
    )


def complete_program_candidate_study(
    *,
    study_id: str,
    schedule: DecompositionExecutionSchedule,
    evidence_refs: tuple[MatchedCandidateEvidenceRef, ...],
) -> ProgramCandidateStudy:
    """Close an exact study matrix before any evaluation outcome is resolved."""
    return ProgramCandidateStudy(
        study_id=study_id,
        kernel_ref=schedule.kernel_ref,
        fixed_harness_ref=schedule.fixed_harness_ref,
        evaluation_regime_ref=schedule.evaluation_regime_ref,
        proposal_freeze=schedule.proposal_freeze,
        aggregate_budget=schedule.aggregate_budget,
        incumbent_candidate=schedule.incumbent_candidate,
        coordinates=schedule.coordinates,
        evidence_refs=evidence_refs,
    )


def complete_decomposition_optimization_cycle(
    *,
    cycle_id: str,
    schedule: DecompositionExecutionSchedule,
    study: ProgramCandidateStudy,
    outcome_bindings: tuple[EvidenceOutcomeBinding, ...],
    selection_rule: FrozenSelectionRule,
    development_critic: CriticRef,
) -> DevelopmentSelectionResult:
    """Resolve exact outcomes and apply a frozen selection rule without repair semantics."""
    _validate_development_critic(
        development_critic,
        evaluation_regime_ref=schedule.evaluation_regime_ref,
    )
    _validate_study_against_schedule(schedule, study)
    _validate_selection_rule(
        study,
        selection_rule,
        error_type=OptimizationExperimentError,
    )
    outcomes = _resolve_exact_outcomes(
        study,
        outcome_bindings,
        error_type=OptimizationExperimentError,
    )
    cycle = _derive_cycle(
        cycle_id=cycle_id,
        study=study,
        outcomes=outcomes,
        selection_rule=selection_rule,
        selected_disposition=OptimizationDisposition.DEVELOPMENT_SELECTED,
    )
    optimization_result = DecompositionOptimizationResult(
        schedule=schedule,
        selection_rule=selection_rule,
        outcome_bindings=outcome_bindings,
        cycle=cycle,
    )
    return DevelopmentSelectionResult(
        selection_regime=DevelopmentSelectionRegime(
            evaluation_regime_ref=schedule.evaluation_regime_ref,
            development_critic=development_critic,
            selection_rule_sha256=selection_rule.content_sha256,
        ),
        optimization_result=optimization_result,
    )


def load_decomposition_optimization_result(
    content: bytes | str,
) -> DevelopmentSelectionResult:
    """Load one current development-selection result."""
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise ValueError("decomposition optimization artifact is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("decomposition optimization artifact must be a JSON object")
    schema_version = payload.get("schema_version")
    if schema_version == "aecbench.development-selection-result.v1":
        return DevelopmentSelectionResult.model_validate(payload)
    raise ValueError(f"unsupported decomposition optimization schema {schema_version!r}")


def _validate_development_critic(
    critic: CriticRef,
    *,
    evaluation_regime_ref: EvaluationRegimeRef,
) -> None:
    if critic.role is not CriticRole.DEVELOPMENT:
        raise OptimizationExperimentError("optimization selection requires a development critic")
    if critic.regime != evaluation_regime_ref:
        raise OptimizationExperimentError("development critic differs from the evaluation regime")


def _validate_study_against_schedule(
    schedule: DecompositionExecutionSchedule,
    study: ProgramCandidateStudy,
) -> None:
    expected = complete_program_candidate_study(
        study_id=study.study_id,
        schedule=schedule,
        evidence_refs=study.evidence_refs,
    )
    if expected.content_sha256 != study.content_sha256:
        raise OptimizationExperimentError("candidate study does not bind the exact frozen execution schedule")


def _validate_selection_rule(
    study: ProgramCandidateStudy,
    selection_rule: FrozenSelectionRule,
    *,
    error_type: type[ValueError],
) -> None:
    expected_sha256 = study.proposal_freeze.candidate_manifest.selection_policy_sha256
    if selection_rule.content_sha256 != expected_sha256:
        raise error_type("selection rule does not match the frozen selection policy")


def _resolve_exact_outcomes(
    study: ProgramCandidateStudy,
    outcome_bindings: tuple[EvidenceOutcomeBinding, ...],
    *,
    error_type: type[ValueError],
) -> dict[str, EvaluationOutcome]:
    evidence_ids = tuple(binding.evidence_id for binding in outcome_bindings)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise error_type("outcome evidence ids must be unique")

    evidence_by_id = {reference.evidence_id: reference for reference in study.evidence_refs}
    bindings_by_id = {binding.evidence_id: binding for binding in outcome_bindings}
    _validate_exact_outcome_binding_set(
        evidence_by_id=evidence_by_id,
        bindings_by_id=bindings_by_id,
        error_type=error_type,
    )
    candidates_by_id = {
        study.incumbent_candidate.candidate_id: study.incumbent_candidate,
        **{candidate.candidate_id: candidate for candidate in study.proposal_freeze.realized_candidates},
    }
    outcomes: dict[str, EvaluationOutcome] = {}
    for evidence_id, reference in evidence_by_id.items():
        binding = bindings_by_id[evidence_id]
        outcome = binding.outcome
        candidate = candidates_by_id[reference.candidate_id]
        _validate_outcome_identity_binding(
            study=study,
            reference=reference,
            binding=binding,
            candidate=candidate,
            error_type=error_type,
        )
        _validate_outcome_evidence_state(
            reference=reference,
            outcome=outcome,
            error_type=error_type,
        )
        _validate_non_trial_outcome(reference=reference, outcome=outcome, error_type=error_type)
        outcomes[evidence_id] = outcome
    return outcomes


def _validate_exact_outcome_binding_set(
    *,
    evidence_by_id: dict[str, MatchedCandidateEvidenceRef],
    bindings_by_id: dict[str, EvidenceOutcomeBinding],
    error_type: type[ValueError],
) -> None:
    missing_ids = tuple(sorted(set(evidence_by_id) - set(bindings_by_id)))
    extra_ids = tuple(sorted(set(bindings_by_id) - set(evidence_by_id)))
    if missing_ids:
        raise error_type("unresolvable evaluation outcome for evidence ids " + ", ".join(missing_ids))
    if extra_ids:
        raise error_type("outcome bindings reference evidence outside the exact study: " + ", ".join(extra_ids))


def _validate_outcome_identity_binding(
    *,
    study: ProgramCandidateStudy,
    reference: MatchedCandidateEvidenceRef,
    binding: EvidenceOutcomeBinding,
    candidate: ProgramCandidateRef,
    error_type: type[ValueError],
) -> None:
    outcome = binding.outcome
    if binding.evidence_sha256 != reference.content_sha256:
        raise error_type(f"outcome binding {binding.evidence_id!r} does not bind exact study evidence")
    if outcome.candidate_sha256 != candidate.candidate_artifact_sha256:
        raise error_type(f"outcome for {binding.evidence_id!r} does not bind the exact candidate artifact")


def _validate_outcome_evidence_state(
    *,
    reference: MatchedCandidateEvidenceRef,
    outcome: EvaluationOutcome,
    error_type: type[ValueError],
) -> None:
    expected_complete = not outcome.integrity.passed or (
        outcome.validity is not None and outcome.validity.verifier_completed
    )
    if reference.evidence_complete is not expected_complete:
        raise error_type(f"evidence {reference.evidence_id!r} completeness disagrees with its typed outcome")
    if reference.integrity_passed is not outcome.integrity.passed:
        raise error_type(f"evidence {reference.evidence_id!r} integrity disagrees with its typed outcome")
    if (
        outcome.disposition is EvaluationDisposition.EXPERIMENT_ERROR
        and reference.evidence_complete
        and reference.integrity_passed
    ):
        raise error_type(
            f"evidence {reference.evidence_id!r} carries an experiment-error outcome "
            "despite claiming complete, integral evidence"
        )


def _validate_non_trial_outcome(
    *,
    reference: MatchedCandidateEvidenceRef,
    outcome: EvaluationOutcome,
    error_type: type[ValueError],
) -> None:
    if reference.kind is CandidateEvidenceKind.TRIAL_RECORD:
        return
    if (
        outcome.disposition is not EvaluationDisposition.REJECT
        or outcome.utility is None
        or not outcome.utility.is_zero
        or outcome.promotion_eligible
        or outcome.validity is None
        or outcome.validity.valid
    ):
        raise error_type("non-trial evidence requires a zero-utility rejection outcome")


def _derive_cycle(
    *,
    cycle_id: str,
    study: ProgramCandidateStudy,
    outcomes: dict[str, EvaluationOutcome],
    selection_rule: FrozenSelectionRule,
    selected_disposition: OptimizationDisposition,
) -> DecompositionOptimizationCycle:
    if selected_disposition not in {
        OptimizationDisposition.ACCEPT,
        OptimizationDisposition.DEVELOPMENT_SELECTED,
    }:
        raise ValueError("selected disposition must identify acceptance or development selection")
    incumbent_id = study.incumbent_candidate.candidate_id
    references_by_candidate = {
        candidate_id: tuple(reference for reference in study.evidence_refs if reference.candidate_id == candidate_id)
        for candidate_id in {
            incumbent_id,
            *(candidate.candidate_id for candidate in study.proposal_freeze.realized_candidates),
        }
    }
    pair_deltas, pair_validity, pair_has_abstention = _derive_pair_evidence(
        study=study,
        outcomes=outcomes,
        references_by_candidate=references_by_candidate,
    )
    has_experiment_error, winner_id = _select_pair_winner(
        pair_deltas=pair_deltas,
        pair_validity=pair_validity,
        pair_has_abstention=pair_has_abstention,
        selection_rule=selection_rule,
    )
    comparisons = _build_pair_comparisons(
        cycle_id=cycle_id,
        study=study,
        references_by_candidate=references_by_candidate,
        pair_deltas=pair_deltas,
        pair_validity=pair_validity,
        pair_has_abstention=pair_has_abstention,
        winner_id=winner_id,
        selected_disposition=selected_disposition,
    )
    cycle_disposition, cycle_selected_id = _derive_cycle_selection(
        comparisons=comparisons,
        incumbent_id=incumbent_id,
        winner_id=winner_id,
        has_experiment_error=has_experiment_error,
        selected_disposition=selected_disposition,
    )
    proposal_ids = tuple(candidate.candidate_id for candidate in study.proposal_freeze.realized_candidates)
    return DecompositionOptimizationCycle(
        cycle_id=cycle_id,
        study=study,
        scheduled_candidate_ids=proposal_ids,
        completed_candidate_ids=proposal_ids,
        comparisons=comparisons,
        cycle_complete=True,
        disposition=cycle_disposition,
        selected_candidate_id=cycle_selected_id,
    )


def _derive_pair_evidence(
    *,
    study: ProgramCandidateStudy,
    outcomes: dict[str, EvaluationOutcome],
    references_by_candidate: dict[str, tuple[MatchedCandidateEvidenceRef, ...]],
) -> tuple[dict[str, float], dict[str, tuple[bool, bool]], dict[str, bool]]:
    incumbent_id = study.incumbent_candidate.candidate_id
    pair_deltas: dict[str, float] = {}
    pair_validity: dict[str, tuple[bool, bool]] = {}
    pair_has_abstention: dict[str, bool] = {}
    for challenger in study.proposal_freeze.realized_candidates:
        incumbent_refs = references_by_candidate[incumbent_id]
        challenger_refs = references_by_candidate[challenger.candidate_id]
        paired_references = (*incumbent_refs, *challenger_refs)
        coverage_complete = {reference.coordinate_sha256 for reference in incumbent_refs} == {
            reference.coordinate_sha256 for reference in challenger_refs
        } and all(reference.evidence_complete for reference in paired_references)
        integrity_passed = all(reference.integrity_passed for reference in paired_references)
        pair_has_abstention[challenger.candidate_id] = any(
            outcomes[reference.evidence_id].disposition is EvaluationDisposition.ABSTAIN
            for reference in paired_references
        )
        pair_validity[challenger.candidate_id] = (
            coverage_complete,
            integrity_passed,
        )
        if coverage_complete and integrity_passed:
            incumbent_values = tuple(
                _required_utility(outcomes[reference.evidence_id], reference) for reference in incumbent_refs
            )
            challenger_values = tuple(
                _required_utility(outcomes[reference.evidence_id], reference) for reference in challenger_refs
            )
            pair_deltas[challenger.candidate_id] = fmean(challenger_values) - fmean(incumbent_values)
    return pair_deltas, pair_validity, pair_has_abstention


def _select_pair_winner(
    *,
    pair_deltas: dict[str, float],
    pair_validity: dict[str, tuple[bool, bool]],
    pair_has_abstention: dict[str, bool],
    selection_rule: FrozenSelectionRule,
) -> tuple[bool, str | None]:
    has_experiment_error = any(not coverage or not integrity for coverage, integrity in pair_validity.values())
    eligible = (
        ()
        if has_experiment_error
        else tuple(
            candidate_id
            for candidate_id, delta in pair_deltas.items()
            if delta > selection_rule.minimum_utility_delta and not pair_has_abstention[candidate_id]
        )
    )
    winner_id = (
        None
        if not eligible
        else min(
            eligible,
            key=lambda candidate_id: (
                -pair_deltas[candidate_id],
                candidate_id,
            ),
        )
    )
    return has_experiment_error, winner_id


def _build_pair_comparisons(
    *,
    cycle_id: str,
    study: ProgramCandidateStudy,
    references_by_candidate: dict[str, tuple[MatchedCandidateEvidenceRef, ...]],
    pair_deltas: dict[str, float],
    pair_validity: dict[str, tuple[bool, bool]],
    pair_has_abstention: dict[str, bool],
    winner_id: str | None,
    selected_disposition: OptimizationDisposition,
) -> tuple[PairedCandidateComparison, ...]:
    incumbent_id = study.incumbent_candidate.candidate_id
    comparisons: list[PairedCandidateComparison] = []
    for challenger in study.proposal_freeze.realized_candidates:
        incumbent_refs = references_by_candidate[incumbent_id]
        challenger_refs = references_by_candidate[challenger.candidate_id]
        coverage_complete, integrity_passed = pair_validity[challenger.candidate_id]
        if not coverage_complete or not integrity_passed:
            disposition = OptimizationDisposition.EXPERIMENT_ERROR
            utility_delta = None
            selected_candidate_id = None
        else:
            utility_delta = pair_deltas[challenger.candidate_id]
            if pair_has_abstention[challenger.candidate_id]:
                disposition = OptimizationDisposition.ABSTAIN
                selected_candidate_id = None
            elif challenger.candidate_id == winner_id:
                disposition = selected_disposition
                selected_candidate_id = challenger.candidate_id
            elif utility_delta <= 0.0:
                disposition = OptimizationDisposition.REJECT
                selected_candidate_id = incumbent_id
            else:
                disposition = OptimizationDisposition.ABSTAIN
                selected_candidate_id = None
        comparisons.append(
            PairedCandidateComparison(
                comparison_id=f"{cycle_id}:{challenger.candidate_id}",
                study_sha256=study.content_sha256,
                incumbent_candidate=study.incumbent_candidate,
                challenger_candidate=challenger,
                incumbent_evidence_refs=incumbent_refs,
                challenger_evidence_refs=challenger_refs,
                coverage_complete=coverage_complete,
                integrity_passed=integrity_passed,
                utility_delta=utility_delta,
                disposition=disposition,
                selected_candidate_id=selected_candidate_id,
            )
        )
    return tuple(comparisons)


def _derive_cycle_selection(
    *,
    comparisons: tuple[PairedCandidateComparison, ...],
    incumbent_id: str,
    winner_id: str | None,
    has_experiment_error: bool,
    selected_disposition: OptimizationDisposition,
) -> tuple[OptimizationDisposition, str | None]:
    if has_experiment_error:
        cycle_disposition = OptimizationDisposition.EXPERIMENT_ERROR
        cycle_selected_id = None
    elif winner_id is not None:
        cycle_disposition = selected_disposition
        cycle_selected_id = winner_id
    elif any(comparison.disposition is OptimizationDisposition.ABSTAIN for comparison in comparisons):
        cycle_disposition = OptimizationDisposition.ABSTAIN
        cycle_selected_id = None
    else:
        cycle_disposition = OptimizationDisposition.REJECT
        cycle_selected_id = incumbent_id
    return cycle_disposition, cycle_selected_id


def _selection_disposition_for_cycle(
    cycle: DecompositionOptimizationCycle,
) -> OptimizationDisposition:
    if cycle.disposition in {
        OptimizationDisposition.ACCEPT,
        OptimizationDisposition.DEVELOPMENT_SELECTED,
    }:
        return cycle.disposition
    selected_dispositions = {
        comparison.disposition
        for comparison in cycle.comparisons
        if comparison.disposition
        in {
            OptimizationDisposition.ACCEPT,
            OptimizationDisposition.DEVELOPMENT_SELECTED,
        }
    }
    if selected_dispositions:
        raise ValueError("non-selection cycle cannot contain a selected comparison")
    return OptimizationDisposition.DEVELOPMENT_SELECTED


def _required_utility(
    outcome: EvaluationOutcome,
    reference: MatchedCandidateEvidenceRef,
) -> float:
    if outcome.utility is None:
        raise OptimizationExperimentError(f"complete evidence {reference.evidence_id!r} has no interpretable utility")
    return float(outcome.utility.normalized_utility)
