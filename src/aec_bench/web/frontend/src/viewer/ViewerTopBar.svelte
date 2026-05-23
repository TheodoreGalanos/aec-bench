<!-- ABOUTME: Sticky top navigation bar for the viewer page with trial title, experiment ID, and prev/next links. -->
<!-- ABOUTME: Provides a back link to the originating page and arrow navigation between sibling trials. -->
<script lang="ts">
  interface Props {
    experimentId: string;
    trialId: string;
    backUrl: string;
    prevTrial: string | null;
    nextTrial: string | null;
    hasTrajectory?: boolean;
    onreplay?: () => void;
  }

  let {
    experimentId,
    trialId,
    backUrl,
    prevTrial,
    nextTrial,
    hasTrajectory = false,
    onreplay = () => {},
  }: Props = $props();

  function navigate(url: string) {
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
</script>

<div class="viewer-topbar" data-testid="viewer-topbar">
  <div class="topbar-left">
    <a
      class="back-link"
      href={backUrl}
      onclick={(e) => { e.preventDefault(); navigate(backUrl); }}
    >
      &larr; Back
    </a>
  </div>

  <div class="topbar-center">
    <span class="trial-title" data-testid="trial-title">{trialId}</span>
    <span class="trial-meta">{experimentId}</span>
  </div>

  <div class="topbar-right">
    {#if hasTrajectory}
      <button class="replay-btn" onclick={onreplay} title="Replay trajectory">
        ▶ Replay
      </button>
    {/if}

    {#if prevTrial}
      <a
        class="nav-arrow"
        href={`/viewer/${experimentId}/${prevTrial}`}
        onclick={(e) => { e.preventDefault(); navigate(`/viewer/${experimentId}/${prevTrial}`); }}
        aria-label="Previous trial"
        data-testid="prev-trial"
      >
        &larr; Prev
      </a>
    {:else}
      <span class="nav-arrow disabled" aria-label="No previous trial">&larr; Prev</span>
    {/if}

    {#if nextTrial}
      <a
        class="nav-arrow"
        href={`/viewer/${experimentId}/${nextTrial}`}
        onclick={(e) => { e.preventDefault(); navigate(`/viewer/${experimentId}/${nextTrial}`); }}
        aria-label="Next trial"
        data-testid="next-trial"
      >
        Next &rarr;
      </a>
    {:else}
      <span class="nav-arrow disabled" aria-label="No next trial">Next &rarr;</span>
    {/if}
  </div>
</div>

<style>
  .viewer-topbar {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--card);
    border-bottom: 1px solid var(--card-border);
    padding: 12px var(--space-lg);
    min-height: 48px;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .topbar-left {
    flex: 0 0 auto;
  }

  .back-link {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--forest);
    text-decoration: none;
    transition: color var(--transition-fast);
  }

  .back-link:hover {
    color: var(--forest-hover);
  }

  .back-link:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .topbar-center {
    flex: 1 1 auto;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .trial-title {
    font-family: var(--font-heading);
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
  }

  .trial-meta {
    font-size: 0.8rem;
    color: var(--text-2);
  }

  .topbar-right {
    flex: 0 0 auto;
    display: flex;
    gap: 6px;
    margin-left: auto;
  }

  .nav-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-xs) 10px;
    border-radius: var(--radius-sm);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--forest);
    background: var(--forest-light);
    text-decoration: none;
    transition: background var(--transition-fast), color var(--transition-fast);
    cursor: pointer;
  }

  .nav-arrow:hover {
    background: var(--forest);
    color: #fff;
  }

  .nav-arrow:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
  }

  .replay-btn {
    background: transparent;
    color: var(--forest);
    border: 1px solid var(--forest);
    padding: 4px 12px;
    border-radius: var(--radius-sm);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .replay-btn:hover {
    background: var(--forest);
    color: white;
  }

  .nav-arrow.disabled {
    color: var(--text-3);
    background: var(--bg-alt);
    cursor: default;
    pointer-events: none;
    opacity: 0.4;
  }
</style>
