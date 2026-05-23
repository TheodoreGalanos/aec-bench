<!-- ABOUTME: Scrollable message pane rendering trajectory steps with their messages. -->
<!-- ABOUTME: Uses normal document flow for correct layout; step-visibility tracking via IntersectionObserver. -->
<script lang="ts">
  import { onMount, untrack } from "svelte";
  import type { StepSummary, TrajectoryMessage } from "../lib/types";
  import MessageBubble from "./MessageBubble.svelte";
  import SubcallBar from "./SubcallBar.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  interface Props {
    steps: StepSummary[];
    activeStep: number;
    stepMessages: Map<number, TrajectoryMessage[]>;
    loading: boolean;
    isRlm: boolean;
    onStepVisible: (stepNum: number) => void;
    openModal: (title: string, content: string) => void;
    scrollToStep?: number;
    containerWidth?: number;
  }

  let {
    steps,
    activeStep,
    stepMessages,
    loading,
    isRlm,
    onStepVisible,
    openModal,
    scrollToStep = -1,
    containerWidth = 600,
  }: Props = $props();

  let containerEl: HTMLElement | undefined = $state(undefined);

  // Track last scrollToStep we acted on to avoid re-scrolling on every render
  let lastScrolledTo = $state(-1);

  // Track last step reported visible to avoid calling onStepVisible in a loop
  let lastReportedStep = $state(-1);

  // IntersectionObserver for step-visibility tracking
  let observer: IntersectionObserver | undefined;

  onMount(() => {
    if (!containerEl) return;

    observer = new IntersectionObserver(
      (entries) => {
        // Find the topmost visible step-header
        let topStep = -1;
        let topY = Infinity;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const stepNum = Number(entry.target.getAttribute("data-step"));
            if (!isNaN(stepNum) && entry.boundingClientRect.top < topY) {
              topY = entry.boundingClientRect.top;
              topStep = stepNum;
            }
          }
        }
        if (topStep >= 0 && topStep !== untrack(() => lastReportedStep)) {
          lastReportedStep = topStep;
          onStepVisible(topStep);
        }
      },
      { root: containerEl, rootMargin: "0px", threshold: 0.1 },
    );

    // Observe all step-header elements
    const headers = containerEl.querySelectorAll("[data-step]");
    headers.forEach((el) => observer!.observe(el));

    return () => observer?.disconnect();
  });

  // Re-observe when steps change
  $effect(() => {
    // Read steps to trigger reactivity
    const _len = steps.length;
    if (!containerEl || !observer) return;
    observer.disconnect();
    // Wait a tick for DOM to update
    requestAnimationFrame(() => {
      if (!containerEl || !observer) return;
      const headers = containerEl.querySelectorAll("[data-step]");
      headers.forEach((el) => observer!.observe(el));
    });
  });

  // Scroll to a specific step when scrollToStep changes.
  $effect(() => {
    if (scrollToStep >= 0 && scrollToStep !== untrack(() => lastScrolledTo) && containerEl) {
      const target = containerEl.querySelector(`[data-step="${scrollToStep}"]`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      lastScrolledTo = scrollToStep;
    }
  });

  function stepStatusClass(step: StepSummary): string {
    if (step.error_count > 0) return "step-status-error";
    if (step.status === "success" || step.status === "ok") return "step-status-ok";
    return "";
  }

  function handleSubcallSelect(stepNum: number, index: number) {
    const step = steps.find((s) => s.step === stepNum);
    const subcall = step?.metadata?.subcalls?.[index];
    if (subcall) {
      openModal(`Sub-call ${index + 1}`, JSON.stringify(subcall, null, 2));
    }
  }
</script>

<div
  class="message-pane-scroll"
  bind:this={containerEl}
  data-testid="message-pane"
>
  {#if steps.length === 0 && loading}
    <div class="skeleton-group">
      <Skeleton height="3rem" />
      <Skeleton height="5rem" />
      <Skeleton height="2rem" width="60%" />
    </div>
  {:else}
    {#each steps as step (step.step)}
      <div class="step-section">
        <div
          class="step-header {stepStatusClass(step)}"
          class:active={step.step === activeStep}
          data-step={step.step}
        >
          <span class="step-header-num">Step {step.step}</span>
          <span class="step-header-tool">{step.tool_name || step.description}</span>
          {#if step.duration_ms}
            <span class="step-header-duration">
              {step.duration_ms < 1000
                ? `${step.duration_ms}ms`
                : `${(step.duration_ms / 1000).toFixed(1)}s`}
            </span>
          {/if}
          {#if step.error_count > 0}
            <span class="step-header-errors">
              {step.error_count} error{step.error_count > 1 ? "s" : ""}
            </span>
          {/if}
        </div>

        {#each stepMessages.get(step.step) ?? [] as message, i}
          <MessageBubble {message} {containerWidth} />
        {/each}

        {#if isRlm && Array.isArray(step.metadata?.subcalls) && step.metadata.subcalls.length > 0}
          <SubcallBar
            subcalls={step.metadata.subcalls}
            onselect={(i) => handleSubcallSelect(step.step, i)}
          />
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .message-pane-scroll {
    overflow-y: auto;
    height: 100%;
    padding: var(--space-lg);
    background: var(--bg);
  }

  .skeleton-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-sm) 0;
  }

  .step-section {
    margin-bottom: var(--space-lg);
  }

  .step-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    margin-bottom: var(--space-md);
    border-left: 3px solid var(--card-border);
    background: var(--card);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    box-shadow: var(--shadow-sm);
    font-family: var(--font-heading);
    font-size: 0.95rem;
    font-weight: 700;
    transition: border-color var(--transition-fast), background var(--transition-fast);
  }

  .step-header.active {
    border-left-color: var(--forest);
    background: var(--forest-light);
  }

  .step-header.step-status-error {
    border-left-color: var(--reward-zero);
  }

  .step-header.step-status-error.active {
    border-left-color: var(--reward-zero);
    background: var(--reward-zero-bg);
  }

  .step-header-num {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.82rem;
    color: var(--text-2);
  }

  .step-header-tool {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step-header-duration {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-3);
    margin-left: auto;
  }

  .step-header-errors {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--reward-zero);
    background: var(--reward-zero-bg);
    padding: 1px var(--space-sm);
    border-radius: 9999px;
  }
</style>
