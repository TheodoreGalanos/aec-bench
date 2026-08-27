# ABOUTME: Tests for pure swarm outcome reduction.
# ABOUTME: Proves host-evidence authority, immutable state updates, and bounded decisions.

from datetime import UTC, datetime

import pytest

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    ProposalUsage,
    SwarmAgentState,
    TraceDigest,
    WorkspaceSnapshot,
)
from aec_bench.evolution.archive import ArchiveBatchOutcome, ArchiveInsertionResult, ArchiveInsertionStatus
from aec_bench.evolution.core import (
    CandidateProposal,
    EvaluatedCandidate,
    ProposalStatus,
    RevisionAttempt,
    SelectionPlan,
)
from aec_bench.evolution.swarm.config import SwarmConfig
from aec_bench.evolution.swarm.core import (
    AgentBudget,
    AgentPivotState,
    BudgetSnapshot,
    PivotState,
    SwarmAgentResult,
    SwarmAssignment,
    SwarmOutcome,
    SwarmState,
    next_swarm_state,
)
from tests.support.trial_record_factories import make_trial_record

NOW = datetime(2026, 8, 26, 12, 30, tzinfo=UTC)


def _config(*, pivot_after: int = 5, consolidate_every: int = 10) -> SwarmConfig:
    return SwarmConfig(
        task={"workspace": "workspace", "task_path": "tasks/example"},
        agents={"default_model": "model"},
        budget={"max_cost_usd": 10.0, "eval_budget_usd": 10.0},
        heartbeat={"pivot_after": pivot_after, "consolidate_every": consolidate_every},
    )


def _assignment(agent_id: str = "agent-1", assignment_id: str = "assignment-1") -> SwarmAssignment:
    selection = SelectionPlan("parent", (), MutationStrategy.CONSERVATIVE, "Improve", "Use exact material")
    return SwarmAssignment(
        run_id="run-test",
        assignment_id=assignment_id,
        agent_id=agent_id,
        selection=selection,
        parent=WorkspaceSnapshot(system_prompt="Parent", candidate_id="parent"),
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=NOW,
    )


def _state(*agent_ids: str, **updates: object) -> SwarmState:
    agent_best_score = updates.pop("agent_best_score", 0.0)
    agents = tuple(
        SwarmAgentState(agent_id=agent_id, model="model", status="active", best_score=agent_best_score)
        for agent_id in agent_ids
    )
    best_score = updates.pop("best_score", None)
    best_candidate_id = updates.pop("best_candidate_id", "existing" if best_score is not None else None)
    return SwarmState(
        run_id="run-1",
        total_evaluations=updates.pop("total_evaluations", 0),
        best_candidate_id=best_candidate_id,
        best_score=best_score,
        agent_states=agents,
        recent_scores=updates.pop("recent_scores", ()),
        recent_descriptors=updates.pop("recent_descriptors", ()),
        pivot_state=PivotState(
            agent_states=tuple(AgentPivotState(agent_id) for agent_id in agent_ids),
        ),
        stopped=updates.pop("stopped", False),
        stop_reason=updates.pop("stop_reason", None),
    )


def _outcome(
    *,
    agent_id: str = "agent-1",
    assignment_id: str = "assignment-1",
    candidate_id: str | None = "child-1",
    score: float = 0.8,
    structural_score: float | None = 0.4,
    observation_count: int = 1,
    cost: float = 0.2,
    archive_status: ArchiveInsertionStatus = ArchiveInsertionStatus.NEW_CELL,
    valid: bool = True,
) -> SwarmOutcome:
    assignment = _assignment(agent_id, assignment_id)
    if candidate_id is None:
        usage = ProposalUsage(model_requests=1, model_cost_usd=cost)
        result = SwarmAgentResult(
            agent_id=agent_id,
            assignment_id=assignment_id,
            proposal=CandidateProposal(ProposalStatus.ABSTAINED, None, None, "No child", usage),
            agent_usage=usage,
        )
        return SwarmOutcome(assignment, result, None, None)

    child = WorkspaceSnapshot(system_prompt="Child material", candidate_id=candidate_id)
    usage = ProposalUsage(
        model_requests=1,
        development_evaluations=1,
        model_cost_usd=cost,
        development_evaluation_cost_usd=0.0,
    )
    development_trial = make_trial_record(trial_id=f"{candidate_id}-development-trial")
    development_observation = EvolutionObservation(
        trial=development_trial,
        enrichment=ObservationEnrichment(),
        candidate_id=candidate_id,
        discipline="structural",
    )
    development_assessment = CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=score,
        structural_score=structural_score,
        discipline_scores={"structural": score},
        trial_ids=(development_trial.trial_id,),
        evaluation_case_ids=("development-case",),
        valid=valid,
        invalid_reasons=() if valid else ("invalid candidate",),
    )
    development_candidate = EvaluatedCandidate(
        child,
        (development_observation,),
        development_assessment,
    )
    attempt = RevisionAttempt(
        attempt_id=f"{assignment_id}:attempt-1",
        revision=1,
        evaluated=development_candidate,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Submitted test child",
        usage_after=usage,
    )
    result = SwarmAgentResult(
        agent_id=agent_id,
        assignment_id=assignment_id,
        proposal=CandidateProposal(
            ProposalStatus.SUBMITTED,
            child,
            MutationSummary(prompt_modified=True),
            "Submitted child",
            usage,
            attempt,
        ),
        agent_usage=usage,
    )
    observations = tuple(
        EvolutionObservation(
            trial=make_trial_record(
                trial_id=f"trial-{index}",
                evaluation={
                    "reward": score,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            ),
            enrichment=ObservationEnrichment(
                trace_digest=TraceDigest(
                    turn_count=2,
                    tool_call_count=index,
                    tool_error_count=0,
                    bond_sequence="E-V",
                )
            ),
            candidate_id=candidate_id,
            discipline="structural",
        )
        for index in range(1, observation_count + 1)
    )
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=score,
        structural_score=structural_score,
        discipline_scores={"structural": score},
        trial_ids=tuple(f"trial-{index}" for index in range(1, observation_count + 1)),
        evaluation_case_ids=tuple(f"case-{index}" for index in range(1, observation_count + 1)),
        valid=valid,
        invalid_reasons=() if valid else ("invalid candidate",),
    )
    evaluated = EvaluatedCandidate(child, observations, assessment)
    archive_outcome = ArchiveBatchOutcome(
        candidate_id=candidate_id,
        insertions=(ArchiveInsertionResult(archive_status, candidate_id, 0, None),),
    )
    return SwarmOutcome(assignment, result, evaluated, archive_outcome)


