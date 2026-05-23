<!-- ABOUTME: Library template detail page showing description, standards, and input/output tables. -->
<!-- ABOUTME: Fetches from /api/library/{discipline}/{templateId} using route params as props. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchLibraryDetail } from "../lib/api";
  import type { LibraryDetailData, Template, TemplateIO } from "../lib/types";
  import Card from "../lib/components/Card.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";
  import DetailShell from "../lib/components/DetailShell.svelte";

  interface Props {
    discipline: string;
    templateId: string;
  }

  let { discipline, templateId }: Props = $props();

  let data: LibraryDetailData | null = $state(null);

  onMount(async () => {
    data = await fetchLibraryDetail(discipline, templateId);
  });
</script>

{#if data === null}
  <div class="skeleton-page">
    <Skeleton height="2rem" width="50%" />
    <Skeleton height="1rem" width="30%" />
    <Skeleton height="8rem" />
    <Skeleton height="6rem" />
  </div>
{:else}
  {@const template = data.template}
  <DetailShell
    backHref="/library"
    backLabel="Library"
    crumbs={[{ label: template.discipline }]}
    title={template.task_id}
  >
    <section class="page-header-meta">
      <div class="title-row">
        <span class="discipline-pill">{template.discipline}</span>
        <span class="param-badge">{template.param_count} params</span>
      </div>

      {#if template.description}
        <p class="template-description">{template.description}</p>
      {/if}

      <div class="tag-row">
        {#each template.tags as tag (tag)}
          <Badge text={tag} />
        {/each}
      </div>
    </section>

    <div class="detail-grid">
      <!-- Long description -->
      {#if template.long_description}
        <Card>
          <h2 class="section-heading">Description</h2>
          <p class="long-desc">{template.long_description}</p>
        </Card>
      {/if}

      <!-- Standards -->
      {#if template.standards.length > 0}
        <Card>
          <h2 class="section-heading">Standards</h2>
          <ul class="standards-list">
            {#each template.standards as standard (standard)}
              <li class="standard-item">{standard}</li>
            {/each}
          </ul>
        </Card>
      {/if}

      <!-- Inputs -->
      {#if template.inputs.length > 0}
        <Card padding="0">
          <div class="table-header">
            <h2 class="section-heading table-heading">Inputs</h2>
          </div>
          <table class="io-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {#each template.inputs as input (input.name)}
                <tr>
                  <td class="io-name">{input.name}</td>
                  <td class="io-desc">{input.description}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Card>
      {/if}

      <!-- Outputs -->
      {#if template.outputs.length > 0}
        <Card padding="0">
          <div class="table-header">
            <h2 class="section-heading table-heading">Outputs</h2>
          </div>
          <table class="io-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {#each template.outputs as output (output.name)}
                <tr>
                  <td class="io-name">{output.name}</td>
                  <td class="io-desc">{output.description}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Card>
      {/if}
    </div>
  </DetailShell>
{/if}

<style>
  .skeleton-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .page-header-meta {
    margin-bottom: var(--space-md);
  }

  .title-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
    flex-wrap: wrap;
  }

  .discipline-pill {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--forest);
    background: var(--forest-light);
    border-radius: 9999px;
    padding: 2px 10px;
  }

  .param-badge {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-3);
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    padding: 1px 8px;
  }

  .template-description {
    font-size: 0.9rem;
    color: var(--text-2);
    margin-bottom: var(--space-sm);
    line-height: 1.6;
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .detail-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .section-heading {
    font-family: var(--font-heading);
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: var(--space-sm);
  }

  .table-heading {
    padding: var(--space-md) var(--space-md) 0;
    margin-bottom: 0;
  }

  .long-desc {
    font-size: 0.9rem;
    color: var(--text-2);
    line-height: 1.7;
    white-space: pre-wrap;
  }

  .standards-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .standard-item {
    font-size: 0.875rem;
    color: var(--text-2);
    padding-left: var(--space-md);
    position: relative;
  }

  .standard-item::before {
    content: "→";
    position: absolute;
    left: 0;
    color: var(--forest);
    font-weight: 700;
  }

  /* IO table */
  .io-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  thead {
    background: var(--bg-alt);
  }

  th {
    padding: var(--space-sm) var(--space-md);
    font-family: var(--font-heading);
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-2);
    border-bottom: 1px solid var(--card-border);
    border-top: 1px solid var(--card-border);
    text-align: left;
  }

  td {
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    vertical-align: top;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  tbody tr:hover {
    background: var(--bg-alt);
  }

  .io-name {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    width: 200px;
  }

  .io-desc {
    font-size: 0.875rem;
    color: var(--text-2);
    line-height: 1.5;
  }
</style>
