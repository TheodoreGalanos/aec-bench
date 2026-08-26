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
    AVOBudget,
    AVOState,
    CycleOutcome,
    DevelopmentAttempt,
    EvaluatedCandidate,
    EvolutionState,
    GateResult,
    SelectionPlan,
    VariationRequest,
    VariationResult,
    VariationStatus,
    VariationUsage,
    assessment_score,
    budget_exhausted,
    budget_exhaustion_reason,
    decide_candidate,
    is_revision_valid,
    rebase_evolution_state_for_parent,
    reduce_evolution_state,
)
from aec_bench.evolution.evaluation import bind_evaluated_candidate
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


def _usage() -> VariationUsage:
    return VariationUsage(
        model_requests=1,
        tool_calls=2,
        development_evaluations=1,
        model_cost_usd=0.1,
        development_evaluation_cost_usd=0.02,
        elapsed_seconds=0.5,
    )


def _attempt(candidate: EvaluatedCandidate, revision: int = 1) -> DevelopmentAttempt:
    return DevelopmentAttempt(
        attempt_id=f"attempt-{revision}",
        revision=revision,
        evaluated=candidate,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Improve the candidate prompt.",
        usage_after=_usage(),
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


class TestAVOContracts:
    def test_budget_defaults_are_bounded(self) -> None:
        budget = AVOBudget()

        assert budget.max_model_requests == 12
        assert budget.max_tool_calls == 40
        assert budget.max_development_evaluations == 7
        assert budget.max_elapsed_seconds == 1800.0
        assert budget.max_supervisor_interventions == 0

    @pytest.mark.parametrize(
        "field_name",
        [
            "max_model_requests",
            "max_tool_calls",
            "max_development_evaluations",
            "max_consecutive_evaluation_errors",
            "max_stagnant_evaluations",
        ],
    )
    def test_budget_rejects_non_positive_or_boolean_active_limits(self, field_name: str) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            AVOBudget(**{field_name: -1})
        with pytest.raises(ValueError, match="positive integer"):
            AVOBudget(**{field_name: True})

    def test_supervisor_limit_zero_disables_supervision(self) -> None:
        assert AVOBudget(max_supervisor_interventions=0).max_supervisor_interventions == 0

    @pytest.mark.parametrize("field_name", ["max_elapsed_seconds", "max_cost_usd"])
    def test_budget_rejects_non_finite_limits(self, field_name: str) -> None:
        with pytest.raises(ValueError, match="finite"):
            AVOBudget(**{field_name: float("nan")})

    def test_usage_keeps_unknown_cost_distinct_from_known_cost(self) -> None:
        unknown = VariationUsage(model_requests=1, development_evaluations=1)
        known = _usage()

        assert unknown.model_cost_usd is None
        assert unknown.development_evaluation_cost_usd is None
        assert unknown.total_cost_usd is None
        assert known.total_cost_usd == pytest.approx(0.12)

    def test_usage_distinguishes_known_zero_cost_from_unknown(self) -> None:
        known_free = VariationUsage(
            model_requests=1,
            development_evaluations=1,
            model_cost_usd=0.0,
            development_evaluation_cost_usd=0.0,
        )
        unknown = VariationUsage(model_requests=1, development_evaluations=1)

        assert known_free.total_cost_usd == 0.0
        assert unknown.total_cost_usd is None

    def test_attempt_binds_exact_evidence_and_usage(self) -> None:
        attempt = _attempt(_candidate("child"))

        assert attempt.evaluated.snapshot.candidate_id == "child"
        assert attempt.usage_after.development_evaluations == 1

    def test_state_rejects_duplicate_attempt_identity(self) -> None:
        attempt = _attempt(_candidate("child"))
        duplicate = DevelopmentAttempt(
            attempt_id=attempt.attempt_id,
            revision=2,
            evaluated=attempt.evaluated,
            mutation=attempt.mutation,
            hypothesis=attempt.hypothesis,
            usage_after=attempt.usage_after,
        )

        with pytest.raises(ValueError, match="attempt IDs must be unique"):
            AVOState(
                variation_id="variation-1",
                parent_candidate_id="parent",
                child_candidate_id="child",
                current_revision=2,
                attempts=(attempt, duplicate),
                usage=attempt.usage_after,
            )

    def test_state_rejects_duplicate_internal_snapshot_identity(self) -> None:
        attempt = _attempt(_candidate("snapshot-1"))
        duplicate_snapshot = DevelopmentAttempt(
            attempt_id="attempt-2",
            revision=2,
            evaluated=attempt.evaluated,
            mutation=attempt.mutation,
            hypothesis=attempt.hypothesis,
            usage_after=attempt.usage_after,
        )

        with pytest.raises(ValueError, match="snapshot IDs must be unique"):
            AVOState(
                variation_id="variation-1",
                parent_candidate_id="parent",
                child_candidate_id="child",
                current_revision=2,
                attempts=(attempt, duplicate_snapshot),
                usage=attempt.usage_after,
            )

    def test_state_rejects_reused_trial_identity_across_attempts(self) -> None:
        first = _attempt(_candidate("snapshot-1"), revision=1)
        second = _attempt(_candidate("snapshot-2"), revision=2)

        with pytest.raises(ValueError, match="development attempt trial IDs must be unique"):
            AVOState(
                variation_id="variation-1",
                parent_candidate_id="parent",
                child_candidate_id="child",
                current_revision=2,
                attempts=(first, second),
                usage=second.usage_after,
            )

    def test_current_evaluated_revision_is_the_only_eligible_revision(self) -> None:
        attempt = _attempt(_candidate("child"), revision=1)
        state = AVOState(
            variation_id="variation-1",
            parent_candidate_id="parent",
            child_candidate_id="child",
            current_revision=1,
            attempts=(attempt,),
            best_attempt_id=attempt.attempt_id,
            usage=attempt.usage_after,
            parent_snapshot=WorkspaceSnapshot(system_prompt="Parent prompt.", candidate_id="parent"),
        )

        assert is_revision_valid(state, 1, attempt.evaluated.snapshot) is True
        assert is_revision_valid(state, 0) is False
        drifted = attempt.evaluated.snapshot.model_copy(update={"system_prompt": "Drifted."})
        assert is_revision_valid(state, 1, drifted, parent_snapshot=state.parent_snapshot) is False

    def test_revision_with_unchanged_parent_material_is_not_eligible(self) -> None:
        attempt = _attempt(_candidate("internal-snapshot-1"))
        parent_snapshot = _candidate("parent").snapshot
        state = AVOState(
            variation_id="variation-1",
            parent_candidate_id="parent",
            child_candidate_id="final-child",
            current_revision=1,
            attempts=(attempt,),
            usage=attempt.usage_after,
            parent_snapshot=parent_snapshot,
        )

        assert is_revision_valid(state, 1, parent_snapshot=parent_snapshot) is False

    def test_budget_reports_state_counter_and_unknown_cost_limits(self) -> None:
        attempt = _attempt(_candidate("child"))
        state = AVOState(
            variation_id="variation-1",
            parent_candidate_id="parent",
            child_candidate_id="child",
            current_revision=1,
            attempts=(attempt,),
            consecutive_evaluation_errors=2,
            usage=attempt.usage_after,
            parent_snapshot=WorkspaceSnapshot(system_prompt="Parent prompt.", candidate_id="parent"),
        )
        budget = AVOBudget(
            max_model_requests=10,
            max_tool_calls=10,
            max_development_evaluations=10,
            max_elapsed_seconds=10.0,
            max_consecutive_evaluation_errors=2,
            max_stagnant_evaluations=10,
            max_supervisor_interventions=10,
        )

        assert budget_exhaustion_reason(budget, state) == "max_consecutive_evaluation_errors"
        assert budget_exhausted(budget, state) is True

        disabled_supervision_budget = AVOBudget(
            max_model_requests=10,
            max_tool_calls=10,
            max_development_evaluations=10,
            max_elapsed_seconds=10.0,
            max_consecutive_evaluation_errors=10,
            max_stagnant_evaluations=10,
            max_supervisor_interventions=0,
        )
        healthy_state = AVOState(
            variation_id=state.variation_id,
            parent_candidate_id=state.parent_candidate_id,
            child_candidate_id=state.child_candidate_id,
            current_revision=state.current_revision,
            attempts=state.attempts,
            usage=state.usage,
            parent_snapshot=state.parent_snapshot,
        )
        assert budget_exhaustion_reason(disabled_supervision_budget, healthy_state) is None

        unknown_budget = AVOBudget(
            max_model_requests=10,
            max_tool_calls=10,
            max_development_evaluations=10,
            max_elapsed_seconds=10.0,
            max_consecutive_evaluation_errors=10,
            max_stagnant_evaluations=10,
            max_supervisor_interventions=10,
            max_cost_usd=1.0,
        )
        unknown_state = AVOState(
            variation_id=state.variation_id,
            parent_candidate_id=state.parent_candidate_id,
            child_candidate_id=state.child_candidate_id,
            current_revision=state.current_revision,
            attempts=state.attempts,
            usage=VariationUsage(model_requests=1),
            parent_snapshot=state.parent_snapshot,
        )
        assert budget_exhaustion_reason(unknown_budget, unknown_state) == "max_cost_usd_unknown"

    def test_non_submission_result_has_no_child_or_attempt(self) -> None:
        result = VariationResult(
            status=VariationStatus.BUDGET_EXHAUSTED,
            child=None,
            mutation=None,
            reasoning="The model request limit was reached.",
            usage=VariationUsage(model_requests=1),
        )

        assert result.status is VariationStatus.BUDGET_EXHAUSTED
        assert result.usage.total_cost_usd is None

    def test_submitted_result_requires_exact_evaluated_attempt_snapshot(self) -> None:
        attempt = _attempt(_candidate("child"))

        with pytest.raises(ValueError, match="exact evaluated attempt snapshot"):
            VariationResult(
                status=VariationStatus.SUBMITTED,
                child=WorkspaceSnapshot(system_prompt="Different.", candidate_id="child"),
                mutation=attempt.mutation,
                reasoning="submitted",
                usage=attempt.usage_after,
                attempt=attempt,
            )

    def test_submitted_result_allows_final_child_id_to_differ_from_attempt_snapshot(self) -> None:
        attempt = _attempt(_candidate("internal-snapshot-1"))
        result = VariationResult(
            status=VariationStatus.SUBMITTED,
            child=attempt.evaluated.snapshot.model_copy(update={"candidate_id": "final-child"}),
            mutation=attempt.mutation,
            reasoning="submitted",
            usage=attempt.usage_after,
            attempt=attempt,
        )

        assert result.child is not None
        assert result.child.candidate_id == "final-child"


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
            VariationResult(VariationStatus.SUBMITTED, None, None, "submitted", VariationUsage())

    def test_cycle_outcome_rejects_submitted_variation_without_child(self) -> None:
        parent = _candidate("parent")
        selection = SelectionPlan("parent", (), "conservative", "Improve checks", "Reason")
        variation = VariationResult(
            status=VariationStatus.SUBMITTED,
            child=_candidate("child").snapshot,
            mutation=MutationSummary(prompt_modified=True),
            reasoning="submitted",
            usage=_usage(),
            attempt=_attempt(_candidate("child")),
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
            status=VariationStatus.SUBMITTED,
            child=parent.snapshot,
            mutation=MutationSummary(prompt_modified=True),
            reasoning="submitted",
            usage=_usage(),
            attempt=_attempt(parent),
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
        variation = VariationResult(VariationStatus.ABSTAINED, None, None, "none", VariationUsage())
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
    def test_decision_compares_current_paired_parent_not_stale_best_score(self) -> None:
        parent = _candidate("parent")
        parent = bind_evaluated_candidate(
            parent.snapshot,
            parent.observations,
            parent.assessment.model_copy(update={"batch_score": 0.80}),
        )
        child = bind_evaluated_candidate(
            WorkspaceSnapshot(system_prompt="Child.", candidate_id="child"),
            (_observation("child", "trial-1"),),
            _assessment("child").model_copy(update={"batch_score": 0.85}),
        )
        variation = VariationResult(
            status=VariationStatus.SUBMITTED,
            child=child.snapshot,
            mutation=MutationSummary(prompt_modified=True),
            reasoning="submitted",
            usage=_usage(),
            attempt=_attempt(child),
        )
        stale_state = EvolutionState(
            cycle=2,
            active_candidate_id="parent",
            best_candidate_id="old-best",
            best_score=0.95,
            cycles_without_improvement=0,
            best_score_history=(0.95,),
        )
        current_state = rebase_evolution_state_for_parent(
            stale_state,
            parent,
            structural_weight=0.0,
        )
        decision = decide_candidate(
            parent=parent,
            child=child,
            variation=variation,
            state=current_state,
            config=_GateConfig(),  # type: ignore[arg-type]
        )

        assert decision.improved is True
        assert decision.effective_score == pytest.approx(0.835)

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
            status=VariationStatus.SUBMITTED,
            child=child.snapshot,
            mutation=MutationSummary(prompt_modified=True),
            reasoning="submitted",
            usage=_usage(),
            attempt=_attempt(child),
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
            status=VariationStatus.SUBMITTED,
            child=child.snapshot,
            mutation=MutationSummary(prompt_modified=True),
            reasoning="submitted",
            usage=_usage(),
            attempt=_attempt(child),
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
        variation = VariationResult(VariationStatus.ABSTAINED, None, None, "no change", VariationUsage())
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
