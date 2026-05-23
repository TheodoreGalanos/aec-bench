<!-- ABOUTME: Evolution workspaces list page showing discovered workspace cards with cycle counts and scores. -->
<!-- ABOUTME: Fetches from /api/evolution/workspaces; each card links to the workspace explorer. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchEvolutionWorkspaces } from "../lib/api";
  import type { EvolutionWorkspacesData, EvolutionWorkspaceSummary } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import StatPill from "../lib/components/StatPill.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: EvolutionWorkspacesData | null = $state(null);

  onMount(async () => {
    data = await fetchEvolutionWorkspaces();
  });

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function workspaceHref(ws: EvolutionWorkspaceSummary): string {
    const base = `/evolution/${ws.path}`;
    return ws.run_id ? `${base}?run_id=${encodeURIComponent(ws.run_id)}` : base;
  }

  function scoreColor(score: number): string {
    if (score >= 0.8) return "var(--forest)";
    if (score >= 0.5) return "var(--reward-mid)";
    return "var(--reward-zero)";
  }
</script>

<section class="page-header">
  <h1>Evolution</h1>
  {#if data}
    <div class="summary-pills">
      <StatPill value={data.workspaces.length} label="runs" />
    </div>
  {/if}
</section>

{#if data === null}
  <div class="runs-grid">
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
{:else if data.workspaces.length === 0}
  <Card>
    <div class="empty-state">
      <p>No evolution workspaces found.</p>
      <p class="empty-hint">Run <code>aec-bench evolve init</code> to create one.</p>
    </div>
  </Card>
{:else}
  <div class="runs-grid">
    {#each data.workspaces as ws (`${ws.path}-${ws.run_id}`)}
      <Card hoverable>
        <button
          class="workspace-card"
          onclick={() => navigate(workspaceHref(ws))}
          type="button"
        >
          <div class="workspace-name">{ws.name}</div>
          <div class="card-header">
            <span class="run-label">{ws.run_id || "latest"}</span>
            <span class="strategy-pill" class:hill-climb={ws.strategy === "hill_climb"} class:qd={ws.strategy === "qd"}>
              {ws.strategy === "hill_climb" ? "hill climb" : ws.strategy}
            </span>
            {#if ws.has_swarm}
              <span class="swarm-badge">swarm</span>
            {/if}
          </div>

          <div class="score-blocks">
            <div class="score-block">
              <span class="score-value" style:color={scoreColor(ws.best_score)}>
                {ws.best_score.toFixed(2)}
              </span>
              <span class="score-label">Best</span>
            </div>
            <div class="score-block">
              <span class="score-value" style:color={scoreColor(ws.final_score)}>
                {ws.final_score.toFixed(2)}
              </span>
              <span class="score-label">Final</span>
            </div>
            <div class="score-block">
              <span class="score-value">{ws.cycles}</span>
              <span class="score-label">Cycles</span>
            </div>
          </div>

          <div class="card-footer">
            <Badge text={ws.model} />
          </div>
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
    font-size: 1.5rem;
  }

  .summary-pills {
    display: flex;
    gap: var(--space-sm);
    margin-left: auto;
  }

  .runs-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: var(--space-md);
  }

  .workspace-name {
    font-family: var(--font-heading);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: var(--space-xs);
    word-break: break-word;
  }

  .workspace-card {
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

  .run-label {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.88rem;
    color: var(--text);
  }

  .strategy-pill {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 9999px;
    white-space: nowrap;
    background: var(--bg-alt);
    color: var(--text-3);
  }

  .strategy-pill.hill-climb {
    background: var(--forest-light);
    color: var(--forest);
  }

  .strategy-pill.qd {
    background: rgba(97, 170, 242, 0.15);
    color: var(--reward-perfect);
  }

  .swarm-badge {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 9999px;
    background: rgba(137, 201, 37, 0.15);
    color: #89c925;
    text-transform: uppercase;
  }

  .score-blocks {
    display: flex;
    gap: var(--space-md);
    padding: var(--space-sm) 0;
  }

  .score-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .score-value {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 1.1rem;
    line-height: 1.2;
    color: var(--text);
  }

  .score-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    line-height: 1;
  }

  .card-footer {
    margin-top: auto;
    padding-top: var(--space-xs);
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
