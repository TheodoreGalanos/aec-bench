<!-- ABOUTME: Canvas-based line charts showing BD dimension trajectories like a W&B training run. -->
<!-- ABOUTME: Each dimension gets its own chart with proper X/Y axes, gridlines, and step-based positioning. -->
<script lang="ts">
  import type { SwarmCentroid } from "../lib/types";

  interface Props {
    centroids: SwarmCentroid[];
    agentColors: Record<string, string>;
    selectedAgentId: string | null;
  }

  let { centroids, agentColors, selectedAgentId }: Props = $props();

  // --- Types ---

  interface TrajectoryEntry {
    version: string;
    agent_id: string;
    reward: number;
    token_cost: number;
    verification_depth: number;
    tool_density: number;
    exploration_ratio: number;
    deliberation_ratio: number;
    step: number;
  }

  const BD_DIMS: { key: keyof TrajectoryEntry; label: string }[] = [
    { key: "reward", label: "Reward" },
    { key: "token_cost", label: "Token Cost" },
    { key: "verification_depth", label: "Verify Depth" },
    { key: "tool_density", label: "Tool Density" },
    { key: "exploration_ratio", label: "Exploration" },
    { key: "deliberation_ratio", label: "Deliberation" },
  ];

  // --- Chart padding (pixels) ---
  const PAD_LEFT = 50;
  const PAD_RIGHT = 16;
  const PAD_TOP = 10;
  const PAD_BOTTOM = 22;

  // --- Derived data ---

  let trajectoryEntries = $derived.by((): TrajectoryEntry[] => {
    const occupied = centroids.filter((c) => c.occupied && c.version);
    const sorted = [...occupied].sort((a, b) => {
      const numA = parseInt(a.version!.replace(/\D/g, "") || "0");
      const numB = parseInt(b.version!.replace(/\D/g, "") || "0");
      return numA - numB;
    });
    return sorted.map((c, i) => ({
      version: c.version!,
      agent_id: c.agent_id ?? "unknown",
      reward: c.reward ?? 0,
      token_cost: c.token_cost ?? 0,
      verification_depth: c.verification_depth ?? 0,
      tool_density: c.tool_density ?? 0,
      exploration_ratio: c.exploration_ratio ?? 0,
      deliberation_ratio: c.deliberation_ratio ?? 0,
      step: i + 1,
    }));
  });

  // X axis range: at least 10, rounded up to a nice number
  let maxStep = $derived.by((): number => {
    const actual = trajectoryEntries.length;
    if (actual <= 10) return 10;
    if (actual <= 25) return 25;
    if (actual <= 50) return 50;
    if (actual <= 100) return 100;
    return Math.ceil(actual / 50) * 50;
  });

  let bestSoFar = $derived.by((): number[] => {
    let best = 0;
    return trajectoryEntries.map((e) => {
      best = Math.max(best, e.reward);
      return best;
    });
  });

  let dimExtents = $derived.by((): Record<string, [number, number]> => {
    const result: Record<string, [number, number]> = {};
    for (const dim of BD_DIMS) {
      if (trajectoryEntries.length === 0) {
        result[dim.key as string] = [0, 1];
        continue;
      }
      const values = trajectoryEntries.map((e) => e[dim.key] as number);
      let min = Math.min(...values);
      let max = Math.max(...values);
      // Add 10% padding to Y range
      const pad = (max - min) * 0.1 || 0.1;
      min = Math.max(0, min - pad);
      max = max + pad;
      result[dim.key as string] = [min, max];
    }
    return result;
  });

  // --- Canvas refs and sizing ---

  let canvasRefs: (HTMLCanvasElement | null)[] = $state(Array(BD_DIMS.length).fill(null));
  let containerRefs: (HTMLDivElement | null)[] = $state(Array(BD_DIMS.length).fill(null));
  let rowSizes: { w: number; h: number }[] = $state(
    Array(BD_DIMS.length).fill({ w: 300, h: 60 })
  );

  $effect(() => {
    const observers: ResizeObserver[] = [];
    for (let idx = 0; idx < BD_DIMS.length; idx++) {
      const container = containerRefs[idx];
      if (!container) continue;
      const observer = new ResizeObserver((entries) => {
        const { width: w, height: h } = entries[0].contentRect;
        if (w > 0 && h > 0) {
          rowSizes[idx] = { w, h };
        }
      });
      observer.observe(container);
      observers.push(observer);
    }
    return () => observers.forEach((o) => o.disconnect());
  });

  $effect(() => {
    const _entries = trajectoryEntries;
    const _best = bestSoFar;
    const _extents = dimExtents;
    const _colors = agentColors;
    const _selected = selectedAgentId;
    const _sizes = rowSizes;
    const _maxStep = maxStep;

    for (let idx = 0; idx < BD_DIMS.length; idx++) {
      const canvas = canvasRefs[idx];
      if (!canvas) continue;
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;

      const dim = BD_DIMS[idx];
      const { w, h } = _sizes[idx];
      const dpr = window.devicePixelRatio || 1;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);

      drawRow(ctx, dim, w, h, _entries, _best, _extents, _colors, _selected, _maxStep);
    }
  });

  // --- Scale functions ---

  function sx(step: number, maxS: number, w: number): number {
    return PAD_LEFT + (step / maxS) * (w - PAD_LEFT - PAD_RIGHT);
  }

  function sy(value: number, min: number, max: number, h: number): number {
    const range = max - min || 1;
    const normalised = (value - min) / range;
    return h - PAD_BOTTOM - normalised * (h - PAD_TOP - PAD_BOTTOM);
  }

  // --- Draw ---

  function drawRow(
    ctx: CanvasRenderingContext2D,
    dim: { key: keyof TrajectoryEntry; label: string },
    w: number,
    h: number,
    entries: TrajectoryEntry[],
    best: number[],
    extents: Record<string, [number, number]>,
    colors: Record<string, string>,
    selected: string | null,
    maxS: number,
  ): void {
    ctx.clearRect(0, 0, w, h);

    const extent = extents[dim.key as string] ?? [0, 1];
    const [eMin, eMax] = extent;

    const style = getComputedStyle(ctx.canvas);
    const borderColor = style.getPropertyValue("--card-border").trim() || "#e8e5de";
    const textColor = style.getPropertyValue("--text-3").trim() || "#999";

    const plotLeft = PAD_LEFT;
    const plotRight = w - PAD_RIGHT;
    const plotTop = PAD_TOP;
    const plotBottom = h - PAD_BOTTOM;

    // --- Axes ---
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(plotLeft, plotTop);
    ctx.lineTo(plotLeft, plotBottom);
    ctx.lineTo(plotRight, plotBottom);
    ctx.stroke();

    // Horizontal gridlines (4)
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;
    for (let g = 1; g <= 3; g++) {
      const gy = plotTop + (g / 4) * (plotBottom - plotTop);
      ctx.beginPath();
      ctx.moveTo(plotLeft, gy);
      ctx.lineTo(plotRight, gy);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Y axis labels (top, mid, bottom)
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.fillStyle = textColor;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(fmtVal(eMax), plotLeft - 4, plotTop);
    ctx.fillText(fmtVal((eMin + eMax) / 2), plotLeft - 4, (plotTop + plotBottom) / 2);
    ctx.fillText(fmtVal(eMin), plotLeft - 4, plotBottom);

    // X axis tick labels
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const xTicks = computeXTicks(maxS);
    for (const tick of xTicks) {
      const tx = sx(tick, maxS, w);
      if (tx < plotLeft || tx > plotRight) continue;
      ctx.fillText(String(tick), tx, plotBottom + 3);
      // Tick mark
      ctx.globalAlpha = 0.15;
      ctx.beginPath();
      ctx.moveTo(tx, plotTop);
      ctx.lineTo(tx, plotBottom);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // X axis label
    ctx.fillStyle = textColor;
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillText("step", plotRight, plotBottom + 3);

    if (entries.length === 0) return;

    // --- Best-so-far step line (reward row only) ---
    if (dim.key === "reward" && entries.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = "gold";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 2]);
      ctx.globalAlpha = 0.5;
      for (let i = 0; i < entries.length; i++) {
        const x = sx(entries[i].step, maxS, w);
        const y = sy(best[i], eMin, eMax, h);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // --- Connecting lines ---
    for (let i = 1; i < entries.length; i++) {
      const entry = entries[i];
      const prev = entries[i - 1];
      const sameAgent = entry.agent_id === prev.agent_id;
      const dimmed =
        selected != null &&
        entry.agent_id !== selected &&
        prev.agent_id !== selected;

      ctx.beginPath();
      ctx.strokeStyle = colors[entry.agent_id] ?? "#999";
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = dimmed ? 0.1 : 0.5;
      if (!sameAgent) ctx.setLineDash([3, 2]);
      ctx.moveTo(sx(prev.step, maxS, w), sy(prev[dim.key] as number, eMin, eMax, h));
      ctx.lineTo(sx(entry.step, maxS, w), sy(entry[dim.key] as number, eMin, eMax, h));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // --- Data points ---
    const radius = entries.length < 10 ? 5 : entries.length < 30 ? 4 : 3;
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i];
      const dimmed = selected != null && entry.agent_id !== selected;

      const x = sx(entry.step, maxS, w);
      const y = sy(entry[dim.key] as number, eMin, eMax, h);

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = colors[entry.agent_id] ?? "#999";
      ctx.globalAlpha = dimmed ? 0.15 : 0.9;
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.15)";
      ctx.lineWidth = 0.5;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  function fmtVal(v: number): string {
    if (Math.abs(v) >= 100) return v.toFixed(0);
    if (Math.abs(v) >= 1) return v.toFixed(1);
    return v.toFixed(2);
  }

  function computeXTicks(maxS: number): number[] {
    const ticks: number[] = [];
    const step = maxS <= 10 ? 2 : maxS <= 25 ? 5 : maxS <= 50 ? 10 : maxS <= 100 ? 20 : 50;
    for (let t = step; t <= maxS; t += step) {
      ticks.push(t);
    }
    return ticks;
  }

  // --- Expand/collapse ---
  let expandedIdx: number | null = $state(null);

  function toggleExpand(idx: number): void {
    expandedIdx = expandedIdx === idx ? null : idx;
  }

  // --- Tooltip ---
  let hoveredEntry: TrajectoryEntry | null = $state(null);

  function handleMouseMove(dimIdx: number, event: MouseEvent): void {
    const canvas = canvasRefs[dimIdx];
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const { w } = rowSizes[dimIdx];
    const count = trajectoryEntries.length;
    if (count === 0) return;

    let closestIdx = 0;
    let closestDist = Infinity;
    for (let i = 0; i < count; i++) {
      const x = sx(trajectoryEntries[i].step, maxStep, w);
      const d = Math.abs(mx - x);
      if (d < closestDist) {
        closestDist = d;
        closestIdx = i;
      }
    }

    hoveredEntry = closestDist < 20 ? trajectoryEntries[closestIdx] : null;
  }

  function handleMouseLeave(): void {
    hoveredEntry = null;
  }
</script>

<div class="traj-grid">
  {#each BD_DIMS as dim, idx}
    {@const isExpanded = expandedIdx === idx}
    {@const isCollapsed = expandedIdx !== null && expandedIdx !== idx}
    <div
      class="traj-row"
      class:expanded={isExpanded}
      class:collapsed={isCollapsed}
    >
      <button
        class="traj-label"
        class:label-clickable={true}
        onclick={() => toggleExpand(idx)}
        title={isExpanded ? "Collapse" : "Expand"}
        type="button"
      >{dim.label}</button>
      <div
        class="traj-chart"
        bind:this={containerRefs[idx]}
        onmousemove={(e) => handleMouseMove(idx, e)}
        onmouseleave={handleMouseLeave}
        role="img"
        aria-label="{dim.label} chart"
      >
        <canvas
          bind:this={canvasRefs[idx]}
          style="width: {rowSizes[idx].w}px; height: {rowSizes[idx].h}px;"
        ></canvas>
      </div>
    </div>
  {/each}

  {#if hoveredEntry}
    <div class="traj-tooltip">
      <strong>{hoveredEntry.version}</strong> — {hoveredEntry.agent_id}<br />
      Reward: {hoveredEntry.reward.toFixed(3)} |
      Tokens: {hoveredEntry.token_cost.toFixed(2)} |
      Verify: {hoveredEntry.verification_depth.toFixed(2)} |
      Tools: {hoveredEntry.tool_density.toFixed(2)}
    </div>
  {/if}
</div>

<style>
  .traj-grid {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    background: var(--bg-alt);
    border-radius: var(--radius-sm);
    overflow: hidden;
    position: relative;
  }

  .traj-row {
    display: flex;
    align-items: stretch;
    flex-grow: 1;
    flex-shrink: 1;
    flex-basis: 0;
    min-height: 50px;
    border-bottom: 1px solid var(--card-border);
    transition: flex-grow 0.25s ease, min-height 0.25s ease, opacity 0.25s ease;
    overflow: hidden;
  }

  .traj-row:last-of-type {
    border-bottom: none;
  }

  .traj-row.expanded {
    flex-grow: 10;
  }

  .traj-row.collapsed {
    flex-grow: 0;
    min-height: 22px;
    opacity: 0.5;
  }

  .traj-label {
    width: 80px;
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: 0.62rem;
    font-weight: 600;
    color: var(--text-3);
    text-align: right;
    padding-right: var(--space-sm);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    background: none;
    border: none;
  }

  .label-clickable {
    cursor: pointer;
    user-select: none;
  }

  .label-clickable:hover {
    color: var(--forest);
  }

  .expanded .traj-label {
    color: var(--forest);
    font-weight: 700;
  }

  .traj-chart {
    flex: 1;
    min-width: 0;
    position: relative;
    cursor: crosshair;
  }

  canvas {
    display: block;
  }

  .traj-tooltip {
    position: absolute;
    top: var(--space-sm);
    right: var(--space-sm);
    background: var(--card);
    color: var(--text);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    pointer-events: none;
    z-index: 10;
    border: 1px solid var(--card-border);
    box-shadow: var(--shadow-md);
    white-space: nowrap;
  }
</style>
