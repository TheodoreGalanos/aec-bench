<!-- ABOUTME: Clickable list of RLM scratchpad keys for inspecting persistent working memory entries. -->
<!-- ABOUTME: Click dispatches onselect for the parent to open a modal with the scratchpad value. -->
<script lang="ts">
  interface Props {
    keys: string[];
    onselect: (key: string) => void;
  }

  let { keys, onselect }: Props = $props();
</script>

<div class="scratchpad-list" data-testid="scratchpad-list">
  {#if keys.length === 0}
    <div class="empty-hint">No scratchpad entries.</div>
  {:else}
    {#each keys as key}
      <button
        class="scratchpad-item"
        onclick={() => onselect(key)}
        data-testid="scratchpad-{key}"
      >
        <span class="key-icon">&#9998;</span>
        <span class="key-name">{key}</span>
      </button>
    {/each}
  {/if}
</div>

<style>
  .scratchpad-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .scratchpad-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-xs) var(--space-sm);
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }

  .scratchpad-item:hover {
    background: rgba(74, 103, 65, 0.1);
  }

  .scratchpad-item:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -1px;
  }

  .key-icon {
    font-size: 0.75rem;
    color: var(--text-3);
    flex: 0 0 auto;
  }

  .key-name {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }

  .empty-hint {
    font-size: 0.8rem;
    color: var(--text-3);
    font-style: italic;
    padding: var(--space-sm);
  }
</style>
