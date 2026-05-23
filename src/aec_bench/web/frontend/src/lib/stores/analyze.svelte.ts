// ABOUTME: Svelte 5 runes-based store for the Analyze page — pivot dims + scope filters + URL sync.
// ABOUTME: Follows the same pattern as runs.svelte.ts (URL is source of truth, atomic assignment).

import type { AnalyzeCol, AnalyzeDim, AnalyzeMetric } from "../types";

export type AnalyzeState = {
  rows: AnalyzeDim;
  cols: AnalyzeCol;
  metrics: AnalyzeMetric[];
  delta: boolean;
  experiment?: string;
  dataset?: string;
  model?: string;
  adapter?: string;
  task_type?: string;
};

const DEFAULT_STATE: AnalyzeState = {
  rows: "adapter",
  cols: "task_type",
  metrics: ["mean_reward"],
  delta: false,
};

const VALID_DIMS = new Set<AnalyzeDim>([
  "experiment", "adapter", "model", "task_type", "discipline", "dataset",
]);
const VALID_METRICS = new Set<AnalyzeMetric>([
  "mean_reward", "perfect_pct", "zero_pct", "count", "cost",
]);

function isDim(s: string): s is AnalyzeDim {
  return VALID_DIMS.has(s as AnalyzeDim);
}
function isCol(s: string): s is AnalyzeCol {
  return s === "none" || isDim(s);
}
function isMetric(s: string): s is AnalyzeMetric {
  return VALID_METRICS.has(s as AnalyzeMetric);
}

export function parseAnalyzeStateFromQuery(query: string): AnalyzeState {
  const params = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
  const state: AnalyzeState = { ...DEFAULT_STATE, metrics: [...DEFAULT_STATE.metrics] };

  const rawRows = params.get("rows");
  if (rawRows && isDim(rawRows)) state.rows = rawRows;

  const rawCols = params.get("cols");
  if (rawCols && isCol(rawCols)) state.cols = rawCols;

  const rawMetrics = params.get("metrics");
  if (rawMetrics) {
    const parsed = rawMetrics.split(",").map((s) => s.trim()).filter(isMetric);
    if (parsed.length > 0) state.metrics = parsed;
  }

  if (params.get("delta") === "true") state.delta = true;

  for (const key of ["experiment", "dataset", "model", "adapter", "task_type"] as const) {
    const v = params.get(key);
    if (v) state[key] = v;
  }

  return state;
}

export function analyzeStateToQuery(state: AnalyzeState): string {
  const parts: string[] = [];
  if (state.rows !== DEFAULT_STATE.rows) parts.push(`rows=${encodeURIComponent(state.rows)}`);
  if (state.cols !== DEFAULT_STATE.cols) parts.push(`cols=${encodeURIComponent(state.cols)}`);
  // Emit metrics= when metrics differ from the single-element default, OR when any other pivot
  // field differs from its default (so the URL always carries context for non-default pivot state).
  const isDefaultMetrics =
    state.metrics.length === 1 && state.metrics[0] === DEFAULT_STATE.metrics[0];
  const emitMetrics =
    !isDefaultMetrics ||
    state.rows !== DEFAULT_STATE.rows ||
    state.cols !== DEFAULT_STATE.cols ||
    state.delta;
  if (emitMetrics) {
    parts.push(`metrics=${state.metrics.join(",")}`);
  }
  if (state.delta) parts.push("delta=true");
  for (const key of ["experiment", "dataset", "model", "adapter", "task_type"] as const) {
    const v = state[key];
    if (v) parts.push(`${key}=${encodeURIComponent(v)}`);
  }
  return parts.length > 0 ? `?${parts.join("&")}` : "";
}

export type PivotPatch = Pick<AnalyzeState, "rows" | "cols" | "metrics" | "delta">;
export type ScopePatch = Partial<Pick<AnalyzeState, "experiment" | "dataset" | "model" | "adapter" | "task_type">>;

export class AnalyzeStore {
  state: AnalyzeState = $state({ ...DEFAULT_STATE, metrics: [...DEFAULT_STATE.metrics] });

  loadFromCurrentUrl(): void {
    if (typeof window === "undefined") return;
    this.state = parseAnalyzeStateFromQuery(window.location.search);
  }

  setPivot(pivot: PivotPatch): void {
    this.state = {
      ...this.state,
      rows: pivot.rows,
      cols: pivot.cols,
      metrics: [...pivot.metrics],
      // Delta has no meaning without at least two columns; normalise the invariant here.
      delta: pivot.cols === "none" ? false : pivot.delta,
    };
    this.#syncUrl(true);
  }

  setScope(patch: ScopePatch): void {
    const next: AnalyzeState = { ...this.state, ...patch };
    for (const k of Object.keys(next) as (keyof AnalyzeState)[]) {
      if (next[k] === undefined) delete (next as Record<string, unknown>)[k];
    }
    this.state = next;
    this.#syncUrl(false);
  }

  clearScope(): void {
    const { rows, cols, metrics, delta } = this.state;
    this.state = { rows, cols, metrics: [...metrics], delta };
    this.#syncUrl(true);
  }

  removeScopeKey(key: keyof AnalyzeState): void {
    if (key === "rows" || key === "cols" || key === "metrics" || key === "delta") return;
    const next = { ...this.state };
    delete next[key];
    this.state = next;
    this.#syncUrl(false);
  }

  #syncUrl(push: boolean): void {
    if (typeof window === "undefined") return;
    const qs = analyzeStateToQuery(this.state);
    const url = `${window.location.pathname}${qs}`;
    if (push) window.history.pushState({}, "", url);
    else window.history.replaceState({}, "", url);
  }
}

export const analyzeStore = new AnalyzeStore();
