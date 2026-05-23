<!-- ABOUTME: Canvas-based Voronoi tessellation showing QD archive cells using d3-delaunay native rendering. -->
<!-- ABOUTME: High-density view for occupied archives; supports agent and reward colour modes with O(1) hit testing. -->
<script lang="ts">
  import { Delaunay } from "d3-delaunay";
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

  const PADDING = 20;

  // Module-level Delaunay reference for O(1) hit testing — not reactive state
  let delaunayRef: ReturnType<typeof Delaunay.from> | null = null;

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
    return PADDING + ((x - min) / range) * (width - 2 * PADDING);
  }

  function scaleY(y: number): number {
    const [min, max] = yExtent;
    const range = max - min || 1;
    return PADDING + ((y - min) / range) * (height - 2 * PADDING);
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

    if (centroids.length < 2) return;

    // Compute scaled points and build triangulation
    const points = centroids.map((c) => [scaleX(c.x), scaleY(c.y)] as [number, number]);
    const delaunay = Delaunay.from(points);
    const voronoi = delaunay.voronoi([0, 0, width, height]);

    // Store for hit testing — updated each draw so it stays in sync with current scale
    delaunayRef = delaunay;

    // Resolve theme colours from CSS variables
    const style = getComputedStyle(canvas);
    const cardBorder = style.getPropertyValue("--card-border").trim() || "#e8e5de";

    // Draw each Voronoi cell using native Canvas path rendering
    for (let i = 0; i < centroids.length; i++) {
      const c = centroids[i];
      ctx.beginPath();
      voronoi.renderCell(i, ctx);

      if (!c.occupied) {
        ctx.strokeStyle = cardBorder;
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.15;
        ctx.stroke();
        ctx.globalAlpha = 1;
        continue;
      }

      // Determine fill colour based on active mode
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
      const opacity = dimmed ? 0.1 : 0.3 + (c.reward ?? 0) * 0.6;

      ctx.fillStyle = fillColor;
      ctx.globalAlpha = opacity;
      ctx.fill();

      ctx.globalAlpha = dimmed ? 0.1 : 0.5;
      ctx.strokeStyle = fillColor;
      ctx.lineWidth = 0.5;
      ctx.stroke();

      ctx.globalAlpha = 1;
    }

    // Draw gold star over the best occupied cell
    const best = findBest();
    if (best) {
      const bx = scaleX(best.x);
      const by = scaleY(best.y);
      ctx.font = "14px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.globalAlpha = 1;
      ctx.fillStyle = "gold";
      ctx.fillText("★", bx, by);
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
    if (!canvas || !delaunayRef) return;
    const rect = canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;

    // O(1) nearest-centroid lookup via d3-delaunay
    const idx = delaunayRef.find(mx, my);
    const c = centroids[idx];

    if (c && c.occupied) {
      onCentroidHover?.(c, event.clientX, event.clientY);
    } else {
      onCentroidHover?.(null, 0, 0);
    }
  }

  function handleMouseLeave(): void {
    onCentroidHover?.(null, 0, 0);
  }

  function handleClick(event: MouseEvent): void {
    if (!canvas || !delaunayRef) return;
    const rect = canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;

    const idx = delaunayRef.find(mx, my);
    const c = centroids[idx];

    if (c && c.occupied) {
      onCentroidClick?.(c);
    }
  }
</script>

<div class="territory-container" bind:this={container}>
  <!-- svelte-ignore a11y_no_interactive_element_to_noninteractive_role -->
  <canvas
    bind:this={canvas}
    style="width: {width}px; height: {height}px;"
    onmousemove={handleMouseMove}
    onmouseleave={handleMouseLeave}
    onclick={handleClick}
    aria-label="Archive territory Voronoi map"
  ></canvas>
</div>

<style>
  .territory-container {
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
