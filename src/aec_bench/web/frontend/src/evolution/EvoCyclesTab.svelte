<!-- ABOUTME: Cycles tab body — cycle bar, file tree, and content/diff viewer. -->
<!-- ABOUTME: Pure presentational; parent owns fetching and mutation. -->
<script lang="ts">
  import type {
    EvolutionData,
    EvolutionTreeData,
    FileContent,
    FileDiff,
  } from "../lib/types";
  import EvoCycleBar from "./EvoCycleBar.svelte";
  import EvoFileTree from "./EvoFileTree.svelte";
  import EvoContentViewer from "./EvoContentViewer.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  interface Props {
    data: EvolutionData | null;
    treeData: EvolutionTreeData | null;
    fileContent: FileContent | null;
    fileDiff: FileDiff | null;
    activeCycle: number;
    activeFile: string | null;
    viewMode: "content" | "diff";
    loadingTree: boolean;
    loadingFile: boolean;
    onCycleChange: (cycle: number) => void;
    onFileSelect: (path: string) => void;
    onViewModeChange: (mode: "content" | "diff") => void;
  }

  let {
    data,
    treeData,
    fileContent,
    fileDiff,
    activeCycle,
    activeFile,
    viewMode,
    loadingTree,
    loadingFile,
    onCycleChange,
    onFileSelect,
    onViewModeChange,
  }: Props = $props();
</script>

{#if data === null}
  <div class="placeholder">Loading cycles…</div>
{:else}
  <EvoCycleBar
    cycles={data.cycles}
    {activeCycle}
    workspaceName={data.workspace_name}
    model={data.model}
    onselect={onCycleChange}
  />

  <div class="evo-columns">
    <div class="col-tree">
      {#if loadingTree}
        <div class="tree-loading">
          <Skeleton height="1rem" width="60%" />
          <Skeleton height="1rem" width="80%" />
          <Skeleton height="1rem" width="50%" />
          <Skeleton height="1rem" width="70%" />
          <Skeleton height="1rem" width="40%" />
        </div>
      {:else if treeData}
        <EvoFileTree
          tree={treeData.tree}
          {activeFile}
          onselect={onFileSelect}
        />
      {:else}
        <div class="tree-empty">
          <p>No files found for this version.</p>
        </div>
      {/if}
    </div>

    <div class="col-content">
      <EvoContentViewer
        {fileContent}
        {fileDiff}
        {viewMode}
        loading={loadingFile}
        onToggleMode={onViewModeChange}
      />
    </div>
  </div>
{/if}

<style>
  .placeholder {
    padding: var(--space-xl);
    text-align: center;
    color: var(--text-3);
  }

  .evo-columns {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .col-tree {
    width: 260px;
    min-width: 260px;
    flex-shrink: 0;
    border-right: 1px solid var(--card-border);
    overflow-y: auto;
    height: 100%;
    background: var(--card);
  }

  .col-content {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    height: 100%;
    background: var(--bg);
  }

  .tree-loading {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-md);
  }

  .tree-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-3);
    font-size: 0.85rem;
    padding: var(--space-md);
    text-align: center;
  }

  /* Responsive: stack on narrow viewports */
  @media (max-width: 900px) {
    .evo-columns {
      flex-direction: column;
      height: auto;
      overflow: visible;
    }

    .col-tree {
      width: 100%;
      min-width: auto;
      max-height: 200px;
      border-right: none;
      border-bottom: 1px solid var(--card-border);
    }
  }
</style>
