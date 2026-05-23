<!-- ABOUTME: Sortable data table with clickable column headers and empty state messaging. -->
<!-- ABOUTME: Accepts typed Column definitions and emits sort events to parent via onsort callback. -->
<script lang="ts">
  export interface Column {
    key: string;
    label: string;
    sortable?: boolean;
    align?: string;
    width?: string;
  }

  interface Props {
    columns: Column[];
    rows: Record<string, any>[];
    sortKey?: string;
    sortDir?: "asc" | "desc";
    onsort?: (key: string) => void;
    emptyMessage?: string;
  }

  let {
    columns,
    rows,
    sortKey,
    sortDir = "asc",
    onsort,
    emptyMessage = "No data available.",
  }: Props = $props();

  function handleHeaderClick(col: Column) {
    if (col.sortable && onsort) {
      onsort(col.key);
    }
  }

  function getSortIndicator(key: string): string {
    if (key !== sortKey) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        {#each columns as col (col.key)}
          <th
            class:sortable={col.sortable}
            class:sorted={col.key === sortKey}
            style:text-align={col.align ?? "left"}
            style:width={col.width}
            onclick={() => handleHeaderClick(col)}
          >
            {col.label}{getSortIndicator(col.key)}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if rows.length === 0}
        <tr>
          <td class="empty-cell" colspan={columns.length}>{emptyMessage}</td>
        </tr>
      {:else}
        {#each rows as row, i (i)}
          <tr>
            {#each columns as col (col.key)}
              <td style:text-align={col.align ?? "left"}>
                {row[col.key] ?? ""}
              </td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>

<style>
  .table-wrapper {
    width: 100%;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    color: var(--text);
  }

  thead {
    background: var(--bg-alt);
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
    white-space: nowrap;
    user-select: none;
  }

  th.sortable {
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  th.sortable:hover {
    color: var(--forest);
  }

  th.sorted {
    color: var(--forest);
  }

  td {
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    vertical-align: middle;
  }

  tbody tr {
    transition: background var(--transition-fast);
  }

  tbody tr:hover {
    background: var(--bg-alt);
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .empty-cell {
    text-align: center;
    color: var(--text-3);
    padding: var(--space-xl);
    font-style: italic;
  }
</style>
