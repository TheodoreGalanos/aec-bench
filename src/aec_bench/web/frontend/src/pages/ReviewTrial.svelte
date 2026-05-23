<!-- ABOUTME: Internal review page for a single trial, showing the review bundle data. -->
<!-- ABOUTME: Receives trialId as a prop and reads reviewer_id from URL query params. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReviewTrial } from "../lib/api";
  import type { ReviewTrialData } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";
  import DetailShell from "../lib/components/DetailShell.svelte";

  interface Props {
    trialId: string;
  }

  let { trialId }: Props = $props();

  let reviewerId = $state("");
  let data: ReviewTrialData | null = $state(null);
  let error: string | null = $state(null);

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    reviewerId = params.get("reviewer_id") ?? "";
    if (reviewerId) loadTrial();
  });

  async function loadTrial() {
    data = null;
    error = null;
    try {
      data = await fetchReviewTrial(trialId, { reviewer_id: reviewerId });
    } catch (err) {
      error = err instanceof Error ? err.message : "Review trial failed to load.";
    }
  }

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function backToQueue(): string {
    return reviewerId
      ? `/review/queue?reviewer_id=${reviewerId}`
      : "/review/queue";
  }

  function getBundleEntries(bundle: Record<string, any>): Array<[string, any]> {
    return Object.entries(bundle);
  }

  function formatValue(value: any): string {
    if (typeof value === "object" && value !== null) {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  }

  function isObject(value: any): boolean {
    return typeof value === "object" && value !== null;
  }

  function nestedValue(source: Record<string, any>, path: string): any {
    return path.split(".").reduce((value, key) => value?.[key], source);
  }
</script>

<DetailShell
  backHref={backToQueue()}
  backLabel="Review Queue"
  title={`Trial: ${trialId}`}
  subtitle={reviewerId ? `Reviewer: ${reviewerId}` : undefined}
>
  {#if !reviewerId}
    <Card>
      <div class="empty-state">
        <p>No reviewer ID provided.</p>
        <p class="empty-hint">
          <button
            class="queue-link"
            onclick={() => navigate("/review/queue")}
            type="button"
          >
            Go to Review Queue
          </button>
          to set your reviewer ID.
        </p>
      </div>
    </Card>
  {:else if error}
    <Card>
      <div class="empty-state error-state">
        <p>Review trial could not load.</p>
        <p class="empty-hint">{error}</p>
      </div>
    </Card>
  {:else if data === null}
    <div class="bundle-sections">
      {#each [1, 2] as _}
        <Card>
          <div class="skeleton-block">
            <Skeleton height="0.9rem" width="25%" />
            <Skeleton height="5rem" />
          </div>
        </Card>
      {/each}
    </div>
  {:else}
    {@const entries = getBundleEntries(data.bundle)}
    {#if entries.length === 0}
      <Card>
        <div class="empty-state">
          <p>No review bundle data available for this trial.</p>
        </div>
      </Card>
    {:else}
      <Card>
        <div class="summary-grid">
          <div>
            <span class="summary-label">Experiment</span>
            <strong>{nestedValue(data.bundle, "trial.experiment_id") ?? "unknown"}</strong>
          </div>
          <div>
            <span class="summary-label">Task</span>
            <strong>{nestedValue(data.bundle, "trial.task.task_id") ?? "unknown"}</strong>
          </div>
          <div>
            <span class="summary-label">Model</span>
            <strong>{nestedValue(data.bundle, "trial.agent.model") ?? "unknown"}</strong>
          </div>
          <div>
            <span class="summary-label">Reward</span>
            <strong>{nestedValue(data.bundle, "trial.evaluation.reward") ?? "unknown"}</strong>
          </div>
        </div>
      </Card>
      <div class="bundle-sections">
        {#each entries as [key, value] (key)}
          <Card>
            <div class="bundle-section">
              <h2 class="section-key">{key}</h2>
              {#if isObject(value)}
                <pre class="bundle-value">{formatValue(value)}</pre>
              {:else}
                <p class="bundle-scalar">{formatValue(value)}</p>
              {/if}
            </div>
          </Card>
        {/each}
      </div>
    {/if}
  {/if}
</DetailShell>

<style>
  .bundle-sections {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-md);
  }

  .summary-grid div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .summary-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-3);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .summary-grid strong {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: var(--text);
    overflow-wrap: anywhere;
  }

  .bundle-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .section-key {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    padding-bottom: var(--space-xs);
    border-bottom: 1px solid var(--card-border);
  }

  .bundle-value {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    line-height: 1.6;
    color: var(--text-2);
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
    background: var(--bg-alt);
    border-radius: var(--radius-sm);
    padding: var(--space-sm);
  }

  .bundle-scalar {
    font-size: 0.9rem;
    color: var(--text);
    line-height: 1.5;
  }

  .skeleton-block {
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

  .queue-link {
    color: var(--forest);
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
    font-weight: 500;
  }

  .queue-link:hover {
    text-decoration: underline;
  }

  .error-state p:first-child {
    color: var(--reward-zero);
    font-weight: 700;
  }
</style>
