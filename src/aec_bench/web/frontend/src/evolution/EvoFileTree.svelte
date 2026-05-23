<!-- ABOUTME: Sidebar file tree for the evolution workspace explorer with expand/collapse and change indicators. -->
<!-- ABOUTME: Purpose-built for directory browsing, not reused from StepList. Shows added/modified/removed status. -->
<script lang="ts">
  import type { FileTreeNode } from "../lib/types";

  interface Props {
    tree: FileTreeNode[];
    activeFile: string | null;
    onselect: (path: string) => void;
  }

  let { tree, activeFile, onselect }: Props = $props();

  // Track expanded directories by path
  let expandedDirs: Set<string> = $state(new Set());

  // Expand all top-level directories on mount / tree change
  $effect(() => {
    const topDirs = new Set<string>();
    for (const node of tree) {
      if (node.type === "directory") {
        topDirs.add(node.name);
        // Also expand second-level directories
        if (node.children) {
          for (const child of node.children) {
            if (child.type === "directory") {
              topDirs.add(`${node.name}/${child.name}`);
            }
          }
        }
      }
    }
    expandedDirs = topDirs;
  });

  function toggleDir(path: string) {
    const next = new Set(expandedDirs);
    if (next.has(path)) {
      next.delete(path);
    } else {
      next.add(path);
    }
    expandedDirs = next;
  }

  function statusIndicator(status: string): { symbol: string; className: string } {
    switch (status) {
      case "added":
        return { symbol: "+", className: "status-added" };
      case "modified":
        return { symbol: "~", className: "status-modified" };
      case "removed":
        return { symbol: "-", className: "status-removed" };
      default:
        return { symbol: "", className: "" };
    }
  }

  function fileIcon(node: FileTreeNode): string {
    if (node.type === "directory") return "\u{1F4C1}";
    if (node.name.endsWith(".md")) return "\u{1F4C4}";
    if (node.name.endsWith(".yaml") || node.name.endsWith(".toml") || node.name.endsWith(".yml")) return "\u2699";
    return "\u{1F4C4}";
  }
</script>

