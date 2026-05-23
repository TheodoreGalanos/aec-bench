<!-- ABOUTME: Trial information panel showing task details, scores, cost, and artefact thumbnails. -->
<!-- ABOUTME: Serves as the right column for non-RLM trials, or bottom section for RLM trials. -->
<script lang="ts">
  import type { ViewerMeta } from "../lib/types";
  import RewardBadge from "../lib/components/RewardBadge.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import { ScrollText, Database, FlaskConical, ClipboardCheck } from "lucide-svelte";

  interface Props {
    trial: ViewerMeta;
    artefacts: string[];
    openModal: (title: string, content: string) => void;
  }

  let { trial, artefacts, openModal }: Props = $props();

  // Track which artefact is shown in a full-size lightbox
  let lightboxSrc: string | null = $state(null);

  function formatTokens(n: number | null): string {
    if (n === null) return "-";
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
  }

  // Derive lateral link targets from trial fields.
  // task_id format: "<discipline>/<template>/<instance>"
  const templateParts = $derived.by(() => {
    const parts = trial.task_id.split("/");
    const discipline = parts[0] ?? "";
    const tplId = parts[1] ?? "";
    const hasTemplate = parts.length >= 2 && discipline && tplId;
    return {
      discipline,
      templateId: tplId,
      href: hasTemplate ? `/library/${discipline}/${tplId}` : null,
    };
  });

  // dataset_id format: "name@version" or null for inline runs
  const datasetParts = $derived.by(() => {
    if (!trial.dataset_id) return { name: "", version: "", href: null };
    const at = trial.dataset_id.indexOf("@");
    if (at <= 0) return { name: "", version: "", href: null };
    const name = trial.dataset_id.slice(0, at);
    const version = trial.dataset_id.slice(at + 1);
    return { name, version, href: `/datasets/${name}/${version}` };
  });

  const experimentHref = $derived(`/?experiment=${encodeURIComponent(trial.experiment_id)}`);
  const reviewHref = $derived(`/review/trials/${encodeURIComponent(trial.trial_id)}`);

  function handleArtefactClick(src: string) {
    lightboxSrc = src;
  }

  function closeLightbox() {
    lightboxSrc = null;
  }
</script>

