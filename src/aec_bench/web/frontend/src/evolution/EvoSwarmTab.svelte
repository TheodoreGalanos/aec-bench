<!-- ABOUTME: Swarm tab body — KPI strip, archive panel, agent sidebar, and tabbed bottom panels. -->
<!-- ABOUTME: Lazily initialises the swarmStore + SSE connection when active=true. -->
<script lang="ts">
  import { onDestroy } from "svelte";
  import { fade } from "svelte/transition";
  import { swarmStore } from "../lib/stores/swarm.svelte";
  import KpiStrip from "../swarm/KpiStrip.svelte";
  import ArchivePanel from "../swarm/ArchivePanel.svelte";
  import SwarmAgentSidebar from "../swarm/SwarmAgentSidebar.svelte";
  import LineageTree from "../swarm/LineageTree.svelte";
  import ConsolidationPanel from "../swarm/ConsolidationPanel.svelte";
  import NotesPanel from "../swarm/NotesPanel.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";

  interface Props {
    workspace: string;
    active: boolean;
  }

  let { workspace, active }: Props = $props();

  const AGENT_PALETTE = [
    "#89c925",
    "#61AAF2",
    "#e4572e",
    "#D4A27F",
    "#2d4a5e",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
  ];

  type TabId = "lineage" | "consolidation" | "notes";
  let activeTab: TabId = $state("lineage");

  let swarmState = $derived(swarmStore.state);
  let connectionStatus = $derived(swarmStore.connectionStatus);

  let initializedFor: string | null = $state(null);

  $effect(() => {
    if (active && initializedFor !== workspace) {
      void swarmStore.initSwarmStore(workspace);
      initializedFor = workspace;
    } else if (!active && initializedFor !== null) {
      swarmStore.resetSwarmStore();
      initializedFor = null;
    }
  });

  // onDestroy is redundant with the !active branch above when a parent sets
  // active=false immediately before unmount, but resetSwarmStore is idempotent.
  // Keeping both makes the teardown contract explicit even when the parent
  // unmounts without flipping active first.
  onDestroy(() => {
    swarmStore.resetSwarmStore();
    initializedFor = null;
  });

  let agentColors = $derived.by((): Record<string, string> => {
    if (!swarmState) return {};
    const map: Record<string, string> = {};
    swarmState.agents.forEach((a, i) => {
      map[a.agent_id] = AGENT_PALETTE[i % AGENT_PALETTE.length];
    });
    return map;
  });

  function handleAgentSelect(agentId: string): void {
    if (swarmStore.selectedAgentId === agentId) {
      swarmStore.selectedAgentId = null;
    } else {
      swarmStore.selectedAgentId = agentId;
    }
  }
</script>

{#if !active}
  <div class="placeholder">Swarm tab inactive.</div>
{:else if !swarmState}
  <div class="loading">
    <p class="loading-text">Connecting to swarm…</p>
    <Skeleton height="3rem" width="100%" />
    <Skeleton height="80vh" width="100%" />
  </div>
{:else}
  <div class="mission-control">
    <div class="kpi-area">
      <KpiStrip state={swarmState} {connectionStatus} />
    </div>

    <div class="sidebar-area">
      <SwarmAgentSidebar
        agents={swarmState.agents}
        events={swarmState.events}
        {agentColors}
        selectedAgentId={swarmStore.selectedAgentId}
        onAgentSelect={handleAgentSelect}
      />
    </div>

    <div class="archive-area">
      <ArchivePanel
        centroids={swarmState.centroids}
        {agentColors}
        selectedAgentId={swarmStore.selectedAgentId}
      />
    </div>

    <div class="tabs-area">
      <div class="tab-bar">
        <button class:active={activeTab === "lineage"} onclick={() => (activeTab = "lineage")}>
          Lineage
        </button>
        <button class:active={activeTab === "consolidation"} onclick={() => (activeTab = "consolidation")}>
          Consolidation
          {#if swarmState.consolidation_reports.length > 0}
            <span class="tab-count">{swarmState.consolidation_reports.length}</span>
          {/if}
        </button>
        <button class:active={activeTab === "notes"} onclick={() => (activeTab = "notes")}>
          Notes
          {#if swarmState.notes.length > 0}
            <span class="tab-count">{swarmState.notes.length}</span>
          {/if}
        </button>
      </div>

      <div class="tab-content">
        {#key activeTab}
          <div class="tab-fade" transition:fade={{ duration: 150 }}>
            {#if activeTab === "lineage"}
              <LineageTree nodes={swarmState.lineage} {agentColors} />
            {:else if activeTab === "consolidation"}
              <ConsolidationPanel reports={swarmState.consolidation_reports} />
            {:else if activeTab === "notes"}
              <NotesPanel notes={swarmState.notes} {agentColors} />
            {/if}
          </div>
        {/key}
      </div>
    </div>
  </div>
{/if}

<style>
  .mission-control {
    display: grid;
    grid-template-columns: minmax(200px, 260px) 1fr;
    grid-template-rows: auto 1fr minmax(100px, 25vh);
    grid-template-areas:
      "sidebar kpi"
      "sidebar archive"
      "sidebar tabs";
    height: calc(100vh - 48px);
    overflow: hidden;
  }

  .kpi-area {
    grid-area: kpi;
  }

  .sidebar-area {
    grid-area: sidebar;
    overflow: hidden;
  }

  .archive-area {
    grid-area: archive;
    overflow: hidden;
    min-height: 0;
  }

  .tabs-area {
    grid-area: tabs;
    overflow: hidden;
    border-top: 1px solid var(--card-border);
    display: flex;
    flex-direction: column;
  }

  .loading {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    padding: var(--space-lg);
  }

  .loading-text {
    color: var(--text-3);
    font-size: 0.85rem;
    margin: 0;
  }

  .placeholder {
    padding: var(--space-xl);
    text-align: center;
    color: var(--text-3);
  }

  .tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--card-border);
    background: var(--bg);
    flex-shrink: 0;
  }

  .tab-bar button {
    padding: var(--space-xs) var(--space-md);
    border: none;
    background: none;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-3);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .tab-bar button.active {
    color: var(--forest);
    border-bottom-color: var(--forest);
  }

  .tab-count {
    font-size: 0.6rem;
    background: var(--bg-alt);
    padding: 0 4px;
    border-radius: 9999px;
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .tab-fade {
    height: 100%;
  }

  /* Responsive: stack on narrow viewport */
  @media (max-width: 768px) {
    .mission-control {
      grid-template-columns: 1fr;
      grid-template-rows: auto auto 1fr auto;
      grid-template-areas:
        "kpi"
        "sidebar"
        "archive"
        "tabs";
    }

    .sidebar-area {
      max-height: 200px;
      border-right: none;
      border-bottom: 1px solid var(--card-border);
    }
  }
</style>
