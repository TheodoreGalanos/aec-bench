<!-- ABOUTME: Single experiment card in the Runs experiments rail. -->
<!-- ABOUTME: Click selects this experiment as the active filter; renders as <a> for ⌘-click semantics. -->
<script lang="ts">
  import type { ExperimentSummary } from "../lib/types";
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import { modelColour } from "../lib/model-colour";

  type Props = {
    experiment: ExperimentSummary;
    active?: boolean;
    onSelect?: (experimentId: string) => void;
  };
  let { experiment, active = false, onSelect }: Props = $props();

  function handleClick(e: MouseEvent) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; // let browser handle ⌘-click / middle-click
    e.preventDefault();
    onSelect?.(experiment.experiment_id);
  }
</script>

<a
  href={`/?experiment=${encodeURIComponent(experiment.experiment_id)}`}
  class="rail-item"
  class:active
  aria-current={active ? "page" : undefined}
  onclick={handleClick}
>
  <div class="rail-item-header">
    <span class="exp-id">{experiment.experiment_id}</span>
    {#if experiment.adapters.includes("rlm")}
      <Badge text="RLM" variant="rlm" />
    {/if}
  </div>
  <div class="rail-item-meta">
    <span class="trial-count">n={experiment.trial_count}</span>
    <RewardBadge reward={experiment.mean_reward} size="sm" />
  </div>
  {#if experiment.models.length > 0}
    <div class="rail-item-models">
      {#each experiment.models as model (model)}
        <Badge text={model} variant="model" colour={modelColour(model)} />
      {/each}
    </div>
  {/if}
</a>

<style>
  .rail-item {
    display: block;
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    text-decoration: none;
    color: inherit;
    cursor: pointer;
    transition: background var(--transition-fast);
  }
  .rail-item:hover {
    background: var(--bg-alt);
  }
  .rail-item.active {
    background: var(--bg-active, var(--bg-alt));
    border-left: 3px solid var(--forest);
    padding-left: calc(var(--space-md) - 3px);
  }
  .rail-item-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-xs);
    margin-bottom: var(--space-xs);
  }
  .exp-id {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rail-item-meta {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-size: 0.75rem;
    color: var(--text-3);
  }
  .rail-item-models {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-top: var(--space-xs);
  }
</style>
