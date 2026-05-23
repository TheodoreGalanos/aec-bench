// ABOUTME: Shared pivot-preset constants for the Analyze page and its URL redirects.
// ABOUTME: Consumed by PresetChips and by App.svelte's /evaluate, /compare, /leaderboard redirects.

import type { AnalyzeMetric } from "../lib/types";
import type { PivotPatch } from "../lib/stores/analyze.svelte";

export const EVALUATE_PRESET: PivotPatch = {
  rows: "adapter",
  cols: "task_type",
  metrics: ["mean_reward"],
  delta: false,
};

export const COMPARE_PRESET: PivotPatch = {
  rows: "task_type",
  cols: "model",
  metrics: ["mean_reward"],
  delta: true,
};

export const LEADERBOARD_PRESET: PivotPatch = {
  rows: "model",
  cols: "none",
  metrics: ["mean_reward", "perfect_pct", "zero_pct", "count", "cost"] as AnalyzeMetric[],
  delta: false,
};
