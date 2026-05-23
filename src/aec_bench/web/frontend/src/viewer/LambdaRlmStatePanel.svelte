<!-- ABOUTME: Right-column panel for lambda-RLM trials showing deterministic pipeline state. -->
<!-- ABOUTME: Displays stats line and section pipeline with phase dots, detail modals on click. -->
<script lang="ts">
  import type { StepSummary, LambdaRlmState } from "../lib/types";
  import SectionPipeline from "./SectionPipeline.svelte";

  interface Props {
    steps: StepSummary[];
    activeStep: number;
    planState: LambdaRlmState | null;
    openModal: (title: string, content: string) => void;
  }

  let { steps, activeStep, planState, openModal }: Props = $props();

  // Get plan_state from the active step's metadata, falling back to global planState
  let activePlanState = $derived.by(() => {
    const currentStep = steps.find((s) => s.step === activeStep);
    const stepPlan = currentStep?.metadata?.plan_state;
    if (stepPlan) return stepPlan;
    return planState?.plan_state ?? null;
  });

  // Stats line
  let statsText = $derived.by(() => {
    if (!activePlanState) return "";
    const calls = activePlanState.llm_calls ?? 0;
    const estimated = activePlanState.estimated_calls ?? 0;
    const tokens = activePlanState.tokens_used ?? 0;
    const callsLabel = estimated > 0 ? `${calls}/${estimated}` : `${calls}`;
    const tokensLabel = tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}K` : `${tokens}`;
    return `${callsLabel} calls \u00b7 ${tokensLabel} tokens`;
  });

  // Build section rows from plan_state
  let sectionRows = $derived.by(() => {
    if (!activePlanState) return [];
    const extractions = activePlanState.extractions ?? {};
    const reviews = activePlanState.reviews ?? {};
    const sections = activePlanState.sections ?? {};
    const currentSection = activePlanState.current_section;
    const phase = activePlanState.phase;

    // Get section order from template_progress if available
    const currentStep = steps.find((s) => s.step === activeStep);
    const tp = currentStep?.metadata?.template_progress;
    const sectionList = tp?.section_list ?? [];

    // If no section_list, derive from plan_state keys
    const allSectionIds: string[] = sectionList.length > 0
      ? sectionList.map((s: any) => s.id)
      : [...new Set([
          ...Object.keys(extractions),
          ...Object.keys(reviews),
          ...Object.keys(sections),
          ...(currentSection ? [currentSection] : []),
        ])];

    return allSectionIds.map((id: string) => {
      const hasExtraction = id in extractions;
      const hasReview = id in reviews;
      const hasGeneration = id in sections;
      const isCurrent = id === currentSection;

      let extractStatus = "pending";
      let reviewStatus = "pending";
      let generateStatus = "pending";

      if (hasExtraction) extractStatus = "done";
      if (isCurrent && phase === "extract") extractStatus = "active";

      if (hasReview) {
        const review = reviews[id];
        reviewStatus = review?.gaps?.length > 0 ? "gaps" : "done";
      }
      if (isCurrent && phase === "review") reviewStatus = "active";

      if (hasGeneration) generateStatus = "done";
      if (isCurrent && phase === "generate") generateStatus = "active";

      return {
        id,
        phases: { extract: extractStatus, review: reviewStatus, generate: generateStatus },
        skipped: false,
        current: isCurrent,
      };
    });
  });

  function handleSectionSelect(sectionId: string) {
    if (!activePlanState) return;
    const extractions = activePlanState.extractions ?? {};
    const reviews = activePlanState.reviews ?? {};
    const sections = activePlanState.sections ?? {};

    const lines: string[] = [];

    // Extraction section
    const sectionExtractions = extractions[sectionId];
    if (sectionExtractions) {
      lines.push("## Extraction\n");
      const sources = Object.keys(sectionExtractions);
      lines.push(`Sources: ${sources.join(", ")}`);
      for (const [source, data] of Object.entries(sectionExtractions)) {
        if (data && typeof data === "object") {
          const fields = Object.keys(data as Record<string, any>);
          lines.push(`  ${source}: ${fields.join(", ")}`);
        }
      }
      lines.push("");
    }

    // Review section
    const review = reviews[sectionId];
    if (review) {
      lines.push("## Review\n");
      lines.push(`Status: ${review.status}`);
      if (review.gaps?.length > 0) {
        lines.push(`Gaps: ${review.gaps.join("; ")}`);
      }
      if (review.risks?.length > 0) {
        lines.push(`Risks: ${review.risks.join("; ")}`);
      }
      lines.push("");
    }

    // Generation section
    const content = sections[sectionId];
    if (content) {
      lines.push("## Generation\n");
      lines.push(`Content: ${content}`);
    }

    if (lines.length === 0) {
      lines.push("No data yet for this section.");
    }

    openModal(`Section: ${sectionId}`, lines.join("\n"));
  }
</script>

<div class="lambda-rlm-panel" data-testid="lambda-rlm-state-panel">
  {#if !activePlanState}
    <div class="empty-panel">Select a step to view pipeline state.</div>
  {:else}
    {#if statsText}
      <div class="stats-line" data-testid="lambda-stats">
        {statsText}
      </div>
    {/if}

    <div class="panel-section">
      <h3 class="panel-heading">Pipeline</h3>
      <div class="phase-legend">
        <span class="legend-item"><span class="legend-dot extract"></span>Extract</span>
        <span class="legend-item"><span class="legend-dot review"></span>Review</span>
        <span class="legend-item"><span class="legend-dot generate"></span>Generate</span>
      </div>
      <SectionPipeline sections={sectionRows} onselect={handleSectionSelect} />
    </div>
  {/if}
</div>

<style>
  .lambda-rlm-panel {
    overflow-y: auto;
    height: 100%;
    padding: var(--space-md);
    background: var(--card);
  }

  .stats-line {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    padding: var(--space-sm) 0;
    margin-bottom: var(--space-md);
    border-bottom: 1px solid var(--card-border);
  }

  .panel-section {
    margin-bottom: var(--space-lg);
  }

  .panel-heading {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-family: var(--font-heading);
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--forest);
    margin-bottom: 10px;
  }

  .phase-legend {
    display: flex;
    gap: var(--space-md);
    margin-bottom: var(--space-sm);
    font-size: 0.7rem;
    color: var(--text-3);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .legend-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .legend-dot.extract { background: var(--forest); }
  .legend-dot.review { background: var(--forest); }
  .legend-dot.generate { background: var(--forest); }

  .empty-panel {
    font-size: 0.85rem;
    color: var(--text-3);
    font-style: italic;
    padding: var(--space-lg) var(--space-md);
    text-align: center;
  }
</style>
