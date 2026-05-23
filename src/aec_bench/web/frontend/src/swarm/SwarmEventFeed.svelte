<!-- ABOUTME: Scrollable feed of recent swarm events with agent colour coding. -->
<!-- ABOUTME: Shows timestamp, event type, and agent attribution for the last 30 events. Auto-scrolls to bottom on new events. -->
<script lang="ts">
  import type { SwarmEvent } from "../lib/types";

  interface Props {
    events: SwarmEvent[];
    agentColors: Record<string, string>;
  }

  let { events, agentColors }: Props = $props();

  let feedEl: HTMLDivElement;

  // Suppress noise — these always follow eval_completed and add no info
  const SUPPRESSED = new Set(["archive_updated", "lineage_recorded", "graveyard_updated"]);

  let reversed = $derived(
    [...events]
      .reverse()
      .filter((e) => !SUPPRESSED.has(e.event_type))
      .slice(0, 30)
  );

  $effect(() => {
    if (feedEl && events.length > 0) {
      feedEl.scrollTop = feedEl.scrollHeight;
    }
  });

  function formatTime(timestamp: string): string {
    try {
      const d = new Date(timestamp);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return timestamp;
    }
  }

  function formatCost(usd: number): string {
    return usd < 0.01 ? "<$0.01" : `$${usd.toFixed(2)}`;
  }

  function eventLabel(event: SwarmEvent): string {
    const p = event.payload;
    switch (event.event_type) {
      case "eval_completed": {
        const score = (p.score ?? 0).toFixed(2);
        const version = p.version ?? "";
        const cost = p.cost_usd != null ? ` ${formatCost(p.cost_usd)}` : "";
        const inserted = p.inserted ? " ★" : "";
        return `${score} → ${version}${cost}${inserted}`;
      }
      case "agent_spawned":
        return `Spawned${p.model ? ": " + p.model.split(".").pop() : ""}`;
      case "agent_retired":
        return `Retired${p.reason ? ": " + p.reason : ""}`;
      case "agent_pivoting":
        return `Pivoting${p.reason ? ": " + p.reason : ""}`;
      case "agent_restarted":
        return `Restarted${p.error ? ": " + p.error : ""}`;
      case "note_written":
        return `Note: ${p.title ?? "untitled"}`;
      case "consolidation_produced":
        return "Consolidation report";
      case "swarm_started": {
        const agents = p.agent_count ?? "?";
        const budget = p.max_cost_usd != null ? ` $${p.max_cost_usd}` : "";
        return `Started: ${agents} agents${budget}`;
      }
      case "swarm_completed": {
        const best = p.best_score != null ? (p.best_score as number).toFixed(2) : "?";
        const cost = p.total_cost_usd != null ? ` ${formatCost(p.total_cost_usd)}` : "";
        return `Completed: best ${best}${cost}`;
      }
      default:
        return event.event_type.replace(/_/g, " ");
    }
  }
</script>

<div class="event-feed" bind:this={feedEl}>
  {#each reversed as event, i (event.sequence_number + "-" + i)}
    <div class="event-row">
      <span class="event-time">{formatTime(event.timestamp)}</span>
      {#if event.agent_id}
        <span
          class="agent-dot"
          style:background={agentColors[event.agent_id] ?? "var(--text-3)"}
        ></span>
      {/if}
      <span class="event-text">{eventLabel(event)}</span>
    </div>
  {/each}

  {#if events.length === 0}
    <div class="empty">No events yet</div>
  {/if}
</div>

<style>
  .event-feed {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    font-size: 0.72rem;
    font-family: var(--font-mono);
  }

  .event-row {
    display: flex;
    align-items: flex-start;
    gap: var(--space-xs);
    padding: 2px 0;
    color: var(--text-2);
  }

  .event-time {
    color: var(--text-3);
    font-size: 0.65rem;
    white-space: nowrap;
  }

  .agent-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .event-text {
    word-break: break-word;
  }

  .empty {
    color: var(--text-3);
    text-align: center;
    padding: var(--space-sm);
  }
</style>
