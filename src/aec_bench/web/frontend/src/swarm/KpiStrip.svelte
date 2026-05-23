<!-- ABOUTME: Horizontal KPI strip for the Swarm Mission Control dashboard header. -->
<!-- ABOUTME: Displays workspace name, coverage, best score, evals, budget, elapsed, and agent count. -->
<script lang="ts">
  import Card from "../lib/components/Card.svelte";
  import StatPill from "../lib/components/StatPill.svelte";
  import type { SwarmState } from "../lib/types";
  import type { ConnectionStatus } from "../lib/stores/swarm.svelte";

  interface Props {
    state: SwarmState;
    connectionStatus: ConnectionStatus;
  }

  let { state, connectionStatus }: Props = $props();

  let coverage = $derived.by((): string => {
    const total = state.centroids.length;
    if (total === 0) return "0%";
    const occupied = state.centroids.filter((c) => c.occupied).length;
    return `${((occupied / total) * 100).toFixed(0)}% (${occupied}/${total})`;
  });

  let budgetColor = $derived.by((): string => {
    const pct = state.budget.spend_percentage;
    if (pct >= 0.95) return "var(--reward-zero)";
    if (pct >= 0.8) return "var(--reward-mid)";
    return "var(--forest)";
  });

  let budgetValue = $derived(
    `${(state.budget.spend_percentage * 100).toFixed(0)}%`
  );

  let bestScoreValue = $derived(state.best_score.toFixed(2));

  let activeAgents = $derived(
    state.agents.filter((a) => a.status === "active").length
  );

  let agentsValue = $derived(`${activeAgents}/${state.agents.length}`);

  function formatElapsed(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 60) {
      const hrs = Math.floor(mins / 60);
      const remainMins = mins % 60;
      return `${hrs}h ${remainMins}m`;
    }
    return `${mins}m ${secs}s`;
  }
</script>

<Card padding="var(--space-xs) var(--space-md)">
  <div class="kpi-strip">
    <div class="workspace-name">
      {#if connectionStatus === "live"}
        <span class="live-dot"></span>
      {/if}
      <span class="name-text">{state.workspace}</span>
    </div>

    <StatPill value={coverage} label="Coverage" />

    <div class="colored-pill-wrapper" style:color="var(--forest)">
      <StatPill value={bestScoreValue} label="Best Score" />
    </div>

    <StatPill value={state.total_evals} label="Evals" />

    <div class="colored-pill-wrapper" style:color={budgetColor}>
      <StatPill value={budgetValue} label="Budget" />
    </div>

    <StatPill value={formatElapsed(state.elapsed_seconds)} label="Elapsed" />

    <StatPill value={agentsValue} label="Agents" />
  </div>
</Card>

<style>
  .kpi-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-sm);
  }

  .workspace-name {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--text);
    padding-right: var(--space-sm);
  }

  .live-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--forest);
    animation: pulse 2s ease-in-out infinite;
    flex-shrink: 0;
  }

  /*
   * Wrapper that applies a color override to the StatPill's value text
   * via the CSS currentColor cascade. StatPill uses --text for the value;
   * we override the color on the wrapper so the pill value inherits it.
   */
  .colored-pill-wrapper :global(.stat-value) {
    color: currentColor;
  }

  /* Compact pill sizing for the dashboard header context */
  .kpi-strip :global(.stat-pill) {
    padding: 2px var(--space-sm);
    gap: 1px;
  }

  .kpi-strip :global(.stat-value) {
    font-size: 0.82rem;
  }

  .kpi-strip :global(.stat-label) {
    font-size: 0.58rem;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
</style>
