<!-- ABOUTME: Visible chips for the active Runs filter; clicking × removes one key. -->
<!-- ABOUTME: Pure presentational — parent owns the filter state. -->
<script lang="ts">
  import type { RunsFilter } from "../lib/stores/runs.svelte";
  import X from "lucide-svelte/icons/x";

  type Props = {
    filter: RunsFilter;
    onRemove?: (key: keyof RunsFilter) => void;
  };
  let { filter, onRemove }: Props = $props();

  let entries = $derived.by(() => {
    const out: { key: keyof RunsFilter; label: string; value: string }[] = [];
    if (filter.experiment) out.push({ key: "experiment", label: "experiment", value: filter.experiment });
    if (filter.model) out.push({ key: "model", label: "model", value: filter.model });
    if (filter.adapter) out.push({ key: "adapter", label: "adapter", value: filter.adapter });
    if (filter.task_type) out.push({ key: "task_type", label: "task type", value: filter.task_type });
    if (filter.annotated !== undefined) out.push({ key: "annotated", label: "annotated", value: String(filter.annotated) });
    if (filter.reward_min !== undefined) out.push({ key: "reward_min", label: "reward ≥", value: filter.reward_min.toFixed(2) });
    if (filter.reward_max !== undefined) out.push({ key: "reward_max", label: "reward ≤", value: filter.reward_max.toFixed(2) });
    return out;
  });
</script>

{#if entries.length > 0}
  <div class="chip-row">
    {#each entries as e (e.key)}
      <span class="chip">
        <span class="chip-label">{e.label}:</span>
        <span class="chip-value">{e.value}</span>
        <button
          type="button"
          class="chip-x"
          aria-label={`remove ${e.label} filter`}
          onclick={() => onRemove?.(e.key)}
        ><X size={12} /></button>
      </span>
    {/each}
  </div>
{/if}

<style>
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    padding: var(--space-sm) var(--space-lg);
    background: var(--bg-alt);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    padding: 2px 8px;
    border: 1px solid var(--card-border);
    border-radius: 999px;
    background: var(--bg-alt);
    font-size: 0.78rem;
  }
  .chip-label {
    color: var(--text-3);
  }
  .chip-value {
    font-family: var(--font-mono);
    font-weight: 600;
  }
  .chip-x {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0 2px;
    color: var(--text-3);
  }
  .chip-x:hover {
    color: var(--text);
  }
</style>
