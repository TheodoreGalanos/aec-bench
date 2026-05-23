<!-- ABOUTME: Dataset detail page with tabbed view for Tasks, Results, and Integrity data. -->
<!-- ABOUTME: Fetches from /api/datasets/{name}/{version}; integrity data loads lazily on tab switch. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchDatasetDetail } from "../lib/api";
  import type { DatasetDetailData, DatasetTaskEntry, ExperimentResult, IntegrityResult } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";
  import DetailShell from "../lib/components/DetailShell.svelte";

  interface Props {
    name: string;
    version: string;
  }

  let { name, version }: Props = $props();

  let data: DatasetDetailData | null = $state(null);
  let activeTab: "tasks" | "results" | "integrity" = $state("tasks");
  let integrityLoaded: boolean = $state(false);

  onMount(async () => {
    data = await fetchDatasetDetail(name, version);
  });

  async function switchTab(tab: "tasks" | "results" | "integrity") {
    activeTab = tab;
    if (tab === "integrity" && !integrityLoaded && data) {
      // Reload with integrity tab param to get full integrity data
      const updated = await fetchDatasetDetail(name, version, { tab: "integrity" });
      data = updated;
      integrityLoaded = true;
    }
  }

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function drillToRuns(experimentId: string) {
    const params = new URLSearchParams();
    params.set("experiment", experimentId);
    navigate(`/?${params.toString()}`);
  }

  function integrityStatusClass(status: string): string {
    if (status === "verified") return "status-ok";
    if (status === "drifted") return "status-warn";
    return "status-error";
  }

  function integrityIcon(status: string): string {
    if (status === "verified") return "✓";
    if (status === "drifted") return "~";
    return "✗";
  }
</script>

{#if data === null}
  <div class="skeleton-page">
    <Skeleton height="2rem" width="40%" />
    <Skeleton height="1rem" width="60%" />
    <Skeleton height="16rem" />
  </div>
{:else}
  {@const dataset = data}
  <DetailShell
    backHref="/datasets"
    backLabel="Datasets"
    title={dataset.name}
    subtitle={dataset.summary || undefined}
  >
    {#snippet actions()}
      <span class="version-badge">v{dataset.version}</span>
    {/snippet}

    <div class="meta-row">
      <span class="task-count">{dataset.task_count} tasks</span>
      {#each dataset.domains as domain (domain)}
        <Badge text={domain} />
      {/each}
    </div>
    <div class="hash-row">
      <span class="hash-label">Content hash</span>
      <code class="hash-value">{dataset.content_hash}</code>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar" role="tablist">
      <button
        class="tab-btn"
        class:active={activeTab === "tasks"}
        role="tab"
        aria-selected={activeTab === "tasks"}
        onclick={() => switchTab("tasks")}
      >
        Tasks ({dataset.tasks.length})
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === "results"}
        role="tab"
        aria-selected={activeTab === "results"}
        onclick={() => switchTab("results")}
      >
        Results ({dataset.experiment_results.length})
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === "integrity"}
        role="tab"
        aria-selected={activeTab === "integrity"}
        onclick={() => switchTab("integrity")}
      >
        Integrity
      </button>
    </div>

    <!-- Tab content -->
    {#if activeTab === "tasks"}
      {#if dataset.tasks.length === 0}
        <Card>
          <div class="empty-state"><p>No tasks in this dataset.</p></div>
        </Card>
      {:else}
        <Card padding="0">
          <table class="task-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Domain</th>
                <th>Difficulty</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {#each dataset.tasks as task (task.task_id)}
                <tr>
                  <td class="task-id-cell">{task.task_id}</td>
                  <td><Badge text={task.domain} /></td>
                  <td><Badge text={task.difficulty} /></td>
                  <td>
                    <div class="tag-row">
                      {#each task.tags as tag (tag)}
                        <Badge text={tag} />
                      {/each}
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Card>
      {/if}

    {:else if activeTab === "results"}
      {#if dataset.experiment_results.length === 0}
        <Card>
          <div class="empty-state"><p>No experiment results linked to this dataset.</p></div>
        </Card>
      {:else}
        <Card padding="0">
          <table class="results-table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th class="num-col">Trials</th>
                <th class="num-col">Mean Reward</th>
                <th>Models</th>
              </tr>
            </thead>
            <tbody>
              {#each dataset.experiment_results as result (result.experiment_id)}
                <tr class="clickable-row" onclick={() => drillToRuns(result.experiment_id)}>
                  <td class="exp-id-cell">{result.experiment_id}</td>
                  <td class="num-cell">{result.trial_count}</td>
                  <td class="num-cell">
                    <RewardBadge reward={result.mean_reward} size="sm" />
                  </td>
                  <td>
                    <div class="tag-row">
                      {#each result.models as model (model)}
                        <Badge text={model} />
                      {/each}
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Card>
      {/if}

    {:else if activeTab === "integrity"}
      {#if dataset.integrity_results.length === 0}
        <Card>
          <div class="empty-state"><p>No integrity data available.</p></div>
        </Card>
      {:else}
        <Card padding="0">
          <table class="integrity-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Task ID</th>
                <th>Expected Hash</th>
              </tr>
            </thead>
            <tbody>
              {#each dataset.integrity_results as result (result.task_id)}
                <tr>
                  <td class="status-cell">
                    <span class="status-icon {integrityStatusClass(result.status)}" title={result.status}>
                      {integrityIcon(result.status)}
                    </span>
                    <span class="status-label {integrityStatusClass(result.status)}">{result.status}</span>
                  </td>
                  <td class="task-id-cell">{result.task_id}</td>
                  <td class="hash-cell">{result.expected_hash.slice(0, 16)}…</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Card>
      {/if}
    {/if}
  </DetailShell>
{/if}

<style>
  .skeleton-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .version-badge {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: var(--text-3);
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    padding: 2px 8px;
  }

  .meta-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    flex-wrap: wrap;
    margin-bottom: var(--space-sm);
  }

  .task-count {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--forest);
  }

  .hash-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .hash-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }

  .hash-value {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-3);
  }

  /* Tab bar */
  .tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 2px solid var(--card-border);
    margin-bottom: var(--space-md);
  }

  .tab-btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    padding: var(--space-sm) var(--space-lg);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    color: var(--text-2);
    transition: color var(--transition-fast), border-color var(--transition-fast);
  }

  .tab-btn:hover {
    color: var(--text);
  }

  .tab-btn.active {
    color: var(--forest);
    border-bottom-color: var(--forest);
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
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

  .num-col {
    text-align: right;
  }

  .num-cell {
    text-align: right;
    font-family: var(--font-mono);
  }

  .task-id-cell, .exp-id-cell {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    color: var(--text);
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  /* Integrity */
  .status-cell {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
  }

  .status-icon {
    font-weight: 700;
    font-size: 0.9rem;
  }

  .status-label {
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: lowercase;
  }

  .status-ok {
    color: var(--reward-good);
  }

  .status-warn {
    color: var(--reward-mid);
  }

  .status-error {
    color: var(--reward-zero);
  }

  .hash-cell {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-3);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }
</style>
