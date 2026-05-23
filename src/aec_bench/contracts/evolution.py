# ABOUTME: Boundary models for the evolution domain in aec-bench.
# ABOUTME: Defines workspace, observation, cycle, engine, and orchestration contracts.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.behavioral_types import BondType, ClassifiedTrace, StructuralScore
from aec_bench.contracts.experiment_manifest import AgentConfig, TaskSelector
from aec_bench.contracts.trial_record import CostRecord, TrialRecord
from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_non_empty_string,
    resolve_env_ref,
)


class FailureCategory(StrEnum):
    """Classification of why an agent trial failed — guides mutation strategy."""

    TASK_MISUNDERSTANDING = "task_misunderstanding"
    MISSING_DOMAIN_KNOWLEDGE = "missing_domain_knowledge"
    MISSING_TOOL_USE = "missing_tool_use"
    WRONG_TOOL_USE = "wrong_tool_use"
    WEAK_INFORMATION_GATHERING = "weak_information_gathering"
    BAD_EXECUTION_STRATEGY = "bad_execution_strategy"
    MISSING_VERIFICATION = "missing_verification"
    ARITHMETIC_ERROR = "arithmetic_error"
    ENVIRONMENT_ISSUE = "environment_issue"
    SILENT_FAILURE = "silent_failure"
    OVERFITTING = "overfitting"


class EvolvableLayer(StrEnum):
    """The workspace components that the evolver is permitted to modify."""

    PROMPTS = "prompts"
    SKILLS = "skills"
    MEMORY = "memory"


class WorkspaceManifest(StrictModel):
    """Top-level descriptor for an evolution workspace. Stored as manifest.toml."""

    name: NonEmptyStr
    version: str = "0.1.0"
    agent_adapter: NonEmptyStr
    evolvable_layers: list[EvolvableLayer]
    skill_budget: PositiveInt = 10

    @model_validator(mode="before")
    @classmethod
    def _rewrite_harness_to_adapter(cls, data: Any) -> Any:
        """Accept 'agent_harness' as a user-facing synonym for 'agent_adapter'."""
        if not isinstance(data, dict):
            return data
        has_adapter = "agent_adapter" in data
        has_harness = "agent_harness" in data
        if has_adapter and has_harness:
            msg = "Provide either 'agent_adapter' or 'agent_harness', not both"
            raise ValueError(msg)
        if has_harness:
            data["agent_adapter"] = data.pop("agent_harness")
        return data


class SkillEntry(StrictModel):
    """A single reusable skill stored in a workspace."""

    name: NonEmptyStr
    description: NonEmptyStr
    discipline: str | None = None
    body: NonEmptyStr


class WorkspaceVersion(StrictModel):
    """An immutable snapshot of a workspace at a point in evolutionary history."""

    tag: NonEmptyStr
    parent_tag: str | None = None
    sha: NonEmptyStr
    timestamp: datetime
    summary: NonEmptyStr
    score_at_tag: float | None = None


class WorkspaceSnapshot(StrictModel):
    """The full runtime state of a workspace at a given version."""

    system_prompt: NonEmptyStr
    skills: list[SkillEntry] = Field(default_factory=list)
    workspace_version: NonEmptyStr


class FieldScore(StrictModel):
    """Score for a single output field in a trial evaluation."""

    field_name: NonEmptyStr
    reward: float
    expected: str | None = None
    actual: str | None = None


class TraceDigest(StrictModel):
    """Compact summary of a classified trace for storage and comparison."""

    turn_count: int
    tool_call_count: int
    tool_error_count: int
    bond_sequence: str
    key_actions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    agent_reasoning: list[str] = Field(default_factory=list)


class BehaviourDescriptor(StrictModel):
    """Characterises an agent's execution behaviour for MAP-Elites archiving.

    Extracted from TraceDigest (bond ratios, tool density) and CostRecord
    (token cost). The reward field enables performance-as-diversity — treating
    performance bands as a behaviour dimension rather than just a quality target.
    """

    model_config = ConfigDict(frozen=True)

    token_cost: float  # total tokens (in + out)
    verification_depth: float  # V_count / sequence_length
    tool_density: float  # tool_calls / turns
    exploration_ratio: float  # X_count / sequence_length
    deliberation_ratio: float  # D_count / sequence_length
    reward: float  # performance band source


class ObservationEnrichment(StrictModel):
    """Optional behavioral enrichments attached to an evolution observation."""

    # ClassifiedTrace and StructuralScore are frozen dataclasses, not Pydantic models.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    classified_trace: ClassifiedTrace | None = None
    structural_score: StructuralScore | None = None
    field_scores: list[FieldScore] = Field(default_factory=list)
    trace_digest: TraceDigest | None = None


