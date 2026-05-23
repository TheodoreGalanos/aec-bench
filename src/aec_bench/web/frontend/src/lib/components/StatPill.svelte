<!-- ABOUTME: Compact stat display showing a numeric value and descriptive label. -->
<!-- ABOUTME: Used in summary rows and headers to surface key metrics at a glance. -->
<script lang="ts">
  interface Props {
    value: string | number;
    label: string;
  }

  let { value, label }: Props = $props();
</script>

<div class="stat-pill">
  <span class="stat-value">{value}</span>
  <span class="stat-label">{label}</span>
</div>

<style>
  .stat-pill {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: 9999px;
    padding: var(--space-xs) var(--space-md);
  }

  .stat-value {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 1rem;
    color: var(--text);
    line-height: 1.2;
  }

  .stat-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    line-height: 1;
  }
</style>
