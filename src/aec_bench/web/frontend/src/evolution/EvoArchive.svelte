<!-- ABOUTME: Collapsible QD archive scatter plot showing MAP-Elites coverage in 2D PCA space. -->
<!-- ABOUTME: Points coloured by reward, with hover tooltips showing version and discipline. -->
<script lang="ts">
  import type { ArchiveData, ArchivePoint } from "../lib/types";

  interface Props {
    data: ArchiveData;
  }

  let { data }: Props = $props();
  let expanded: boolean = $state(true);
  let hoveredPoint: ArchivePoint | null = $state(null);
  let tooltipX: number = $state(0);
  let tooltipY: number = $state(0);

  const WIDTH = 400;
  const HEIGHT = 280;
  const PADDING = 40;

  // Scale points to SVG coordinates
  function scaleX(x: number): number {
    if (data.points_2d.length < 2) return WIDTH / 2;
    const xs = data.points_2d.map(p => p.x);
    const min = Math.min(...xs);
    const max = Math.max(...xs);
    const range = max - min || 1;
    return PADDING + ((x - min) / range) * (WIDTH - 2 * PADDING);
  }

  function scaleY(y: number): number {
    if (data.points_2d.length < 2) return HEIGHT / 2;
    const ys = data.points_2d.map(p => p.y);
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const range = max - min || 1;
    return HEIGHT - PADDING - ((y - min) / range) * (HEIGHT - 2 * PADDING);
  }

  function rewardColor(reward: number): string {
    if (reward >= 0.8) return "var(--reward-perfect)";
    if (reward >= 0.5) return "var(--reward-mid)";
    return "var(--reward-zero)";
  }

  function handleMouseEnter(point: ArchivePoint, event: MouseEvent) {
    hoveredPoint = point;
    const rect = (event.currentTarget as SVGElement).closest("svg")?.getBoundingClientRect();
    if (rect) {
      tooltipX = event.clientX - rect.left;
      tooltipY = event.clientY - rect.top - 40;
    }
  }

  function handleMouseLeave() {
    hoveredPoint = null;
  }
</script>

{#if data.summary.size > 0}
  <div class="archive-panel">
    <button class="archive-header" onclick={() => expanded = !expanded}>
      <span class="archive-title">
        QD Archive
        <span class="archive-count">{data.summary.size}</span>
        <span class="archive-coverage">{(data.summary.coverage * 100).toFixed(1)}% coverage</span>
      </span>
      <span class="chevron" class:open={expanded}>&#9656;</span>
    </button>

    {#if expanded}
      <div class="archive-content">
        <div class="archive-stats">
          <span class="stat">Best: <strong>{data.summary.best_reward.toFixed(2)}</strong></span>
          <span class="stat">Mean: <strong>{data.summary.mean_reward.toFixed(2)}</strong></span>
          <span class="stat">Disciplines: <strong>{data.summary.disciplines.join(", ")}</strong></span>
        </div>

        <div class="scatter-container">
          <svg viewBox="0 0 {WIDTH} {HEIGHT}" class="scatter-svg">
            <!-- Axes -->
            <line x1={PADDING} y1={HEIGHT - PADDING} x2={WIDTH - PADDING} y2={HEIGHT - PADDING} stroke="var(--card-border)" stroke-width="1" />
            <line x1={PADDING} y1={PADDING} x2={PADDING} y2={HEIGHT - PADDING} stroke="var(--card-border)" stroke-width="1" />

            <!-- Axis labels -->
            <text x={WIDTH / 2} y={HEIGHT - 8} text-anchor="middle" class="axis-label">PCA 1</text>
            <text x={12} y={HEIGHT / 2} text-anchor="middle" transform="rotate(-90, 12, {HEIGHT / 2})" class="axis-label">PCA 2</text>

            <!-- Points -->
            {#each data.points_2d as point (point.version)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <circle
                cx={scaleX(point.x)}
                cy={scaleY(point.y)}
                r={6}
                fill={rewardColor(point.reward)}
                stroke="var(--card)"
                stroke-width="1.5"
                opacity="0.85"
                class="scatter-point"
                onmouseenter={(e) => handleMouseEnter(point, e)}
                onmouseleave={handleMouseLeave}
              />
            {/each}
          </svg>

          <!-- Tooltip -->
          {#if hoveredPoint}
            <div class="scatter-tooltip" style="left: {tooltipX}px; top: {tooltipY}px;">
              <div class="tooltip-version">{hoveredPoint.version}</div>
              <div class="tooltip-reward">Reward: {hoveredPoint.reward.toFixed(3)}</div>
              <div class="tooltip-discipline">{hoveredPoint.discipline}</div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .archive-panel {
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    background: var(--card);
    margin-bottom: var(--space-md);
  }

  .archive-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
  }

  .archive-title {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .archive-count {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 9999px;
    background: var(--reward-perfect);
    color: white;
  }

  .archive-coverage {
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--text-3);
  }

  .chevron {
    transition: transform var(--transition-fast);
    color: var(--text-3);
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .archive-content {
    padding: 0 var(--space-md) var(--space-md);
  }

  .archive-stats {
    display: flex;
    gap: var(--space-lg);
    margin-bottom: var(--space-sm);
    font-size: 0.78rem;
    color: var(--text-2);
  }

  .stat strong {
    color: var(--text);
  }

  .scatter-container {
    position: relative;
    max-width: 500px;
  }

  .scatter-svg {
    width: 100%;
    height: auto;
  }

  .axis-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-3);
  }

  .scatter-point {
    cursor: pointer;
    transition: r 0.15s ease;
  }

  .scatter-point:hover {
    r: 9;
  }

  .scatter-tooltip {
    position: absolute;
    background: var(--text);
    color: var(--bg);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    pointer-events: none;
    white-space: nowrap;
    z-index: 10;
    transform: translateX(-50%);
  }

  .tooltip-version {
    font-weight: 700;
  }

  .tooltip-reward, .tooltip-discipline {
    opacity: 0.85;
  }
</style>
