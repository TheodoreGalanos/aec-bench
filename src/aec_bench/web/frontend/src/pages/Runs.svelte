<!-- ABOUTME: Runs landing page combining experiments rail, stats strip, chips, and trial list. -->
<!-- ABOUTME: Replaces the legacy Dashboard + Triage pair; URL is the source of truth via runsStore. -->
<script lang="ts">
  import { onMount } from "svelte";
  import ExperimentsRail from "../runs/ExperimentsRail.svelte";
  import StatsStrip from "../runs/StatsStrip.svelte";
  import FilterChips from "../runs/FilterChips.svelte";
  import TrialList from "../runs/TrialList.svelte";
  import { fetchDashboard, fetchTriage } from "../lib/api";
  import { runsStore } from "../lib/stores/runs.svelte";
  import type { DashboardData, TriageData } from "../lib/types";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let dashboard: DashboardData | null = $state(null);
  let triage: TriageData | null = $state(null);

  async function loadDashboard() {
    dashboard = await fetchDashboard();
  }

  let triageFetchSeq = 0;

  async function loadTriage() {
    const seq = ++triageFetchSeq;
    const f = runsStore.filter;
    const data = await fetchTriage({
      experiment: f.experiment,
      model: f.model,
      adapter: f.adapter,
      task_type: f.task_type,
      annotated: f.annotated === undefined ? undefined : String(f.annotated),
    });
    if (seq !== triageFetchSeq) return; // stale, discard
    triage = data;
  }

  onMount(() => {
    runsStore.loadFromCurrentUrl();
    void loadDashboard(); // $effect will trigger loadTriage once dashboard resolves
    function onPopState() {
      runsStore.loadFromCurrentUrl();
      void loadTriage();
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  });

  // Re-fetch trials when filter changes.
  $effect(() => {
    // Touch the filter to register reactivity, then fire the fetch.
    void runsStore.filter;
    if (dashboard) loadTriage();
  });

  function selectExperiment(id: string) {
    runsStore.patchFilter({ experiment: id });
  }

  function clearExperiment() {
    runsStore.removeKey("experiment");
  }

  function navigateToTrial(experimentId: string, trialId: string) {
    window.history.pushState({}, "", `/viewer/${experimentId}/${trialId}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
</script>

<div class="runs-shell">
  <ExperimentsRail
    experiments={dashboard?.experiments ?? []}
    activeExperimentId={runsStore.filter.experiment}
    onSelect={selectExperiment}
    onClear={clearExperiment}
  />
  <main class="runs-main">
    <header class="runs-header">
      <h1>Runs</h1>
    </header>
    <StatsStrip
      totalExperiments={dashboard?.total_experiments ?? 0}
      totalTrials={triage?.trial_count ?? 0}
      meanReward={dashboard?.mean_reward ?? 0}
      annotatedCount={dashboard?.annotated_count ?? 0}
    />
    <FilterChips filter={runsStore.filter} onRemove={(k) => runsStore.removeKey(k)} />
    <div class="runs-list">
      {#if triage === null}
        <div class="skeleton-table">
          {#each [1, 2, 3, 4, 5, 6] as _}
            <div class="skeleton-row">
              <Skeleton height="0.85rem" width="30%" />
              <Skeleton height="0.85rem" width="20%" />
              <Skeleton height="0.85rem" width="18%" rounded />
              <Skeleton height="0.85rem" width="10%" />
            </div>
          {/each}
        </div>
      {:else}
        <TrialList trials={triage.trials} onTrialClick={navigateToTrial} />
      {/if}
    </div>
  </main>
</div>

<style>
  .runs-shell {
    display: flex;
    height: calc(100vh - var(--navbar-height));
  }
  .runs-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .runs-header {
    padding: var(--space-md) var(--space-lg) 0;
  }
  .runs-header h1 {
    font-family: var(--font-heading);
    font-size: 1.5rem;
  }
  .runs-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-md) var(--space-lg);
  }
  .skeleton-table {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    padding: var(--space-md) 0;
  }
  .skeleton-row {
    display: flex;
    gap: var(--space-lg);
    align-items: center;
  }
  @media (max-width: 768px) {
    .runs-shell {
      flex-direction: column;
    }
  }
</style>
