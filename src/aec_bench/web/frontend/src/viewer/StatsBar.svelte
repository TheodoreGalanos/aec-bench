<!-- ABOUTME: Horizontal bar displaying trial-level summary metrics and annotation controls. -->
<!-- ABOUTME: Shows reward badge, stat pills for steps/errors/tokens/cost, RLM per-step metrics, and triage annotation buttons. -->
<script lang="ts">
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import type { Annotation, StepSummary } from "../lib/types";

  interface Props {
    reward: number;
    rewardClass: string;
    totalSteps: number;
    totalErrors: number;
    tokensIn: number | null;
    tokensOut: number | null;
    totalTokens: number | null;
    costUsd?: number | null;
    adapterType: string;
    annotation: Annotation | null;
    experimentId: string;
    trialId: string;
    activeStep?: number;
    steps?: StepSummary[];
    onAnnotate?: (verdict: string) => void;
  }

  let {
    reward,
    rewardClass,
    totalSteps,
    totalErrors,
    tokensIn,
    tokensOut,
    totalTokens,
    costUsd = null,
    adapterType,
    annotation,
    experimentId,
    trialId,
    activeStep = -1,
    steps = [],
    onAnnotate,
  }: Props = $props();

  function formatTokens(n: number | null): string {
    if (n === null) return "-";
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
  }

  function formatCost(n: number | null | undefined): string {
    if (n == null) return "-";
    return `$${n.toFixed(2)}`;
  }

  // Per-step RLM metrics derived from step metadata.tokens
  let rlmMetrics = $derived.by(() => {
    if (adapterType !== "rlm") return null;
    const currentStep = steps.find((s) => s.step === activeStep);
    const tokens = currentStep?.metadata?.tokens;
    if (!tokens) return null;
    const callInput = tokens.call_input ?? tokens.input ?? null;
    const cacheRead = tokens.cache_read ?? null;
    const costCumulative = tokens.cost_cumulative ?? null;
    return { callInput, cacheRead, costCumulative };
  });

  const annotationButtons = [
    { verdict: "pass", label: "Pass", key: "1" },
    { verdict: "fail", label: "Fail", key: "2" },
    { verdict: "defer", label: "Defer", key: "3" },
    { verdict: "note", label: "Note", key: "n" },
  ] as const;
</script>

<div class="stats-bar" data-testid="stats-bar">
  <!-- Trial metrics group -->
  <div class="stats-group">
    <RewardBadge {reward} size="sm" />
    <span class="divider"></span>
    <span class="stat-pill" data-testid="pill-steps">
      <span class="stat-value">{totalSteps}</span>
      <span class="stat-label">steps</span>
    </span>
    <span class="stat-pill" data-testid="pill-errors">
      <span class="stat-value">{totalErrors}</span>
      <span class="stat-label">errors</span>
    </span>
    {#if totalTokens !== null}
      <span class="stat-pill" data-testid="pill-tokens">
        <span class="stat-value">{formatTokens(totalTokens)}</span>
        <span class="stat-label">tokens</span>
      </span>
    {/if}
    {#if costUsd !== null}
      <span class="stat-pill" data-testid="pill-cost">
        <span class="stat-value">{formatCost(costUsd)}</span>
      </span>
    {/if}
    {#if adapterType === "rlm"}
      <span class="divider"></span>
      <Badge text="RLM" variant="rlm" />
    {:else if adapterType === "lambda-rlm"}
      <span class="divider"></span>
      <Badge text={"\u03bb-RLM"} variant="lambda-rlm" />
    {/if}
  </div>

  <!-- RLM per-step metrics (live, updates with active step) -->
  {#if rlmMetrics}
    <div class="stats-group rlm-live">
      <span class="rlm-metric" data-testid="rlm-metrics">
        <span class="rlm-metric-label">ctx</span> {formatTokens(rlmMetrics.callInput)}
      </span>
      {#if rlmMetrics.cacheRead !== null}
        <span class="rlm-metric">
          <span class="rlm-metric-label">cache</span> {formatTokens(rlmMetrics.cacheRead)}r
        </span>
      {/if}
      {#if rlmMetrics.costCumulative !== null}
        <span class="rlm-metric">
          <span class="rlm-metric-label">cost</span> {formatCost(rlmMetrics.costCumulative)}
        </span>
      {/if}
    </div>
  {/if}

  <!-- Annotation controls -->
  <div class="stats-group stats-annotations">
    {#if annotation}
      <span class="annotation-current" data-testid="annotation-verdict">
        {annotation.verdict}
      </span>
    {/if}
    <div class="annotation-group">
      {#each annotationButtons as btn}
        <button
          class="annotation-btn"
          class:active={annotation?.verdict === btn.verdict}
          onclick={() => onAnnotate?.(btn.verdict)}
          title="{btn.label} ({btn.key})"
          data-testid="annotate-{btn.verdict}"
        >
          {btn.label}<span class="key-hint">{btn.key}</span>
        </button>
      {/each}
    </div>
  </div>
</div>

<style>
  .stats-bar {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: 6px var(--space-lg);
    background: var(--card);
    border-bottom: 1px solid var(--card-border);
    flex-wrap: nowrap;
    overflow-x: auto;
    flex-shrink: 0;
  }

  .stats-group {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .stats-annotations {
    margin-left: auto;
  }

  .divider {
    width: 1px;
    height: 16px;
    background: var(--card-border);
  }

  .stat-pill {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    padding: 3px 8px;
    background: var(--bg-alt);
    border-radius: 4px;
    font-size: 0.82rem;
    white-space: nowrap;
    line-height: 1.4;
  }

  .stat-value {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.82rem;
    color: var(--text);
  }

  .stat-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: lowercase;
    color: var(--text-3);
  }

  .rlm-live {
    padding: 2px var(--space-sm);
    background: var(--forest-light);
    border-radius: var(--radius-sm);
    gap: var(--space-sm);
  }

  .rlm-metric {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
  }

  .rlm-metric-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-3);
    letter-spacing: 0.03em;
  }

  .annotation-current {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--forest);
    text-transform: uppercase;
    padding: 2px var(--space-sm);
    background: var(--forest-light);
    border-radius: var(--radius-sm);
  }

  .annotation-group {
    display: flex;
    gap: 0;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .annotation-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    padding: var(--space-xs) var(--space-md);
    border: none;
    border-right: 1px solid var(--card-border);
    background: var(--card);
    color: var(--text-2);
    cursor: pointer;
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .annotation-btn:last-child {
    border-right: none;
  }

  .annotation-btn:hover {
    background: var(--forest-light);
    color: var(--forest);
  }

  .annotation-btn:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: -2px;
  }

  .annotation-btn.active {
    background: var(--forest);
    color: #fff;
  }

  .key-hint {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    font-size: 0.65rem;
    font-family: var(--font-mono);
    font-weight: 700;
    border-radius: var(--radius-sm);
    background: rgba(0, 0, 0, 0.06);
    color: var(--text-3);
    margin-left: 2px;
  }

  .annotation-btn.active .key-hint {
    background: rgba(255, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.8);
  }
</style>