class EvolutionObservation(StrictModel):
    """A single trial outcome observed during an evolutionary cycle."""

    trial: TrialRecord
    enrichment: ObservationEnrichment
    workspace_version: NonEmptyStr
    discipline: NonEmptyStr


class TraceQueryRequest(StrictModel):
    """Parameters for querying a subset of turns from a trial trace."""

    trial_id: NonEmptyStr
    turn_range: tuple[int, int] | None = None
    bond_type_filter: BondType | None = None
    errors_only: bool = False
    reasoning_only: bool = False


class TraceSliceTurn(StrictModel):
    """A single turn extracted as part of a trace slice."""

    turn_index: int
    role: str
    bond_type: BondType | None = None
    bond_confidence: float | None = None
    content: str
    tool_calls: list[str] = Field(default_factory=list)
    tool_outputs: list[str] = Field(default_factory=list)
    is_error: bool = False


class TraceSlice(StrictModel):
    """A windowed subset of turns from a trace with contextual metadata."""

    trial_id: NonEmptyStr
    turns: list[TraceSliceTurn]
    context: NonEmptyStr


class GateDecision(StrEnum):
    """Outcome of the quality gate evaluation after a cycle mutation."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class MutationSummary(StrictModel):
    """What the evolver changed in a workspace during an evolution cycle."""

    prompt_modified: bool = False
    skills_added: list[str] = Field(default_factory=list)
    skills_modified: list[str] = Field(default_factory=list)
    skills_removed: list[str] = Field(default_factory=list)
    memory_entries_added: int = 0
    evolver_reasoning: str | None = None


class DisciplineScore(StrictModel):
    """Aggregate performance metrics for a single engineering discipline in a cycle."""

    discipline: NonEmptyStr
    task_count: int
    mean_reward: float
    field_pass_rate: float
    mean_structural_similarity: float | None = None


class EvolutionCycleRecord(StrictModel):
    """Immutable record of a single evolution cycle."""

    cycle: int
    workspace_version_before: NonEmptyStr
    workspace_version_after: NonEmptyStr
    batch_score: float
    discipline_scores: list[DisciplineScore] = Field(default_factory=list)
    structural_score: float | None
    mutation: MutationSummary | None
    gate_decision: GateDecision
    trial_ids: list[str]
    timestamp: datetime
    evolver_cost: CostRecord | None = None


class StepResult(StrictModel):
    """The outcome of a single evolution step including gate decision and cycle record."""

    mutated: bool
    gate_decision: GateDecision
    mutation: MutationSummary | None = None
    cycle_record: EvolutionCycleRecord
    enriched_observations: list[EvolutionObservation] = Field(default_factory=list)


class StagnationInfo(StrictModel):
    """Describes a stagnation event where no improvement was observed over several cycles."""

    cycles_without_improvement: int
    best_score: float
    best_workspace_version: NonEmptyStr
    rolled_back: bool


class EvolutionResult(StrictModel):
    """Final result of a completed evolution run capturing all outcomes and history."""

    run_id: NonEmptyStr
    workspace_name: NonEmptyStr
    cycles_completed: int
    final_score: float
    best_score: float
    best_workspace_version: NonEmptyStr
    score_history: list[float]
    converged: bool
    stagnation: StagnationInfo | None = None
    total_trials: int
    total_evolver_cost: CostRecord | None = None
    cycle_records: list[EvolutionCycleRecord]
    archive_summary: dict[str, Any] | None = None


class EvolverModelConfig(StrictModel):
    """Model and temperature settings for the classifier and evolver LLM roles."""

    classifier: str
    evolver: str
    classifier_temperature: float = 0.0
    evolver_temperature: float = 0.7
    evolver_max_tokens: int = 16384

    @field_validator("classifier", "evolver", mode="before")
    @classmethod
    def resolve_env_and_validate(cls, value: str) -> str:
        resolved = resolve_env_ref(value)
        return ensure_non_empty_string(resolved)


class TaskGenerateConfig(StrictModel):
    """Configuration for generating parameterised task instances from a template."""

    template: NonEmptyStr
    count: PositiveInt = 5
    seed: int = 42
    difficulties: list[str] = Field(default_factory=lambda: ["easy", "medium"])


class EvolutionConfig(StrictModel):
    """Top-level configuration for running an evolution experiment."""

    workspace_path: NonEmptyStr
    models: EvolverModelConfig
    task_selector: TaskSelector
    batch_size: PositiveInt = 10
    max_cycles: PositiveInt = 20
    improvement_threshold: float = 0.02
    stagnation_window: PositiveInt = 5
    structural_weight: float = 0.3
    discipline_balanced: bool = False
    solver: AgentConfig | None = None
    backend: str = "local"
    timeout: PositiveInt = 1800
    harness_config: str | None = None
    strategy: Literal["hill_climb", "qd"] = "hill_climb"
    generate: TaskGenerateConfig | None = None


class WorkspaceReadRequest(StrictModel):
    """A request to read a file from the evolution workspace."""

    path: NonEmptyStr


class WorkspaceWriteRequest(StrictModel):
    """A request to write content to a file in the evolution workspace."""

    path: NonEmptyStr
    content: NonEmptyStr


# ---------------------------------------------------------------------------
# Swarm contracts — multi-agent QD evolution
# ---------------------------------------------------------------------------


class AgentStatus(StrEnum):
    """Runtime status of a swarm agent."""

    ACTIVE = "active"
    PIVOTING = "pivoting"
    WINDING_DOWN = "winding_down"
    RETIRED = "retired"
    ERROR = "error"
    RESTARTING = "restarting"


class SwarmEventType(StrEnum):
    """Event types emitted by the swarm manager to the event log."""

    SWARM_STARTED = "swarm_started"
    AGENT_SPAWNED = "agent_spawned"
    EVAL_COMPLETED = "eval_completed"
    ARCHIVE_UPDATED = "archive_updated"
    GRAVEYARD_UPDATED = "graveyard_updated"
    LINEAGE_RECORDED = "lineage_recorded"
    BUDGET_SPENT = "budget_spent"
    AGENT_RESTARTED = "agent_restarted"
    AGENT_RETIRED = "agent_retired"
    AGENT_PIVOTING = "agent_pivoting"
    WIND_DOWN_STARTED = "wind_down_started"
    SWARM_COMPLETED = "swarm_completed"
    # Fast-follow event types — reserved in schema, not emitted in v1.
    NOTE_WRITTEN = "note_written"
    CONSOLIDATION_PRODUCED = "consolidation_produced"
    HEARTBEAT_FIRED = "heartbeat_fired"


class SwarmAgentState(StrictModel):
    """Snapshot of a single swarm agent's runtime state."""

    model_config = ConfigDict(frozen=True)

    agent_id: NonEmptyStr
    model: NonEmptyStr
    status: AgentStatus
    current_bd_focus: BehaviourDescriptor | None = None
    eval_count: int = 0
    best_score: float = 0.0
    budget_consumed_usd: float = 0.0
    restart_count: int = 0
    last_eval_timestamp: str = ""
    consecutive_non_improving: int = 0
    worktree_branch: NonEmptyStr = ""


