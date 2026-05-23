<!-- ABOUTME: Generic modal dialog with backdrop, fade animation, and keyboard close. -->
<!-- ABOUTME: Renders children via Svelte 5 snippets, closes on backdrop click or Escape key. -->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    open: boolean;
    title: string;
    onclose?: () => void;
    wide?: boolean;
    children?: Snippet;
  }

  let { open, title, onclose, wide = false, children }: Props = $props();

  function handleBackdropClick() {
    onclose?.();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      onclose?.();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="backdrop"
    data-testid="modal-backdrop"
    onclick={handleBackdropClick}
    role="presentation"
    aria-label={title}
  >
    <div
      class="modal"
      class:wide
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="modal-header">
        <h2 class="modal-title">{title}</h2>
        {#if onclose}
          <button class="close-btn" onclick={onclose} aria-label="Close modal">×</button>
        {/if}
      </div>
      <div class="modal-body">
        {@render children?.()}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fade-in var(--transition-normal) ease;
  }

  .modal {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: var(--space-lg);
    width: min(560px, 90vw);
    max-height: 80vh;
    overflow-y: auto;
    animation: slide-up var(--transition-normal) ease;
  }

  .modal.wide {
    width: min(860px, 95vw);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-md);
  }

  .modal-title {
    font-family: var(--font-heading);
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    line-height: 1;
    cursor: pointer;
    color: var(--text-3);
    padding: 0 var(--space-xs);
    transition: color var(--transition-fast);
  }

  .close-btn:hover {
    color: var(--text);
  }

  .modal-body {
    color: var(--text);
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slide-up {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
