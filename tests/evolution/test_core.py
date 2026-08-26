# ABOUTME: Tests for immutable evolution candidate, selection, variation, and state values.
# ABOUTME: Proves that candidate evidence cannot be detached from its snapshot or reordered.

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    WorkspaceSnapshot,
)
from aec_bench.evolution.analysis import EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.convergence import is_converged
from aec_bench.evolution.core import (
    CycleOutcome,
    EvaluatedCandidate,
    EvolutionState,
    GateResult,
    SelectionPlan,
    VariationRequest,
    VariationResult,
    VariationStatus,
    assessment_score,
    bind_evaluated_candidate,
    decide_candidate,
    reduce_evolution_state,
)
from tests.support.trial_record_factories import make_trial_record


def _observation(candidate_id: str, trial_id: str) -> EvolutionObservation:
    return EvolutionObservation(
        trial=make_trial_record(trial_id=trial_id),
        enrichment=ObservationEnrichment(),
        candidate_id=candidate_id,
        discipline="structural",
    )


def _assessment(
    candidate_id: str,
    trial_ids: tuple[str, ...] = ("trial-1",),
    evaluation_case_ids: tuple[str, ...] = ("case-1",),
    structural_score: float | None = 0.8,
    valid: bool = True,
    invalid_reasons: tuple[str, ...] = (),
) -> CandidateAssessment:
    return CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=0.75,
        structural_score=structural_score,
        discipline_scores={"structural": 0.75},
        trial_ids=trial_ids,
        evaluation_case_ids=evaluation_case_ids,
        valid=valid,
        invalid_reasons=invalid_reasons,
    )


def _candidate(candidate_id: str = "candidate-1") -> EvaluatedCandidate:
    observations = (_observation(candidate_id, "trial-1"),)
    return bind_evaluated_candidate(
        WorkspaceSnapshot(system_prompt="Use engineering checks.", candidate_id=candidate_id),
        observations,
        _assessment(candidate_id),
    )


class _GateConfig:
    improvement_threshold = 0.02
    stagnation_window = 3
    structural_weight = 0.3


class TestCandidateAssessment:
    def test_tuple_ids_are_canonical_and_unique(self) -> None:
        assessment = _assessment("candidate-1")
        assert assessment.trial_ids == ("trial-1",)
        assert assessment.evaluation_case_ids == ("case-1",)

    def test_duplicate_trial_ids_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="trial_ids must be unique"):
            _assessment("candidate-1", ("trial-1", "trial-1"))

    def test_trial_and_case_ids_must_have_equal_cardinality(self) -> None:
        with pytest.raises(ValidationError, match="equal cardinality"):
            _assessment("candidate-1", ("trial-1", "trial-2"), ("case-1",))

    def test_structural_score_can_be_absent(self) -> None:
        assessment = _assessment("candidate-1", structural_score=None)
        assert assessment.structural_score is None

    def test_non_finite_structural_score_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scores must be finite"):
            _assessment("candidate-1", structural_score=float("nan"))

    def test_valid_assessment_cannot_have_invalid_reasons(self) -> None:
        with pytest.raises(ValidationError, match="valid candidate assessments"):
            _assessment("candidate-1", invalid_reasons=("provider failure",))

    def test_invalid_assessment_requires_invalid_reason(self) -> None:
        with pytest.raises(ValidationError, match="require invalid reasons"):
            _assessment("candidate-1", valid=False)

    def test_empty_evidence_ids_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="evaluation_case_ids must not be empty"):
            CandidateAssessment(
                candidate_id="candidate-1",
                batch_score=0.75,
                structural_score=0.8,
                discipline_scores={},
                trial_ids=("trial-1",),
                evaluation_case_ids=(),
                valid=True,
            )


