// ABOUTME: Typed fetch wrappers for all /api/* endpoints served by FastAPI.
// ABOUTME: All functions return typed promises and throw ApiError on non-2xx responses.

import type {
  DashboardData,
  TriageData,
  ViewerMeta,
  ViewerStepData,
  ViewerState,
  LeaderboardData,
  DatasetsListData,
  DatasetDetailData,
  LibraryListData,
  LibraryDetailData,
  SearchData,
  ReviewQueueData,
  ReviewTrialData,
  EvolutionWorkspacesData,
  EvolutionData,
  EvolutionRunsData,
  GraveyardData,
  ArchiveData,
  EvolutionTreeData,
  FileContent,
  FileDiff,
  SwarmRunsData,
  SwarmState,
  SwarmEventsData,
  AnalyzeData,
  AnalyzeMetric,
} from "./types";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`HTTP ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    let detail: string;
    try {
      const body = await resp.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await resp.text();
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const defined: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      defined[key] = value;
    }
  }
  const qs = new URLSearchParams(defined).toString();
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export function fetchDashboard(params?: { sort?: string }): Promise<DashboardData> {
  const qs = buildQuery({ sort: params?.sort });
  return fetchJson<DashboardData>(`/api/dashboard${qs}`);
}

// ---------------------------------------------------------------------------
// Triage
// ---------------------------------------------------------------------------

export function fetchTriage(params?: {
  experiment?: string;
  model?: string;
  adapter?: string;
  task_type?: string;
  reward?: string;
  errors?: string;
  annotated?: string;
  sort?: string;
}): Promise<TriageData> {
  const qs = buildQuery({
    experiment: params?.experiment,
    model: params?.model,
    adapter: params?.adapter,
    task_type: params?.task_type,
    reward: params?.reward,
    errors: params?.errors,
    annotated: params?.annotated,
    sort: params?.sort,
  });
  return fetchJson<TriageData>(`/api/triage${qs}`);
}

// ---------------------------------------------------------------------------
// Annotation (POST)
// ---------------------------------------------------------------------------

export async function submitAnnotation(body: {
  trial_id: string;
  experiment_id: string;
  verdict: string;
  notes?: string;
}): Promise<{ verdict: string; notes: string; timestamp: string }> {
  const resp = await fetch("/api/triage/annotate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    let detail: string;
    try {
      const err = await resp.json();
      detail = err?.detail ?? JSON.stringify(err);
    } catch {
      detail = await resp.text();
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Viewer
// ---------------------------------------------------------------------------

export function fetchViewerMeta(
  experimentId: string,
  trialId: string,
  params?: { from_page?: string },
): Promise<ViewerMeta> {
  const qs = buildQuery({ from_page: params?.from_page });
  return fetchJson<ViewerMeta>(`/api/viewer/${experimentId}/${trialId}${qs}`);
}

export function fetchViewerStep(
  experimentId: string,
  trialId: string,
  stepNum: number,
): Promise<ViewerStepData> {
  return fetchJson<ViewerStepData>(
    `/api/viewer/${experimentId}/${trialId}/steps/${stepNum}`,
  );
}

export function fetchViewerState(
  experimentId: string,
  trialId: string,
): Promise<ViewerState> {
  return fetchJson<ViewerState>(`/api/viewer/${experimentId}/${trialId}/state`);
}

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

export function fetchLeaderboard(params?: {
  dataset?: string;
  view?: "scorecard";
}): Promise<LeaderboardData> {
  const qs = buildQuery({ dataset: params?.dataset, view: params?.view });
  return fetchJson<LeaderboardData>(`/api/leaderboard${qs}`);
}

// ---------------------------------------------------------------------------
// Datasets
// ---------------------------------------------------------------------------

export function fetchDatasetsList(): Promise<DatasetsListData> {
  return fetchJson<DatasetsListData>("/api/datasets");
}

export function fetchDatasetDetail(
  name: string,
  version: string,
  params?: { tab?: string },
): Promise<DatasetDetailData> {
  const qs = buildQuery({ tab: params?.tab });
  return fetchJson<DatasetDetailData>(`/api/datasets/${name}/${version}${qs}`);
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

export function fetchLibraryList(params?: { discipline?: string }): Promise<LibraryListData> {
  const qs = buildQuery({ discipline: params?.discipline });
  return fetchJson<LibraryListData>(`/api/library${qs}`);
}

export function fetchLibraryDetail(
  discipline: string,
  templateId: string,
): Promise<LibraryDetailData> {
  return fetchJson<LibraryDetailData>(`/api/library/${discipline}/${templateId}`);
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export function fetchSearch(params?: { q?: string }): Promise<SearchData> {
  const qs = buildQuery({ q: params?.q });
  return fetchJson<SearchData>(`/api/search${qs}`);
}

// ---------------------------------------------------------------------------
// Review
// ---------------------------------------------------------------------------

export function fetchReviewQueue(params: { reviewer_id: string }): Promise<ReviewQueueData> {
  const qs = buildQuery({ reviewer_id: params.reviewer_id });
  return fetchJson<ReviewQueueData>(`/api/review/queue${qs}`);
}

export function fetchReviewTrial(
  trialId: string,
  params: { reviewer_id: string },
): Promise<ReviewTrialData> {
  const qs = buildQuery({ reviewer_id: params.reviewer_id });
  return fetchJson<ReviewTrialData>(`/api/review/trial/${encodeURIComponent(trialId)}${qs}`);
}

// ---------------------------------------------------------------------------
// Evolution
// ---------------------------------------------------------------------------

export function fetchEvolutionWorkspaces(): Promise<EvolutionWorkspacesData> {
  return fetchJson<EvolutionWorkspacesData>("/api/evolution/workspaces");
}

export function fetchEvolutionData(workspace: string, runId?: string): Promise<EvolutionData> {
  const params = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return fetchJson<EvolutionData>(`/api/evolution/${workspace}${params}`);
}

export function fetchEvolutionRuns(workspace: string): Promise<EvolutionRunsData> {
  return fetchJson<EvolutionRunsData>(`/api/evolution/${workspace}/runs`);
}

export function fetchEvolutionGraveyard(workspace: string): Promise<GraveyardData> {
  return fetchJson<GraveyardData>(`/api/evolution/${workspace}/graveyard`);
}

export function fetchEvolutionArchive(workspace: string): Promise<ArchiveData> {
  return fetchJson<ArchiveData>(`/api/evolution/${workspace}/archive`);
}

export function fetchEvolutionTree(workspace: string, version: string): Promise<EvolutionTreeData> {
  return fetchJson<EvolutionTreeData>(`/api/evolution/${workspace}/tree/${version}`);
}

export function fetchEvolutionFile(workspace: string, version: string, path: string): Promise<FileContent> {
  return fetchJson<FileContent>(`/api/evolution/${workspace}/file/${version}/${path}`);
}

export function fetchEvolutionDiff(workspace: string, version: string, path: string): Promise<FileDiff> {
  return fetchJson<FileDiff>(`/api/evolution/${workspace}/diff/${version}/${path}`);
}

// ---------------------------------------------------------------------------
// Swarm Mission Control
// ---------------------------------------------------------------------------

export function fetchSwarmRuns(): Promise<SwarmRunsData> {
  return fetchJson<SwarmRunsData>("/api/evolution/swarm/runs");
}

export function fetchSwarmState(workspace: string): Promise<SwarmState> {
  return fetchJson<SwarmState>(`/api/evolution/swarm/${workspace}/state`);
}

export function fetchSwarmEvents(workspace: string, after?: number): Promise<SwarmEventsData> {
  const qs = after !== undefined ? `?after=${after}` : "";
  return fetchJson<SwarmEventsData>(`/api/evolution/swarm/${workspace}/events${qs}`);
}

// ---------------------------------------------------------------------------
// Analyze
// ---------------------------------------------------------------------------

export function fetchAnalyze(params?: {
  rows?: string;
  cols?: string;
  metrics?: AnalyzeMetric[];
  delta?: boolean;
  experiment?: string;
  dataset?: string;
  model?: string;
  adapter?: string;
  task_type?: string;
}): Promise<AnalyzeData> {
  const qs = buildQuery({
    rows: params?.rows,
    cols: params?.cols,
    // Join the array internally so callsites pass typed arrays, not pre-joined strings.
    metrics: params?.metrics?.length ? params.metrics.join(",") : undefined,
    delta: params?.delta ? "true" : undefined,
    experiment: params?.experiment,
    dataset: params?.dataset,
    model: params?.model,
    adapter: params?.adapter,
    task_type: params?.task_type,
  });
  return fetchJson<AnalyzeData>(`/api/analyze${qs}`);
}
