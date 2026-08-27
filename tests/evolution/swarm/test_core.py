# ABOUTME: Tests for immutable functional swarm assignment and outcome values.
# ABOUTME: Proves exact material identity, host-owned evidence, and state invariants.

from dataclasses import FrozenInstanceError
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
    WorkspaceSnapshot,
)
from aec_bench.evolution.core import (
    CandidateProposal,
    EvaluatedCandidate,
    ProposalStatus,
    RevisionAttempt,
    SelectionPlan,
)
from aec_bench.evolution.swarm.core import (
    AgentBudget,
    AgentPivotState,
    PivotInstruction,
    PivotState,
    SwarmAgentResult,
    SwarmAssignment,
    SwarmDecision,
    SwarmOutcome,
    SwarmState,
)
from tests.support.trial_record_factories import make_trial_record


def _assignment() -> SwarmAssignment:
    selection = SelectionPlan(
        "parent",
        ("inspiration",),
        MutationStrategy.CONSERVATIVE,
        "Improve checks",
        "Use exact selected material",
    )
    return SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-1",
        selection=selection,
        parent=WorkspaceSnapshot(system_prompt="Parent prompt", candidate_id="parent"),
        inspirations=(WorkspaceSnapshot(system_prompt="Inspiration prompt", candidate_id="inspiration"),),
        budget=AgentBudget(max_cost_usd=1.0),
        issued_at=datetime(2026, 8, 26, tzinfo=UTC),
    )


def _candidate(candidate_id: str) -> EvaluatedCandidate:
    observation = EvolutionObservation(
        trial=make_trial_record(trial_id=f"{candidate_id}-trial"),
        enrichment=ObservationEnrichment(),
        candidate_id=candidate_id,
        discipline="structural",
    )
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=0.5,
        structural_score=None,
        discipline_scores={"structural": 0.5},
        trial_ids=(f"{candidate_id}-trial",),
        evaluation_case_ids=(f"{candidate_id}-case",),
        valid=True,
    )
    return EvaluatedCandidate(
        WorkspaceSnapshot(system_prompt="Candidate prompt", candidate_id=candidate_id),
        (observation,),
        assessment,
    )


def _usage() -> ProposalUsage:
    return ProposalUsage(model_requests=1, model_cost_usd=0.1)


def _attempt(candidate: EvaluatedCandidate) -> RevisionAttempt:
    return RevisionAttempt(
        attempt_id="attempt-1",
        revision=1,
        evaluated=candidate,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Try a changed prompt.",
        usage_after=ProposalUsage(development_evaluations=1, development_evaluation_cost_usd=0.1),
    )


def _result(assignment: SwarmAssignment | None = None) -> SwarmAgentResult:
    assignment = assignment or _assignment()
    return SwarmAgentResult(
        agent_id=assignment.agent_id,
        assignment_id=assignment.assignment_id,
        proposal=CandidateProposal(ProposalStatus.ABSTAINED, None, None, "No child", _usage()),
        agent_usage=_usage(),
    )


def test_assignment_canonicalises_material_and_is_frozen() -> None:
    assignment = _assignment()
    assert isinstance(assignment.inspirations, tuple)
    with pytest.raises(FrozenInstanceError):
        assignment.agent_id = "other"  # type: ignore[misc]


