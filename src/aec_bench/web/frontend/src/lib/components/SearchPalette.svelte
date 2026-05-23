<!-- ABOUTME: Global ⌘K search overlay — fades the page, centres a search input. -->
<!-- ABOUTME: Queries /api/search and groups results by type; arrow keys navigate. -->
<script lang="ts">
  import { paletteStore } from "../stores/palette.svelte";
  import { fetchSearch } from "../api";
  import type { SearchData, TrialSearchResult, ExperimentSearchResult, WorkspaceSearchResult } from "../types";

  let inputEl: HTMLInputElement | undefined = $state();
  let results: SearchData | null = $state(null);
  let activeIndex = $state(0);
  let fetchSeq = 0;

  // Focus the input each time the palette opens; reset state.
  $effect(() => {
    if (paletteStore.isOpen) {
      results = null;
      activeIndex = 0;
      // Defer to next tick so the input exists in the DOM.
      queueMicrotask(() => inputEl?.focus());
    }
  });

  // Global Escape listener (the palette is mounted in App.svelte at root).
  $effect(() => {
    if (typeof window === "undefined") return;
    function onKey(e: KeyboardEvent) {
      if (!paletteStore.isOpen) return;
      if (e.key === "Escape") {
        e.preventDefault();
        paletteStore.close();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function runSearch() {
    const seq = ++fetchSeq;
    const q = paletteStore.query.trim();
    if (!q) {
      results = null;
      return;
    }
    const data = await fetchSearch({ q });
    if (seq !== fetchSeq) return; // stale response, discard
    results = data;
    activeIndex = 0;
  }

  // Group order is fixed by design: Templates · Datasets · Experiments · Workspaces · Trials.
  // Templates/Datasets lead because they're the narrowest matches (exact vocabulary).
  // Trials trail because they can be the most numerous; placing them last avoids pushing
  // other groups off-screen. See docs/superpowers/specs/2026-04-15-search-index-extension.md.
  let allResults = $derived.by(() => {
    if (!results) return [] as { kind: string; label: string; href: string }[];
    const items: { kind: string; label: string; href: string }[] = [];
    for (const r of results.template_results) {
      const tid = (r as any).task_id ?? (r as any).name ?? "unknown";
      const disc = (r as any).discipline ?? "";
      const id = String(tid).split("/").slice(1).join("/") || tid;
      items.push({ kind: "Template", label: `${disc}/${id}`, href: `/library/${disc}/${id}` });
    }
    for (const r of results.dataset_results) {
      const name = (r as any).name ?? "unknown";
      const ver = (r as any).version ?? "unknown";
      items.push({ kind: "Dataset", label: `${name} v${ver}`, href: `/datasets/${name}/${ver}` });
    }
    for (const r of (results.experiment_results ?? []) as ExperimentSearchResult[]) {
      items.push({
        kind: "Experiment",
        label: `${r.experiment_id} · n=${r.trial_count}`,
        href: `/?experiment=${encodeURIComponent(r.experiment_id)}`,
      });
    }
    for (const r of (results.workspace_results ?? []) as WorkspaceSearchResult[]) {
      items.push({
        kind: "Workspace",
        label: r.name + (r.has_swarm ? " · swarm" : ""),
        href: `/evolution/${encodeURIComponent(r.path)}`,
      });
    }
    for (const r of (results.trial_results ?? []) as TrialSearchResult[]) {
      items.push({
        kind: "Trial",
        label: `${r.trial_id} · ${r.model}`,
        href: `/viewer/${encodeURIComponent(r.experiment_id)}/${encodeURIComponent(r.trial_id)}`,
      });
    }
    return items;
  });

  function navigate(href: string) {
    window.history.pushState({}, "", href);
    window.dispatchEvent(new PopStateEvent("popstate"));
    paletteStore.close();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, Math.max(0, allResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (e.key === "Enter" && allResults[activeIndex]) {
      e.preventDefault();
      navigate(allResults[activeIndex].href);
    } else if (e.key === "Tab") {
      // Single-element trap: keep focus on the input.
      e.preventDefault();
      inputEl?.focus();
    }
  }
</script>

{#if paletteStore.isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="palette-overlay" onclick={() => paletteStore.close()} role="presentation">
    <!-- svelte-ignore a11y_interactive_supports_focus -->
    <div class="palette" role="dialog" aria-modal="true" aria-label="Search" onclick={(e) => e.stopPropagation()}>
      <input
        bind:this={inputEl}
        bind:value={paletteStore.query}
        oninput={runSearch}
        onkeydown={onKey}
        placeholder="What are you looking for?"
        class="palette-input"
        aria-label="Search query"
        aria-controls="palette-results"
        aria-activedescendant={allResults[activeIndex] ? `palette-result-${activeIndex}` : undefined}
        role="combobox"
        aria-expanded={allResults.length > 0}
        aria-autocomplete="list"
      />
      {#if allResults.length > 0}
        <ul class="palette-results" id="palette-results" role="listbox">
          {#each allResults as item, i (item.href)}
            <li
              id={`palette-result-${i}`}
              class="palette-item"
              class:active={i === activeIndex}
              onclick={() => navigate(item.href)}
              role="option"
              aria-selected={i === activeIndex}
            >
              <span class="palette-kind">{item.kind}</span>
              <span class="palette-label">{item.label}</span>
            </li>
          {/each}
        </ul>
      {:else if paletteStore.query.trim()}
        <p class="palette-empty">No results.</p>
      {/if}
    </div>
  </div>
{/if}

<style>
  .palette-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(2px);
    z-index: 1000;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    animation: fade-in 120ms ease-out;
  }
  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  .palette {
    width: 600px;
    max-width: calc(100vw - 32px);
    background: var(--card);
    border-radius: var(--radius-md);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    overflow: hidden;
  }
  .palette-input {
    width: 100%;
    padding: var(--space-md);
    border: none;
    outline: none;
    font-size: 1.1rem;
    border-bottom: 1px solid var(--card-border);
    font-family: var(--font-body);
  }
  .palette-results {
    list-style: none;
    margin: 0;
    padding: var(--space-xs) 0;
    max-height: 50vh;
    overflow-y: auto;
  }
  .palette-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    cursor: pointer;
  }
  .palette-item.active,
  .palette-item:hover {
    background: var(--bg-alt);
  }
  .palette-kind {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-3);
    min-width: 70px;
  }
  .palette-label {
    font-family: var(--font-mono);
    font-size: 0.88rem;
  }
  .palette-empty {
    padding: var(--space-md);
    color: var(--text-3);
    text-align: center;
  }
</style>
