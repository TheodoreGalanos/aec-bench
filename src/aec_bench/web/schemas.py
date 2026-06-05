# ABOUTME: Pydantic response models for all JSON API endpoints in the web layer.
# ABOUTME: These schemas define the serializable contract between the backend API and frontend.

from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class ExperimentSummarySchema(BaseModel):
    """Aggregated stats for a single experiment."""

    experiment_id: str
    trial_count: int
    mean_reward: float
    models: list[str]
    disciplines: list[str]
    adapters: list[str]


class DashboardResponse(BaseModel):
    """Response for the dashboard overview endpoint."""

    experiments: list[ExperimentSummarySchema]
    total_trials: int
    total_experiments: int
    mean_reward: float
    annotated_count: int


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


class TrialRowSchema(BaseModel):
    """Pre-computed view model for one trial in the triage list."""

    trial_id: str
    experiment_id: str
    task_id: str
    model: str
    adapter: str
    compute_backend: str = ""
    discipline: str
    reward: float
    reward_class: str
    annotation_icon: str
    annotation_verdict: str


class TriageResponse(BaseModel):
    """Response for the triage trial list endpoint."""

    trials: list[TrialRowSchema]
    trial_count: int
    annotations: dict[str, dict[str, str]]
    filters: dict[str, str]
    experiments: list[str]
    models: list[str]


# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------


class StepSummarySchema(BaseModel):
    """Lightweight view of one trajectory step for the step list sidebar."""

    step: int
    status: str
    description: str
    tool_name: str
    duration_ms: int | None
    error_count: int
    metadata: dict[str, Any] | None = None
    call_type: str | None = None
    output_summary: str | None = None


class AnnotationSchema(BaseModel):
    """Triage annotation for a trial."""

    verdict: str
    notes: str
    timestamp: str


class ViewerMetaResponse(BaseModel):
    """Full trial viewer metadata response."""

    trial_id: str
    experiment_id: str
    dataset_id: str | None = None
    task_id: str
    model: str
    adapter: str
    compute_backend: str = ""
    reward: float
    reward_class: str
    steps: list[StepSummarySchema]
    is_rlm_trial: bool
    adapter_type: str = "other"  # "rlm", "lambda-rlm", or "other"
    artefacts: list[str]
    annotation: AnnotationSchema | None
    total_errors: int
    tokens_in: int | None
    tokens_out: int | None
    total_tokens: int | None
    cost_usd: float | None = None
    siblings: list[str]
    prev_trial: str | None
    next_trial: str | None
    back_url: str
    has_trajectory: bool


class ViewerStepResponse(BaseModel):
    """Response for a single step's messages."""

    step_num: int
    messages: list[dict[str, Any]]


class ViewerStateResponse(BaseModel):
    """Response for symbolic state and scratchpad data for an RLM trial."""

    symbolic_state: dict[str, Any]
    scratchpad_data: dict[str, Any]
    plan_state: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


class CellStatsSchema(BaseModel):
    """Aggregated statistics for one (adapter, task_prefix) matrix cell."""

    count: int
    mean_reward: float
    perfect_count: int
    zero_count: int
    total_cost: float
    reward_class: str
    reward_bg: str


class EvaluateResponse(BaseModel):
    """Response for the evaluate adapter x task-type matrix endpoint."""

    matrix: dict[str, CellStatsSchema]
    adapters: list[str]
    task_prefixes: list[str]
    row_totals: dict[str, CellStatsSchema]
    col_totals: dict[str, CellStatsSchema]
    grand_total: CellStatsSchema
    label_to_parts: dict[str, list[str]]
    experiments: list[str]
    selected_experiment: str


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


class AggregateRowSchema(BaseModel):
    """One row in the aggregate comparison table (per task type)."""

    task_type: str
    model_means: dict[str, float]
    model_counts: dict[str, int]
    model_reward_classes: dict[str, str]
    delta: float | None
    delta_class: str


class OverallRowSchema(BaseModel):
    """Overall totals row across all task types."""

    model_means: dict[str, float]
    model_counts: dict[str, int]
    model_reward_classes: dict[str, str]
    delta: float | None
    delta_class: str


class CompareResponse(BaseModel):
    """Response for the compare head-to-head model analysis endpoint."""

    models: list[str]
    task_types: list[str]
    aggregate_table: list[AggregateRowSchema]
    overall: OverallRowSchema
    model_colours: dict[str, str]
    model_to_parts: dict[str, list[str]]
    experiments: list[str]
    selected_experiment: str
    view_mode: str
    active_task_type: str | None


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


class ModelRowSchema(BaseModel):
    """One row in the single-dataset leaderboard table."""

    adapter: str
    model: str
    trials: int
    mean_reward: float
    perfect_pct: float
    zero_pct: float
    cost: float | None


class ScorecardCellSchema(BaseModel):
    """One cell in the cross-dataset scorecard grid."""

    mean_reward: float | None
    trials: int


class ScorecardRowSchema(BaseModel):
    """One model row in the scorecard with per-dataset scores."""

    adapter: str
    model: str
    cells: dict[str, ScorecardCellSchema]
    overall: float | None


