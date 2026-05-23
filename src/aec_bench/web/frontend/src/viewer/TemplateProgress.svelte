<!-- ABOUTME: Progress bar and section checklist for RLM template completion tracking. -->
<!-- ABOUTME: Shows a filled progress bar with "N / M sections" text and a list of filled/unfilled sections. -->
<script lang="ts">
  interface SectionInfo {
    id: string;
    filled: boolean;
  }

  interface Props {
    completed: number;
    total: number;
    sections: SectionInfo[];
  }

  let { completed, total, sections }: Props = $props();

  let pct = $derived(total > 0 ? (completed / total) * 100 : 0);
</script>

<div class="template-progress" data-testid="template-progress">
  <div class="progress-header">
    <span class="progress-text" data-testid="progress-text">{completed} / {total} sections</span>
  </div>

  <div class="progress-track">
    <div class="progress-fill" style:width="{pct}%"></div>
  </div>

  {#if sections.length > 0}
    <ul class="section-list">
      {#each sections as section}
        <li class="section-item" class:filled={section.filled} data-testid="section-{section.id}">
          <span class="section-icon">{section.filled ? "\u2713" : "\u2022"}</span>
          <span class="section-name" class:bold={section.filled}>{section.id}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .template-progress {
    padding: var(--space-sm) 0;
  }

  .progress-header {
    margin-bottom: var(--space-xs);
  }

  .progress-text {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }

  .progress-track {
    height: 8px;
    background: var(--bg-alt);
    border-radius: 9999px;
    overflow: hidden;
    margin-bottom: var(--space-sm);
  }

  .progress-fill {
    height: 100%;
    background: var(--forest);
    border-radius: 9999px;
    transition: width var(--transition-normal);
  }

  .section-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .section-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 0.78rem;
    color: var(--text-3);
    padding: 2px var(--space-xs);
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }

  .section-item.filled {
    color: var(--text);
  }

  .section-icon {
    font-size: 0.75rem;
    width: 16px;
    text-align: center;
  }

  .section-item.filled .section-icon {
    color: var(--forest);
    font-weight: 700;
  }

  .section-name.bold {
    font-weight: 600;
  }
</style>
