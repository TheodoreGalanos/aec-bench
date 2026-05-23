<!-- ABOUTME: Generic pivot-table renderer for the Analyze page. -->
<!-- ABOUTME: Single-metric grid mode (cols_dim != 'none') or multi-metric list mode (cols_dim === 'none'). -->
<script lang="ts">
  import type { AnalyzeCell, AnalyzeData, AnalyzeMetric } from "../lib/types";
  import Card from "../lib/components/Card.svelte";

  type Props = {
    data: AnalyzeData;
    onCellClick?: (rowLabel: string, colLabel: string) => void;
  };
  let { data, onCellClick }: Props = $props();

  const METRIC_LABELS: Record<AnalyzeMetric, string> = {
    mean_reward: "mean reward",
    perfect_pct: "perfect %",
    zero_pct: "zero %",
    count: "count",
    cost: "cost",
  };

  function formatMetric(m: AnalyzeMetric, v: number | null | undefined): string {
    if (v === null || v === undefined) return "—";
    if (m === "perfect_pct" || m === "zero_pct") return `${Math.round(v * 100)}%`;
    if (m === "count") return String(v);
    if (m === "cost") return `$${v.toFixed(4)}`;
    return v.toFixed(3);
  }

  function formatDelta(v: number | null | undefined): string {
    if (v === null || v === undefined) return "—";
    const sign = v >= 0 ? "+" : "";
    return `${sign}${v.toFixed(3)}`;
  }

  function deltaColor(v: number | null | undefined): string {
    if (v === null || v === undefined) return "var(--delta-neutral)";
    if (v > 0) return "var(--delta-positive)";
    if (v < 0) return "var(--delta-negative)";
    return "var(--delta-neutral)";
  }

  function cellKey(row: string, col: string): string {
    return `${row}|${col}`;
  }

  function cellValue(cell: AnalyzeCell | undefined, metric: AnalyzeMetric): number | null {
    if (!cell) return null;
    const v = cell[metric];
    return v === undefined ? null : v;
  }

  let primaryMetric = $derived(data.metrics[0]);
  let isMultiMetric = $derived(data.cols_dim === "none");
</script>

<Card padding="0">
  <div class="table-wrap">
    <table class="result-table">
      <thead>
        <tr>
          <th class="row-header">{data.rows_dim}</th>
          {#if isMultiMetric}
            {#each data.metrics as m (m)}
              <th class="num">{METRIC_LABELS[m]}</th>
            {/each}
          {:else}
            {#each data.col_labels as col (col)}
              <th class="num">{col}</th>
            {/each}
            <th class="num total">Total</th>
            {#if data.delta_enabled}
              <th class="num delta-col">Δ</th>
            {/if}
          {/if}
        </tr>
      </thead>
      <tbody>
        {#each data.row_labels as row (row)}
          <tr>
            <td class="row-header">{row}</td>
            {#if isMultiMetric}
              {#each data.metrics as m (m)}
                <td class="num">
                  {formatMetric(m, cellValue(data.row_totals[row], m))}
                </td>
              {/each}
            {:else}
              {#each data.col_labels as col (col)}
                {@const v = cellValue(data.cells[cellKey(row, col)], primaryMetric)}
                <td
                  class="num {v !== null ? 'clickable' : ''}"
                  onclick={v !== null ? () => onCellClick?.(row, col) : undefined}
                  role={v !== null ? "button" : undefined}
                  tabindex={v !== null ? 0 : undefined}
                  onkeydown={v !== null
                    ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onCellClick?.(row, col); } }
                    : undefined}
                >
                  {formatMetric(primaryMetric, v)}
                </td>
              {/each}
              <td class="num total">
                {formatMetric(primaryMetric, cellValue(data.row_totals[row], primaryMetric))}
              </td>
              {#if data.delta_enabled}
                <td class="num delta-col" style:color={deltaColor(data.row_deltas?.[row])}>
                  {formatDelta(data.row_deltas?.[row])}
                </td>
              {/if}
            {/if}
          </tr>
        {/each}

        {#if !isMultiMetric && data.col_labels.length > 0}
          <tr class="totals-row">
            <td class="row-header">Total</td>
            {#each data.col_labels as col (col)}
              <td class="num">
                {formatMetric(primaryMetric, cellValue(data.col_totals[col], primaryMetric))}
              </td>
            {/each}
            <td class="num total">
              {formatMetric(primaryMetric, cellValue(data.grand_total, primaryMetric))}
            </td>
            {#if data.delta_enabled}
              <td class="num delta-col">—</td>
            {/if}
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
</Card>

<style>
  .table-wrap { overflow-x: auto; }
  .result-table {
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
  }
  .row-header {
    font-family: var(--font-mono);
    font-size: 0.82rem;
  }
  .num {
    text-align: right;
    font-family: var(--font-mono);
  }
  .total {
    border-left: 1px solid var(--card-border);
    font-weight: 700;
  }
  .delta-col {
    border-left: 1px solid var(--card-border);
    font-weight: 700;
  }
  .clickable {
    cursor: pointer;
  }
  .clickable:hover {
    background: var(--bg-alt);
  }
  .totals-row td {
    border-top: 2px solid var(--card-border);
    font-weight: 700;
    background: var(--bg-alt);
  }
</style>