class DatasetSummarySchema(BaseModel):
    """Summary of a dataset for leaderboard context."""

    name: str
    version: str
    summary: str
    task_count: int
    domains: list[str]


class LeaderboardResponse(BaseModel):
    """Response for the leaderboard endpoint."""

    model_rows: list[ModelRowSchema]
    is_scorecard: bool
    scorecard_rows: list[ScorecardRowSchema]
    datasets: list[DatasetSummarySchema]
    selected_dataset: str | None


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class DatasetListItemSchema(BaseModel):
    """One dataset card in the datasets list."""

    name: str
    version: str
    summary: str
    task_count: int
    domains: list[str]
    content_hash: str


class DatasetsListResponse(BaseModel):
    """Response for the datasets list endpoint."""

    datasets: list[DatasetListItemSchema]
    total_datasets: int
    total_tasks: int


class ExperimentResultSchema(BaseModel):
    """Summary of experiment results linked to a dataset."""

    experiment_id: str
    trial_count: int
    mean_reward: float
    reward_class: str
    models: list[str]


class IntegrityResultSchema(BaseModel):
    """Per-task integrity check result for a dataset."""

    task_id: str
    status: str
    expected_hash: str


class DatasetTaskEntrySchema(BaseModel):
    """One task entry in a dataset's task list."""

    task_id: str
    domain: str
    difficulty: str
    tags: list[str]


class DatasetDetailResponse(BaseModel):
    """Response for the dataset detail endpoint."""

    name: str
    version: str
    summary: str
    content_hash: str
    task_count: int
    domains: list[str]
    tasks: list[DatasetTaskEntrySchema]
    experiment_results: list[ExperimentResultSchema]
    integrity_results: list[IntegrityResultSchema]


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


class TemplateIOSchema(BaseModel):
    """One input or output parameter for a benchmark template."""

    name: str
    description: str


class TemplateSchema(BaseModel):
    """Full representation of a benchmark template for the library."""

    task_id: str
    discipline: str
    description: str
    long_description: str
    tags: list[str]
    standards: list[str]
    inputs: list[TemplateIOSchema]
    outputs: list[TemplateIOSchema]
    param_count: int


class LibraryListResponse(BaseModel):
    """Response for the library template catalogue list endpoint."""

    templates: list[TemplateSchema]
    disciplines: list[str]
    selected_discipline: str


class LibraryDetailResponse(BaseModel):
    """Response for the library template detail endpoint."""

    template: TemplateSchema


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TrialSearchResult(BaseModel):
    """Single trial match in /api/search response."""

    trial_id: str
    experiment_id: str
    task_id: str
    model: str
    reward: float


class ExperimentSearchResult(BaseModel):
    """Single experiment match (aggregated) in /api/search response."""

    experiment_id: str
    trial_count: int
    mean_reward: float


class WorkspaceSearchResult(BaseModel):
    """Single workspace match in /api/search response."""

    name: str
    path: str
    has_swarm: bool


class SearchResponse(BaseModel):
    """Response for the search endpoint."""

    query: str
    template_results: list[dict[str, Any]]
    dataset_results: list[dict[str, Any]]
    trial_results: list[TrialSearchResult] = []
    experiment_results: list[ExperimentSearchResult] = []
    workspace_results: list[WorkspaceSearchResult] = []
    total_results: int


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ReviewQueueResponse(BaseModel):
    """Response for the internal review queue endpoint."""

    assignments: dict[str, Any]


class ReviewTrialResponse(BaseModel):
    """Response for the internal review trial detail endpoint."""

    bundle: dict[str, Any]


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------


class EvolutionWorkspaceSummarySchema(BaseModel):
    """One run card in the evolution workspaces list (one per run, not per workspace)."""

    name: str
    path: str
    run_id: str = ""
    strategy: str = "unknown"
    cycles: int
    best_score: float
    final_score: float
    model: str
    has_swarm: bool = False


class EvolutionWorkspacesResponse(BaseModel):
    """Response for the evolution workspaces list endpoint."""

    workspaces: list[EvolutionWorkspaceSummarySchema]


class EvolutionCycleSchema(BaseModel):
    """Data for one evolution cycle."""

    cycle: int
    version_tag: str
    score: float
    prompt_diff: str
    skills_added: list[str]
    skills_modified: list[str]
    skills_removed: list[str]
    skill_diffs: dict[str, str]
    evolver_reasoning: str | None = None


class EvolutionDataResponse(BaseModel):
    """Full evolution report data for the workspace explorer."""

    workspace_name: str
    model: str
    strategy: str = "unknown"
    total_cycles: int
    converged: bool
    best_score: float
    final_score: float
    cycles: list[EvolutionCycleSchema]


class FileTreeNodeSchema(BaseModel):
    """One node in the evolution file tree."""

    name: str
    type: str
    status: str = "unchanged"
    size: int | None = None
    children: list["FileTreeNodeSchema"] | None = None


class EvolutionTreeResponse(BaseModel):
    """Response for the file tree at a specific version."""

    version: str
    tree: list[FileTreeNodeSchema]


