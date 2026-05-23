<!-- ABOUTME: Row of pill-shaped buttons representing RLM sub-calls within a trajectory step. -->
<!-- ABOUTME: Each pill displays the subcall type, a prompt preview, and a token count. -->
<script lang="ts">
  interface Props {
    subcalls: any[];
    onselect: (index: number) => void;
  }

  let { subcalls, onselect }: Props = $props();

  function truncate(text: string, max: number = 40): string {
    if (!text) return "";
    return text.length > max ? text.slice(0, max) + "\u2026" : text;
  }

  function formatTokens(n: number | null | undefined): string {
    if (n == null) return "";
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  }
</script>

<div class="subcall-bar" data-testid="subcall-bar">
  {#each subcalls as subcall, i}
    <button
      class="subcall-pill"
      onclick={() => onselect(i)}
      data-testid="subcall-{i}"
    >
      <span class="subcall-type">{subcall.type ?? "call"}</span>
      <span class="subcall-prompt">{truncate(subcall.prompt ?? subcall.content ?? "")}</span>
      {#if subcall.tokens || subcall.token_count}
        <span class="subcall-tokens">{formatTokens(subcall.tokens ?? subcall.token_count)}</span>
      {/if}
    </button>
  {/each}
</div>

<style>
  .subcall-bar {
    display: flex;
    gap: var(--space-xs);
    flex-wrap: wrap;
    padding: var(--space-sm) 0;
    margin-left: 38px;
  }

  .subcall-pill {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    padding: 3px 10px;
    border: 1px solid var(--card-border);
    border-radius: 12px;
    background: var(--card);
    cursor: pointer;
    font-size: 0.72rem;
    color: var(--text-2);
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: background var(--transition-fast), border-color var(--transition-fast);
  }

  .subcall-pill:hover {
    background: var(--forest-light);
    border-color: var(--forest);
  }

  .subcall-pill:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 1px;
  }

  .subcall-type {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--forest);
  }

  .subcall-prompt {
    font-size: 0.73rem;
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
  }

  .subcall-tokens {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--text-3);
    background: var(--bg-alt);
    padding: 1px 6px;
    border-radius: 9999px;
    margin-left: auto;
  }
</style>
