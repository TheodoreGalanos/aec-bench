<!-- ABOUTME: Section list with per-section phase dots showing Extract/Review/Generate progress. -->
<!-- ABOUTME: Reflects the deterministic pipeline structure of lambda-RLM execution. -->
<script lang="ts">
  interface SectionRow {
    id: string;
    phases: { extract: string; review: string; generate: string };
    skipped: boolean;
    current: boolean;
  }

  interface Props {
    sections: SectionRow[];
    onselect: (sectionId: string) => void;
  }

  let { sections, onselect }: Props = $props();

  function dotClass(status: string): string {
    if (status === "done") return "dot-done";
    if (status === "active") return "dot-active";
    if (status === "gaps") return "dot-gaps";
    return "dot-pending";
  }
</script>

<div class="section-pipeline" data-testid="section-pipeline">
  {#each sections as section}
    <button
      class="section-row"
      class:skipped={section.skipped}
      class:current={section.current}
      onclick={() => onselect(section.id)}
      data-testid="section-row-{section.id}"
    >
      {#if section.skipped}
        <span class="dots skipped-dots">
          <span class="dash">--</span>
          <span class="dash">--</span>
        </span>
      {:else}
        <span class="dots">
          <span class="dot {dotClass(section.phases.extract)}" title="Extract"></span>
          <span class="dot {dotClass(section.phases.review)}" title="Review"></span>
          <span class="dot {dotClass(section.phases.generate)}" title="Generate"></span>
        </span>
      {/if}
      <span class="section-label">{section.id}</span>
    </button>
  {/each}
</div>

<style>
  .section-pipeline {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .section-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 4px var(--space-xs);
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
    text-align: left;
    width: 100%;
  }

  .section-row:hover {
    background: var(--bg-alt);
  }

  .section-row.current {
    background: color-mix(in srgb, var(--forest) 10%, transparent);
  }

  .section-row.skipped {
    opacity: 0.45;
    cursor: default;
  }

  .dots {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    transition: background var(--transition-fast);
  }

  .dot-pending {
    background: var(--card-border);
  }

  .dot-active {
    background: var(--forest);
    animation: pulse 1.5s infinite;
  }

  .dot-done {
    background: var(--forest);
  }

  .dot-gaps {
    background: var(--reward-zero);
  }

  .dash {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-3);
    line-height: 8px;
  }

  .skipped-dots {
    gap: 2px;
  }

  .section-label {
    font-size: 0.78rem;
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .section-row.current .section-label {
    color: var(--forest);
    font-weight: 600;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
