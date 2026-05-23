<!-- ABOUTME: Analyze landing page — pivot picker + scope filters + preset chips + result table. -->
<!-- ABOUTME: Replaces /evaluate, /compare, and the single-dataset branch of /leaderboard. -->
<script lang="ts">
  import { onMount } from "svelte";
  import PivotPicker from "../analyze/PivotPicker.svelte";
  import ScopeFilters from "../analyze/ScopeFilters.svelte";
  import PresetChips from "../analyze/PresetChips.svelte";
  import ResultTable from "../analyze/ResultTable.svelte";
  import { fetchAnalyze, fetchDashboard } from "../lib/api";
  import { analyzeStore, type AnalyzeState } from "../lib/stores/analyze.svelte";
  import type { AnalyzeData, DashboardData } from "../lib/types";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: AnalyzeData | null = $state(null);
  let dashboard: DashboardData | null = $state(null);
  let analyzeSeq = 0;

  async function loadDashboard() {
    dashboard = await fetchDashboard();
  }

  async function loadAnalyze() {
    const seq = ++analyzeSeq;
    const s = analyzeStore.state;
    const fresh = await fetchAnalyze({
      rows: s.rows,
      cols: s.cols,
      metrics: s.metrics,
      delta: s.delta,
      experiment: s.experiment,
      dataset: s.dataset,
      model: s.model,
      adapter: s.adapter,
      task_type: s.task_type,
    });
    if (seq !== analyzeSeq) return;
    data = fresh;
  }

  onMount(() => {
    analyzeStore.loadFromCurrentUrl();
    void loadDashboard();
    void loadAnalyze();
    function onPopState() {
      analyzeStore.loadFromCurrentUrl();
      void loadAnalyze();
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  });

  // Re-fetch whenever the store state changes.
  $effect(() => {
    void analyzeStore.state;
    if (dashboard) void loadAnalyze();
  });

  function applyPivot(p: Pick<AnalyzeState, "rows" | "cols" | "metrics" | "delta">) {
    analyzeStore.setPivot(p);
  }

  function applyScope(patch: Partial<AnalyzeState>) {
    analyzeStore.setScope(patch);
  }

  function drillToRuns(row: string, col: string) {
    const s = analyzeStore.state;
    const params = new URLSearchParams();
    // Write active scope filters first…
    if (s.experiment) params.set("experiment", s.experiment);
    if (s.model) params.set("model", s.model);
    // …then the clicked row/col — these overwrite any scope key with the same
    // name (e.g. rows=experiment drilling a specific experiment). Drill wins.
    params.set(s.rows, row);
    if (s.cols !== "none") params.set(s.cols, col);
    window.history.pushState({}, "", `/?${params.toString()}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  // Derive dropdown sources from the dashboard data.
  let experiments = $derived.by(
    (): string[] => dashboard?.experiments.map((e) => e.experiment_id) ?? [],
  );
  let models = $derived.by(
    (): string[] =>
      Array.from(new Set((dashboard?.experiments ?? []).flatMap((e) => e.models))).sort(),
  );
  let adapters = $derived.by(
    (): string[] =>
      Array.from(new Set((dashboard?.experiments ?? []).flatMap((e) => e.adapters))).sort(),
  );
</script>

<section class="analyze-page">
  <div class="controls">
    <header>
      <h1>Analyze</h1>
    </header>

    <PresetChips onApply={applyPivot} />
    <PivotPicker state={analyzeStore.state} onChange={applyPivot} />
    <ScopeFilters
      state={analyzeStore.state}
      {experiments}
      datasets={[]}
      {models}
      {adapters}
      taskTypes={[]}
      onScopeChange={applyScope}
    />
  </div>

  <div class="result">
    {#if data}
      <ResultTable {data} onCellClick={drillToRuns} />
    {:else}
      <div class="skeleton-table">
        <div class="skeleton-header">
          <Skeleton height="0.75rem" width="10%" />
          {#each [1, 2, 3, 4] as _}
            <Skeleton height="0.75rem" width="14%" />
          {/each}
        </div>
        {#each [1, 2, 3, 4, 5] as _}
          <div class="skeleton-row">
            <Skeleton height="0.85rem" width="16%" />
            {#each [1, 2, 3, 4] as _}
              <Skeleton height="0.85rem" width="12%" />
            {/each}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>

<style>
  .analyze-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - var(--navbar-height));
    overflow: hidden;
  }
  .controls {
    flex-shrink: 0;
    border-bottom: 1px solid var(--card-border);
    background: var(--card);
  }
  header {
    padding: var(--space-md) var(--space-lg) 0;
  }
  h1 {
    font-family: var(--font-heading);
    font-size: 1.5rem;
  }
  .result {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-md) var(--space-lg);
  }
  .skeleton-table {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    padding: var(--space-sm) 0;
  }
  .skeleton-header,
  .skeleton-row {
    display: flex;
    gap: var(--space-lg);
    align-items: center;
  }
  @media (max-width: 768px) {
    h1 { font-size: 1.25rem; }
  }
</style>
