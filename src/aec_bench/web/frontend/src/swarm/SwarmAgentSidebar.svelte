<!-- ABOUTME: Sidebar for the swarm dashboard containing agent cards and event feed. -->
<!-- ABOUTME: Agent cards stacked vertically with colour-coded borders, event feed below divider. Supports click-to-filter by agent. -->
<script lang="ts">
  import type { SwarmAgent, SwarmEvent } from "../lib/types";
  import SwarmAgentCard from "./SwarmAgentCard.svelte";
  import SwarmEventFeed from "./SwarmEventFeed.svelte";

  interface Props {
    agents: SwarmAgent[];
    events: SwarmEvent[];
    agentColors: Record<string, string>;
    selectedAgentId: string | null;
    onAgentSelect?: (agentId: string) => void;
  }

  let { agents, events, agentColors, selectedAgentId, onAgentSelect }: Props = $props();
</script>

<aside class="sidebar">
  <div class="agent-list">
    {#each agents as agent (agent.agent_id)}
      <SwarmAgentCard
        {agent}
        color={agentColors[agent.agent_id] ?? "var(--text-3)"}
        selected={agent.agent_id === selectedAgentId}
        onclick={() => onAgentSelect?.(agent.agent_id)}
      />
    {/each}
  </div>

  <hr class="divider" />

  <div class="feed-section">
    <span class="feed-title">Events</span>
    <SwarmEventFeed {events} {agentColors} />
  </div>
</aside>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-sm);
    overflow-y: auto;
    border-right: 1px solid var(--card-border);
    background: var(--bg);
  }

  .agent-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .divider {
    border: none;
    border-top: 1px solid var(--card-border);
    margin: var(--space-xs) 0;
  }

  .feed-section {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .feed-title {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    margin-bottom: var(--space-xs);
  }
</style>
