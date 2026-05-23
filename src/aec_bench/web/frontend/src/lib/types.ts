// ABOUTME: TypeScript interfaces mirroring the Pydantic schemas in web/schemas.py.
// ABOUTME: Used by the API client to type all JSON responses from the backend.

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface ExperimentSummary {
  experiment_id: string;
  trial_count: number;
  mean_reward: number;
  models: string[];
  disciplines: string[];
  adapters: string[];
}

export interface DashboardData {
  experiments: ExperimentSummary[];
  total_trials: number;
  total_experiments: number;
  mean_reward: number;
  annotated_count: number;
}

// ---------------------------------------------------------------------------
// Triage
// ---------------------------------------------------------------------------

export interface TrialRow {
  trial_id: string;
  experiment_id: string;
  task_id: string;
  model: string;
  adapter: string;
  discipline: string;
  reward: number;
  reward_class: string;
  annotation_icon: string;
  annotation_verdict: string;
}

export interface TriageData {
  trials: TrialRow[];
  trial_count: number;
  annotations: Record<string, Record<string, string>>;
  filters: Record<string, string>;
  experiments: string[];
  models: string[];
}

// ---------------------------------------------------------------------------
// Viewer
// ---------------------------------------------------------------------------

export interface StepSummary {
  step: number;
  status: string;
  description: string;
  tool_name: string;
  duration_ms: number | null;
  error_count: number;
  metadata: Record<string, any> | null;
  call_type?: string | null;
  output_summary?: string | null;
}

export interface Annotation {
  verdict: string;
  notes: string;
  timestamp: string;
}

export interface ViewerMeta {
  trial_id: string;
  experiment_id: string;
  dataset_id?: string | null;          // "name@version" for dataset trials, null for inline runs
  task_id: string;
  model: string;
  adapter: string;
  reward: number;
  reward_class: string;
  steps: StepSummary[];
  is_rlm_trial: boolean;
  adapter_type: string;  // "rlm", "lambda-rlm", or "other"
  artefacts: string[];
  annotation: Annotation | null;
  total_errors: number;
  tokens_in: number | null;
  tokens_out: number | null;
  total_tokens: number | null;
  cost_usd: number | null;
  siblings: string[];
  prev_trial: string | null;
  next_trial: string | null;
  back_url: string;
  has_trajectory: boolean;
}

export interface TrajectoryMessage {
  [key: string]: any;
}

export interface ViewerStepData {
  step_num: number;
  messages: TrajectoryMessage[];
}

export interface ViewerState {
  symbolic_state: Record<string, any>;
  scratchpad_data: Record<string, any>;
  plan_state?: Record<string, any> | null;
}

export interface LambdaRlmState {
  plan_state: Record<string, any> | null;
}

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

export interface ModelRow {
  adapter: string;
  model: string;
  trials: number;
  mean_reward: number;
  perfect_pct: number;
  zero_pct: number;
  cost: number | null;
}

export interface ScorecardCell {
  mean_reward: number | null;
  trials: number;
}

export interface ScorecardRow {
  adapter: string;
  model: string;
  cells: Record<string, ScorecardCell>;
  overall: number | null;
}

export interface DatasetSummary {
  name: string;
  version: string;
  summary: string;
  task_count: number;
  domains: string[];
}

export interface LeaderboardData {
  model_rows: ModelRow[];
  is_scorecard: boolean;
  scorecard_rows: ScorecardRow[];
  datasets: DatasetSummary[];
  selected_dataset: string | null;
}

// ---------------------------------------------------------------------------
// Datasets
// ---------------------------------------------------------------------------

export interface DatasetListItem {
  name: string;
  version: string;
  summary: string;
  task_count: number;
  domains: string[];
  content_hash: string;
}

export interface DatasetsListData {
  datasets: DatasetListItem[];
  total_datasets: number;
  total_tasks: number;
}

export interface DatasetTaskEntry {
  task_id: string;
  domain: string;
  difficulty: string;
  tags: string[];
}

export interface ExperimentResult {
  experiment_id: string;
  trial_count: number;
  mean_reward: number;
  reward_class: string;
  models: string[];
}

export interface IntegrityResult {
  task_id: string;
  status: string;
  expected_hash: string;
}

