# ABOUTME: Immutable value contracts for functional swarm coordination.
# ABOUTME: Binds exact selection material to agent results and explicit swarm decisions.

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from aec_bench.contracts.evolution import BehaviourDescriptor, SwarmAgentState, WorkspaceSnapshot
from aec_bench.evolution.archive import ArchiveBatchOutcome
from aec_bench.evolution.core import EvaluatedCandidate, SelectionPlan, VariationResult


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_non_negative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_finite_non_negative(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True)
class AgentBudget:
    """Finite cost allowance carried by one swarm assignment."""

    max_cost_usd: float

    def __post_init__(self) -> None:
        _require_finite_non_negative(self.max_cost_usd, "max_cost_usd")


@dataclass(frozen=True)
class PivotState:
    """Explicit per-agent counters used to decide when agents should pivot."""

    agent_states: tuple[AgentPivotState, ...] = ()

    def __post_init__(self) -> None:
        agent_states = tuple(self.agent_states)
        for agent_state in agent_states:
            if not isinstance(agent_state, AgentPivotState):
                raise TypeError("pivot agent states must contain AgentPivotState values")
        if len({agent_state.agent_id for agent_state in agent_states}) != len(agent_states):
            raise ValueError("pivot agent states must have unique agent IDs")
        object.__setattr__(self, "agent_states", agent_states)


@dataclass(frozen=True)
class AgentPivotState:
    """Counters for one agent's pivot cooldown and pivot count."""

    agent_id: str
    cooldown_remaining: int = 0
    pivot_count: int = 0

    def __post_init__(self) -> None:
        _require_text(self.agent_id, "pivot agent_id")
        _require_non_negative_integer(self.cooldown_remaining, "cooldown_remaining")
        _require_non_negative_integer(self.pivot_count, "pivot_count")


@dataclass(frozen=True)
class PivotInstruction:
    """Bounded instruction for an agent pivot."""

    reason: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "pivot reason")


@dataclass(frozen=True)
class SwarmAssignment:
    """Exact parent and inspiration material assigned to one swarm agent."""

    assignment_id: str
    agent_id: str
    selection: SelectionPlan
    parent: WorkspaceSnapshot
    inspirations: tuple[WorkspaceSnapshot, ...]
    budget: AgentBudget
    issued_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.assignment_id, "assignment_id")
        _require_text(self.agent_id, "agent_id")
        if not isinstance(self.selection, SelectionPlan):
            raise TypeError("selection must be a SelectionPlan")
        if not isinstance(self.parent, WorkspaceSnapshot):
            raise TypeError("parent must be a WorkspaceSnapshot")
        if not isinstance(self.budget, AgentBudget):
            raise TypeError("budget must be an AgentBudget")
        if not isinstance(self.issued_at, datetime):
            raise TypeError("issued_at must be a datetime")
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise ValueError("issued_at must be timezone-aware")

        inspirations = tuple(self.inspirations)
        if any(not isinstance(snapshot, WorkspaceSnapshot) for snapshot in inspirations):
            raise TypeError("inspirations must contain WorkspaceSnapshot values")
        object.__setattr__(self, "inspirations", inspirations)

        if self.parent.candidate_id != self.selection.parent_candidate_id:
            raise ValueError("assignment parent must match the selection parent_candidate_id")
        inspiration_ids = tuple(snapshot.candidate_id for snapshot in inspirations)
        if inspiration_ids != self.selection.inspiration_candidate_ids:
            raise ValueError("assignment inspirations must match the selection candidate IDs exactly")


@dataclass(frozen=True)
class SwarmAgentResult:
    """Variation returned by an agent without host-owned evaluation evidence."""

    agent_id: str
    assignment_id: str
    variation: VariationResult
    agent_cost_usd: float

    def __post_init__(self) -> None:
        _require_text(self.agent_id, "agent_id")
        _require_text(self.assignment_id, "assignment_id")
        if not isinstance(self.variation, VariationResult):
            raise TypeError("variation must be a VariationResult")
        _require_finite_non_negative(self.agent_cost_usd, "agent_cost_usd")


def _validate_descriptor(descriptor: BehaviourDescriptor) -> None:
    _require_finite_non_negative(descriptor.token_cost, "behaviour descriptor token_cost")
    _require_finite(descriptor.verification_depth, "behaviour descriptor verification_depth")
    _require_finite(descriptor.tool_density, "behaviour descriptor tool_density")
    _require_finite(descriptor.exploration_ratio, "behaviour descriptor exploration_ratio")
    _require_finite(descriptor.deliberation_ratio, "behaviour descriptor deliberation_ratio")
    _require_finite(descriptor.reward, "behaviour descriptor reward")


def _validate_agent_state(agent_state: SwarmAgentState) -> None:
    if not isinstance(agent_state, SwarmAgentState):
        raise TypeError("agent_states must contain SwarmAgentState values")
    _require_non_negative_integer(agent_state.eval_count, "agent state eval_count")
    _require_non_negative_integer(agent_state.restart_count, "agent state restart_count")
    _require_non_negative_integer(agent_state.consecutive_non_improving, "agent state consecutive_non_improving")
    _require_finite(agent_state.best_score, "agent state best_score")
    _require_finite_non_negative(agent_state.budget_consumed_usd, "agent state budget_consumed_usd")