<div class="file-tree" data-testid="evo-file-tree">
  <div class="tree-header">Files</div>
  <div class="tree-list" role="tree" aria-label="Workspace file tree">
    {#each tree as node (node.name)}
      {@const nodePath = node.name}
      {@const indicator = statusIndicator(node.status)}
      {#if node.type === "directory"}
        <button
          class="tree-node dir-node"
          class:expanded={expandedDirs.has(nodePath)}
          role="treeitem"
          aria-selected={false}
          aria-expanded={expandedDirs.has(nodePath)}
          onclick={() => toggleDir(nodePath)}
        >
          <span class="chevron" class:rotated={expandedDirs.has(nodePath)}>
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path d="M3 2L7 5L3 8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span class="node-icon">{fileIcon(node)}</span>
          <span class="node-name {indicator.className}">{node.name}</span>
          {#if indicator.symbol}
            <span class="status-badge {indicator.className}">{indicator.symbol}</span>
          {/if}
        </button>

        {#if expandedDirs.has(nodePath) && node.children}
          <div class="tree-children" role="group">
            {#each node.children as child (child.name)}
              {@const childPath = `${nodePath}/${child.name}`}
              {@const childIndicator = statusIndicator(child.status)}
              {#if child.type === "directory"}
                <button
                  class="tree-node dir-node indent-1"
                  class:expanded={expandedDirs.has(childPath)}
                  role="treeitem"
                  aria-selected={false}
                  aria-expanded={expandedDirs.has(childPath)}
                  onclick={() => toggleDir(childPath)}
                >
                  <span class="chevron" class:rotated={expandedDirs.has(childPath)}>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                      <path d="M3 2L7 5L3 8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </span>
                  <span class="node-icon">{fileIcon(child)}</span>
                  <span class="node-name {childIndicator.className}">{child.name}</span>
                  {#if childIndicator.symbol}
                    <span class="status-badge {childIndicator.className}">{childIndicator.symbol}</span>
                  {/if}
                </button>

                {#if expandedDirs.has(childPath) && child.children}
                  <div class="tree-children" role="group">
                    {#each child.children as grandchild (grandchild.name)}
                      {@const grandchildPath = `${childPath}/${grandchild.name}`}
                      {@const gcIndicator = statusIndicator(grandchild.status)}
                      <button
                        class="tree-node file-node indent-2"
                        class:active={activeFile === grandchildPath}
                        class:removed={grandchild.status === "removed"}
                        role="treeitem"
                        aria-selected={activeFile === grandchildPath}
                        onclick={() => onselect(grandchildPath)}
                      >
                        <span class="node-icon">{fileIcon(grandchild)}</span>
                        <span class="node-name {gcIndicator.className}">{grandchild.name}</span>
                        {#if gcIndicator.symbol}
                          <span class="status-badge {gcIndicator.className}">{gcIndicator.symbol}</span>
                        {/if}
                      </button>
                    {/each}
                  </div>
                {/if}
              {:else}
                <button
                  class="tree-node file-node indent-1"
                  class:active={activeFile === childPath}
                  class:removed={child.status === "removed"}
                  role="treeitem"
                  aria-selected={activeFile === childPath}
                  onclick={() => onselect(childPath)}
                >
                  <span class="node-icon">{fileIcon(child)}</span>
                  <span class="node-name {childIndicator.className}">{child.name}</span>
                  {#if childIndicator.symbol}
                    <span class="status-badge {childIndicator.className}">{childIndicator.symbol}</span>
                  {/if}
                </button>
              {/if}
            {/each}
          </div>
        {/if}
      {:else}
        <button
          class="tree-node file-node"
          class:active={activeFile === nodePath}
          class:removed={node.status === "removed"}
          role="treeitem"
          aria-selected={activeFile === nodePath}
          onclick={() => onselect(nodePath)}
        >
          <span class="node-icon">{fileIcon(node)}</span>
          <span class="node-name {indicator.className}">{node.name}</span>
          {#if indicator.symbol}
            <span class="status-badge {indicator.className}">{indicator.symbol}</span>
          {/if}
        </button>
      {/if}
    {/each}
  </div>
</div>

<style>
  .file-tree {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .tree-header {
    font-family: var(--font-heading);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    flex-shrink: 0;
  }

  .tree-list {
    overflow-y: auto;
    flex: 1;
    padding: var(--space-xs) 0;
  }

  .tree-node {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    width: 100%;
    padding: 3px var(--space-md);
    border: none;
    background: transparent;
    color: var(--text-2);
    font-family: var(--font-body);
    font-size: 0.82rem;
    text-align: left;
    cursor: pointer;
    transition: background var(--transition-fast), color var(--transition-fast);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tree-node:hover {
    background: var(--bg-alt);
  }

  .tree-node.active {
    background: var(--forest-light);
    color: var(--forest);
  }

  .tree-node.removed {
    text-decoration: line-through;
    opacity: 0.7;
  }

  .indent-1 {
    padding-left: calc(var(--space-md) + 16px);
  }

  .indent-2 {
    padding-left: calc(var(--space-md) + 32px);
  }

  .chevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    transition: transform var(--transition-fast);
    color: var(--text-3);
  }

  .chevron.rotated {
    transform: rotate(90deg);
  }

  .node-icon {
    flex-shrink: 0;
    font-size: 0.78rem;
    line-height: 1;
  }

  .node-name {
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }

  .status-badge {
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 700;
    width: 16px;
    height: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
  }

  /* Status colours for text and badges */
  .status-added {
    color: var(--forest);
  }

  .status-modified {
    color: var(--reward-mid);
  }

  .status-removed {
    color: var(--reward-zero);
  }

  .status-badge.status-added {
    background: rgba(74, 103, 65, 0.12);
    color: var(--forest);
  }

  .status-badge.status-modified {
    background: rgba(212, 162, 127, 0.12);
    color: var(--reward-mid);
  }

  .status-badge.status-removed {
    background: rgba(191, 77, 67, 0.12);
    color: var(--reward-zero);
  }

  .dir-node {
    font-weight: 600;
  }
</style>