def _reduce(state: SwarmState, outcome: SwarmOutcome, *, budget: BudgetSnapshot | None = None, **config: int):
    return next_swarm_state(
        state=state,
        outcome=outcome,
        budget=budget or BudgetSnapshot(10.0, 0.0, 10.0, 0.0),
        config=_config(**config),
        now=NOW,
    )


def test_reducer_is_deterministic_and_uses_host_score() -> None:
    state = _state("agent-1")
    outcome = _outcome(score=0.8, structural_score=0.4)
    first = _reduce(state, outcome)
    second = _reduce(state, outcome)
    assert first == second
    new_state, decision = first
    assert new_state.best_candidate_id == "child-1"
    assert new_state.best_score == pytest.approx(0.68)  # 0.8*0.7 + 0.4*0.3
    assert decision.continue_agent is True


@pytest.mark.parametrize(
    ("archive_status", "valid"),
    [
        (ArchiveInsertionStatus.NOT_ADDED, True),
        (ArchiveInsertionStatus.NEW_CELL, False),
    ],
)
def test_reducer_does_not_promote_rejected_or_invalid_candidates(
    archive_status: ArchiveInsertionStatus, valid: bool
) -> None:
    state = _state("agent-1", best_score=0.5)
    new_state, _ = _reduce(
        state,
        _outcome(score=0.99, archive_status=archive_status, valid=valid),
    )
    assert new_state.best_candidate_id == "existing"
    assert new_state.best_score == pytest.approx(0.5)


def test_no_child_updates_only_explicit_agent_cost() -> None:
    state = _state("agent-1")
    new_state, decision = _reduce(state, _outcome(candidate_id=None, cost=0.3))
    assert new_state.total_evaluations == 0
    assert new_state.best_candidate_id is None
    assert new_state.recent_scores == ()
    assert new_state.recent_descriptors == ()
    assert new_state.agent_states[0].budget_consumed_usd == 0.3
    assert decision.reason == "no child submitted"


def test_multiple_descriptors_are_one_host_evaluation() -> None:
    new_state, _ = _reduce(_state("agent-1"), _outcome(observation_count=2))
    assert new_state.total_evaluations == 1
    assert len(new_state.recent_scores) == 1
    assert len(new_state.recent_descriptors) == 2


def test_pivot_and_three_evaluation_cooldown_are_keyed_per_agent() -> None:
    state = _state("agent-1", best_score=0.9, agent_best_score=0.9)
    state, decision = _reduce(state, _outcome(score=0.9), pivot_after=1)
    assert decision.pivot is not None
    assert state.pivot_state.agent_states[0].cooldown_remaining == 3
    for index in range(2, 5):
        state, decision = _reduce(state, _outcome(assignment_id=f"assignment-{index}", score=0.9), pivot_after=1)
        assert decision.pivot is None
    state, decision = _reduce(state, _outcome(assignment_id="assignment-5", score=0.9), pivot_after=1)
    assert decision.pivot is not None


def test_consolidation_is_requested_at_global_evaluation_interval() -> None:
    state = _state("agent-1")
    state, decision = _reduce(state, _outcome(), consolidate_every=2)
    assert decision.consolidate is False
    state, decision = _reduce(
        state, _outcome(assignment_id="assignment-2", candidate_id="child-2"), consolidate_every=2
    )
    assert state.total_evaluations == 2
    assert decision.consolidate is True


def test_exhausted_post_effect_budget_stops_without_double_counting_cost() -> None:
    state = _state("agent-1")
    budget = BudgetSnapshot(1.0, 1.0, 10.0, 0.0)
    new_state, decision = _reduce(state, _outcome(cost=0.2), budget=budget)
    assert new_state.stopped is True
    assert decision.stop is True
    assert decision.continue_agent is False
    assert new_state.agent_states[0].budget_consumed_usd == 0.2


def test_reducer_uses_explicit_timezone_aware_time_and_does_not_mutate_inputs() -> None:
    state = _state("agent-1")
    outcome = _outcome()
    original = (state, outcome)
    new_state, _ = next_swarm_state(
        state=state,
        outcome=outcome,
        budget=BudgetSnapshot(10.0, 0.0, 10.0, 0.0),
        config=_config(),
        now=NOW,
    )
    assert new_state.agent_states[0].last_evaluated_at == NOW.isoformat()
    assert (state, outcome) == original
