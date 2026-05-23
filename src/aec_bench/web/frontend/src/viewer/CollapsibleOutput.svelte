<!-- ABOUTME: Collapsible pre/code block that truncates long output with a click-to-expand overlay. -->
<!-- ABOUTME: Uses dark code-block styling and CSS max-height transition for smooth expand/collapse animation. -->
<script lang="ts">
  import { measureText, getDefaultLineHeight } from "../lib/pretext-service";

  interface Props {
    content: string;
    maxHeight?: number;
    label?: string;
    containerWidth?: number;
  }

  let { content, maxHeight = 300, label = "", containerWidth = 600 }: Props = $props();
  let expanded = $state(false);

  // Pretext measurement replaces DOM scrollHeight read
  let measured = $derived(
    measureText(content, "mono", containerWidth, getDefaultLineHeight("mono")),
  );

  let overflows = $derived(measured.height > maxHeight);
  let lineCount = $derived(measured.lineCount);
  let expandedHeight = $derived(measured.height + 32); // +32 for padding
</script>

<div
  class="collapsible"
  class:collapsed={!expanded && overflows}
  data-testid="collapsible-output"
>
  {#if label}
    <div class="collapsible-label">{label}</div>
  {/if}

  <pre
    class="collapsible-pre"
    style:max-height={expanded ? `${expandedHeight}px` : `${maxHeight}px`}
  ><code>{content}</code></pre>

  {#if overflows && !expanded}
    <button class="expand-overlay" onclick={() => expanded = true} data-testid="expand-toggle">
      <span class="expand-icon">&#9660;</span> Show all ({lineCount} lines)
    </button>
  {/if}

  {#if expanded && overflows}
    <button class="collapse-btn" onclick={() => expanded = false} data-testid="collapse-toggle">
      <span class="collapse-icon">&#9650;</span> Collapse
    </button>
  {/if}
</div>

<style>
  .collapsible {
    position: relative;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--code-border);
  }

  .collapsible-label {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--code-line-num);
    background: var(--code-bg);
    padding: var(--space-xs) var(--space-md);
    border-bottom: 1px solid var(--code-border);
  }

  .collapsible-pre {
    margin: 0;
    padding: var(--space-md);
    background: var(--code-bg);
    border-radius: 0;
    overflow: hidden;
    font-size: 0.82rem;
    line-height: 1.5;
    color: var(--code-text);
    transition: max-height var(--transition-slow);
  }

  .collapsible-pre code {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--font-mono);
    color: var(--code-text);
  }

  /*
   * Collapsed state: no mask-image (which caused the "shine" glitch).
   * The fade-to-dark effect comes entirely from the expand-overlay gradient.
   */

  .expand-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    border: none;
    padding: var(--space-lg) var(--space-md) var(--space-sm);
    text-align: center;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--forest);
    cursor: pointer;
    background: linear-gradient(to top, var(--code-bg) 50%, transparent);
    transition: color var(--transition-fast);
  }

  .expand-overlay:hover {
    color: var(--reward-perfect);
  }

  .expand-overlay:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -2px;
  }

  .expand-icon,
  .collapse-icon {
    font-size: 0.65rem;
    margin-right: 4px;
  }

  .collapse-btn {
    display: block;
    width: 100%;
    padding: var(--space-xs) 0;
    text-align: center;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--forest);
    background: var(--code-bg);
    border: none;
    border-top: 1px solid var(--code-border);
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  .collapse-btn:hover {
    color: var(--reward-perfect);
  }

  .collapse-btn:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -2px;
  }
</style>