@dataclass(frozen=True)
class SwarmState:
    """Immutable aggregate state for one functional swarm run."""

    run_id: str
    total_evaluations: int
    best_candidate_id: str | None
    best_score: float | None
    agent_states: tuple[SwarmAgentState, ...]
    recent_scores: tuple[float, ...]
    recent_descriptors: tuple[BehaviourDescriptor, ...]
    pivot_state: PivotState
    stopped: bool
    stop_reason: str | None

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        _require_non_negative_integer(self.total_evaluations, "total_evaluations")
        if self.best_candidate_id is not None:
            _require_text(self.best_candidate_id, "best_candidate_id")
        if self.best_score is not None:
            _require_finite(self.best_score, "best_score")
        if (self.best_candidate_id is None) != (self.best_score is None):
            raise ValueError("best_candidate_id and best_score must be provided together")
        if not isinstance(self.pivot_state, PivotState):
            raise TypeError("pivot_state must be a PivotState")
        if not isinstance(self.stopped, bool):
            raise TypeError("stopped must be a boolean")
        if self.stopped:
            if self.stop_reason is None:
                raise ValueError("stopped swarm state requires a stop_reason")
            _require_text(self.stop_reason, "stop_reason")
        elif self.stop_reason is not None:
            raise ValueError("running swarm state must not have a stop_reason")

        agent_states = tuple(self.agent_states)
        for agent_state in agent_states:
            _validate_agent_state(agent_state)
        if len({agent_state.agent_id for agent_state in agent_states}) != len(agent_states):
            raise ValueError("swarm agent states must have unique agent IDs")
        pivot_agent_ids = {agent_state.agent_id for agent_state in self.pivot_state.agent_states}
        agent_ids = {agent_state.agent_id for agent_state in agent_states}
        if not pivot_agent_ids.issubset(agent_ids):
            raise ValueError("pivot state agent IDs must belong to swarm agent state IDs")
        object.__setattr__(self, "agent_states", agent_states)

        recent_scores = tuple(self.recent_scores)
        for score in recent_scores:
            _require_finite(score, "recent score")
        object.__setattr__(self, "recent_scores", recent_scores)

        recent_descriptors = tuple(self.recent_descriptors)
        for descriptor in recent_descriptors:
            if not isinstance(descriptor, BehaviourDescriptor):
                raise TypeError("recent_descriptors must contain BehaviourDescriptor values")
            _validate_descriptor(descriptor)
        object.__setattr__(self, "recent_descriptors", recent_descriptors)


@dataclass(frozen=True)
class SwarmDecision:
    """Bounded next action for one completed assignment."""

    continue_agent: bool
    pivot: PivotInstruction | None
    consolidate: bool
    stop: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.continue_agent, bool):
            raise TypeError("continue_agent must be a boolean")
        if not isinstance(self.consolidate, bool):
            raise TypeError("consolidate must be a boolean")
        if not isinstance(self.stop, bool):
            raise TypeError("stop must be a boolean")
        if self.pivot is not None and not isinstance(self.pivot, PivotInstruction):
            raise TypeError("pivot must be a PivotInstruction or None")
        _require_text(self.reason, "decision reason")
        if self.stop and self.continue_agent:
            raise ValueError("stopped decision cannot continue an agent")
        if self.stop and self.pivot is not None:
            raise ValueError("stopped decision cannot include a pivot")
        if self.pivot is not None and not self.continue_agent:
            raise ValueError("pivot decision must continue the agent")


@dataclass(frozen=True)
class SwarmOutcome:
    """Complete host-visible outcome for one swarm assignment."""

    assignment: SwarmAssignment
    agent_result: SwarmAgentResult
    evaluated_candidate: EvaluatedCandidate | None
    archive_outcome: ArchiveBatchOutcome | None
    decision: SwarmDecision

    def __post_init__(self) -> None:
        if not isinstance(self.assignment, SwarmAssignment):
            raise TypeError("assignment must be a SwarmAssignment")
        if not isinstance(self.agent_result, SwarmAgentResult):
            raise TypeError("agent_result must be a SwarmAgentResult")
        if not isinstance(self.decision, SwarmDecision):
            raise TypeError("decision must be a SwarmDecision")
        if self.assignment.agent_id != self.agent_result.agent_id:
            raise ValueError("assignment and result agent_id must match")
        if self.assignment.assignment_id != self.agent_result.assignment_id:
            raise ValueError("assignment and result assignment_id must match")

        child = self.agent_result.variation.child
        if child is None:
            if self.evaluated_candidate is not None or self.archive_outcome is not None:
                raise ValueError("variation without a child cannot have evaluation or archive outcome")
        elif self.evaluated_candidate is None:
            raise ValueError("submitted variation child requires an evaluated candidate")
        if self.evaluated_candidate is not None:
            if not isinstance(self.evaluated_candidate, EvaluatedCandidate):
                raise TypeError("evaluated_candidate must be an EvaluatedCandidate or None")
            if child is None:
                raise ValueError("evaluated candidate requires a submitted variation child")
            if self.evaluated_candidate.snapshot.candidate_id != child.candidate_id:
                raise ValueError("evaluated candidate must match the variation child")
        if self.archive_outcome is not None:
            if not isinstance(self.archive_outcome, ArchiveBatchOutcome):
                raise TypeError("archive_outcome must be an ArchiveBatchOutcome or None")
            if self.evaluated_candidate is None:
                raise ValueError("archive outcome requires an evaluated candidate")
            candidate_id = self.evaluated_candidate.snapshot.candidate_id
            if self.archive_outcome.candidate_id != candidate_id:
                raise ValueError("archive outcome must match the evaluated candidate")
