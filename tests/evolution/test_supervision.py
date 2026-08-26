# ABOUTME: Tests deterministic AVO supervision triggers and bounded contracts.
# ABOUTME: Proves supervisor inputs, advice, and budget projections stay read-only and validated.

from dataclasses import FrozenInstanceError, replace

import pytest

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.core import AVOBudget, AVOState, DevelopmentAttempt
from aec_bench.evolution.evaluation import bind_evaluated_candidate
from aec_bench.evolution.memory import AVOMemoryEntry, AVOMemoryOutcome
from aec_bench.evolution.supervision import (
    AVORemainingBudget,
    AVOSupervisionAdvice,
    AVOSupervisionRequest,
    AVOSupervisionTrigger,
    project_remaining_budget,
    should_trigger_supervision,
    supervision_trigger_reason,
)
from tests.support.trial_record_factories import make_trial_record


def _attempt(revision: int, *, valid: bool = True) -> DevelopmentAttempt:
    candidate_id = f"candidate-{revision}"
    trial_id = f"trial-{revision}"
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=0.5,
        structural_score=0.5,
        discipline_scores={"structural": 0.5},
        trial_ids=(trial_id,),
        evaluation_case_ids=(f"case-{revision}",),
        valid=valid,
        invalid_reasons=(() if valid else ("development evaluation failed",)),
    )
    evaluated = bind_evaluated_candidate(
        WorkspaceSnapshot(system_prompt=f"Prompt {revision}.", candidate_id=candidate_id),
        (
            EvolutionObservation(
                trial=make_trial_record(trial_id=trial_id),
                enrichment=ObservationEnrichment(),
                candidate_id=candidate_id,
                discipline="structural",
            ),
        ),
        assessment,
    )
    return DevelopmentAttempt(
        attempt_id=f"attempt-{revision}",
        revision=revision,
        evaluated=evaluated,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis=f"Hypothesis {revision}.",
        usage_after=VariationUsage(development_evaluations=revision),
    )


def _state(
    *,
    attempts: tuple[DevelopmentAttempt, ...] = (),
    stagnant: int = 0,
    errors: int = 0,
    interventions: int = 0,
) -> AVOState:
    return AVOState(
        variation_id="variation-1",
        parent_candidate_id="parent",
        child_candidate_id="child",
        current_revision=len(attempts),
        attempts=attempts,
        consecutive_without_progress=stagnant,
        consecutive_evaluation_errors=errors,
        usage=VariationUsage(
            development_evaluations=len(attempts),
            supervisor_interventions=interventions,
        ),
    )


def _budget(*, interventions: int = 1) -> AVOBudget:
    return AVOBudget(max_supervisor_interventions=interventions)


def test_three_latest_valid_non_progress_attempts_trigger_supervision() -> None:
    state = _state(attempts=tuple(_attempt(revision) for revision in range(1, 4)), stagnant=3)

    assert supervision_trigger_reason(state, _budget()) is AVOSupervisionTrigger.VALID_DEVELOPMENT_STAGNATION
    assert should_trigger_supervision(state, _budget()) is True


def test_parent_baseline_does_not_count_toward_valid_stagnation() -> None:
    state = _state(attempts=(_attempt(1), _attempt(2)), stagnant=3)

    assert supervision_trigger_reason(state, _budget()) is None


def test_invalid_or_failed_evaluations_trigger_supervision() -> None:
    invalid_state = _state(attempts=(_attempt(1, valid=False), _attempt(2, valid=False)))
    mixed_state = _state(attempts=(_attempt(1, valid=False),), errors=1)
    failed_state = _state(errors=2)

    assert (
        supervision_trigger_reason(invalid_state, _budget())
        is AVOSupervisionTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    )
    assert (
        supervision_trigger_reason(failed_state, _budget())
        is AVOSupervisionTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    )
    assert (
        supervision_trigger_reason(mixed_state, _budget())
        is AVOSupervisionTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    )


