<!-- ABOUTME: Base card container with optional hover state and configurable padding. -->
<!-- ABOUTME: Used as the standard surface for all content blocks across the UI. -->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    hoverable?: boolean;
    padding?: string;
    children?: Snippet;
  }

  let { hoverable = false, padding = "var(--space-lg)", children }: Props = $props();
</script>

<div
  class="card"
  class:hoverable
  style:padding
>
  {@render children?.()}
</div>

<style>
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
  }

  .card.hoverable {
    cursor: pointer;
    transition: box-shadow var(--transition-fast), background var(--transition-fast), transform var(--transition-fast);
  }

  .card.hoverable:hover {
    background: var(--card-hover);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
  }
</style>
