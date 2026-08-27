# ABOUTME: Tests deterministic AVO supervision triggers and bounded contracts.
# ABOUTME: Proves supervisor inputs, advice, and budget projections stay read-only and validated.

from dataclasses import FrozenInstanceError, replace

import pytest
from pydantic_ai.models.test import TestModel

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    ProposalUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.advice import (
    AVOAdvice,
    AVOAdviceFailure,
    AVOAdviceFailureCode,
    AVOAdviceRecord,
    AVOAdviceRequest,
    AVOAdviceResult,
    AVOAdviceTrigger,
    AVORemainingBudget,
    PydanticAIAdvisor,
    advice_trigger,
    complete_advisor_usage,
    remaining_avo_budget,
    reserve_advisor_budget,
)
from aec_bench.evolution.core import AVOBudget, AVOState, EvaluatedCandidate, RevisionAttempt, budget_exhaustion_reason
from aec_bench.evolution.memory import AVOMemoryEntry, AVOMemoryOutcome
from tests.support.trial_record_factories import make_trial_record


def _attempt(revision: int, *, valid: bool = True) -> RevisionAttempt:
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
    evaluated = EvaluatedCandidate(
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
    return RevisionAttempt(
        attempt_id=f"attempt-{revision}",
        revision=revision,
        evaluated=evaluated,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis=f"Hypothesis {revision}.",
        usage_after=ProposalUsage(development_evaluations=revision),
    )


def _state(
    *,
    attempts: tuple[RevisionAttempt, ...] = (),
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
        usage=ProposalUsage(
            development_evaluations=len(attempts),
            supervisor_interventions=interventions,
        ),
    )


def _budget(*, interventions: int = 1) -> AVOBudget:
    return AVOBudget(max_supervisor_interventions=interventions)


def test_three_latest_valid_non_progress_attempts_trigger_supervision() -> None:
    state = _state(attempts=tuple(_attempt(revision) for revision in range(1, 4)), stagnant=3)

    assert advice_trigger(state, _budget()) is AVOAdviceTrigger.VALID_DEVELOPMENT_STAGNATION


def test_parent_baseline_does_not_count_toward_valid_stagnation() -> None:
    state = _state(attempts=(_attempt(1), _attempt(2)), stagnant=3)

    assert advice_trigger(state, _budget()) is None


def test_invalid_or_failed_evaluations_trigger_supervision() -> None:
    invalid_state = _state(attempts=(_attempt(1, valid=False), _attempt(2, valid=False)))
    mixed_state = _state(attempts=(_attempt(1, valid=False),), errors=1)
    failed_state = _state(errors=2)

    assert advice_trigger(invalid_state, _budget()) is AVOAdviceTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    assert advice_trigger(failed_state, _budget()) is AVOAdviceTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    assert advice_trigger(mixed_state, _budget()) is AVOAdviceTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS


def test_explicit_exhausted_direction_request_is_bounded_by_intervention_limit() -> None:
    state = _state()

    assert (
        advice_trigger(state, _budget(), exhausted_direction_requested=True)
        is AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST
    )
    assert advice_trigger(_state(interventions=1), _budget(), exhausted_direction_requested=True) is None
    assert advice_trigger(state, _budget(interventions=0), exhausted_direction_requested=True) is None


def test_remaining_budget_projects_only_unspent_non_negative_allowances() -> None:
    state = AVOState(
        variation_id="variation-1",
        parent_candidate_id="parent",
        child_candidate_id="child",
        current_revision=0,
        usage=ProposalUsage(
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

    remaining = remaining_avo_budget(budget, state)

    assert remaining == AVORemainingBudget(2, 3, 2, 7.5, 1, 2, 1.4)
    assert remaining.remaining_model_requests == 2
    with pytest.raises(FrozenInstanceError):
        remaining.remaining_model_requests = 0  # type: ignore[misc]


def test_unknown_or_unconfigured_cost_remains_unknown() -> None:
    unknown = replace(_state(), usage=ProposalUsage(model_requests=1))
    unknown_budget = AVOBudget(max_cost_usd=2)
    unconfigured_budget = AVOBudget()

    unknown_projection = remaining_avo_budget(unknown_budget, unknown)
    unconfigured_projection = remaining_avo_budget(unconfigured_budget, unknown)
    assert unknown_projection.cost_limit_usd == 2
    assert unknown_projection.remaining_cost_usd is None
    assert unconfigured_projection.cost_limit_usd is None
    assert unconfigured_projection.remaining_cost_usd is None


def test_token_projection_preserves_bounded_unknown_and_unbounded_states() -> None:
    bounded = AVOBudget(max_input_tokens=100, max_output_tokens=20)
    empty = remaining_avo_budget(bounded, _state())
    unknown = remaining_avo_budget(
        bounded,
        replace(_state(), usage=ProposalUsage(model_requests=1, input_tokens=40)),
    )
    unbounded = remaining_avo_budget(AVOBudget(), _state())

    assert empty.input_token_limit == 100
    assert empty.remaining_input_tokens == 100
    assert empty.output_token_limit == 20
    assert empty.remaining_output_tokens == 20
    assert unknown.input_token_limit == 100
    assert unknown.remaining_input_tokens == 60
    assert unknown.output_token_limit == 20
    assert unknown.remaining_output_tokens is None
    assert unbounded.input_token_limit is None
    assert unbounded.remaining_input_tokens is None


def test_supervision_request_and_advice_validate_and_canonicalise_values() -> None:
    summary = AVOMemoryEntry(
        source_variation_id="variation-1",
        source_attempt_id="attempt-1",
        hypothesis="Try a narrower prompt.",
        change_summary="system prompt modified",
        evidence_summary="valid=False",
        outcome=AVOMemoryOutcome.INVALID,
    )
    request = AVOAdviceRequest(
        goal="Improve the candidate.",
        selected_parent_id="parent",
        strategy=MutationStrategy.EXPLORATORY,
        attempt_summaries=[summary],  # type: ignore[arg-type]
        remaining_budget=AVORemainingBudget(1, 2, 3, 4.0, 1, None, None),
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
    )
    advice = AVOAdvice(directions=("  Try a different tool order. ",), reasoning="The prior path repeats.")

    assert request.strategy is MutationStrategy.EXPLORATORY
    assert request.attempt_summaries == (summary,)
    assert request.trigger_reason is AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST
    assert advice.directions == ("Try a different tool order.",)


def _request() -> AVOAdviceRequest:
    return AVOAdviceRequest(
        goal="Improve the candidate.",
        selected_parent_id="parent",
        strategy=MutationStrategy.EXPLORATORY,
        attempt_summaries=(),
        remaining_budget=AVORemainingBudget(
            remaining_model_requests=5,
            remaining_tool_calls=5,
            remaining_development_evaluations=5,
            remaining_elapsed_seconds=30.0,
            remaining_supervisor_interventions=1,
            cost_limit_usd=None,
            remaining_cost_usd=None,
        ),
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
    )


def test_pydantic_supervisor_returns_one_validated_result_without_tools_or_retry() -> None:
    model = TestModel(custom_output_args={"directions": ["Try a narrower prompt."], "reasoning": "The path repeats."})
    result = PydanticAIAdvisor(model, model_identity="test-supervisor:model")(_request())

    assert isinstance(result, AVOAdviceResult)
    assert isinstance(result.output, AVOAdvice)
    assert result.output.directions == ("Try a narrower prompt.",)
    assert result.usage.model_requests == 1
    assert result.usage.supervisor_interventions == 1
    assert result.usage.input_tokens is not None
    assert result.usage.output_tokens is not None
    assert result.usage.elapsed_seconds >= 0
    assert model.last_model_request_parameters is not None
    assert model.last_model_request_parameters.function_tools == []
    assert model.last_model_request_parameters.builtin_tools == []


def test_supervision_failure_and_result_are_immutable_typed_contracts() -> None:
    failure = AVOAdviceFailure(
        code=AVOAdviceFailureCode.OUTPUT_VALIDATION_REJECTED,
        detail="The injected supervisor output was rejected.",
    )
    result = AVOAdviceResult(
        output=failure,
        usage=ProposalUsage(model_requests=1, supervisor_interventions=1),
    )

    assert isinstance(result.output, AVOAdviceFailure)
    assert result.output.code is AVOAdviceFailureCode.OUTPUT_VALIDATION_REJECTED
    with pytest.raises(FrozenInstanceError):
        result.output = failure  # type: ignore[misc]


def test_advice_result_rejects_revision_evaluation_cost() -> None:
    advice = AVOAdvice(directions=("Try one bounded alternative.",), reasoning="The direction stalled.")

    with pytest.raises(ValueError, match="must not include revision evaluation cost"):
        AVOAdviceResult(
            output=advice,
            usage=ProposalUsage(
                model_requests=1,
                supervisor_interventions=1,
                development_evaluation_cost_usd=0.0,
            ),
        )


def test_supervision_record_requires_exactly_one_confirmed_outcome() -> None:
    advice = AVOAdvice(directions=("Try a new direction.",), reasoning="The current direction repeats.")
    failure = AVOAdviceFailure(
        code=AVOAdviceFailureCode.OUTPUT_VALIDATION_REJECTED,
        detail="The supervisor output was rejected.",
    )
    valid = AVOAdviceRecord(
        trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
        advice=advice,
    )

    assert valid.advice == advice
    with pytest.raises(ValueError, match="advice or confirmed failure"):
        AVOAdviceRecord(trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST)
    with pytest.raises(ValueError, match="advice or confirmed failure"):
        AVOAdviceRecord(
            trigger_reason=AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST,
            advice=advice,
            failure=failure,
        )


def test_supervision_usage_reservation_and_reconciliation_share_avo_budget() -> None:
    before = ProposalUsage(model_requests=1, input_tokens=10, output_tokens=4, model_cost_usd=0.4)
    budget = AVOBudget(max_model_requests=3, max_supervisor_interventions=1, max_input_tokens=30, max_output_tokens=20)

    reserved = reserve_advisor_budget(before, budget)
    reconciled = complete_advisor_usage(
        before,
        budget,
        ProposalUsage(
            model_requests=1,
            supervisor_interventions=1,
            input_tokens=7,
            output_tokens=3,
            model_cost_usd=0.2,
            elapsed_seconds=1.5,
        ),
    )

    assert reserved.model_requests == 2
    assert reserved.supervisor_interventions == 1
    assert reconciled.model_requests == 2
    assert reconciled.supervisor_interventions == 1
    assert reconciled.input_tokens == 17
    assert reconciled.output_tokens == 7
    assert reconciled.model_cost_usd == pytest.approx(0.6)
    assert reconciled.elapsed_seconds == pytest.approx(1.5)


def test_supervision_usage_rejects_unknown_tokens_when_a_bound_cannot_be_proved() -> None:
    with pytest.raises(ValueError, match="max_input_tokens_unknown"):
        complete_advisor_usage(
            ProposalUsage(model_requests=1),
            AVOBudget(max_input_tokens=100, max_supervisor_interventions=1),
            ProposalUsage(model_requests=1, supervisor_interventions=1, input_tokens=None, output_tokens=2),
        )


def test_supervision_reconciliation_preserves_unknown_cost_for_budget_exhaustion() -> None:
    budget = AVOBudget(max_cost_usd=2, max_supervisor_interventions=2)

    reserved = reserve_advisor_budget(ProposalUsage(), budget)

    assert reserved.model_requests == 1
    reconciled = complete_advisor_usage(
        ProposalUsage(),
        budget,
        ProposalUsage(model_requests=1, supervisor_interventions=1),
    )

    assert reconciled.model_cost_usd is None
    assert (
        budget_exhaustion_reason(
            budget,
            AVOState(
                variation_id="variation",
                parent_candidate_id="parent",
                child_candidate_id="child",
                current_revision=0,
                usage=reconciled,
            ),
        )
        == "max_cost_usd_unknown"
    )


def test_supervision_reservation_allows_first_model_cost_after_known_evaluation_cost() -> None:
    usage = ProposalUsage(
        development_evaluations=1,
        development_evaluation_cost_usd=0.25,
    )

    reserved = reserve_advisor_budget(
        usage,
        AVOBudget(max_cost_usd=2, max_supervisor_interventions=1),
    )

    assert reserved.model_requests == 1
    assert reserved.development_evaluation_cost_usd == 0.25


def test_supervision_reservation_rejects_elapsed_budget_at_limit() -> None:
    with pytest.raises(ValueError, match="max_elapsed_seconds"):
        reserve_advisor_budget(
            ProposalUsage(elapsed_seconds=5.0),
            AVOBudget(max_elapsed_seconds=5.0, max_supervisor_interventions=1),
        )


@pytest.mark.parametrize("directions", [(), ("",), ("A", "A"), ("A", "B", "C", "D")])
def test_supervision_advice_requires_one_to_three_unique_non_blank_directions(directions: tuple[str, ...]) -> None:
    with pytest.raises((TypeError, ValueError)):
        AVOAdvice(directions=directions, reasoning="Reason.")
