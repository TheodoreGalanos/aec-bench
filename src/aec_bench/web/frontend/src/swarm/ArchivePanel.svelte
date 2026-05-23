<!-- ABOUTME: Container panel managing view mode, colour mode, tooltip, and legend for the QD archive. -->
<!-- ABOUTME: Renders ArchiveScatter, ArchiveTerritory, or ArchiveTrend based on user selection with smart defaults. -->
<script lang="ts">
  import type { SwarmCentroid } from "../lib/types";
  import ArchiveScatter from "./ArchiveScatter.svelte";
  import ArchiveTerritory from "./ArchiveTerritory.svelte";
  import ArchiveTrend from "./ArchiveTrend.svelte";

  interface Props {
    centroids: SwarmCentroid[];
    agentColors: Record<string, string>;
    selectedAgentId: string | null;
  }

  let { centroids, agentColors, selectedAgentId }: Props = $props();

  // --- State ---

  type ArchiveViewMode = "scatter" | "territory" | "trend";
  type ColourMode = "agent" | "reward";

  let viewMode: ArchiveViewMode = $state("scatter");
  let colourMode: ColourMode = $state("agent");

  // Tracks whether the user has manually selected a view mode
  let userOverride = $state(false);

  // --- Smart default: switch to territory when occupancy >= 20% ---

  $effect(() => {
    if (userOverride || centroids.length === 0) return;
    const occupied = centroids.filter((c) => c.occupied).length;
    const occupancyPct = occupied / centroids.length;
    viewMode = occupancyPct >= 0.2 ? "territory" : "scatter";
  });

  function setViewMode(mode: ArchiveViewMode): void {
    userOverride = true;
    viewMode = mode;
  }

  // --- Tooltip state (owned by panel, passed to children) ---

  let hoveredCentroid: SwarmCentroid | null = $state(null);
  let tooltipX: number = $state(0);
  let tooltipY: number = $state(0);

  function handleHover(centroid: SwarmCentroid | null, x: number, y: number): void {
    hoveredCentroid = centroid;
    tooltipX = x;
    tooltipY = y;
  }

  function handleClick(centroid: SwarmCentroid): void {
    // Future: could dispatch a selection event to the parent page
    void centroid;
  }

  // --- Legend data ---

  let agentCellCounts = $derived.by((): { agentId: string; color: string; count: number }[] => {
    const counts = new Map<string, number>();
    for (const c of centroids) {
      if (c.occupied && c.agent_id) {
        counts.set(c.agent_id, (counts.get(c.agent_id) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .map(([agentId, count]) => ({
        agentId,
        color: agentColors[agentId] ?? "var(--text-3)",
        count,
      }))
      .sort((a, b) => b.count - a.count);
  });

  let emptyCount = $derived(centroids.filter((c) => !c.occupied).length);

  let bestCentroid = $derived.by((): SwarmCentroid | null => {
    let best: SwarmCentroid | null = null;
    let bestReward = -1;
    let bestCost = Infinity;
    for (const c of centroids) {
      if (!c.occupied) continue;
      const reward = c.reward ?? 0;
      const cost = c.token_cost ?? Infinity;
      if (reward > bestReward || (reward === bestReward && cost < bestCost)) {
        best = c;
        bestReward = reward;
        bestCost = cost;
      }
    }
    return best;
  });
</script>

<div class="archive-panel">
  <div class="archive-header">
    <div class="toggle-group">
      <div class="view-toggle">
        <button class:active={viewMode === "scatter"} onclick={() => setViewMode("scatter")}>
          Scatter
        </button>
        <button class:active={viewMode === "territory"} onclick={() => setViewMode("territory")}>
          Territory
        </button>
        <button class:active={viewMode === "trend"} onclick={() => setViewMode("trend")}>
          Trend
        </button>
      </div>
      {#if viewMode !== "trend"}
        <div class="view-toggle">
          <button class:active={colourMode === "agent"} onclick={() => (colourMode = "agent")}>
            Agent
          </button>
          <button class:active={colourMode === "reward"} onclick={() => (colourMode = "reward")}>
            Reward
          </button>
        </div>
      {/if}
    </div>
  </div>

  <div class="archive-content">
    {#if viewMode === "scatter"}
      <ArchiveScatter
        {centroids}
        {agentColors}
        {colourMode}
        {selectedAgentId}
        onCentroidHover={handleHover}
        onCentroidClick={handleClick}
      />
    {:else if viewMode === "territory"}
      <ArchiveTerritory
        {centroids}
        {agentColors}
        {colourMode}
        {selectedAgentId}
        onCentroidHover={handleHover}
        onCentroidClick={handleClick}
      />
    {:else}
      <ArchiveTrend {centroids} {agentColors} {selectedAgentId} />
    {/if}
  </div>

  {#if viewMode !== "trend"}
  <div class="archive-legend">
    {#if colourMode === "reward"}
      <!-- Reward-mode legend -->
      <span class="legend-item">
        <span class="legend-swatch" style:background="var(--reward-perfect)"></span>
        perfect
      </span>
      <span class="legend-item">
        <span class="legend-swatch" style:background="var(--reward-mid)"></span>
        mid
      </span>
      <span class="legend-item">
        <span class="legend-swatch" style:background="var(--reward-zero)"></span>
        zero
      </span>
    {:else}
      <!-- Agent-mode legend (also used for trend view) -->
      {#each agentCellCounts as entry}
        <span class="legend-item">
          <span class="legend-swatch" style:background={entry.color}></span>
          {entry.agentId} ({entry.count})
        </span>
      {/each}
      <span class="legend-item">
        <span class="legend-swatch empty-swatch"></span>
        empty ({emptyCount})
      </span>
      {#if bestCentroid}
        <span class="legend-item"><span class="legend-star">&#9733;</span> best</span>
      {/if}
    {/if}
  </div>
  {/if}

  <!-- Tooltip overlay (fixed position, from child mouse coordinates) -->
  {#if hoveredCentroid}
    <div class="centroid-tooltip" style="left: {tooltipX + 12}px; top: {tooltipY - 10}px;">
      <div class="tt-version">{hoveredCentroid.version}</div>
      <div class="tt-row">Reward: {(hoveredCentroid.reward ?? 0).toFixed(3)}</div>
      {#if hoveredCentroid.agent_id}
        <div class="tt-row">Agent: {hoveredCentroid.agent_id}</div>
      {/if}
      <div class="tt-row">Tokens: {(hoveredCentroid.token_cost ?? 0).toFixed(2)}</div>
    </div>
  {/if}
</div>

<style>
  .archive-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    position: relative;
  }

  .archive-header {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: var(--space-xs) var(--space-md);
    flex-shrink: 0;
  }

  .toggle-group {
    display: flex;
    gap: var(--space-sm);
  }

  .view-toggle {
    display: flex;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .view-toggle button {
    background: var(--card);
    border: none;
    padding: 3px 10px;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-3);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .view-toggle button.active {
    background: var(--forest);
    color: white;
  }

  .archive-content {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .archive-legend {
    display: flex;
    gap: var(--space-md);
    padding: var(--space-xs) var(--space-md);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--text-2);
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .legend-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
  }

  .empty-swatch {
    border: 1px solid var(--card-border);
    background: transparent;
  }

  .legend-star {
    color: gold;
    font-size: 0.85rem;
  }

  .centroid-tooltip {
    position: fixed;
    background: var(--card);
    color: var(--text);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    pointer-events: none;
    white-space: nowrap;
    z-index: 100;
    border: 1px solid var(--card-border);
    box-shadow: var(--shadow-md);
  }

  .tt-version {
    font-weight: 700;
    margin-bottom: 2px;
  }

  .tt-row {
    opacity: 0.85;
  }
</style>
