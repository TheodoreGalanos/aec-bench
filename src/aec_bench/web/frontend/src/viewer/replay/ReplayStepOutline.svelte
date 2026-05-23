<!-- ABOUTME: Left panel step list for trajectory replay, showing step number, tool name, and duration. -->
<!-- ABOUTME: Highlights the current step, dims played/future steps, and auto-scrolls active step into view. -->
<script lang="ts">
  import type { StepTiming } from "./replay-engine";

  interface Props {
    stepTimings: StepTiming[];
    currentStep: number;
    onseek: (ms: number) => void;
  }

  let { stepTimings, currentStep, onseek }: Props = $props();

  let listEl: HTMLDivElement | undefined = $state(undefined);

  // Auto-scroll the active step into view whenever currentStep changes
  $effect(() => {
    if (currentStep >= 0 && listEl) {
      const active = listEl.querySelector(`[data-step="${currentStep}"]`);
      if (active && typeof active.scrollIntoView === "function") {
        active.scrollIntoView({ block: "nearest" });
      }
    }
  });

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function stepClass(step: number): string {
    if (step === currentStep) return "current";
    if (step < currentStep) return "played";
    return "future";
  }
</script>

<div class="step-outline" bind:this={listEl} data-testid="replay-step-outline">
  {#each stepTimings as timing}
    <!-- svelte-ignore a11y_interactive_supports_focus -->
    <div
      class="step-item {stepClass(timing.step)}"
      role="button"
      tabindex="0"
      data-step={timing.step}
      data-testid="replay-step-{timing.step}"
      onclick={() => onseek(timing.startMs)}
      onkeydown={(e) => { if (e.key === "Enter" || e.key === " ") onseek(timing.startMs); }}
    >
      <div class="step-row">
        <span class="step-num">{timing.step}.</span>
        <span class="step-tool" title={timing.label ?? timing.toolName}>
          {timing.label ?? timing.toolName}
        </span>
        {#if timing.errorCount > 0}
          <span class="error-dot" title="{timing.errorCount} error(s)"></span>
        {/if}
      </div>
      <div class="step-duration">{formatDuration(timing.durationMs)}</div>
    </div>
  {/each}
</div>

<style>
  .step-outline {
    width: 120px;
    min-width: 120px;
    background: #1e1e1e;
    border-right: 1px solid #40403E;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .step-item {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: var(--space-sm) var(--space-sm) var(--space-sm) var(--space-md);
    border-left: 3px solid transparent;
    border-bottom: 1px solid #40403E;
    cursor: pointer;
    transition: background 120ms ease, opacity 120ms ease;
  }

  .step-item:last-child {
    border-bottom: none;
  }

  .step-item:hover {
    background: #262625;
  }

  .step-item:focus-visible {
    outline: 2px solid #4a6741;
    outline-offset: -2px;
  }

  .step-item.current {
    border-left-color: #4a6741;
    background: rgba(74, 103, 65, 0.15);
    opacity: 1;
  }

  .step-item.played {
    opacity: 0.5;
  }

  .step-item.future {
    opacity: 0.35;
  }

  .step-row {
    display: flex;
    align-items: center;
    gap: 4px;
    overflow: hidden;
  }

  .step-num {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: #91918D;
    flex-shrink: 0;
  }

  .step-tool {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: #E5E4DF;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .error-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #BF4D43;
    flex-shrink: 0;
  }

  .step-duration {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: #91918D;
  }
</style>
