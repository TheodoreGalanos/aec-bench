<!-- ABOUTME: Library page showing template cards filtered by discipline. -->
<!-- ABOUTME: Fetches from /api/library; discipline filter buttons control which templates are shown. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchLibraryList } from "../lib/api";
  import type { LibraryListData, Template } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  let data: LibraryListData | null = $state(null);
  let selectedDiscipline: string = $state("");

  async function loadData() {
    data = null;
    data = await fetchLibraryList(selectedDiscipline ? { discipline: selectedDiscipline } : undefined);
    if (!selectedDiscipline && data?.selected_discipline) {
      selectedDiscipline = data.selected_discipline;
    }
  }

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    selectedDiscipline = params.get("discipline") ?? "";
    loadData();
  });

  function selectDiscipline(discipline: string) {
    selectedDiscipline = discipline === selectedDiscipline ? "" : discipline;
    loadData();
  }

  function navigate(path: string) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  let filteredTemplates = $derived.by((): Template[] => data?.templates ?? []);
</script>

<section class="page-header">
  <h1>Template Library</h1>
  {#if data}
    <span class="template-count">{filteredTemplates.length} templates</span>
  {/if}
</section>

<!-- Discipline filter buttons -->
{#if data && data.disciplines.length > 0}
  <div class="discipline-filters" role="group" aria-label="Discipline filter">
    <button
      class="discipline-btn"
      class:active={selectedDiscipline === ""}
      onclick={() => selectDiscipline("")}
    >
      All
    </button>
    {#each data.disciplines as disc (disc)}
      <button
        class="discipline-btn"
        class:active={selectedDiscipline === disc}
        onclick={() => selectDiscipline(disc)}
      >
        {disc}
      </button>
    {/each}
  </div>
{/if}

<!-- Template cards -->
{#if data === null}
  <div class="cards-grid">
    {#each [1, 2, 3, 4, 5, 6] as _}
      <Card>
        <div class="skeleton-card">
          <Skeleton height="1.1rem" width="70%" />
          <Skeleton height="0.9rem" width="90%" />
          <Skeleton height="0.9rem" width="50%" />
        </div>
      </Card>
    {/each}
  </div>
{:else if filteredTemplates.length === 0}
  <Card>
    <div class="empty-state">
      <p>No templates available.</p>
      {#if selectedDiscipline}
        <p class="empty-hint">Try selecting a different discipline or clear the filter.</p>
      {:else}
        <p class="empty-hint">Run <code>aec-bench generate template</code> to create one.</p>
      {/if}
    </div>
  </Card>
{:else}
  <div class="cards-grid">
    {#each filteredTemplates as template (`${template.discipline}::${template.task_id}`)}
      <Card hoverable>
        <button
          class="template-card"
          onclick={() => navigate(`/library/${template.discipline}/${template.task_id}`)}
          type="button"
        >
          <div class="card-header">
            <span class="template-id">{template.task_id}</span>
            <span class="discipline-pill">{template.discipline}</span>
          </div>

          {#if template.description}
            <p class="template-desc">{template.description}</p>
          {/if}

          <div class="card-footer">
            <div class="tag-row">
              {#each template.tags.slice(0, 4) as tag (tag)}
                <Badge text={tag} />
              {/each}
              {#if template.tags.length > 4}
                <span class="more-tags">+{template.tags.length - 4}</span>
              {/if}
            </div>
            <span class="param-count">{template.param_count} params</span>
          </div>
        </button>
      </Card>
    {/each}
  </div>
{/if}

<style>
  .page-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
  }

  .page-header h1 {
    font-family: var(--font-heading);
    font-size: 1.75rem;
  }

  .template-count {
    font-size: 0.875rem;
    color: var(--text-3);
  }

  .discipline-filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
  }

  .discipline-btn {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 9999px;
    padding: var(--space-xs) var(--space-md);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    color: var(--text-2);
    text-transform: capitalize;
    transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
  }

  .discipline-btn:hover {
    background: var(--forest-light);
    color: var(--forest);
    border-color: var(--forest);
  }

  .discipline-btn.active {
    background: var(--forest);
    color: #fff;
    border-color: var(--forest);
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-md);
  }

  .template-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-sm);
  }

  .template-id {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.85rem;
    color: var(--text);
    word-break: break-all;
    line-height: 1.4;
  }

  .discipline-pill {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--forest);
    background: var(--forest-light);
    border-radius: 9999px;
    padding: 2px 8px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .template-desc {
    font-size: 0.85rem;
    color: var(--text-2);
    line-height: 1.5;
    flex: 1;
    /* Clamp to 3 lines */
    line-clamp: 3;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-footer {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-sm);
    margin-top: auto;
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }

  .more-tags {
    font-size: 0.7rem;
    color: var(--text-3);
  }

  .param-count {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-3);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .skeleton-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }

  .empty-hint {
    margin-top: var(--space-xs);
    font-size: 0.875rem;
  }

  .empty-hint code {
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 1px var(--space-xs);
    border-radius: var(--radius-sm);
  }
</style>
