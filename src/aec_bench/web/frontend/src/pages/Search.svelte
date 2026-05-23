<!-- ABOUTME: Search page displaying template and dataset results for a given query string. -->
<!-- ABOUTME: Reads query from URL params on mount and fetches from /api/search. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchSearch } from "../lib/api";
  import type {
    DatasetSearchResult,
    ExperimentSearchResult,
    SearchData,
    TemplateSearchResult,
    TrialSearchResult,
    WorkspaceSearchResult,
  } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: SearchData | null = $state(null);
  let query: string = $state("");
  let error: string | null = $state(null);

  onMount(async () => {
    const params = new URLSearchParams(window.location.search);
    query = params.get("q") ?? "";
    try {
      data = await fetchSearch({ q: query });
    } catch (err) {
      error = err instanceof Error ? err.message : "Search failed.";
    }
  });

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function getTemplateId(result: TemplateSearchResult): string {
    const taskId = result.task_id ?? result.name ?? "unknown";
    // task_id is "discipline/template-name" — strip the discipline prefix for the URL
    const parts = taskId.split("/");
    return parts.length > 1 ? parts.slice(1).join("/") : taskId;
  }

  function getTemplateDiscipline(result: TemplateSearchResult): string {
    return result.discipline ?? "";
  }

  function datasetHref(result: DatasetSearchResult): string {
    return `/datasets/${encodeURIComponent(result.name)}/${encodeURIComponent(result.version)}`;
  }

  function experimentHref(result: ExperimentSearchResult): string {
    return `/?experiment=${encodeURIComponent(result.experiment_id)}`;
  }

  function workspaceHref(result: WorkspaceSearchResult): string {
    return `/evolution/${encodeURIComponent(result.path)}`;
  }

  function trialHref(result: TrialSearchResult): string {
    return `/viewer/${encodeURIComponent(result.experiment_id)}/${encodeURIComponent(result.trial_id)}`;
  }

  function formatReward(value: number): string {
    return value.toFixed(2);
  }
</script>

