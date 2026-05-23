<!-- ABOUTME: Canvas-based scatter plot for QD archive centroids with adaptive dot sizing. -->
<!-- ABOUTME: Default view when archive occupancy is sparse (<20%); supports agent and reward colour modes. -->
<script lang="ts">
  import type { SwarmCentroid } from "../lib/types";

  interface Props {
    centroids: SwarmCentroid[];
    agentColors: Record<string, string>;
    colourMode: "agent" | "reward";
    selectedAgentId: string | null;
    onCentroidHover?: (centroid: SwarmCentroid | null, x: number, y: number) => void;
    onCentroidClick?: (centroid: SwarmCentroid) => void;
  }

  let {
    centroids,
    agentColors,
    colourMode,
    selectedAgentId,
    onCentroidHover,
    onCentroidClick,
  }: Props = $props();

  let canvas: HTMLCanvasElement;
  let container: HTMLDivElement;
  let width = $state(600);
  let height = $state(450);

  const PADDING_LEFT = 45;
  const PADDING_BOTTOM = 35;
  const PADDING_TOP = 20;
  const PADDING_RIGHT = 20;

  // Precompute extents so scale functions don't recompute on every call
  let xExtent = $derived.by((): [number, number] => {
    if (centroids.length === 0) return [0, 1];
    const xs = centroids.map((c) => c.x);
    return [Math.min(...xs), Math.max(...xs)];
  });

  let yExtent = $derived.by((): [number, number] => {
    if (centroids.length === 0) return [0, 1];
    const ys = centroids.map((c) => c.y);
    return [Math.min(...ys), Math.max(...ys)];
  });

  function scaleX(x: number): number {
    const [min, max] = xExtent;
    const range = max - min || 1;
    return PADDING_LEFT + ((x - min) / range) * (width - PADDING_LEFT - PADDING_RIGHT);
  }

  function scaleY(y: number): number {
    const [min, max] = yExtent;
    const range = max - min || 1;
    return PADDING_TOP + ((y - min) / range) * (height - PADDING_TOP - PADDING_BOTTOM);
  }

  function findBest(): SwarmCentroid | null {
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
  }

  function draw(ctx: CanvasRenderingContext2D): void {
    ctx.clearRect(0, 0, width, height);

    // Resolve theme colours from CSS variables
    const style = getComputedStyle(canvas);
    const cardBorder = style.getPropertyValue("--card-border").trim() || "#e8e5de";
    const textColor = style.getPropertyValue("--text-3").trim() || "#999";

    // --- Axes ---
    const plotLeft = PADDING_LEFT;
    const plotRight = width - PADDING_RIGHT;
    const plotTop = PADDING_TOP;
    const plotBottom = height - PADDING_BOTTOM;

    ctx.strokeStyle = cardBorder;
    ctx.lineWidth = 1;
    ctx.beginPath();
    // Y axis
    ctx.moveTo(plotLeft, plotTop);
    ctx.lineTo(plotLeft, plotBottom);
    // X axis
    ctx.lineTo(plotRight, plotBottom);
    ctx.stroke();

    // Tick marks (5 per axis)
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;
    for (let t = 1; t <= 4; t++) {
      const xTick = plotLeft + (t / 4) * (plotRight - plotLeft);
      ctx.beginPath();
      ctx.moveTo(xTick, plotTop);
      ctx.lineTo(xTick, plotBottom);
      ctx.stroke();

      const yTick = plotTop + (t / 4) * (plotBottom - plotTop);
      ctx.beginPath();
      ctx.moveTo(plotLeft, yTick);
      ctx.lineTo(plotRight, yTick);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Axis labels
    ctx.font = "10px 'JetBrains Mono', monospace";
    ctx.fillStyle = textColor;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText("PC 1", (plotLeft + plotRight) / 2, plotBottom + 6);

    ctx.save();
    ctx.translate(12, (plotTop + plotBottom) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("PC 2", 0, 0);
    ctx.restore();

    // Draw empty centroids as faint small dots
    for (const c of centroids) {
      if (c.occupied) continue;
      const cx = scaleX(c.x);
      const cy = scaleY(c.y);
      ctx.beginPath();
      ctx.arc(cx, cy, 2, 0, Math.PI * 2);
      ctx.fillStyle = cardBorder;
      ctx.globalAlpha = 0.3;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Adaptive radius based on number of occupied cells
    const occupiedCount = centroids.filter((c) => c.occupied).length;
    const baseRadius = occupiedCount < 10 ? 8 : occupiedCount < 50 ? 6 : 5;

    // Draw occupied centroids
    for (const c of centroids) {
      if (!c.occupied) continue;
      const cx = scaleX(c.x);
      const cy = scaleY(c.y);

      let fillColor: string;
      if (colourMode === "agent") {
        fillColor = c.agent_id ? (agentColors[c.agent_id] ?? "#999") : "#999";
      } else {
        const r = c.reward ?? 0;
        if (r >= 0.8) fillColor = style.getPropertyValue("--reward-perfect").trim() || "#61AAF2";
        else if (r >= 0.5) fillColor = style.getPropertyValue("--reward-mid").trim() || "#D4A27F";
        else fillColor = style.getPropertyValue("--reward-zero").trim() || "#BF4D43";
      }

      // Dim non-selected agents when a filter is active
      const dimmed = selectedAgentId != null && c.agent_id !== selectedAgentId;
      ctx.globalAlpha = dimmed ? 0.15 : 0.9;

      ctx.beginPath();
      ctx.arc(cx, cy, baseRadius, 0, Math.PI * 2);
      ctx.fillStyle = fillColor;
      ctx.fill();

      ctx.strokeStyle = fillColor;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Draw gold star for best centroid
    const best = findBest();
    if (best) {
      const bx = scaleX(best.x);
      const by = scaleY(best.y);
      ctx.font = "14px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "gold";
      ctx.fillText("★", bx, by - baseRadius - 8);
    }
  }

  // Observe container resize and update canvas dimensions
  $effect(() => {
    if (!canvas || !container) return;
    const observer = new ResizeObserver((entries) => {
      const { width: w, height: h } = entries[0].contentRect;
      if (w > 0 && h > 0) {
        width = w;
        height = h;
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  });

  // Redraw whenever any reactive dependency changes
  $effect(() => {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    // Access reactive deps so the effect re-runs on changes
    centroids;
    agentColors;
    colourMode;
    selectedAgentId;
    draw(ctx);
  });

  function handleMouseMove(event: MouseEvent): void {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;

    let closest: SwarmCentroid | null = null;
    let closestDist = 15; // pixel threshold

    for (const c of centroids) {
      if (!c.occupied) continue;
      const cx = scaleX(c.x);
      const cy = scaleY(c.y);
      const dist = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
      if (dist < closestDist) {
        closestDist = dist;
        closest = c;
      }
    }

    onCentroidHover?.(closest, event.clientX, event.clientY);
  }

  function handleMouseLeave(): void {
    onCentroidHover?.(null, 0, 0);
  }

  function handleClick(event: MouseEvent): void {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;

    let closest: SwarmCentroid | null = null;
    let closestDist = 15;

    for (const c of centroids) {
      if (!c.occupied) continue;
      const cx = scaleX(c.x);
      const cy = scaleY(c.y);
      const dist = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
      if (dist < closestDist) {
        closestDist = dist;
        closest = c;
      }
    }

    if (closest) {
      onCentroidClick?.(closest);
    }
  }
</script>

<div class="scatter-container" bind:this={container}>
  <!-- svelte-ignore a11y_no_interactive_element_to_noninteractive_role -->
  <canvas
    bind:this={canvas}
    style="width: {width}px; height: {height}px;"
    onmousemove={handleMouseMove}
    onmouseleave={handleMouseLeave}
    onclick={handleClick}
    aria-label="Archive scatter plot"
  ></canvas>
</div>

<style>
  .scatter-container {
    width: 100%;
    height: 100%;
    min-height: 200px;
    position: relative;
  }

  canvas {
    display: block;
    cursor: crosshair;
  }
</style>
