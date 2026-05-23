<!-- ABOUTME: Leaderboard page showing model rankings across datasets as a scorecard grid. -->
<!-- ABOUTME: Renders a cross-dataset scorecard; single-dataset mode redirected to /analyze. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchLeaderboard } from "../lib/api";
  import type { LeaderboardData } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: LeaderboardData | null = $state(null);

  async function loadData() {
    data = null;
    // Single-dataset mode was redirected to /analyze; /leaderboard is now scorecard-only.
    data = await fetchLeaderboard({ view: "scorecard" });
  }

  onMount(() => {
    loadData();
  });

  function modelColour(model: string): string {
    if (model.includes("sonnet-4") || model.includes("claude-sonnet-4")) return "#3cb2b1";
    if (model.includes("sonnet")) return "#89c925";
    if (model.includes("haiku")) return "#2d4a5e";
    if (model.includes("gpt") && model.includes("mini")) return "#e4572e";
    return "#4a6741";
  }

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function drillToRuns(model: string) {
    const params = new URLSearchParams();
    params.set("model", model);
    navigate(`/?${params.toString()}`);
  }
</script>

<section class="page-header">
  <h1>Leaderboard</h1>
</section>

{#if data === null}
  <Card>
    <div class="skeleton-block">
      <Skeleton height="1.5rem" width="30%" />
      <Skeleton height="10rem" />
    </div>
  </Card>
{:else}
  <!-- Scorecard: cross-dataset grid -->
  {#if data.scorecard_rows.length === 0}
    <Card>
      <div class="empty-state">
        <p>No scorecard data available.</p>
      </div>
    </Card>
  {:else}
    <Card padding="0">
      <div class="table-scroll">
        <table class="scorecard-table">
          <thead>
            <tr>
              <th class="model-col-sc">Model</th>
              <th class="adapter-col-sc">Adapter</th>
              {#each data.datasets as ds (ds.name + ds.version)}
                <th class="dataset-col">{ds.name}<br /><span class="ds-version">v{ds.version}</span></th>
              {/each}
              <th class="overall-col">Overall</th>
            </tr>
          </thead>
          <tbody>
            {#each data.scorecard_rows as row (row.model + row.adapter)}
              <tr class="clickable-row" onclick={() => drillToRuns(row.model)}>
                <td>
                  <Badge text={row.model} variant="model" colour={modelColour(row.model)} />
                </td>
                <td>
                  {#if row.adapter === "rlm"}
                    <Badge text="RLM" variant="rlm" />
                  {:else}
                    <Badge text={row.adapter} />
                  {/if}
                </td>
                {#each data.datasets as ds (ds.name + ds.version)}
                  {@const cell = row.cells[ds.name + "@" + ds.version]}
                  <td class="scorecard-cell">
                    {#if cell && cell.mean_reward !== null}
                      <RewardBadge reward={cell.mean_reward} size="sm" />
                      <span class="sc-count">n={cell.trials}</span>
                    {:else}
                      <span class="no-data">—</span>
                    {/if}
                  </td>
                {/each}
                <td class="overall-cell">
                  {#if row.overall !== null}
                    <RewardBadge reward={row.overall} size="sm" />
                  {:else}
                    <span class="no-data">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </Card>
  {/if}
{/if}

<style>
  .page-header {
    display: flex;
    align-items: center;
    gap: var(--space-lg);
    margin-bottom: var(--space-lg);
    flex-wrap: wrap;
  }

  .page-header h1 {
    font-family: var(--font-heading);
    font-size: 1.75rem;
  }

  thead {
    background: var(--bg-alt);
  }

  th {
    padding: var(--space-sm) var(--space-md);
    font-family: var(--font-heading);
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-2);
    border-bottom: 1px solid var(--card-border);
    text-align: left;
    white-space: nowrap;
  }

  td {
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    vertical-align: middle;
  }

  tbody tr:hover {
    background: var(--bg-alt);
  }

  .clickable-row {
    cursor: pointer;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  /* Scorecard table */
  .table-scroll {
    overflow-x: auto;
  }

  .scorecard-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  .model-col-sc {
    min-width: 160px;
  }

  .adapter-col-sc {
    min-width: 100px;
  }

  .dataset-col {
    text-align: center;
    min-width: 120px;
    line-height: 1.3;
  }

  .ds-version {
    font-weight: 400;
    font-size: 0.7rem;
    color: var(--text-3);
  }

  .overall-col {
    text-align: center;
    min-width: 100px;
    border-left: 2px solid var(--card-border);
  }

  .scorecard-cell {
    text-align: center;
  }

  .sc-count {
    display: block;
    font-size: 0.65rem;
    color: var(--text-3);
    margin-top: 2px;
  }

  .overall-cell {
    text-align: center;
    border-left: 2px solid var(--card-border);
  }

  .no-data {
    color: var(--text-3);
    font-family: var(--font-mono);
  }

  .skeleton-block {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }
</style>
