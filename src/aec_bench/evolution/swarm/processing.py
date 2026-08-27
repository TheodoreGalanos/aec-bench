# ABOUTME: Host-owned evaluation and archive finalisation for one swarm result.
# ABOUTME: Keeps candidate evidence and archive effects outside agent authority.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aec_bench.evolution.archive import ArchiveBatchOutcome, ArchiveInsertionStatus, QDArchive
from aec_bench.evolution.behaviour import extract_behaviour_descriptor
from aec_bench.evolution.core import EvaluatedCandidate, ProposalStatus
from aec_bench.evolution.evaluation import (
    CandidateChecks,
    CandidateEvaluationBatch,
    require_same_evaluation_cases,
)
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.swarm.core import SwarmAgentResult, SwarmAssignment, SwarmOutcome
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard


@dataclass(frozen=True)
class SwarmEvaluation:
    """Exact parent and child evidence produced before shared-state effects."""

    assignment: SwarmAssignment
    agent_result: SwarmAgentResult
    parent: EvaluatedCandidate | None
    child: EvaluatedCandidate | None

    def __post_init__(self) -> None:
        if not isinstance(self.assignment, SwarmAssignment):
            raise TypeError("assignment must be a SwarmAssignment")
        if not isinstance(self.agent_result, SwarmAgentResult):
            raise TypeError("agent_result must be a SwarmAgentResult")
        if self.assignment.agent_id != self.agent_result.agent_id:
            raise ValueError("assignment and result agent_id must match")
        if self.assignment.assignment_id != self.agent_result.assignment_id:
            raise ValueError("assignment and result assignment_id must match")
        if self.parent is None and self.child is not None:
            raise ValueError("evaluated child requires an evaluated parent")
        submitted_child = self.agent_result.proposal.child
        if submitted_child is None and (self.parent is not None or self.child is not None):
            raise ValueError("proposal without a child cannot have evaluation")
        if submitted_child is not None and self.parent is None:
            raise ValueError("submitted proposal requires an evaluated parent")
        if submitted_child is not None and self.agent_result.proposal.status is not ProposalStatus.SUBMITTED:
            raise ValueError("proposal child requires submitted proposal status")
        if self.parent is not None and self.parent.snapshot.candidate_id != self.assignment.parent.candidate_id:
            raise ValueError("evaluated parent must match the assigned parent")
        if self.child is not None and self.child.snapshot is not submitted_child:
            raise ValueError("evaluated child must bind the exact submitted snapshot")
        if self.child is not None and self.child.snapshot.candidate_id == self.assignment.parent.candidate_id:
            raise ValueError("evaluated child candidate_id must differ from the assigned parent")


def _validate_inputs(
    assignment: SwarmAssignment,
    agent_result: SwarmAgentResult,
    *,
    run_id: str,
    cycle: int,
    now: datetime,
) -> None:
    """Validate identities and explicit host values before any effect."""
    if not isinstance(assignment, SwarmAssignment):
        raise TypeError("assignment must be a SwarmAssignment")
    if not isinstance(agent_result, SwarmAgentResult):
        raise TypeError("agent_result must be a SwarmAgentResult")
    if assignment.agent_id != agent_result.agent_id:
        raise ValueError("assignment and result agent_id must match")
    if assignment.assignment_id != agent_result.assignment_id:
        raise ValueError("assignment and result assignment_id must match")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must not be blank")
    if isinstance(cycle, bool) or not isinstance(cycle, int) or cycle < 1:
        raise ValueError("cycle must be a positive integer")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")

    child = agent_result.proposal.child
    if child is not None and agent_result.proposal.status is not ProposalStatus.SUBMITTED:
        raise ValueError("proposal child requires submitted proposal status")
    if agent_result.proposal.status is ProposalStatus.SUBMITTED:
        if child is None:
            raise ValueError("submitted proposal did not provide a child snapshot")
        if child.candidate_id == assignment.parent.candidate_id:
            raise ValueError("submitted child candidate_id must differ from the parent")