<div class="info-panel" data-testid="info-panel">
  <!-- Task info -->
  <div class="panel-section">
    <h3 class="panel-heading">Task</h3>
    <dl class="info-dl">
      <dt>Task ID</dt>
      <dd class="mono">{trial.task_id}</dd>

      <dt>Model</dt>
      <dd>
        <Badge text={trial.model} />
      </dd>

      <dt>Adapter</dt>
      <dd>
        <Badge text={trial.adapter} />
      </dd>
    </dl>
  </div>

  <!-- Score -->
  <div class="panel-section">
    <h3 class="panel-heading">Score</h3>
    <div class="score-row">
      <RewardBadge reward={trial.reward} />
    </div>
  </div>

  <!-- Cost -->
  {#if trial.tokens_in !== null || trial.tokens_out !== null || trial.total_tokens !== null}
    <div class="panel-section">
      <h3 class="panel-heading">Cost</h3>
      <dl class="info-dl">
        {#if trial.tokens_in !== null}
          <dt>Tokens In</dt>
          <dd class="mono">{formatTokens(trial.tokens_in)}</dd>
        {/if}
        {#if trial.tokens_out !== null}
          <dt>Tokens Out</dt>
          <dd class="mono">{formatTokens(trial.tokens_out)}</dd>
        {/if}
        {#if trial.total_tokens !== null}
          <dt>Total</dt>
          <dd class="mono">{formatTokens(trial.total_tokens)}</dd>
        {/if}
      </dl>
    </div>
  {/if}

  <!-- Artefacts -->
  {#if artefacts.length > 0}
    <div class="panel-section">
      <h3 class="panel-heading">Artefacts</h3>
      <div class="artefact-grid">
        {#each artefacts as src}
          <button
            class="artefact-thumb-button"
            onclick={() => handleArtefactClick(src)}
            type="button"
          >
            <img
              class="artefact-thumb"
              {src}
              alt="Trial artefact"
              data-testid="artefact-thumb"
            />
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Related lateral links -->
  <div class="panel-section related-section">
    <h3 class="panel-heading">Related</h3>
    <ul class="related-links">
      {#if templateParts.href}
        <li>
          <a href={templateParts.href} class="related-link">
            <ScrollText size={14} aria-hidden="true" />
            <span>Template: {templateParts.discipline}/{templateParts.templateId}</span>
          </a>
        </li>
      {/if}
      {#if datasetParts.href}
        <li>
          <a href={datasetParts.href} class="related-link">
            <Database size={14} aria-hidden="true" />
            <span>Dataset: {datasetParts.name} v{datasetParts.version}</span>
          </a>
        </li>
      {/if}
      <li>
        <a href={experimentHref} class="related-link">
          <FlaskConical size={14} aria-hidden="true" />
          <span>Experiment: {trial.experiment_id}</span>
        </a>
      </li>
      <li>
        <a href={reviewHref} class="related-link">
          <ClipboardCheck size={14} aria-hidden="true" />
          <span>Review this trial</span>
        </a>
      </li>
    </ul>
  </div>
</div>

<!-- Image lightbox modal -->
{#if lightboxSrc}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="lightbox-backdrop"
    data-testid="lightbox-backdrop"
    onclick={closeLightbox}
    role="presentation"
  >
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="lightbox-content" onclick={(e) => e.stopPropagation()}>
      <button class="lightbox-close" onclick={closeLightbox} aria-label="Close lightbox">&times;</button>
      <img
        class="lightbox-img"
        src={lightboxSrc}
        alt="Artefact full view"
        data-testid="lightbox-img"
      />
    </div>
  </div>
{/if}

<style>
  .info-panel {
    overflow-y: auto;
    height: 100%;
    padding: var(--space-md);
    background: var(--card);
  }

  .panel-section {
    margin-bottom: var(--space-lg);
    padding-bottom: var(--space-md);
    border-bottom: 1px solid var(--card-border);
  }

  .panel-section:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .panel-heading {
    font-family: var(--font-heading);
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--forest);
    margin-bottom: 10px;
  }

  .info-dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-xs) var(--space-md);
    font-size: 0.82rem;
  }

  .info-dl dt {
    font-weight: 500;
    color: var(--text-3);
    white-space: nowrap;
  }

  .info-dl dd {
    color: var(--text);
  }

  .info-dl .mono {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    word-break: break-all;
    overflow-wrap: anywhere;
  }

  .score-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .artefact-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-sm);
  }

  .artefact-thumb-button {
    display: block;
    width: 100%;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
  }

  .artefact-thumb {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    border-radius: var(--radius-sm);
    border: 1px solid var(--card-border);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .artefact-thumb-button:hover .artefact-thumb,
  .artefact-thumb-button:focus-visible .artefact-thumb {
    border-color: var(--forest);
    box-shadow: var(--shadow-md);
  }

  /* Lightbox overlay for full-size artefact images */
  .lightbox-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
    animation: fade-in var(--transition-normal) ease;
  }

  .lightbox-content {
    position: relative;
    max-width: 90vw;
    max-height: 85vh;
  }

  .lightbox-close {
    position: absolute;
    top: -12px;
    right: -12px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: none;
    background: var(--card);
    color: var(--text);
    font-size: 1.2rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-md);
    transition: background var(--transition-fast);
    z-index: 1;
  }

  .lightbox-close:hover {
    background: var(--bg-alt);
  }

  .lightbox-close:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
  }

  .lightbox-img {
    max-width: 90vw;
    max-height: 80vh;
    object-fit: contain;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .related-links {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .related-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    color: var(--forest);
    text-decoration: none;
    font-size: 0.82rem;
    line-height: 1.3;
    padding: 2px 0;
    border-radius: var(--radius-sm);
    transition: color var(--transition-fast);
  }

  .related-link:hover {
    color: var(--forest-hover, var(--forest));
    text-decoration: underline;
  }

  .related-link:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
  }

  .related-link > span {
    word-break: break-word;
  }
</style>