<section class="page-header">
  <h1>
    Search{query ? `: "${query}"` : ""}
  </h1>
  {#if data}
    <span class="result-count">{data.total_results} result{data.total_results !== 1 ? "s" : ""}</span>
  {/if}
</section>

{#if error}
  <Card>
    <div class="empty-state error-state">
      <p>Search could not load.</p>
      <p class="empty-hint">{error}</p>
    </div>
  </Card>
{:else if data === null}
  <div class="sections-list">
    <div class="skeleton-block">
      <Skeleton height="1.2rem" width="25%" />
      <Skeleton height="4rem" />
      <Skeleton height="4rem" />
    </div>
  </div>
{:else if data.total_results === 0}
  <Card>
    <div class="empty-state">
      <p>No results found{query ? ` for "${query}"` : ""}.</p>
      <p class="empty-hint">Try a different search term.</p>
    </div>
  </Card>
{:else}
  <div class="sections-list">
    {#if data.template_results.length > 0}
      <section class="results-section">
        <h2 class="section-heading">Templates ({data.template_results.length})</h2>
        <div class="results-list">
          {#each data.template_results as result, i (i)}
            {@const tid = getTemplateId(result)}
            {@const disc = getTemplateDiscipline(result)}
            <Card hoverable>
              <button
                class="result-item"
                onclick={() => navigate(`/library/${disc}/${tid}`)}
                type="button"
              >
                <div class="result-header">
                  <span class="result-id">{tid}</span>
                  {#if disc}
                    <span class="result-discipline">{disc}</span>
                  {/if}
                </div>
                {#if result.description}
                  <p class="result-desc">{result.description}</p>
                {/if}
                {#if result.tags && result.tags.length > 0}
                  <div class="tag-row">
                    {#each result.tags.slice(0, 5) as tag (tag)}
                      <Badge text={tag} />
                    {/each}
                  </div>
                {/if}
              </button>
            </Card>
          {/each}
        </div>
      </section>
    {/if}

    {#if data.dataset_results.length > 0}
      <section class="results-section">
        <h2 class="section-heading">Datasets ({data.dataset_results.length})</h2>
        <div class="results-list">
          {#each data.dataset_results as result, i (i)}
            <Card hoverable>
              <button
                class="result-item"
                onclick={() => navigate(datasetHref(result))}
                type="button"
              >
                <div class="result-header">
                  <span class="result-id">{result.name}</span>
                  <span class="result-version">v{result.version}</span>
                  <span class="result-version">{result.task_count} tasks</span>
                </div>
                {#if result.summary}
                  <p class="result-desc">{result.summary}</p>
                {/if}
                {#if result.domains && result.domains.length > 0}
                  <div class="tag-row">
                    {#each result.domains as domain (domain)}
                      <Badge text={domain} />
                    {/each}
                  </div>
                {/if}
              </button>
            </Card>
          {/each}
        </div>
      </section>
    {/if}

    {#if data.experiment_results.length > 0}
      <section class="results-section">
        <h2 class="section-heading">Experiments ({data.experiment_results.length})</h2>
        <div class="results-list">
          {#each data.experiment_results as result (result.experiment_id)}
            <Card hoverable>
              <button
                class="result-item"
                onclick={() => navigate(experimentHref(result))}
                type="button"
              >
                <div class="result-header">
                  <span class="result-id">{result.experiment_id}</span>
                  <span class="result-version">{result.trial_count} trials</span>
                  <span class="result-version">mean {formatReward(result.mean_reward)}</span>
                </div>
              </button>
            </Card>
          {/each}
        </div>
      </section>
    {/if}

    {#if data.workspace_results.length > 0}
      <section class="results-section">
        <h2 class="section-heading">Workspaces ({data.workspace_results.length})</h2>
        <div class="results-list">
          {#each data.workspace_results as result (result.path)}
            <Card hoverable>
              <button
                class="result-item"
                onclick={() => navigate(workspaceHref(result))}
                type="button"
              >
                <div class="result-header">
                  <span class="result-id">{result.name}</span>
                  {#if result.has_swarm}
                    <span class="result-discipline">swarm</span>
                  {/if}
                </div>
                <p class="result-desc">{result.path}</p>
              </button>
            </Card>
          {/each}
        </div>
      </section>
    {/if}

    {#if data.trial_results.length > 0}
      <section class="results-section">
        <h2 class="section-heading">Trials ({data.trial_results.length})</h2>
        <div class="results-list">
          {#each data.trial_results as result (result.experiment_id + result.trial_id)}
            <Card hoverable>
              <button
                class="result-item"
                onclick={() => navigate(trialHref(result))}
                type="button"
              >
                <div class="result-header">
                  <span class="result-id">{result.trial_id}</span>
                  <span class="result-version">{result.experiment_id}</span>
                  <span class="result-version">reward {formatReward(result.reward)}</span>
                </div>
                <p class="result-desc">{result.task_id} · {result.model}</p>
              </button>
            </Card>
          {/each}
        </div>
      </section>
    {/if}
  </div>
{/if}

<style>
  .page-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
    flex-wrap: wrap;
  }

  .page-header h1 {
    font-family: var(--font-heading);
    font-size: 1.75rem;
  }

  .result-count {
    font-size: 0.875rem;
    color: var(--text-3);
  }

  .sections-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-xl);
  }

  .results-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .section-heading {
    font-family: var(--font-heading);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding-bottom: var(--space-xs);
    border-bottom: 1px solid var(--card-border);
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .result-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .result-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-sm);
    flex-wrap: wrap;
  }

  .result-id {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--forest);
  }

  .result-discipline {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
    background: var(--bg-alt);
    border-radius: 9999px;
    padding: 1px 8px;
  }

  .result-version {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-3);
  }

  .result-desc {
    font-size: 0.875rem;
    color: var(--text-2);
    line-height: 1.5;
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
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

  .empty-hint {
    margin-top: var(--space-xs);
    font-size: 0.875rem;
  }

  .error-state p:first-child {
    color: var(--reward-zero);
    font-weight: 700;
  }
</style>