class TestEvaluatedCandidate:
    def test_snapshot_and_evidence_candidate_ids_must_match(self) -> None:
        with pytest.raises(ValueError, match="assessment candidate_id"):
            bind_evaluated_candidate(
                WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="child"),
                (_observation("parent", "trial-1"),),
                _assessment("parent"),
            )

    def test_empty_evidence_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            bind_evaluated_candidate(
                WorkspaceSnapshot(system_prompt="Prompt.", candidate_id="candidate-1"),
                (),
                _assessment("candidate-1"),
            )

    def test_reordered_or_relabelled_evidence_is_rejected(self) -> None:
        candidate = _candidate()
        observation = _observation("candidate-1", "trial-2")
        with pytest.raises(ValueError, match="trial_ids must match"):
            bind_evaluated_candidate(
                candidate.snapshot,
                (observation,),
                candidate.assessment,
            )

    def test_value_is_frozen(self) -> None:
        candidate = _candidate()
        with pytest.raises(FrozenInstanceError):
            candidate.snapshot = candidate.snapshot  # type: ignore[misc]


class TestFunctionalEvolutionValues:
    def test_selection_rejects_parent_as_inspiration(self) -> None:
        with pytest.raises(ValueError, match="cannot also be an inspiration"):
            SelectionPlan("candidate-1", ("candidate-1",), "conservative", "Improve checks", "Reason")

    def test_variation_requires_selected_inspiration_material(self) -> None:
        parent = _candidate()
        selection = SelectionPlan("candidate-1", ("inspiration-1",), "conservative", "Improve checks", "Reason")
        analysis = EvolutionAnalysis([], [], GraduatedScope.MINIMAL, None, parent.assessment.batch_score)
        with pytest.raises(ValueError, match="inspirations must match"):
            VariationRequest(
                selection=selection,
                parent=parent,
                inspirations=(),
                analysis=analysis,
                scope=GraduatedScope.MINIMAL,
                history=(),
                graveyard=(),
            )

    def test_variation_status_validates_submitted_child(self) -> None:
        with pytest.raises(ValueError, match="requires a child"):
            VariationResult(VariationStatus.SUBMITTED, None, None, "submitted", 0.0)

    def test_cycle_outcome_rejects_submitted_variation_without_child(self) -> None:
        parent = _candidate("parent")
        selection = SelectionPlan("parent", (), "conservative", "Improve checks", "Reason")
        variation = VariationResult(
            VariationStatus.SUBMITTED,
            WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
            MutationSummary(prompt_modified=True),
            "submitted",
            0.1,
        )
        with pytest.raises(ValueError, match="bound evaluated child"):
            CycleOutcome(
                cycle=1,
                selection=selection,
                parent=parent,
                variation=variation,
                child=None,
                decision=GateResult(GateDecision.REJECTED, "Child was invalid."),
                active_candidate_id_after="parent",
                best_candidate_id_after="parent",
            )

    def test_cycle_outcome_rejects_submitted_child_with_parent_id(self) -> None:
        parent = _candidate("parent")
        selection = SelectionPlan("parent", (), "conservative", "Improve checks", "Reason")
        variation = VariationResult(
            VariationStatus.SUBMITTED,
            parent.snapshot,
            MutationSummary(prompt_modified=True),
            "submitted",
            0.1,
        )
        with pytest.raises(ValueError, match="must differ from the parent"):
            CycleOutcome(
                cycle=1,
                selection=selection,
                parent=parent,
                variation=variation,
                child=parent,
                decision=GateResult(GateDecision.REJECTED, "Child was invalid."),
                active_candidate_id_after="parent",
                best_candidate_id_after="parent",
            )

    def test_cycle_outcome_requires_positive_cycle_number(self) -> None:
        parent = _candidate("parent")
        selection = SelectionPlan("parent", (), "conservative", "Improve checks", "Reason")
        variation = VariationResult(VariationStatus.ABSTAINED, None, None, "none", 0.0)
        with pytest.raises(ValueError, match="must be positive"):
            CycleOutcome(
                cycle=0,
                selection=selection,
                parent=parent,
                variation=variation,
                child=None,
                decision=GateResult(GateDecision.SKIPPED, "No variation submitted."),
                active_candidate_id_after="parent",
                best_candidate_id_after="parent",
            )

    def test_baseline_state_uses_exact_assessment_score(self) -> None:
        state = EvolutionState.from_baseline(_candidate())
        assert state.best_score == pytest.approx(0.75)
        assert state.best_score_history == (0.75,)
        assert state.best_candidate_id == "candidate-1"


