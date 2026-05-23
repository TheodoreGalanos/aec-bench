<!-- ABOUTME: Header shell for EvolutionDetail — back link, workspace/run dropdowns, tab strip. -->
<!-- ABOUTME: Pure presentational; parent wires callbacks to store mutations and navigation. -->
<script lang="ts">
  import type { EvolutionTab } from "../lib/stores/evolution-detail.svelte";
  import ArrowLeft from "lucide-svelte/icons/arrow-left";
  import RefreshCw from "lucide-svelte/icons/refresh-cw";
  import ArchiveIcon from "lucide-svelte/icons/archive";
  import Skull from "lucide-svelte/icons/skull";
  import Zap from "lucide-svelte/icons/zap";
  import type { ComponentType } from "svelte";

  type WorkspaceRef = { name: string; path: string };
  type RunRef = { run_id: string; strategy: string; cycles: number; best_score: number; final_score: number };

  interface Props {
    workspace: string;                 // active workspace path
    workspaces: WorkspaceRef[];        // all workspaces for the dropdown
    runs: RunRef[];                    // runs for the active workspace
    activeRunId: string | null;
    activeTab: EvolutionTab;
    hasSwarm: boolean;
    onWorkspaceChange: (path: string) => void;
    onRunChange: (run_id: string) => void;
    onTabChange: (tab: EvolutionTab) => void;
  }
  let {
    workspace, workspaces, runs,
    activeRunId, activeTab, hasSwarm,
    onWorkspaceChange, onRunChange, onTabChange,
  }: Props = $props();

  // Most-recent-first by path (date-prefix convention)
  let sortedWorkspaces = $derived.by(() =>
    [...workspaces].sort((a, b) => b.path.localeCompare(a.path)),
  );

  const tabIcons: Record<string, ComponentType> = {
    cycles: RefreshCw,
    archive: ArchiveIcon,
    graveyard: Skull,
    swarm: Zap,
  };

  let tabs = $derived.by(() => {
    const base: Array<{ id: EvolutionTab; label: string }> = [
      { id: "cycles", label: "Cycles" },
      { id: "archive", label: "Archive" },
      { id: "graveyard", label: "Graveyard" },
    ];
    if (hasSwarm) base.push({ id: "swarm", label: "Swarm" });
    return base;
  });

  function handleWorkspace(e: Event) {
    onWorkspaceChange((e.target as HTMLSelectElement).value);
  }
  function handleRun(e: Event) {
    onRunChange((e.target as HTMLSelectElement).value);
  }
</script>

<header class="evo-header">
  <div class="row">
    <a href="/evolution" class="back-link"><ArrowLeft size={14} /> Workspaces</a>

    <label class="select-wrap">
      <span class="label">Workspace</span>
      <select value={workspace} onchange={handleWorkspace} aria-label="Workspace">
        {#each sortedWorkspaces as ws (ws.path)}
          <option value={ws.path}>{ws.name}</option>
        {/each}
      </select>
    </label>

    {#if runs.length > 0}
      <label class="select-wrap">
        <span class="label">Run</span>
        <select value={activeRunId ?? ""} onchange={handleRun} aria-label="Run">
          {#each runs as run (run.run_id)}
            <option value={run.run_id}>
              {run.run_id} · {run.strategy} · {run.cycles}c · {run.best_score.toFixed(2)}
            </option>
          {/each}
        </select>
      </label>
    {/if}
  </div>

  <div class="tabs" role="tablist">
    {#each tabs as t (t.id)}
      {@const Icon = tabIcons[t.id]}
      <button
        type="button"
        class="tab"
        class:active={t.id === activeTab}
        id={`evo-tab-${t.id}`}
        role="tab"
        aria-selected={t.id === activeTab}
        aria-controls={`evo-panel-${t.id}`}
        onclick={() => onTabChange(t.id)}
      >
        {#if Icon}
          <Icon size={14} />
        {/if}
        {t.label}
      </button>
    {/each}
  </div>
</header>

<style>
  .evo-header {
    border-bottom: 1px solid var(--card-border);
    background: var(--card);
  }
  .row {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-sm) var(--space-lg);
  }
  .back-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    color: var(--text-2);
    text-decoration: none;
    font-size: 0.88rem;
  }
  .back-link:hover { color: var(--text); }
  .select-wrap {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 0.78rem;
    color: var(--text-3);
  }
  /* Cap workspace/run dropdowns so they don't overflow the header bar */
  .select-wrap select {
    max-width: 280px;
  }
  .tabs {
    display: flex;
    gap: 0;
    padding: 0 var(--space-lg);
  }
  .tab {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    background: none;
    border: none;
    padding: var(--space-sm) var(--space-md);
    font-family: var(--font-heading);
    font-size: 0.88rem;
    color: var(--text-2);
    cursor: pointer;
    border-bottom: 2px solid transparent;
  }
  .tab:hover { color: var(--text); }
  .tab.active {
    color: var(--text);
    border-bottom-color: var(--forest);
  }
</style>