def test_explicit_exhausted_direction_request_is_bounded_by_intervention_limit() -> None:
    state = _state()

    assert (
        supervision_trigger_reason(state, _budget(), exhausted_direction_requested=True)
        is AVOSupervisionTrigger.EXHAUSTED_DIRECTION_REQUEST
    )
    assert supervision_trigger_reason(_state(interventions=1), _budget(), exhausted_direction_requested=True) is None
    assert supervision_trigger_reason(state, _budget(interventions=0), exhausted_direction_requested=True) is None


def test_remaining_budget_projects_only_unspent_non_negative_allowances() -> None:
    state = AVOState(
        variation_id="variation-1",
        parent_candidate_id="parent",
        child_candidate_id="child",
        current_revision=0,
        usage=VariationUsage(
            model_requests=3,
            tool_calls=7,
            development_evaluations=2,
            supervisor_interventions=1,
            model_cost_usd=0.4,
            development_evaluation_cost_usd=0.2,
            elapsed_seconds=12.5,
        ),
    )
    budget = AVOBudget(
        max_model_requests=5,
        max_tool_calls=10,
        max_development_evaluations=4,
        max_elapsed_seconds=20,
        max_supervisor_interventions=2,
        max_cost_usd=2,
    )

    remaining = project_remaining_budget(budget, state)

    assert remaining == AVORemainingBudget(2, 3, 2, 7.5, 1, 2, 1.4)
    assert remaining.remaining_model_requests == 2
    with pytest.raises(FrozenInstanceError):
        remaining.remaining_model_requests = 0  # type: ignore[misc]


def test_unknown_or_unconfigured_cost_remains_unknown() -> None:
    unknown = replace(_state(), usage=VariationUsage(model_requests=1))
    unknown_budget = AVOBudget(max_cost_usd=2)
    unconfigured_budget = AVOBudget()

    unknown_projection = project_remaining_budget(unknown_budget, unknown)
    unconfigured_projection = project_remaining_budget(unconfigured_budget, unknown)
    assert unknown_projection.cost_limit_usd == 2
    assert unknown_projection.remaining_cost_usd is None
    assert unconfigured_projection.cost_limit_usd is None
    assert unconfigured_projection.remaining_cost_usd is None


def test_supervision_request_and_advice_validate_and_canonicalise_values() -> None:
    summary = AVOMemoryEntry(
        source_variation_id="variation-1",
        source_attempt_id="attempt-1",
        hypothesis="Try a narrower prompt.",
        change_summary="system prompt modified",
        evidence_summary="valid=False",
        outcome=AVOMemoryOutcome.INVALID,
    )
    request = AVOSupervisionRequest(
        goal="Improve the candidate.",
        selected_parent_id="parent",
        strategy=MutationStrategy.EXPLORATORY,
        attempt_summaries=[summary],  # type: ignore[arg-type]
        remaining_budget=AVORemainingBudget(1, 2, 3, 4.0, 1, None, None),
        trigger_reason=AVOSupervisionTrigger.EXHAUSTED_DIRECTION_REQUEST,
    )
    advice = AVOSupervisionAdvice(directions=("  Try a different tool order. ",), reasoning="The prior path repeats.")

    assert request.strategy is MutationStrategy.EXPLORATORY
    assert request.attempt_summaries == (summary,)
    assert request.trigger_reason is AVOSupervisionTrigger.EXHAUSTED_DIRECTION_REQUEST
    assert advice.directions == ("Try a different tool order.",)


@pytest.mark.parametrize("directions", [(), ("",), ("A", "A"), ("A", "B", "C", "D")])
def test_supervision_advice_requires_one_to_three_unique_non_blank_directions(directions: tuple[str, ...]) -> None:
    with pytest.raises((TypeError, ValueError)):
        AVOSupervisionAdvice(directions=directions, reasoning="Reason.")