class EvolutionFileResponse(BaseModel):
    """Response for file content at a specific version."""

    path: str
    version: str
    content: str
    language: str


class EvolutionDiffResponse(BaseModel):
    """Response for the unified diff of a file between versions."""

    path: str
    from_version: str
    to_version: str
    diff: str


class EvolutionRunSchema(BaseModel):
    """One evolution run in the runs list."""

    run_id: str
    strategy: str
    cycles: int
    best_score: float
    final_score: float


class EvolutionRunsResponse(BaseModel):
    """Response for the evolution runs list endpoint."""

    runs: list[EvolutionRunSchema]


class GraveyardEntrySchema(BaseModel):
    """One failed mutation in the graveyard."""

    cycle: int
    strategy: str
    mutation_description: str
    score_before: float
    score_after: float
    failure_reason: str
    field_failures: dict[str, str] | None = None
    detected_patterns: list[str] | None = None
    mutation_actions: list[dict[str, Any]] | None = None
    investigation_summary: str | None = None


class GraveyardResponse(BaseModel):
    """Response for the graveyard endpoint."""

    entries: list[GraveyardEntrySchema]
    total: int


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------


class AnalyzeCell(BaseModel):
    """One cell in the Analyze result grid, populated with every requested metric."""

    mean_reward: float | None = None
    perfect_pct: float | None = None
    zero_pct: float | None = None
    count: int = 0
    cost: float | None = None


class AnalyzeResponse(BaseModel):
    """Pivot result from /api/analyze."""

    rows_dim: str
    cols_dim: str
    metrics: list[str]
    delta_enabled: bool
    row_labels: list[str]
    col_labels: list[str]
    cells: dict[str, AnalyzeCell]  # key = "<row>|<col>"
    row_totals: dict[str, AnalyzeCell]  # key = row label
    col_totals: dict[str, AnalyzeCell]  # key = col label
    grand_total: AnalyzeCell
    row_deltas: dict[str, float] | None = None  # set only when delta_enabled


# ---------------------------------------------------------------------------
# Swarm Mission Control
# ---------------------------------------------------------------------------


class SwarmAgentSchema(BaseModel):
    """State of one agent in the swarm."""

    agent_id: str
    model: str
    status: str
    eval_count: int = 0
    best_score: float = 0.0
    budget_consumed_usd: float = 0.0
    restart_count: int = 0
    nudge: str = ""


class SwarmBudgetSchema(BaseModel):
    """Budget tracking for a swarm run."""

    max_cost_usd: float
    total_spent_usd: float
    spend_percentage: float
    phase: str


class SwarmCentroidSchema(BaseModel):
    """One cell in the QD archive grid."""

    x: float
    y: float
    occupied: bool
    reward: float | None = None
    version: str | None = None
    agent_id: str | None = None
    token_cost: float | None = None
    verification_depth: float | None = None
    tool_density: float | None = None
    exploration_ratio: float | None = None
    deliberation_ratio: float | None = None


class SwarmEventSchema(BaseModel):
    """A single swarm event from the event log."""

    event_type: str
    timestamp: str
    agent_id: str | None = None
    payload: dict[str, Any] = {}
    sequence_number: int = 0


class SwarmLineageNodeSchema(BaseModel):
    """One node in the swarm lineage graph."""

    version: str
    parent_version: str | None = None
    agent_id: str
    cross_agent: bool = False
    surprise: bool = False
    mutation_type: str
    reward: float = 0.0
    narrative: str = ""


class SwarmNoteSchema(BaseModel):
    """A research note authored by a swarm agent."""

    note_id: str = ""
    agent_id: str
    timestamp: str
    title: str
    content: str
    tags: list[str] = []


class SwarmConsolidationSchema(BaseModel):
    """Analyst consolidation report across swarm agents."""

    report_id: str
    timestamp: str
    archive_coverage_pct: float = 0.0
    total_evals: int = 0
    cross_agent_patterns: list[str] = []
    strategy_recommendations: list[str] = []
    counterintuitive_findings: list[str] = []
    lineage_insights: str = ""


class SwarmRunSummarySchema(BaseModel):
    """Summary card for one swarm run."""

    run_id: str
    workspace: str
    status: str
    agent_count: int = 0
    total_evals: int = 0
    best_score: float = 0.0
    total_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    strategy: str = "qd"


class SwarmRunsResponse(BaseModel):
    """Response for the swarm runs list endpoint."""

    runs: list[SwarmRunSummarySchema]


class SwarmStateResponse(BaseModel):
    """Full state snapshot for the swarm Mission Control dashboard."""

    run_id: str
    workspace: str
    status: str
    agents: list[SwarmAgentSchema]
    budget: SwarmBudgetSchema
    centroids: list[SwarmCentroidSchema]
    lineage: list[SwarmLineageNodeSchema]
    notes: list[SwarmNoteSchema]
    consolidation_reports: list[SwarmConsolidationSchema]
    events: list[SwarmEventSchema]
    total_evals: int = 0
    best_score: float = 0.0
    elapsed_seconds: float = 0.0


class SwarmEventsResponse(BaseModel):
    """Response for the swarm events stream endpoint."""

    events: list[SwarmEventSchema]