class TestPureEvolutionPolicy:
    def test_assessment_score_preserves_structural_weighting(self) -> None:
        assert assessment_score(_assessment("candidate-1"), structural_weight=0.3) == pytest.approx(0.765)
        state = EvolutionState.from_baseline(_candidate(), structural_weight=0.3)
        assert state.best_score_history == pytest.approx((state.best_score,))

    def test_decision_rejects_unmatched_evaluation_cases(self) -> None:
        parent = _candidate("parent")
        child = bind_evaluated_candidate(
            WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
            (_observation("child", "trial-1"),),
            _assessment("child", evaluation_case_ids=("case-2",)),
        )
        variation = VariationResult(
            VariationStatus.SUBMITTED,
            child.snapshot,
            MutationSummary(prompt_modified=True),
            "submitted",
            0.1,
        )

        with pytest.raises(ValueError, match="same evaluation cases"):
            decide_candidate(
                parent=parent,
                child=child,
                variation=variation,
                state=EvolutionState.from_baseline(parent),
                config=_GateConfig(),  # type: ignore[arg-type]
            )

    def test_gate_uses_child_evidence_and_state_reduction_is_repeatable(self) -> None:
        parent = _candidate("parent")
        child = bind_evaluated_candidate(
            WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
            (_observation("child", "trial-1"),),
            _assessment("child", structural_score=1.0),
        )
        variation = VariationResult(
            VariationStatus.SUBMITTED,
            child.snapshot,
            MutationSummary(prompt_modified=True),
            "submitted",
            0.1,
        )
        baseline_state = EvolutionState.from_baseline(parent, structural_weight=0.3)
        decision = decide_candidate(
            parent=parent,
            child=child,
            variation=variation,
            state=baseline_state,
            config=_GateConfig(),  # type: ignore[arg-type]
        )
        reduced = reduce_evolution_state(state=baseline_state, parent=parent, child=child, decision=decision)

        assert decision.decision is GateDecision.ACCEPTED
        assert decision.effective_score == pytest.approx(0.825)
        assert reduced.active_candidate_id == "child"
        assert reduced.best_candidate_id == "child"
        assert reduced.best_score == pytest.approx(0.825)
        assert reduced.best_score_history == pytest.approx((0.765, 0.825))
        assert reduced == reduce_evolution_state(state=baseline_state, parent=parent, child=child, decision=decision)

    def test_skipped_variation_does_not_advance_candidate_or_stagnation(self) -> None:
        parent = _candidate("parent")
        state = EvolutionState.from_baseline(parent)
        variation = VariationResult(VariationStatus.ABSTAINED, None, None, "no change", 0.0)
        decision = decide_candidate(
            parent=parent,
            child=None,
            variation=variation,
            state=state,
            config=_GateConfig(),  # type: ignore[arg-type]
        )
        reduced = reduce_evolution_state(state=state, parent=parent, child=None, decision=decision)

        assert decision.decision is GateDecision.SKIPPED
        assert reduced.active_candidate_id == "parent"
        assert reduced.best_candidate_id == "parent"
        assert reduced.cycles_without_improvement == 0

    def test_convergence_consumes_explicit_state(self) -> None:
        state = EvolutionState(
            cycle=3,
            active_candidate_id="parent",
            best_candidate_id="parent",
            best_score=0.75,
            cycles_without_improvement=2,
            best_score_history=(0.75, 0.75, 0.76, 0.75),
        )

        assert is_converged(state, _GateConfig()) is True
