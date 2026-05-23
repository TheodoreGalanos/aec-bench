<!-- ABOUTME: Main content viewer for the evolution workspace explorer with content and diff modes. -->
<!-- ABOUTME: Renders file content in a code block and colours unified diff output with add/del/hunk classes. -->
<script lang="ts">
  import type { FileContent, FileDiff } from "../lib/types";
  import Skeleton from "../lib/components/Skeleton.svelte";

  type ViewMode = "content" | "diff";

  interface Props {
    fileContent: FileContent | null;
    fileDiff: FileDiff | null;
    viewMode: ViewMode;
    loading: boolean;
    onToggleMode: (mode: ViewMode) => void;
  }

  let { fileContent, fileDiff, viewMode, loading, onToggleMode }: Props = $props();

  // Classify a diff line by its first character(s)
  type DiffLineKind = "meta" | "add" | "del" | "hunk" | "context";

  function classifyDiffLine(line: string): DiffLineKind {
    if (line.startsWith("+++") || line.startsWith("---")) return "meta";
    if (line.startsWith("@@")) return "hunk";
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "context";
  }

  // Parse diff text into classified lines
  let diffLines = $derived.by(() => {
    if (!fileDiff?.diff) return [];
    return fileDiff.diff.split("\n").map((line) => ({
      text: line,
      kind: classifyDiffLine(line),
    }));
  });

  // Determine if diff mode is available (has diff data)
  let hasDiff = $derived(fileDiff !== null && fileDiff.diff.length > 0);
</script>

<div class="content-viewer" data-testid="evo-content-viewer">
  {#if !fileContent && !fileDiff && !loading}
    <!-- Empty state: no file selected -->
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <rect x="8" y="4" width="24" height="32" rx="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
          <line x1="14" y1="14" x2="26" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="14" y1="20" x2="26" y2="20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="14" y1="26" x2="22" y2="26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
      <p>Select a file from the tree to view its contents.</p>
    </div>
  {:else}
    <!-- Header with file path, version badge, and mode toggle -->
    <div class="viewer-header">
      <div class="header-left">
        {#if fileContent}
          <span class="file-path">{fileContent.path}</span>
          <span class="version-badge">{fileContent.version}</span>
        {:else if fileDiff}
          <span class="file-path">{fileDiff.path}</span>
          <span class="version-badge">{fileDiff.from_version} → {fileDiff.to_version}</span>
        {/if}
      </div>

      <div class="mode-toggle" role="group" aria-label="View mode">
        <button
          class="toggle-btn"
          class:active={viewMode === "content"}
          onclick={() => onToggleMode("content")}
          aria-pressed={viewMode === "content"}
        >
          Content
        </button>
        <button
          class="toggle-btn"
          class:active={viewMode === "diff"}
          disabled={!hasDiff}
          onclick={() => onToggleMode("diff")}
          aria-pressed={viewMode === "diff"}
        >
          Diff
        </button>
      </div>
    </div>

    <!-- Content area -->
    <div class="viewer-body">
      {#if loading}
        <div class="loading-area">
          <Skeleton height="1rem" width="80%" />
          <Skeleton height="1rem" width="60%" />
          <Skeleton height="1rem" width="90%" />
          <Skeleton height="1rem" width="45%" />
          <Skeleton height="1rem" width="70%" />
          <Skeleton height="1rem" width="55%" />
        </div>
      {:else if viewMode === "content" && fileContent}
        <pre class="code-block"><code>{fileContent.content}</code></pre>
      {:else if viewMode === "diff" && fileDiff}
        <div class="diff-block">
          {#each diffLines as line, i (i)}
            <div class="diff-line diff-{line.kind}">{line.text}</div>
          {/each}
        </div>
      {:else}
        <div class="no-content">
          <p>No content available for this view mode.</p>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .content-viewer {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: var(--space-md);
    color: var(--text-3);
    font-size: 0.9rem;
    padding: var(--space-xl);
    text-align: center;
  }

  .empty-icon {
    color: var(--text-3);
    opacity: 0.5;
  }

  .viewer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--card-border);
    background: var(--card);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    min-width: 0;
    overflow: hidden;
  }

  .file-path {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .version-badge {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    padding: 1px var(--space-sm);
    border-radius: 9999px;
    background: var(--forest-light);
    color: var(--forest);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .mode-toggle {
    display: flex;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
    flex-shrink: 0;
  }

  .toggle-btn {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 600;
    padding: var(--space-xs) var(--space-sm);
    border: none;
    background: var(--card);
    color: var(--text-2);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .toggle-btn:not(:last-child) {
    border-right: 1px solid var(--card-border);
  }

  .toggle-btn:hover:not(:disabled) {
    background: var(--bg-alt);
    color: var(--text);
  }

  .toggle-btn.active {
    background: var(--forest);
    color: white;
  }

  .toggle-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .viewer-body {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }

  .loading-area {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-lg);
  }

  .code-block {
    margin: 0;
    padding: var(--space-md);
    background: var(--code-bg);
    color: var(--code-text);
    font-family: var(--font-mono);
    font-size: 0.82rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    border-radius: 0;
    min-height: 100%;
  }

  .code-block code {
    font-size: inherit;
  }

  .diff-block {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    line-height: 1.6;
    min-height: 100%;
    background: var(--code-bg);
  }

  .diff-line {
    padding: 0 var(--space-md);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .diff-context {
    color: var(--code-text);
  }

  .diff-add {
    background: rgba(74, 103, 65, 0.18);
    color: #7bc47f;
  }

  .diff-del {
    background: rgba(191, 77, 67, 0.18);
    color: #e4725c;
  }

  .diff-hunk {
    color: var(--reward-perfect);
    font-style: italic;
    padding-top: var(--space-xs);
    padding-bottom: var(--space-xs);
  }

  .diff-meta {
    color: var(--text-3);
    font-weight: 700;
  }

  .no-content {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-3);
    font-size: 0.9rem;
    padding: var(--space-xl);
  }
</style>
