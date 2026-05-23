<!-- ABOUTME: Clickable list of RLM symbolic-state variables with type hints and new-variable badges. -->
<!-- ABOUTME: Click dispatches onselect for the parent to open a modal with the variable's value. -->
<script lang="ts">
  interface VariableInfo {
    name: string;
    type: string;
    isNew: boolean;
  }

  interface Props {
    variables: VariableInfo[];
    onselect: (name: string) => void;
  }

  let { variables, onselect }: Props = $props();
</script>

<div class="variable-list" data-testid="variable-list">
  {#if variables.length === 0}
    <div class="empty-hint">No variables tracked.</div>
  {:else}
    {#each variables as v}
      <button
        class="variable-item"
        class:is-new={v.isNew}
        onclick={() => onselect(v.name)}
        data-testid="variable-{v.name}"
      >
        <span class="var-name">{v.name}</span>
        <span class="var-type">{v.type}</span>
        {#if v.isNew}
          <span class="new-badge" data-testid="new-badge-{v.name}">new</span>
        {/if}
      </button>
    {/each}
  {/if}
</div>

<style>
  .variable-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .variable-item {
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

  .variable-item:hover {
    background: rgba(74, 103, 65, 0.1);
  }

  .variable-item:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -1px;
  }

  .variable-item.is-new {
    background: rgba(97, 170, 242, 0.08);
  }

  .variable-item.is-new:hover {
    background: rgba(97, 170, 242, 0.15);
  }

  .var-name {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }

  .var-type {
    font-size: 0.72rem;
    color: var(--text-3);
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 0 var(--space-xs);
    border-radius: var(--radius-sm);
  }

  .new-badge {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--reward-perfect);
    background: var(--reward-perfect-bg);
    padding: 1px 6px;
    border-radius: 9999px;
    letter-spacing: 0.04em;
  }

  .empty-hint {
    font-size: 0.8rem;
    color: var(--text-3);
    font-style: italic;
    padding: var(--space-sm);
  }
</style>
