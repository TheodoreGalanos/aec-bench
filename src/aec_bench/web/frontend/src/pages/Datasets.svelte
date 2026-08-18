<!-- ABOUTME: Lists semantic datasets with task counts and human publication labels. -->
<!-- ABOUTME: Links published datasets by label without showing routine integrity hashes. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchDatasetsList } from "../lib/api";
  import type { DatasetsListData, DatasetListItem } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import StatPill from "../lib/components/StatPill.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: DatasetsListData | null = $state(null);

  onMount(async () => {
    data = await fetchDatasetsList();
  });

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function datasetHref(ds: DatasetListItem): string {
    return ds.labels.length > 0 ? `/datasets/${ds.dataset_id}/${ds.labels[0]}` : "/datasets";
  }
</script>

<section class="page-header">
  <h1>Datasets</h1>
  {#if data}
    <div class="summary-pills">
      <StatPill value={data.total_datasets} label="datasets" />
      <StatPill value={data.total_tasks} label="tasks" />
    </div>
  {/if}
</section>

{#if data === null}
  <div class="cards-grid">
    {#each [1, 2, 3] as _}
      <Card>
        <div class="skeleton-card">
          <Skeleton height="1.2rem" width="60%" />
          <Skeleton height="1rem" width="80%" />
          <Skeleton height="1rem" width="40%" />
        </div>
      </Card>
    {/each}
  </div>
{:else if data.datasets.length === 0}
  <Card>
    <div class="empty-state">
      <p>No datasets available.</p>
      <p class="empty-hint">Run <code>aec-bench dataset create</code> to build one.</p>
    </div>
  </Card>
{:else}
  <div class="cards-grid">
    {#each data.datasets as ds (ds.dataset_id)}
      <Card hoverable>
        <button
          class="dataset-card"
          onclick={() => ds.labels.length > 0 && navigate(datasetHref(ds))}
          type="button"
        >
          <div class="card-header">
            <span class="ds-name">{ds.dataset_id}</span>
            <span class="ds-label">{ds.labels[0] ?? "draft"}</span>
          </div>

          {#if ds.description}
            <p class="ds-summary">{ds.description}</p>
          {/if}

          <div class="card-meta">
            <span class="task-count">{ds.task_count} tasks</span>
          </div>

          {#if ds.labels.length > 1}
            <div class="domain-badges">
              {#each ds.labels.slice(1) as label (label)}
                <Badge text={label} />
              {/each}
            </div>
          {/if}
        </button>
      </Card>
    {/each}
  </div>
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

  .summary-pills {
    display: flex;
    gap: var(--space-sm);
    margin-left: auto;
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-md);
  }

  .dataset-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .card-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-sm);
    flex-wrap: wrap;
  }

  .ds-name {
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 1rem;
    color: var(--text);
  }

  .ds-label {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--text-3);
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    padding: 1px 6px;
  }

  .ds-summary {
    font-size: 0.875rem;
    color: var(--text-2);
    line-height: 1.5;
    flex: 1;
  }

  .card-meta {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .task-count {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--forest);
  }

  .domain-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .skeleton-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }

  .empty-hint {
    margin-top: var(--space-xs);
    font-size: 0.875rem;
  }

  .empty-hint code {
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 1px var(--space-xs);
    border-radius: var(--radius-sm);
  }
</style>
