<!-- ABOUTME: Feed of agent notes with colour-coded attribution and tag filtering. -->
<!-- ABOUTME: Displays notes reverse-chronologically with optional agent/tag filter dropdowns. -->
<script lang="ts">
  import type { SwarmNote } from "../lib/types";

  interface Props {
    notes: SwarmNote[];
    agentColors: Record<string, string>;
  }

  let { notes, agentColors }: Props = $props();
  let filterAgent: string = $state("");
  let filterTag: string = $state("");

  let allAgents = $derived([...new Set(notes.map((n) => n.agent_id))].sort());
  let allTags = $derived([...new Set(notes.flatMap((n) => n.tags))].sort());

  let filtered = $derived.by((): SwarmNote[] => {
    let result = [...notes].reverse();
    if (filterAgent) result = result.filter((n) => n.agent_id === filterAgent);
    if (filterTag) result = result.filter((n) => n.tags.includes(filterTag));
    return result;
  });

  function formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  }
</script>

<div class="notes-panel">
  <div class="notes-filters">
    <select bind:value={filterAgent}>
      <option value="">All agents</option>
      {#each allAgents as agent}
        <option value={agent}>{agent}</option>
      {/each}
    </select>
    <select bind:value={filterTag}>
      <option value="">All tags</option>
      {#each allTags as tag}
        <option value={tag}>{tag}</option>
      {/each}
    </select>
  </div>

  {#if filtered.length === 0}
    <div class="empty">No notes{filterAgent || filterTag ? " matching filters" : " yet"}</div>
  {:else}
    <div class="notes-list">
      {#each filtered as note, i (note.note_id || i)}
        <div class="note-row">
          <span
            class="agent-dot"
            style:background={agentColors[note.agent_id] ?? "var(--text-3)"}
          ></span>
          <span class="note-agent">{note.agent_id}</span>
          <span class="note-title">{note.title}</span>
          <span class="note-content">{note.content}</span>
          {#each note.tags as tag}
            <span class="tag-pill">{tag}</span>
          {/each}
          <span class="note-time">{formatTime(note.timestamp)}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .notes-panel { padding: var(--space-sm); }

  .notes-filters {
    display: flex;
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
  }

  .notes-filters select {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    padding: 2px 6px;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    background: var(--card);
    color: var(--text);
  }

  .notes-list {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .note-row {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: 4px var(--space-sm);
    border-bottom: 1px solid var(--card-border);
    font-size: 0.72rem;
    line-height: 1.4;
  }

  .note-row:last-child {
    border-bottom: none;
  }

  .agent-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .note-agent {
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--text);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .note-title {
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .note-content {
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }

  .note-time {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-3);
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: auto;
  }

  .tag-pill {
    font-family: var(--font-mono);
    font-size: 0.55rem;
    padding: 0 4px;
    border-radius: 9999px;
    background: var(--bg-alt);
    color: var(--text-3);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .empty {
    text-align: center;
    padding: var(--space-lg);
    color: var(--text-3);
    font-size: 0.85rem;
  }
</style>
