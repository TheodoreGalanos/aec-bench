<!-- ABOUTME: Sortable trial table rendered from TrialRow[] with optional click-to-view callback. -->
<!-- ABOUTME: Pure presentational; parent owns the data fetch and row navigation. -->
<script lang="ts">
  import type { TrialRow } from "../lib/types";
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import { modelColour } from "../lib/model-colour";

  type Props = {
    trials: TrialRow[];
    onTrialClick?: (experimentId: string, trialId: string) => void;
    emptyMessage?: string;
  };
  let { trials, onTrialClick, emptyMessage = "No trials match the current filters." }: Props = $props();

  function handleRowClick(trial: TrialRow) {
    onTrialClick?.(trial.experiment_id, trial.trial_id);
  }
</script>

{#if trials.length === 0}
  <Card>
    <div class="empty-state">
      <p>{emptyMessage}</p>
    </div>
  </Card>
{:else}
  <Card padding="0">
    <table class="trial-table">
      <thead>
        <tr>
          <th>Trial</th>
          <th>Task</th>
          <th>Model</th>
          <th>Adapter</th>
          <th class="num">Reward</th>
          <th>Verdict</th>
        </tr>
      </thead>
      <tbody>
        {#each trials as trial (`${trial.experiment_id}::${trial.trial_id}`)}
          <tr
            class="row clickable {trial.reward_class}"
            onclick={() => handleRowClick(trial)}
            onkeydown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleRowClick(trial);
              }
            }}
            tabindex="0"
            role="link"
          >
            <td class="mono">{trial.trial_id}</td>
            <td class="mono">{trial.task_id}</td>
            <td><Badge text={trial.model} variant="model" colour={modelColour(trial.model)} /></td>
            <td>
              {#if trial.adapter === "rlm"}
                <Badge text="RLM" variant="rlm" />
              {:else}
                <Badge text={trial.adapter} />
              {/if}
            </td>
            <td class="num"><RewardBadge reward={trial.reward} size="sm" /></td>
            <td>
              {#if trial.annotation_icon}
                <span title={trial.annotation_verdict}>{trial.annotation_icon}</span>
              {:else}
                <span class="no-annotation">—</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </Card>
{/if}

<style>
  .trial-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th {
    padding: var(--space-sm) var(--space-md);
    font-family: var(--font-heading);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-2);
    border-bottom: 1px solid var(--card-border);
    text-align: left;
  }
  td {
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    vertical-align: middle;
  }
  tr.row:hover {
    background: var(--bg-alt);
  }
  tr.clickable {
    cursor: pointer;
  }
  .num {
    text-align: right;
  }
  .mono {
    font-family: var(--font-mono);
    font-size: 0.82rem;
  }
  .empty-state {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }
  .no-annotation {
    color: var(--text-3);
  }
</style>