def evaluate_assignment(
    *,
    assignment: SwarmAssignment,
    agent_result: SwarmAgentResult,
    batch: CandidateEvaluationBatch,
    checks: CandidateChecks,
    run_id: str,
    cycle: int,
    now: datetime,
) -> SwarmEvaluation:
    """Build exact parent and child evidence without mutating shared state.

    A proposal without a child is an explicit agent abstention. It does not
    evaluate even the parent because no candidate was submitted for this step.
    """
    if not isinstance(batch, CandidateEvaluationBatch):
        raise TypeError("batch must be a CandidateEvaluationBatch")
    _validate_inputs(assignment, agent_result, run_id=run_id, cycle=cycle, now=now)
    child_snapshot = agent_result.proposal.child
    if child_snapshot is None:
        return SwarmEvaluation(assignment, agent_result, parent=None, child=None)

    parent = checks.assess(assignment.parent, batch)
    child = checks.assess(child_snapshot, batch)
    require_same_evaluation_cases(parent, child)
    return SwarmEvaluation(assignment, agent_result, parent=parent, child=child)


def _graveyard_entry(
    evaluated: SwarmEvaluation,
    *,
    cycle: int,
    run_id: str,
    now: datetime,
    reason: str,
) -> GraveyardEntry:
    """Build one exact rejected-child entry for the shared graveyard."""
    parent = evaluated.parent
    child = evaluated.child
    if parent is None or child is None:
        raise ValueError("graveyard entry requires evaluated parent and child")
    mutation = evaluated.agent_result.proposal.mutation
    if mutation is None:
        raise ValueError("graveyard entry requires a mutation summary")
    return GraveyardEntry(
        cycle=cycle,
        strategy=evaluated.assignment.selection.strategy.value,
        mutation_description=evaluated.agent_result.proposal.reasoning,
        score_before=parent.assessment.batch_score,
        score_after=child.assessment.batch_score,
        candidate_id=child.snapshot.candidate_id,
        failure_reason=reason,
        parent_candidate_id=parent.snapshot.candidate_id,
        rejected_snapshot=child.snapshot,
        parent_assessment=parent.assessment,
        child_assessment=child.assessment,
        mutation=mutation,
        run_id=run_id,
        timestamp=now,
    )


def apply_swarm_evaluation(
    *,
    evaluated: SwarmEvaluation,
    archive: QDArchive,
    graveyard: SharedGraveyard,
    run_id: str,
    cycle: int,
    now: datetime,
) -> SwarmOutcome:
    """Apply archive and graveyard effects to an already evaluated result."""
    if not isinstance(archive, QDArchive):
        raise TypeError("archive must be a QDArchive")
    if not isinstance(graveyard, SharedGraveyard):
        raise TypeError("graveyard must be a SharedGraveyard")
    _validate_inputs(
        evaluated.assignment,
        evaluated.agent_result,
        run_id=run_id,
        cycle=cycle,
        now=now,
    )
    if evaluated.parent is None or evaluated.child is None:
        return SwarmOutcome(
            assignment=evaluated.assignment,
            agent_result=evaluated.agent_result,
            evaluated_candidate=None,
            archive_outcome=None,
        )

    child = evaluated.child
    archive_outcome: ArchiveBatchOutcome | None = None
    if child.assessment.valid:
        descriptors = tuple(extract_behaviour_descriptor(observation) for observation in child.observations)
        archive_outcome = ArchiveBatchOutcome(
            candidate_id=child.snapshot.candidate_id,
            insertions=tuple(
                archive.insert(
                    descriptor,
                    child.snapshot,
                    task_ids=(observation.trial.task.task_id,),
                    discipline=observation.discipline,
                    run_id=run_id,
                )
                for descriptor, observation in zip(descriptors, child.observations, strict=True)
            ),
        )

    if not child.assessment.valid:
        reason = "; ".join(child.assessment.invalid_reasons) or "candidate evaluation was invalid"
    elif archive_outcome is None or not any(
        insertion.status in (ArchiveInsertionStatus.NEW_CELL, ArchiveInsertionStatus.IMPROVED)
        for insertion in archive_outcome.insertions
    ):
        reason = "candidate did not enter or improve a quality-diversity archive cell"
    else:
        reason = ""
    if reason:
        graveyard.insert(
            _graveyard_entry(evaluated, cycle=cycle, run_id=run_id, now=now, reason=reason),
            extract_behaviour_descriptor(child.observations[0]),
            evaluated.assignment.agent_id,
        )

    return SwarmOutcome(
        assignment=evaluated.assignment,
        agent_result=evaluated.agent_result,
        evaluated_candidate=child,
        archive_outcome=archive_outcome,
    )


__all__ = (
    "SwarmEvaluation",
    "apply_swarm_evaluation",
    "evaluate_assignment",
)
