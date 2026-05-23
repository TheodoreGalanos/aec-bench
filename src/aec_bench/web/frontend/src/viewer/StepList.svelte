<!-- ABOUTME: Scrollable sidebar listing each trajectory step as a clickable item. -->
<!-- ABOUTME: Highlights the active step with a forest green left border and auto-scrolls to keep it visible. -->
<script lang="ts">
  import type { StepSummary } from "../lib/types";

  interface Props {
    steps: StepSummary[];
    activeStep: number;
    onselect: (stepNum: number) => void;
  }

  let { steps, activeStep, onselect }: Props = $props();

  let listEl: HTMLDivElement | undefined = $state(undefined);

  // Auto-scroll the step list to keep the active step visible when it changes
  // (e.g. when the IntersectionObserver in the message pane updates the active step).
  $effect(() => {
    if (activeStep >= 0 && listEl) {
      const active = listEl.querySelector(`[data-testid="step-${activeStep}"]`);
      if (active && typeof active.scrollIntoView === "function") {
        active.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  });

  function statusIcon(status: string): string {
    if (status === "success" || status === "ok") return "\u2713";
    if (status === "error" || status === "fail") return "\u2717";
    return "\u2022";
  }

  function formatDuration(ms: number | null): string {
    if (ms === null) return "";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function templateProgressHint(metadata: Record<string, any> | null): string | null {
    if (!metadata) return null;
    const tp = metadata.template_progress;
    if (!tp) return null;
    const completed = tp.completed ?? tp.filled ?? 0;
    const total = tp.total ?? tp.sections ?? 0;
    if (total <= 0) return null;
    return `${completed}/${total} sections`;
  }

  function statusClass(status: string): string {
    if (status === "success" || status === "ok") return "success";
    if (status === "error" || status === "fail") return "fail";
    return "incomplete";
  }

  function outputPreview(summary: string | null): string | null {
    if (!summary) return null;
    return summary.length > 40 ? summary.slice(0, 40) + "\u2026" : summary;
  }
</script>

<div class="step-list" bind:this={listEl} data-testid="step-list">
  {#each steps as step (step.step)}
    <button
      class="step-item"
      class:active={step.step === activeStep}
      class:error={step.error_count > 0}
      class:warmup={step.call_type === "warmup"}
      onclick={() => onselect(step.step)}
      data-testid="step-{step.step}"
    >
      <span class="step-row">
        <span class="step-icon {statusClass(step.status)}">
          {statusIcon(step.status)}
        </span>
        <span class="step-num">#{step.step}</span>
        {#if step.call_type === "warmup"}
          <span class="warmup-pill">warmup</span>
        {/if}
        <span class="step-tool">{step.tool_name || step.description}</span>
        {#if templateProgressHint(step.metadata)}
          <span class="step-hint">{templateProgressHint(step.metadata)}</span>
        {/if}
        {#if !templateProgressHint(step.metadata) && step.duration_ms}
          <span class="step-duration">{formatDuration(step.duration_ms)}</span>
        {/if}
      </span>
    </button>
  {/each}
</div>

<style>
  .step-list {
    overflow-y: auto;
    scrollbar-gutter: stable;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .step-item {
    display: flex;
    flex-direction: column;
    padding: var(--space-sm) 12px var(--space-sm) var(--space-md);
    min-height: 38px;
    border: none;
    border-left: 3px solid transparent;
    border-bottom: 1px solid var(--card-border);
    background: transparent;
    cursor: pointer;
    text-align: left;
    font-size: 0.82rem;
    color: inherit;
    text-decoration: none;
    transition: background var(--transition-fast), border-color var(--transition-fast);
  }

  .step-item:last-child {
    border-bottom: none;
  }

  .step-item:hover {
    background: var(--bg);
  }

  .step-item:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -2px;
  }

  .step-item.active {
    border-left-color: var(--forest);
    background: var(--bg-warm);
    font-weight: 600;
  }

  .step-item.error {
    background: rgba(191, 77, 67, 0.06);
  }

  .step-item.warmup {
    opacity: 0.5;
  }

  .warmup-pill {
    font-size: 0.6rem;
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--text-3);
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: 9999px;
    padding: 0 5px;
    line-height: 1.4;
    flex: 0 0 auto;
  }

  .step-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    white-space: nowrap;
    overflow: hidden;
  }

  .step-icon {
    font-size: 0.9rem;
    min-width: 18px;
    text-align: center;
    flex: 0 0 auto;
  }

  .step-icon.success { color: var(--forest); }
  .step-icon.fail { color: var(--reward-zero); }
  .step-icon.incomplete { color: var(--text-3); }

  .step-num {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-3);
    min-width: 20px;
    flex: 0 0 auto;
  }

  .step-tool {
    flex: 1 1 auto;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step-duration {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-3);
    flex: 0 0 auto;
  }

  .step-hint {
    font-size: 0.68rem;
    font-family: var(--font-mono);
    color: var(--text-3);
    margin-left: auto;
    flex: 0 0 auto;
  }
</style>
