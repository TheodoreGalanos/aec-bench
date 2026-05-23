<!-- ABOUTME: Pivot controls for the Analyze page — rows/cols/metric selects + delta toggle. -->
<!-- ABOUTME: Enforces rows !== cols by disabling the conflicting option in the cols select. -->
<script lang="ts">
  import type { AnalyzeCol, AnalyzeDim, AnalyzeMetric } from "../lib/types";
  import type { AnalyzeState, PivotPatch } from "../lib/stores/analyze.svelte";

  type Props = {
    state: AnalyzeState;
    onChange: (pivot: PivotPatch) => void;
  };
  let { state, onChange }: Props = $props();

  const DIMS: AnalyzeDim[] = ["experiment", "adapter", "model", "task_type", "discipline", "dataset"];
  const COLS: AnalyzeCol[] = [...DIMS, "none"];
  const METRICS: AnalyzeMetric[] = ["mean_reward", "perfect_pct", "zero_pct", "count", "cost"];

  const DIM_LABELS: Record<AnalyzeDim | "none", string> = {
    experiment: "experiment",
    adapter: "adapter",
    model: "model",
    task_type: "task type",
    discipline: "discipline",
    dataset: "dataset",
    none: "(none)",
  };
  const METRIC_LABELS: Record<AnalyzeMetric, string> = {
    mean_reward: "mean reward",
    perfect_pct: "perfect %",
    zero_pct: "zero %",
    count: "count",
    cost: "cost",
  };

  function onRowsChange(e: Event) {
    const v = (e.target as HTMLSelectElement).value as AnalyzeDim;
    onChange({ rows: v, cols: state.cols, metrics: state.metrics, delta: state.delta });
  }
  function onColsChange(e: Event) {
    const v = (e.target as HTMLSelectElement).value as AnalyzeCol;
    onChange({ rows: state.rows, cols: v, metrics: state.metrics, delta: state.delta });
  }
  function onMetricChange(e: Event) {
    const v = (e.target as HTMLSelectElement).value as AnalyzeMetric;
    onChange({ rows: state.rows, cols: state.cols, metrics: [v], delta: state.delta });
  }
  function onDeltaChange(e: Event) {
    const checked = (e.target as HTMLInputElement).checked;
    onChange({ rows: state.rows, cols: state.cols, metrics: state.metrics, delta: checked });
  }

  let deltaAllowed = $derived(state.cols !== "none" && state.metrics.length === 1);
</script>

<div class="picker">
  <label>
    Rows
    <select value={state.rows} onchange={onRowsChange}>
      {#each DIMS as d (d)}
        <option value={d}>{DIM_LABELS[d]}</option>
      {/each}
    </select>
  </label>

  <label>
    Cols
    <select value={state.cols} onchange={onColsChange}>
      {#each COLS as c (c)}
        <option value={c} disabled={c === state.rows}>{DIM_LABELS[c]}</option>
      {/each}
    </select>
  </label>

  <label>
    Metric
    <select value={state.metrics[0]} onchange={onMetricChange}>
      {#each METRICS as m (m)}
        <option value={m}>{METRIC_LABELS[m]}</option>
      {/each}
    </select>
  </label>

  {#if deltaAllowed}
    <label class="delta-toggle">
      <input type="checkbox" name="delta" checked={state.delta} onchange={onDeltaChange} />
      Show Δ vs first column
    </label>
  {/if}
</div>

<style>
  .picker {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
    align-items: end;
    padding: var(--space-md) var(--space-lg);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    font-size: 0.78rem;
    color: var(--text-2);
  }
  .delta-toggle {
    flex-direction: row;
    align-items: center;
  }
</style>
