<!-- ABOUTME: Collapsible graveyard panel showing failed mutations with diagnostic data. -->
<!-- ABOUTME: Renders field failures, detected patterns, mutation actions, and investigation summaries. -->
<script lang="ts">
  import type { GraveyardEntry } from "../lib/types";

  interface Props {
    entries: GraveyardEntry[];
    total: number;
  }

  let { entries, total }: Props = $props();
  let expanded: boolean = $state(false);
  let expandedEntry: number | null = $state(null);

  function toggleEntry(cycle: number) {
    expandedEntry = expandedEntry === cycle ? null : cycle;
  }

  function scoreDelta(entry: GraveyardEntry): string {
    const delta = entry.score_after - entry.score_before;
    return delta >= 0 ? `+${(delta * 100).toFixed(1)}%` : `${(delta * 100).toFixed(1)}%`;
  }
</script>

{#if total > 0}
  <div class="graveyard-panel">
    <button class="graveyard-header" onclick={() => expanded = !expanded}>
      <span class="graveyard-title">
        Failed Mutations
        <span class="graveyard-count">{total}</span>
      </span>
      <span class="chevron" class:open={expanded}>&#9656;</span>
    </button>

    {#if expanded}
      <div class="graveyard-entries">
        {#each entries as entry (entry.cycle)}
          <div class="graveyard-entry">
            <button class="entry-header" onclick={() => toggleEntry(entry.cycle)}>
              <span class="entry-cycle">Cycle {entry.cycle}</span>
              <span class="entry-strategy chip">{entry.strategy}</span>
              <span class="entry-delta" class:negative={entry.score_after < entry.score_before}>
                {scoreDelta(entry)}
              </span>
            </button>

            {#if expandedEntry === entry.cycle}
              <div class="entry-detail">
                <p class="entry-description">{entry.mutation_description}</p>

                {#if entry.field_failures}
                  <div class="detail-section">
                    <span class="detail-label">Field failures:</span>
                    <div class="chips">
                      {#each Object.entries(entry.field_failures) as [field, direction]}
                        <span class="chip field-chip">{field}: {direction}</span>
                      {/each}
                    </div>
                  </div>
                {/if}

                {#if entry.detected_patterns && entry.detected_patterns.length > 0}
                  <div class="detail-section">
                    <span class="detail-label">Patterns:</span>
                    <div class="chips">
                      {#each entry.detected_patterns as pattern}
                        <span class="chip pattern-chip">{pattern}</span>
                      {/each}
                    </div>
                  </div>
                {/if}

                {#if entry.mutation_actions && entry.mutation_actions.length > 0}
                  <div class="detail-section">
                    <span class="detail-label">Actions:</span>
                    <div class="chips">
                      {#each entry.mutation_actions as action}
                        <span class="chip action-chip">
                          {action.action_type}{action.skill_name ? `(${action.skill_name})` : ""}
                        </span>
                      {/each}
                    </div>
                  </div>
                {/if}

                {#if entry.investigation_summary}
                  <div class="detail-section">
                    <span class="detail-label">Investigation:</span>
                    <p class="investigation-text">{entry.investigation_summary}</p>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .graveyard-panel {
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    background: var(--card);
    margin-bottom: var(--space-md);
  }

  .graveyard-header {
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

  .graveyard-title {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .graveyard-count {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 9999px;
    background: var(--reward-zero);
    color: white;
  }

  .chevron {
    transition: transform var(--transition-fast);
    color: var(--text-3);
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .graveyard-entries {
    padding: 0 var(--space-md) var(--space-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .graveyard-entry {
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
  }

  .entry-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    width: 100%;
    padding: var(--space-xs) var(--space-sm);
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--text);
  }

  .entry-cycle {
    font-weight: 600;
  }

  .entry-delta {
    margin-left: auto;
    font-weight: 600;
  }

  .entry-delta.negative {
    color: var(--reward-zero);
  }

  .entry-detail {
    padding: var(--space-sm) var(--space-md);
    border-top: 1px solid var(--card-border);
    font-size: 0.82rem;
  }

  .entry-description {
    margin: 0 0 var(--space-sm);
    color: var(--text-2);
  }

  .detail-section {
    margin-bottom: var(--space-sm);
  }

  .detail-label {
    font-weight: 600;
    font-size: 0.75rem;
    color: var(--text-3);
    display: block;
    margin-bottom: var(--space-xs);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .chip {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 4px;
    white-space: nowrap;
  }

  .field-chip {
    background: rgba(191, 77, 67, 0.15);
    color: var(--reward-zero);
  }

  .pattern-chip {
    background: rgba(212, 162, 127, 0.2);
    color: var(--reward-mid);
  }

  .action-chip {
    background: rgba(74, 103, 65, 0.15);
    color: var(--forest);
  }

  .investigation-text {
    margin: 0;
    color: var(--text-2);
    font-size: 0.8rem;
    line-height: 1.5;
  }
</style>
