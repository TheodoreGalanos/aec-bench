<!-- ABOUTME: Unified Evolution detail page — header + tabbed content (cycles/archive/graveyard/swarm). -->
<!-- ABOUTME: Replaces the dead-end pairs /evolution/:ws and /evolution/swarm/:ws with a single route. -->
<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchEvolutionData,
    fetchEvolutionRuns,
    fetchEvolutionWorkspaces,
    fetchEvolutionGraveyard,
    fetchEvolutionArchive,
    fetchEvolutionTree,
    fetchEvolutionFile,
    fetchEvolutionDiff,
  } from "../lib/api";
  import type {
    EvolutionData,
    EvolutionRunsData,
    EvolutionWorkspacesData,
    EvolutionWorkspaceSummary,
    GraveyardData,
    ArchiveData,
    EvolutionTreeData,
    FileContent,
    FileDiff,
  } from "../lib/types";
  import EvolutionHeader from "../evolution/EvolutionHeader.svelte";
  import EvoCyclesTab from "../evolution/EvoCyclesTab.svelte";
  import EvoArchive from "../evolution/EvoArchive.svelte";
  import EvoGraveyard from "../evolution/EvoGraveyard.svelte";
  import EvoSwarmTab from "../evolution/EvoSwarmTab.svelte";
  import { evolutionDetailStore } from "../lib/stores/evolution-detail.svelte";

  interface Props {
    workspace: string;
  }

  let { workspace }: Props = $props();

  // Core data
  let data: EvolutionData | null = $state(null);
  let runsData: EvolutionRunsData | null = $state(null);
  let workspacesData: EvolutionWorkspacesData | null = $state(null);
  let graveyardData: GraveyardData | null = $state(null);
  let archiveData: ArchiveData | null = $state(null);
  let treeData: EvolutionTreeData | null = $state(null);
  let fileContent: FileContent | null = $state(null);
  let fileDiff: FileDiff | null = $state(null);

  // UI state (not URL-synced)
  let activeCycle: number = $state(0);
  let activeFile: string | null = $state(null);
  let viewMode: "content" | "diff" = $state("content");
  let loadingTree: boolean = $state(false);
  let loadingFile: boolean = $state(false);

  // Derived: whether the active workspace has a swarm
  let activeWorkspaceSummary: EvolutionWorkspaceSummary | null = $derived.by(() =>
    (workspacesData?.workspaces ?? []).find(
      (w: EvolutionWorkspaceSummary) => w.path === workspace,
    ) ?? null,
  );
  let hasSwarm: boolean = $derived(activeWorkspaceSummary?.has_swarm ?? false);

  // Shorthand for current URL-synced tab
  let tab = $derived(evolutionDetailStore.state.tab);

  // Race guard: workspace-switch can dispatch two loadAll calls (popstate +
  // synthetic) with different workspace values. Discard any result whose
  // sequence number isn't the latest.
  let loadAllSeq = 0;

  async function loadAll(): Promise<void> {
    const seq = ++loadAllSeq;
    const runId = evolutionDetailStore.state.run_id;
    const [e, r, w, g, a] = await Promise.all([
      fetchEvolutionData(workspace, runId),
      fetchEvolutionRuns(workspace),
      fetchEvolutionWorkspaces(),
      fetchEvolutionGraveyard(workspace),
      fetchEvolutionArchive(workspace),
    ]);
    if (seq !== loadAllSeq) return;
    data = e;
    runsData = r;
    workspacesData = w;
    graveyardData = g;
    archiveData = a;
    // Select the first cycle automatically on load
    if (data && data.cycles.length > 0 && activeCycle === 0) {
      const firstCycle = data.cycles[0].cycle;
      activeCycle = firstCycle;
    }
  }

  async function loadTree(versionTag: string): Promise<void> {
    loadingTree = true;
    try {
      treeData = await fetchEvolutionTree(workspace, versionTag);
    } catch {
      treeData = null;
    } finally {
      loadingTree = false;
    }
  }

  async function loadFileOrDiff(versionTag: string, path: string): Promise<void> {
    loadingFile = true;
    try {
      if (viewMode === "diff") {
        fileDiff = await fetchEvolutionDiff(workspace, versionTag, path);
        fileContent = null;
      } else {
        fileContent = await fetchEvolutionFile(workspace, versionTag, path);
        fileDiff = null;
      }
    } catch {
      fileContent = null;
      fileDiff = null;
    } finally {
      loadingFile = false;
    }
  }

  onMount(() => {
    evolutionDetailStore.loadFromCurrentUrl();
    void loadAll();

    function onPopState(): void {
      evolutionDetailStore.loadFromCurrentUrl();
      void loadAll();
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  });

  // Re-fetch file tree when the active cycle changes (Cycles tab only)
  $effect(() => {
    if (data === null) return;
    if (tab !== "cycles") return;
    const cycle = data.cycles.find((c) => c.cycle === activeCycle);
    const version = cycle?.version_tag ?? "evo-0";
    void loadTree(version);
  });

  function handleWorkspaceChange(newWs: string): void {
    window.history.pushState({}, "", `/evolution2/${newWs}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function handleRunChange(newRun: string): void {
    evolutionDetailStore.setRun(newRun);
    void loadAll();
  }

  function handleTabChange(newTab: "cycles" | "archive" | "graveyard" | "swarm"): void {
    evolutionDetailStore.setTab(newTab);
  }

  function handleCycleChange(cycle: number): void {
    activeCycle = cycle;
    activeFile = null;
    fileContent = null;
    fileDiff = null;
  }

  function handleFileSelect(path: string): void {
    activeFile = path;
    const cycle = data?.cycles.find((c) => c.cycle === activeCycle);
    const version = cycle?.version_tag ?? "evo-0";
    void loadFileOrDiff(version, path);
  }

  function handleViewModeChange(mode: "content" | "diff"): void {
    viewMode = mode;
    if (activeFile) {
      const cycle = data?.cycles.find((c) => c.cycle === activeCycle);
      const version = cycle?.version_tag ?? "evo-0";
      void loadFileOrDiff(version, activeFile);
    }
  }
</script>

<section class="evo-detail">
  <EvolutionHeader
    {workspace}
    workspaces={(workspacesData?.workspaces ?? []).map((w) => ({ name: w.name, path: w.path }))}
    runs={runsData?.runs ?? []}
    activeRunId={evolutionDetailStore.state.run_id ?? null}
    activeTab={tab}
    {hasSwarm}
    onWorkspaceChange={handleWorkspaceChange}
    onRunChange={handleRunChange}
    onTabChange={handleTabChange}
  />

  <div class="evo-body" id="evo-panel-{tab}" role="tabpanel" aria-labelledby="evo-tab-{tab}">
    {#if tab === "cycles"}
      <EvoCyclesTab
        {data}
        {treeData}
        {fileContent}
        {fileDiff}
        {activeCycle}
        {activeFile}
        {viewMode}
        {loadingTree}
        {loadingFile}
        onCycleChange={handleCycleChange}
        onFileSelect={handleFileSelect}
        onViewModeChange={handleViewModeChange}
      />
    {:else if tab === "archive"}
      {#if archiveData}
        <EvoArchive data={archiveData} />
      {:else}
        <div class="placeholder">Loading archive…</div>
      {/if}
    {:else if tab === "graveyard"}
      <EvoGraveyard
        entries={graveyardData?.entries ?? []}
        total={graveyardData?.total ?? 0}
      />
    {:else if tab === "swarm" && hasSwarm}
      <EvoSwarmTab {workspace} active={tab === "swarm"} />
    {:else}
      <div class="placeholder">Select a tab above.</div>
    {/if}
  </div>
</section>

<style>
  .evo-detail {
    display: flex;
    flex-direction: column;
    height: calc(100vh - var(--navbar-height, 56px));
  }

  .evo-body {
    flex: 1;
    overflow: hidden;
  }

  .placeholder {
    padding: var(--space-xl);
    text-align: center;
    color: var(--text-3);
  }
</style>