class SwarmEvent(StrictModel):
    """A single event in the swarm event log (JSONL serialisation)."""

    event_type: SwarmEventType
    timestamp: NonEmptyStr
    agent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence_number: int = 0


class LineageRecord(StrictModel):
    """Structured lineage for an archive entry — tracks evolutionary provenance."""

    model_config = ConfigDict(frozen=True)

    entry_version: NonEmptyStr
    parent_version: str | None = None
    source_agent_id: NonEmptyStr
    cross_agent: bool = False
    cross_agent_source: str | None = None
    mutation_type: NonEmptyStr
    bd_region_targeted: BehaviourDescriptor | None = None
    surprise: bool = False
    timestamp: NonEmptyStr


class LineageNarrative(StrictModel):
    """Freeform reasoning provenance attached to a lineage record."""

    model_config = ConfigDict(frozen=True)

    entry_version: NonEmptyStr
    agent_reasoning: NonEmptyStr
    investigation_context: str = ""
    surprise_explanation: str | None = None


class ConsolidationReport(StrictModel):
    """Analyst agent's periodic synthesis of swarm state."""

    model_config = ConfigDict(frozen=True)

    report_id: NonEmptyStr
    timestamp: NonEmptyStr
    archive_coverage_pct: float = 0.0
    total_evals: int = 0
    cross_agent_patterns: list[str] = Field(default_factory=list)
    strategy_recommendations: list[str] = Field(default_factory=list)
    counterintuitive_findings: list[str] = Field(default_factory=list)
    lineage_insights: str = ""


class SwarmNote(StrictModel):
    """An ad-hoc knowledge entry shared between swarm agents."""

    model_config = ConfigDict(frozen=True)

    note_id: NonEmptyStr
    agent_id: NonEmptyStr
    timestamp: NonEmptyStr
    bd_region: BehaviourDescriptor | None = None
    title: NonEmptyStr
    content: NonEmptyStr
    tags: tuple[str, ...] = ()


class SwarmResult(StrictModel):
    """Top-level output of a completed swarm run."""

    run_id: NonEmptyStr
    workspace_name: NonEmptyStr
    agents: list[SwarmAgentState]
    archive_summary: dict[str, Any] = Field(default_factory=dict)
    total_evals: int = 0
    total_cost_usd: float = 0.0
    eval_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    best_score: float = 0.0
    best_workspace_version: str = ""
    converged: bool = False
    lineage_record_count: int = 0
    event_count: int = 0