def test_assignment_requires_exact_parent_and_inspiration_ids() -> None:
    assignment = _assignment()
    with pytest.raises(ValueError, match="parent_candidate_id"):
        SwarmAssignment(
            run_id=assignment.run_id,
            assignment_id=assignment.assignment_id,
            agent_id=assignment.agent_id,
            selection=assignment.selection,
            parent=WorkspaceSnapshot(system_prompt="Wrong", candidate_id="other"),
            inspirations=assignment.inspirations,
            budget=assignment.budget,
            issued_at=assignment.issued_at,
        )
    with pytest.raises(ValueError, match="candidate IDs exactly"):
        SwarmAssignment(
            run_id=assignment.run_id,
            assignment_id=assignment.assignment_id,
            agent_id=assignment.agent_id,
            selection=assignment.selection,
            parent=assignment.parent,
            inspirations=(),
            budget=assignment.budget,
            issued_at=assignment.issued_at,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_budget_rejects_unbounded_or_invalid_cost(value: float) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        AgentBudget(max_cost_usd=value)


def test_agent_result_has_only_variation_and_cost() -> None:
    result = _result()
    assert result.proposal.child is None
    with pytest.raises(TypeError):
        SwarmAgentResult(
            agent_id="agent-1",
            assignment_id="assignment-1",
            proposal=result.proposal,
            agent_usage=result.agent_usage,
            score=0.8,  # type: ignore[call-arg]
        )


def test_swarm_state_validates_counters_and_stop_reason() -> None:
    agent = SwarmAgentState(agent_id="agent-1", model="model", status="active")
    state = SwarmState(
        run_id="run-1",
        total_evaluations=0,
        best_candidate_id=None,
        best_score=None,
        agent_states=[agent],
        recent_scores=[],
        recent_descriptors=[],
        pivot_state=PivotState(agent_states=(AgentPivotState("agent-1"),)),
        stopped=False,
        stop_reason=None,
    )
    assert state.agent_states == (agent,)
    with pytest.raises(ValueError, match="stop_reason"):
        SwarmState(
            run_id="run-1",
            total_evaluations=0,
            best_candidate_id=None,
            best_score=None,
            agent_states=(),
            recent_scores=(),
            recent_descriptors=(),
            pivot_state=PivotState(),
            stopped=True,
            stop_reason=None,
        )
    with pytest.raises(ValueError, match="belong to swarm agent state IDs"):
        SwarmState(
            run_id="run-1",
            total_evaluations=0,
            best_candidate_id=None,
            best_score=None,
            agent_states=(agent,),
            recent_scores=(),
            recent_descriptors=(),
            pivot_state=PivotState(agent_states=(AgentPivotState("agent-2"),)),
            stopped=False,
            stop_reason=None,
        )


def test_outcome_requires_assignment_and_result_identity() -> None:
    assignment = _assignment()
    result = _result(assignment)
    outcome = SwarmOutcome(assignment, result, None, None)
    assert outcome.agent_result.assignment_id == assignment.assignment_id

    mismatched = SwarmAgentResult(
        agent_id="agent-2",
        assignment_id=assignment.assignment_id,
        proposal=result.proposal,
        agent_usage=result.agent_usage,
    )
    with pytest.raises(ValueError, match="agent_id"):
        SwarmOutcome(assignment, mismatched, None, None)


def test_outcome_requires_host_evaluation_for_submitted_child() -> None:
    assignment = _assignment()
    attempt = _attempt(_candidate("internal-snapshot"))
    child = attempt.evaluated.snapshot.model_copy(update={"candidate_id": "child"})
    result = SwarmAgentResult(
        agent_id=assignment.agent_id,
        assignment_id=assignment.assignment_id,
        proposal=CandidateProposal(
            status=ProposalStatus.SUBMITTED,
            child=child,
            mutation=attempt.mutation,
            reasoning="Child",
            usage=_usage(),
            attempt=attempt,
        ),
        agent_usage=_usage(),
    )
    with pytest.raises(ValueError, match="requires an evaluated candidate"):
        SwarmOutcome(
            assignment=assignment,
            agent_result=result,
            evaluated_candidate=None,
            archive_outcome=None,
        )


def test_outcome_without_child_cannot_have_host_values() -> None:
    assignment = _assignment()
    with pytest.raises(ValueError, match="without a child"):
        SwarmOutcome(
            assignment=assignment,
            agent_result=_result(assignment),
            evaluated_candidate=object(),  # type: ignore[arg-type]
            archive_outcome=None,
        )


def test_decision_rejects_conflicting_stop_and_continue() -> None:
    with pytest.raises(ValueError, match="cannot continue"):
        SwarmDecision(True, None, False, True, "Stop")
    with pytest.raises(ValueError, match="must continue"):
        SwarmDecision(False, PivotInstruction("Change strategy"), False, False, "Pivot")
