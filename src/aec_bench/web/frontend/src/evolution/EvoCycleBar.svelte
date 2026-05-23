<!-- ABOUTME: Horizontal bar with cycle selector pills, inline SVG score sparkline, and stat pills. -->
<!-- ABOUTME: Sits below the NavBar in the evolution workspace explorer, drives version selection. -->
<script lang="ts">
  import type { EvolutionCycle } from "../lib/types";
  import StatPill from "../lib/components/StatPill.svelte";

  interface Props {
    cycles: EvolutionCycle[];
    activeCycle: number;
    workspaceName: string;
    model: string;
    onselect: (cycle: number) => void;
  }

  let { cycles, activeCycle, workspaceName, model, onselect }: Props = $props();

  // Derive the active cycle data (null for baseline evo-0)
  let activeCycleData = $derived(
    cycles.find((c) => c.cycle === activeCycle) ?? null
  );

  // Count of skill changes for the active cycle
  let skillsCount = $derived.by(() => {
    if (!activeCycleData) return 0;
    return (
      activeCycleData.skills_added.length +
      activeCycleData.skills_modified.length +
      activeCycleData.skills_removed.length
    );
  });

  // Count of total changes (skill diffs) for the active cycle
  let changesCount = $derived.by(() => {
    if (!activeCycleData) return 0;
    return Object.keys(activeCycleData.skill_diffs).length;
  });

  // Generate sparkline path from cycle scores
  let sparklinePath = $derived.by(() => {
    if (cycles.length === 0) return "";
    const width = 100;
    const height = 24;
    const padding = 2;
    const scores = cycles.map((c) => c.score);
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    const range = maxScore - minScore || 1;
    const stepX = cycles.length > 1 ? (width - padding * 2) / (cycles.length - 1) : 0;

    const points = scores.map((score, i) => {
      const x = padding + i * stepX;
      const y = height - padding - ((score - minScore) / range) * (height - padding * 2);
      return `${x},${y}`;
    });

    return `M${points.join(" L")}`;
  });

  // Dot positions for sparkline
  let sparklineDots = $derived.by(() => {
    if (cycles.length === 0) return [];
    const width = 100;
    const height = 24;
    const padding = 2;
    const scores = cycles.map((c) => c.score);
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    const range = maxScore - minScore || 1;
    const stepX = cycles.length > 1 ? (width - padding * 2) / (cycles.length - 1) : 0;

    return scores.map((score, i) => ({
      cx: padding + i * stepX,
      cy: height - padding - ((score - minScore) / range) * (height - padding * 2),
      cycle: cycles[i].cycle,
    }));
  });
</script>

<div class="cycle-bar" data-testid="evo-cycle-bar">
  <!-- Left section: workspace name + model -->
  <div class="bar-left">
    <span class="ws-name">{workspaceName}</span>
    <span class="model-tag">{model}</span>
  </div>

  <!-- Center: cycle pills + sparkline -->
  <div class="bar-center">
    <div class="cycle-pills" role="tablist" aria-label="Evolution cycles">
      <button
        class="cycle-pill"
        class:active={activeCycle === 0}
        role="tab"
        aria-selected={activeCycle === 0}
        onclick={() => onselect(0)}
      >
        evo-0
      </button>
      {#each cycles as cycle (cycle.cycle)}
        <button
          class="cycle-pill"
          class:active={activeCycle === cycle.cycle}
          role="tab"
          aria-selected={activeCycle === cycle.cycle}
          onclick={() => onselect(cycle.cycle)}
        >
          evo-{cycle.cycle}
        </button>
      {/each}
    </div>

    {#if cycles.length > 1}
      <svg
        class="sparkline"
        viewBox="0 0 100 24"
        preserveAspectRatio="none"
        aria-label="Score trend across cycles"
      >
        <path d={sparklinePath} fill="none" stroke="var(--forest)" stroke-width="1.5" />
        {#each sparklineDots as dot (dot.cycle)}
          <circle
            cx={dot.cx}
            cy={dot.cy}
            r={dot.cycle === activeCycle ? 3 : 1.5}
            fill={dot.cycle === activeCycle ? "var(--forest)" : "var(--text-3)"}
          />
        {/each}
      </svg>
    {/if}
  </div>

  <!-- Right: stat pills for active cycle -->
  <div class="bar-right">
    {#if activeCycleData}
      <StatPill value={activeCycleData.score.toFixed(2)} label="score" />
      <StatPill value={skillsCount} label="skills" />
      <StatPill value={changesCount} label="changes" />
    {:else}
      <StatPill value="--" label="baseline" />
    {/if}
  </div>
</div>

<style>
  .cycle-bar {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-xs) var(--space-lg);
    background: var(--bg-alt);
    border-bottom: 1px solid var(--card-border);
    flex-shrink: 0;
    min-height: 44px;
    overflow-x: auto;
  }

  .bar-left {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    flex-shrink: 0;
  }

  .ws-name {
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--text);
    white-space: nowrap;
  }

  .model-tag {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px var(--space-sm);
    border-radius: 9999px;
    background: var(--forest-light);
    color: var(--forest);
    white-space: nowrap;
  }

  .bar-center {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    flex: 1;
    justify-content: center;
    min-width: 0;
  }

  .cycle-pills {
    display: flex;
    gap: var(--space-xs);
    overflow-x: auto;
    flex-shrink: 0;
  }

  .cycle-pill {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    padding: var(--space-xs) var(--space-sm);
    border-radius: 9999px;
    border: 1px solid var(--card-border);
    background: var(--card);
    color: var(--text-2);
    cursor: pointer;
    white-space: nowrap;
    transition: all var(--transition-fast);
  }

  .cycle-pill:hover {
    border-color: var(--forest);
    color: var(--forest);
  }

  .cycle-pill.active {
    background: var(--forest);
    color: white;
    border-color: var(--forest);
  }

  .sparkline {
    width: 100px;
    height: 24px;
    flex-shrink: 0;
  }

  .bar-right {
    display: flex;
    gap: var(--space-xs);
    flex-shrink: 0;
  }

  /* Scale down StatPill inside the bar for compactness */
  .bar-right :global(.stat-pill) {
    padding: 2px var(--space-sm);
  }

  .bar-right :global(.stat-value) {
    font-size: 0.82rem;
  }

  .bar-right :global(.stat-label) {
    font-size: 0.6rem;
  }
</style>
