<!-- ABOUTME: Left-to-right DAG of archive lineage showing evolutionary history. -->
<!-- ABOUTME: Nodes sized by reward, coloured by agent; dashed edges for cross-agent transfers. -->
<script lang="ts">
  import type { SwarmLineageNode } from "../lib/types";

  interface Props {
    nodes: SwarmLineageNode[];
    agentColors: Record<string, string>;
  }

  let { nodes, agentColors }: Props = $props();
  let hoveredVersion: string | null = $state(null);

  const NODE_RADIUS_MIN = 8;
  const NODE_RADIUS_MAX = 20;
  const LAYER_GAP = 100;
  const VERTICAL_GAP = 50;
  const PADDING = 40;

  interface LayoutNode {
    version: string;
    node: SwarmLineageNode;
    layer: number;
    x: number;
    y: number;
    radius: number;
  }

  let layout = $derived.by((): { nodes: LayoutNode[]; edges: { from: LayoutNode; to: LayoutNode; crossAgent: boolean }[]; width: number; height: number } => {
    if (nodes.length === 0) return { nodes: [], edges: [], width: 200, height: 100 };

    const byVersion = new Map(nodes.map((n) => [n.version, n]));

    const children = new Map<string, string[]>();
    const roots: string[] = [];
    for (const n of nodes) {
      if (!n.parent_version || !byVersion.has(n.parent_version)) {
        roots.push(n.version);
      } else {
        const list = children.get(n.parent_version) ?? [];
        list.push(n.version);
        children.set(n.parent_version, list);
      }
    }

    const layerOf = new Map<string, number>();
    const queue = [...roots];
    for (const r of roots) layerOf.set(r, 0);
    let head = 0;
    while (head < queue.length) {
      const v = queue[head++];
      const layer = layerOf.get(v) ?? 0;
      for (const c of children.get(v) ?? []) {
        if (!layerOf.has(c)) {
          layerOf.set(c, layer + 1);
          queue.push(c);
        }
      }
    }

    const layers = new Map<number, string[]>();
    for (const [v, l] of layerOf) {
      const list = layers.get(l) ?? [];
      list.push(v);
      layers.set(l, list);
    }

    const maxLayer = Math.max(...layerOf.values(), 0);
    const maxPerLayer = Math.max(...[...layers.values()].map((l) => l.length), 1);

    const width = PADDING * 2 + maxLayer * LAYER_GAP + 40;
    const height = PADDING * 2 + (maxPerLayer - 1) * VERTICAL_GAP + 40;

    const layoutNodes: LayoutNode[] = [];
    const posMap = new Map<string, LayoutNode>();

    for (const [layer, versions] of layers) {
      const layerHeight = (versions.length - 1) * VERTICAL_GAP;
      const startY = (height - layerHeight) / 2;
      versions.forEach((v, idx) => {
        const node = byVersion.get(v)!;
        const radius = NODE_RADIUS_MIN + node.reward * (NODE_RADIUS_MAX - NODE_RADIUS_MIN);
        const ln: LayoutNode = {
          version: v,
          node,
          layer,
          x: PADDING + layer * LAYER_GAP,
          y: startY + idx * VERTICAL_GAP,
          radius,
        };
        layoutNodes.push(ln);
        posMap.set(v, ln);
      });
    }

    const edges: { from: LayoutNode; to: LayoutNode; crossAgent: boolean }[] = [];
    for (const n of nodes) {
      if (n.parent_version && posMap.has(n.parent_version)) {
        edges.push({
          from: posMap.get(n.parent_version)!,
          to: posMap.get(n.version)!,
          crossAgent: n.cross_agent,
        });
      }
    }

    return { nodes: layoutNodes, edges, width, height };
  });
</script>

<div class="lineage-container">
  {#if nodes.length === 0}
    <div class="empty">No lineage data</div>
  {:else}
    <div class="lineage-scroll">
      <svg viewBox="0 0 {layout.width} {layout.height}" class="lineage-svg" style="min-width: {layout.width}px;">
        {#each layout.edges as edge}
          <line
            x1={edge.from.x}
            y1={edge.from.y}
            x2={edge.to.x}
            y2={edge.to.y}
            stroke={agentColors[edge.to.node.agent_id] ?? "var(--text-3)"}
            stroke-width="1.5"
            stroke-dasharray={edge.crossAgent ? "4,3" : "none"}
            opacity="0.6"
          />
        {/each}

        {#each layout.nodes as ln (ln.version)}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <g
            class="lineage-node"
            onmouseenter={() => (hoveredVersion = ln.version)}
            onmouseleave={() => (hoveredVersion = null)}
          >
            {#if ln.node.surprise}
              <circle
                cx={ln.x}
                cy={ln.y}
                r={ln.radius + 4}
                fill="none"
                stroke="gold"
                stroke-width="2"
                stroke-dasharray="3,2"
              />
            {/if}
            <circle
              cx={ln.x}
              cy={ln.y}
              r={ln.radius}
              fill={agentColors[ln.node.agent_id] ?? "var(--text-3)"}
              opacity="0.85"
            />
            <text
              x={ln.x}
              y={ln.y + ln.radius + 14}
              text-anchor="middle"
              class="node-label"
            >{ln.version}</text>
          </g>
        {/each}
      </svg>
    </div>

    {#if hoveredVersion}
      {@const ln = layout.nodes.find((n) => n.version === hoveredVersion)}
      {#if ln}
        <div class="lineage-tooltip">
          <strong>{ln.version}</strong> — {ln.node.agent_id}
          <br />Mutation: {ln.node.mutation_type}
          <br />Reward: {ln.node.reward.toFixed(3)}
          {#if ln.node.cross_agent}
            <br /><em>Cross-agent transfer</em>
          {/if}
          {#if ln.node.surprise}
            <br /><em>Surprise entry</em>
          {/if}
          {#if ln.node.narrative}
            <br /><span class="narrative">{ln.node.narrative}</span>
          {/if}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .lineage-container {
    position: relative;
    padding: var(--space-sm);
  }

  .lineage-scroll {
    overflow-x: auto;
    overflow-y: hidden;
  }

  .lineage-svg {
    height: auto;
    display: block;
  }

  .lineage-node {
    cursor: pointer;
  }

  .lineage-node:hover circle {
    opacity: 1;
  }

  .node-label {
    font-family: var(--font-mono);
    font-size: 9px;
    fill: var(--text-2);
  }

  .lineage-tooltip {
    position: absolute;
    top: var(--space-sm);
    right: var(--space-sm);
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    padding: var(--space-sm);
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text);
    max-width: 280px;
    line-height: 1.5;
    z-index: 10;
  }

  .narrative {
    font-style: italic;
    color: var(--text-3);
  }

  .empty {
    text-align: center;
    padding: var(--space-lg);
    color: var(--text-3);
    font-size: 0.85rem;
  }
</style>
