<!-- ABOUTME: Displays consolidation reports from the swarm analyst agent. -->
<!-- ABOUTME: Reverse-chronological collapsible cards with patterns, recommendations, and findings. -->
<script lang="ts">
  import type { SwarmConsolidation } from "../lib/types";

  interface Props {
    reports: SwarmConsolidation[];
  }

  let { reports }: Props = $props();
  let expandedId: string | null = $state(null);

  let sorted = $derived([...reports].reverse());

  function toggle(id: string) {
    expandedId = expandedId === id ? null : id;
  }

  function formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  }
</script>

<div class="consolidation-panel">
  {#if reports.length === 0}
    <div class="empty">No consolidation reports yet</div>
  {:else}
    {#each sorted as report (report.report_id)}
      <div class="report-card">
        <button class="report-header" onclick={() => toggle(report.report_id)}>
          <div class="report-meta">
            <span class="report-time">{formatTime(report.timestamp)}</span>
            <span class="report-coverage">{report.archive_coverage_pct.toFixed(0)}% coverage</span>
            <span class="report-evals">{report.total_evals} evals</span>
          </div>
          <span class="chevron" class:open={expandedId === report.report_id}>&#9656;</span>
        </button>

        {#if expandedId === report.report_id}
          <div class="report-body">
            {#if report.cross_agent_patterns.length > 0}
              <div class="section">
                <span class="section-label">Cross-Agent Patterns</span>
                <ul>
                  {#each report.cross_agent_patterns as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            {#if report.strategy_recommendations.length > 0}
              <div class="section">
                <span class="section-label">Strategy Recommendations</span>
                <ul>
                  {#each report.strategy_recommendations as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            {#if report.counterintuitive_findings.length > 0}
              <div class="section">
                <span class="section-label">Counterintuitive Findings</span>
                <ul>
                  {#each report.counterintuitive_findings as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            {#if report.lineage_insights}
              <div class="section">
                <span class="section-label">Lineage Insights</span>
                <p>{report.lineage_insights}</p>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .consolidation-panel {
    padding: var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .report-card {
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    background: var(--card);
    overflow: hidden;
  }

  .report-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text);
  }

  .report-meta {
    display: flex;
    gap: var(--space-md);
  }

  .report-time { color: var(--text-2); }
  .report-coverage, .report-evals { color: var(--text-3); font-size: 0.7rem; }

  .chevron {
    transition: transform var(--transition-fast);
    color: var(--text-3);
  }

  .chevron.open { transform: rotate(90deg); }

  .report-body { padding: 0 var(--space-md) var(--space-md); }

  .section { margin-bottom: var(--space-sm); }

  .section-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    margin-bottom: var(--space-xs);
  }

  .section ul {
    margin: 0;
    padding-left: var(--space-md);
    font-size: 0.78rem;
    line-height: 1.5;
    color: var(--text-2);
  }

  .section p {
    font-size: 0.78rem;
    line-height: 1.5;
    color: var(--text-2);
    margin: 0;
  }

  .empty {
    text-align: center;
    padding: var(--space-lg);
    color: var(--text-3);
    font-size: 0.85rem;
  }
</style>
