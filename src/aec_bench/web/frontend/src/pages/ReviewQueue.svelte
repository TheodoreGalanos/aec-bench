<!-- ABOUTME: Internal reviewer assignment queue page showing pending review tasks. -->
<!-- ABOUTME: Reads reviewer_id from URL params; fetches from /api/review/queue with reviewer_id query param. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReviewQueue } from "../lib/api";
  import type { ReviewAssignment, ReviewQueueData } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: ReviewQueueData | null = $state(null);
  let reviewerId = $state("");
  let inputValue = $state("");
  let error: string | null = $state(null);

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    reviewerId = params.get("reviewer_id") ?? "";
    if (reviewerId) {
      inputValue = reviewerId;
      loadQueue();
    }
  });

  async function loadQueue() {
    data = null;
    error = null;
    try {
      data = await fetchReviewQueue({ reviewer_id: reviewerId });
    } catch (err) {
      error = err instanceof Error ? err.message : "Review queue failed to load.";
    }
  }

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function submitReviewerId() {
    if (!inputValue.trim()) return;
    reviewerId = inputValue.trim();
    const url = new URL(window.location.href);
    url.searchParams.set("reviewer_id", reviewerId);
    history.pushState({}, "", url.toString());
    loadQueue();
  }

  function getAssignments(assignments: ReviewQueueData | null): ReviewAssignment[] {
    return assignments?.assignments.assignments ?? [];
  }
</script>

<section class="page-header">
  <h1>Review Queue</h1>
  {#if reviewerId}
    <span class="reviewer-id">Reviewer: <code>{reviewerId}</code></span>
  {/if}
</section>

{#if !reviewerId}
  <Card>
    <div class="reviewer-prompt">
      <p>Enter your reviewer ID to load your assignment queue.</p>
      <form class="reviewer-form" onsubmit={(e) => { e.preventDefault(); submitReviewerId(); }}>
        <input
          type="text"
          class="reviewer-input"
          placeholder="Reviewer ID"
          bind:value={inputValue}
          aria-label="Reviewer ID"
        />
        <button type="submit" class="submit-btn">Load Queue</button>
      </form>
    </div>
  </Card>
{:else if error}
  <Card>
    <div class="empty-state error-state">
      <p>Review queue could not load.</p>
      <p class="empty-hint">{error}</p>
    </div>
  </Card>
{:else if data === null}
  <div class="assignments-list">
    {#each [1, 2, 3] as _}
      <Card>
        <div class="skeleton-row">
          <Skeleton height="1rem" width="40%" />
          <Skeleton height="0.85rem" width="70%" />
        </div>
      </Card>
    {/each}
  </div>
{:else}
  {@const assignments = getAssignments(data)}
  {#if assignments.length === 0}
    <Card>
      <div class="empty-state">
        <p>No assignments in your queue.</p>
        <p class="empty-hint">Check back later or contact your review coordinator.</p>
      </div>
    </Card>
  {:else}
    <div class="assignments-list">
      {#each assignments as assignment (assignment.assignment_id)}
        <Card hoverable>
          <button
            class="assignment-row"
            onclick={() => navigate(`/review/trials/${assignment.trial_id}?reviewer_id=${reviewerId}`)}
            type="button"
          >
            <div class="assignment-header">
              <span class="trial-id">{assignment.trial_id}</span>
              <span class="status-badge">{assignment.task_visibility}</span>
              {#if assignment.is_calibration}
                <span class="status-badge">calibration</span>
              {/if}
            </div>
            <p class="task-id">{assignment.task_id}</p>
            <p class="assignment-reason">{assignment.assignment_reason}</p>
          </button>
        </Card>
      {/each}
    </div>
  {/if}
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

  .reviewer-id {
    font-size: 0.875rem;
    color: var(--text-3);
  }

  .reviewer-id code {
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 1px var(--space-xs);
    border-radius: var(--radius-sm);
    color: var(--forest);
  }

  .reviewer-prompt {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    align-items: flex-start;
    padding: var(--space-sm) 0;
  }

  .reviewer-prompt p {
    color: var(--text-2);
    font-size: 0.925rem;
  }

  .reviewer-form {
    display: flex;
    gap: var(--space-sm);
    align-items: center;
    flex-wrap: wrap;
  }

  .reviewer-input {
    font-family: var(--font-mono);
    font-size: 0.9rem;
    padding: var(--space-xs) var(--space-sm);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    background: var(--bg-alt);
    color: var(--text);
    min-width: 240px;
  }

  .reviewer-input:focus {
    outline: none;
    border-color: var(--forest);
  }

  .submit-btn {
    font-size: 0.875rem;
    font-weight: 600;
    padding: var(--space-xs) var(--space-md);
    background: var(--forest);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .submit-btn:hover {
    opacity: 0.88;
  }

  .assignments-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .assignment-row {
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

  .assignment-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-sm);
    flex-wrap: wrap;
  }

  .trial-id {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--forest);
  }

  .status-badge {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
    background: var(--bg-alt);
    border-radius: 9999px;
    padding: 1px 8px;
  }

  .task-id {
    font-size: 0.85rem;
    color: var(--text-2);
    font-family: var(--font-mono);
  }

  .assignment-reason {
    font-size: 0.82rem;
    color: var(--text-3);
  }

  .skeleton-row {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
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