export interface DatasetDetailData {
  name: string;
  version: string;
  summary: string;
  content_hash: string;
  task_count: number;
  domains: string[];
  tasks: DatasetTaskEntry[];
  experiment_results: ExperimentResult[];
  integrity_results: IntegrityResult[];
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

export interface TemplateIO {
  name: string;
  description: string;
}

export interface Template {
  task_id: string;
  discipline: string;
  description: string;
  long_description: string;
  tags: string[];
  standards: string[];
  inputs: TemplateIO[];
  outputs: TemplateIO[];
  param_count: number;
}

export interface LibraryListData {
  templates: Template[];
  disciplines: string[];
  selected_discipline: string;
}

export interface LibraryDetailData {
  template: Template;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface TrialSearchResult {
  trial_id: string;
  experiment_id: string;
  task_id: string;
  model: string;
  reward: number;
}

export interface TemplateSearchResult {
  name?: string;
  task_id: string;
  discipline: string;
  description?: string;
  standards?: string[];
  tags?: string[];
}

export interface DatasetSearchResult {
  name: string;
  version: string;
  summary: string;
  task_count: number;
  domains: string[];
}

export interface ExperimentSearchResult {
  experiment_id: string;
  trial_count: number;
  mean_reward: number;
}

export interface WorkspaceSearchResult {
  name: string;
  path: string;
  has_swarm: boolean;
}

export interface SearchData {
  query: string;
  template_results: TemplateSearchResult[];
  dataset_results: DatasetSearchResult[];
  trial_results: TrialSearchResult[];
  experiment_results: ExperimentSearchResult[];
  workspace_results: WorkspaceSearchResult[];
  total_results: number;
}

// ---------------------------------------------------------------------------
// Review
// ---------------------------------------------------------------------------

export interface ReviewAssignment {
  assignment_id: string;
  trial_id: string;
  experiment_id: string;
  task_id: string;
  task_visibility: string;
  reviewer_id: string;
  reviewer_discipline: string;
  assigned_at: string;
  is_calibration: boolean;
  assignment_reason: string;
}

export interface ReviewerProfile {
  reviewer_id: string;
  discipline: string;
  calibration_status: string;
  calibration_version: string | null;
  can_review_holdout: boolean;
  weighting: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface ReviewQueueSnapshot {
  reviewer: ReviewerProfile;
  assignments: ReviewAssignment[];
}

export interface ReviewQueueData {
  assignments: ReviewQueueSnapshot;
}

export interface ReviewTrialData {
  bundle: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Evolution
// ---------------------------------------------------------------------------

export interface EvolutionWorkspaceSummary {
  name: string;
  path: string;
  run_id?: string;
  strategy?: string;
  cycles: number;
  best_score: number;
  final_score: number;
  model: string;
  has_swarm?: boolean;
}

export interface EvolutionWorkspacesData {
  workspaces: EvolutionWorkspaceSummary[];
}

export interface EvolutionCycle {
  cycle: number;
  version_tag: string;
  score: number;
  prompt_diff: string;
  skills_added: string[];
  skills_modified: string[];
  skills_removed: string[];
  skill_diffs: Record<string, string>;
  evolver_reasoning: string | null;
}

export interface EvolutionData {
  workspace_name: string;
  model: string;
  total_cycles: number;
  converged: boolean;
  best_score: number;
  final_score: number;
  strategy: string;
  cycles: EvolutionCycle[];
}

export interface EvolutionRun {
  run_id: string;
  strategy: string;
  cycles: number;
  best_score: number;
  final_score: number;
}

export interface EvolutionRunsData {
  runs: EvolutionRun[];
}

export interface GraveyardEntry {
  cycle: number;
  strategy: string;
  mutation_description: string;
  score_before: number;
  score_after: number;
  failure_reason: string;
  field_failures: Record<string, string> | null;
  detected_patterns: string[] | null;
  mutation_actions: Record<string, string>[] | null;
  investigation_summary: string | null;
}

export interface GraveyardData {
  entries: GraveyardEntry[];
  total: number;
}

export interface ArchivePoint {
  x: number;
  y: number;
  reward: number;
  version: string;
  token_cost: number;
  verification_depth: number;
  tool_density: number;
  exploration_ratio: number;
  deliberation_ratio: number;
  task_ids: string[];
  discipline: string;
  run_id: string;
}

export interface ArchiveSummary {
  size: number;
  n_centroids: number;
  coverage: number;
  best_reward: number;
  mean_reward: number;
  disciplines: string[];
  task_ids: string[];
  bd_dimensions: string[];
}

export interface ArchiveData {
  summary: ArchiveSummary;
  points_2d: ArchivePoint[];
}

export type FileStatus = "added" | "modified" | "removed" | "unchanged";

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  status: FileStatus;
  size?: number;
  children?: FileTreeNode[];
}

export interface EvolutionTreeData {
  version: string;
  tree: FileTreeNode[];
}

export interface FileContent {
  path: string;
  version: string;
  content: string;
  language: string;
}

export interface FileDiff {
  path: string;
  from_version: string;
  to_version: string;
  diff: string;
}

// ---------------------------------------------------------------------------
// Swarm Mission Control
// ---------------------------------------------------------------------------

export interface SwarmAgent {
  agent_id: string;
  model: string;
  status: string;
  eval_count: number;
  best_score: number;
  budget_consumed_usd: number;
  restart_count: number;
  nudge: string;
}

export interface SwarmBudget {
  max_cost_usd: number;
  total_spent_usd: number;
  spend_percentage: number;
  phase: string;
}

export interface SwarmCentroid {
  x: number;
  y: number;
  occupied: boolean;
  reward?: number;
  version?: string;
  agent_id?: string;
  token_cost?: number;
  verification_depth?: number;
  tool_density?: number;
  exploration_ratio?: number;
  deliberation_ratio?: number;
}

export interface SwarmEvent {
  event_type: string;
  timestamp: string;
  agent_id: string | null;
  payload: Record<string, any>;
  sequence_number: number;
}

export interface SwarmLineageNode {
  version: string;
  parent_version: string | null;
  agent_id: string;
  cross_agent: boolean;
  surprise: boolean;
  mutation_type: string;
  reward: number;
  narrative: string;
}

export interface SwarmNote {
  note_id: string;
  agent_id: string;
  timestamp: string;
  title: string;
  content: string;
  tags: string[];
}

export interface SwarmConsolidation {
  report_id: string;
  timestamp: string;
  archive_coverage_pct: number;
  total_evals: number;
  cross_agent_patterns: string[];
  strategy_recommendations: string[];
  counterintuitive_findings: string[];
  lineage_insights: string;
}

export interface SwarmRunSummary {
  run_id: string;
  workspace: string;
  status: string;
  agent_count: number;
  total_evals: number;
  best_score: number;
  total_cost_usd: number;
  elapsed_seconds: number;
  strategy: string;
}

export interface SwarmRunsData {
  runs: SwarmRunSummary[];
}

export interface SwarmState {
  run_id: string;
  workspace: string;
  status: string;
  agents: SwarmAgent[];
  budget: SwarmBudget;
  centroids: SwarmCentroid[];
  lineage: SwarmLineageNode[];
  notes: SwarmNote[];
  consolidation_reports: SwarmConsolidation[];
  events: SwarmEvent[];
  total_evals: number;
  best_score: number;
  elapsed_seconds: number;
}

export interface SwarmEventsData {
  events: SwarmEvent[];
}

// ---------------------------------------------------------------------------
// Analyze
// ---------------------------------------------------------------------------

export type AnalyzeDim = "experiment" | "adapter" | "model" | "task_type" | "discipline" | "dataset";
export type AnalyzeCol = AnalyzeDim | "none";
export type AnalyzeMetric = "mean_reward" | "perfect_pct" | "zero_pct" | "count" | "cost";

export interface AnalyzeCell {
  mean_reward?: number | null;
  perfect_pct?: number | null;
  zero_pct?: number | null;
  count: number;
  cost?: number | null;
}

export interface AnalyzeData {
  rows_dim: AnalyzeDim;
  cols_dim: AnalyzeCol;
  metrics: AnalyzeMetric[];
  delta_enabled: boolean;
  row_labels: string[];
  col_labels: string[];
  cells: Record<string, AnalyzeCell>;
  row_totals: Record<string, AnalyzeCell>;
  col_totals: Record<string, AnalyzeCell>;
  grand_total: AnalyzeCell;
  row_deltas?: Record<string, number> | null;
}
