<!-- ABOUTME: Individual agent card showing status, model, eval count, and score progress bar. -->
<!-- ABOUTME: Border-left accent colour identifies the agent across all dashboard components. Supports selected state and click handler for agent filtering. -->
<script lang="ts">
  import type { SwarmAgent } from "../lib/types";
  import Badge from "../lib/components/Badge.svelte";
  import type { Variant as BadgeVariant } from "../lib/components/Badge.svelte";

  interface Props {
    agent: SwarmAgent;
    color: string;
    selected?: boolean;
    onclick?: () => void;
  }

  let { agent, color, selected = false, onclick }: Props = $props();

  let statusBadgeVariant = $derived.by((): BadgeVariant =>
    agent.status === "retired" ? "default" : "model"
  );

  let statusBadgeColour = $derived.by((): string | undefined => {
    switch (agent.status) {
      case "active": return "var(--forest)";
      case "pivoting": return "var(--reward-zero)";
      default: return undefined;
    }
  });
</script>

<div
  class="agent-card"
  class:selected
  style:border-left-color={color}
  style:box-shadow={selected ? `0 0 0 2px ${color}` : undefined}
  role="button"
  tabindex="0"
  {onclick}
  onkeydown={(e) => e.key === "Enter" && onclick?.()}
>
  <div class="card-top">
    <span class="agent-id">{agent.agent_id}</span>
    <Badge text={agent.status} variant={statusBadgeVariant} colour={statusBadgeColour} />
  </div>

  <div class="card-stats">
    <span class="stat">{agent.eval_count} evals</span>
    <span class="stat">${agent.budget_consumed_usd.toFixed(2)}</span>
  </div>

  <div class="score-row">
    <div class="score-bar-bg">
      <div
        class="score-bar-fill"
        style:width="{Math.min(agent.best_score * 100, 100)}%"
        style:background={color}
      ></div>
    </div>
    <span class="score-label">{agent.best_score.toFixed(2)}</span>
  </div>

  {#if agent.nudge}
    <div class="nudge">{agent.nudge}</div>
  {/if}
</div>

<style>
  .agent-card {
    padding: var(--space-sm);
    border-left: 3px solid;
    background: var(--card);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    cursor: pointer;
    transition: box-shadow 0.15s ease;
  }

  .agent-card.selected {
    background: var(--bg-alt);
  }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-xs);
  }

  .agent-id {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.8rem;
    color: var(--text);
  }

  .card-stats {
    display: flex;
    gap: var(--space-md);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-2);
    margin-bottom: var(--space-xs);
  }

  .score-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .score-bar-bg {
    flex: 1;
    height: 6px;
    background: var(--bg-alt);
    border-radius: 3px;
    overflow: hidden;
  }

  .score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .score-label {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.72rem;
    color: var(--text);
    min-width: 2.5em;
    text-align: right;
  }

  .nudge {
    margin-top: var(--space-xs);
    font-size: 0.65rem;
    color: var(--text-3);
    font-style: italic;
    line-height: 1.3;
  }
</style>
