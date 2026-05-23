<!-- ABOUTME: Persistent left rail of experiments for the Runs page. -->
<!-- ABOUTME: Sorted most-recent-first, supports text filtering and collapse. -->
<script lang="ts">
  import type { ExperimentSummary } from "../lib/types";
  import RailItem from "./RailItem.svelte";
  import PanelLeftClose from "lucide-svelte/icons/panel-left-close";
  import PanelLeftOpen from "lucide-svelte/icons/panel-left-open";

  type Props = {
    experiments: ExperimentSummary[];
    activeExperimentId?: string;
    onSelect?: (experimentId: string) => void;
    onClear?: () => void;
  };
  let { experiments, activeExperimentId, onSelect, onClear }: Props = $props();

  let filterText = $state("");
  let collapsed = $state(false);

  // Restore collapsed state from localStorage on mount.
  $effect(() => {
    if (typeof window === "undefined") return;
    collapsed = window.localStorage.getItem("runs.rail.collapsed") === "true";
  });

  function toggleCollapse() {
    collapsed = !collapsed;
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("runs.rail.collapsed", String(collapsed));
    } catch {
      // Private-mode browsers may throw SecurityError; non-fatal.
    }
  }

  // Most-recent-first: assume experiment_id sorts lexicographically by date prefix
  // (today's convention is exp-YYYY-MM-DD-HHMM). Reverse-sort handles that.
  let sorted = $derived.by(() =>
    [...experiments].sort((a, b) => b.experiment_id.localeCompare(a.experiment_id)),
  );

  let filtered = $derived.by(() =>
    sorted.filter((e) => e.experiment_id.toLowerCase().includes(filterText.toLowerCase())),
  );
</script>

<aside class="rail" class:collapsed aria-label="Experiments">
  <header class="rail-header">
    {#if !collapsed}
      <input
        type="search"
        class="rail-filter"
        placeholder="Filter rail"
        bind:value={filterText}
        aria-label="Filter experiments rail"
      />
      {#if activeExperimentId}
        <button class="rail-clear" type="button" onclick={() => onClear?.()}>Clear</button>
      {/if}
    {/if}
    <button
      class="rail-toggle"
      type="button"
      onclick={toggleCollapse}
      aria-label={collapsed ? "Expand rail" : "Collapse rail"}
    >
      {#if collapsed}
        <PanelLeftOpen size={14} />
      {:else}
        <PanelLeftClose size={14} />
      {/if}
    </button>
  </header>

  {#if !collapsed}
    <div class="rail-list">
      {#each filtered as exp (exp.experiment_id)}
        <RailItem
          experiment={exp}
          active={exp.experiment_id === activeExperimentId}
          onSelect={(id) => onSelect?.(id)}
        />
      {/each}
      {#if filtered.length === 0}
        <p class="rail-empty">No experiments match.</p>
      {/if}
    </div>
  {/if}
</aside>

<style>
  .rail {
    width: 280px;
    flex-shrink: 0;
    border-right: 1px solid var(--card-border);
    background: var(--card);
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }
  .rail.collapsed {
    width: 48px;
  }
  .rail-header {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-sm);
    border-bottom: 1px solid var(--card-border);
  }
  .rail-filter {
    flex: 1;
    padding: var(--space-xs) var(--space-sm);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
  }
  .rail-clear,
  .rail-toggle {
    background: none;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    padding: var(--space-xs) var(--space-sm);
    cursor: pointer;
    font-size: 0.78rem;
  }
  .rail-list {
    overflow-y: auto;
    flex: 1;
  }
  .rail-empty {
    padding: var(--space-md);
    text-align: center;
    color: var(--text-3);
    font-size: 0.82rem;
  }
</style>
