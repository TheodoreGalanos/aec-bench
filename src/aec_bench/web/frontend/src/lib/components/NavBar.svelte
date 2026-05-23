<!-- ABOUTME: Top navigation bar with brand link, nav links, catalogue dropdown, and search. -->
<!-- ABOUTME: Sticky 48px bar using aec-bench design tokens; highlights the active page. -->
<script lang="ts">
  import { paletteStore } from "../stores/palette.svelte";
  import Play from "lucide-svelte/icons/play";
  import BarChart3 from "lucide-svelte/icons/bar-chart-3";
  import Trophy from "lucide-svelte/icons/trophy";
  import BookOpen from "lucide-svelte/icons/book-open";
  import ChevronDown from "lucide-svelte/icons/chevron-down";
  import LibraryIcon from "lucide-svelte/icons/library";
  import DatabaseIcon from "lucide-svelte/icons/database";
  import ClipboardCheck from "lucide-svelte/icons/clipboard-check";
  import Dna from "lucide-svelte/icons/dna";
  import Search from "lucide-svelte/icons/search";

  interface Props {
    activePage: string;
  }

  let { activePage }: Props = $props();
  let searchQuery = $state("");
  let catalogueOpen = $state(false);

  function handleSearchSubmit(e: Event) {
    e.preventDefault();
    if (searchQuery.trim()) {
      window.location.href = `/search?q=${encodeURIComponent(searchQuery.trim())}`;
    }
  }

  function toggleCatalogue() {
    catalogueOpen = !catalogueOpen;
  }

  function closeCatalogue() {
    catalogueOpen = false;
  }
</script>

<nav class="navbar" aria-label="Main navigation">
  <a href="/" class="brand">aec-bench</a>

  <div class="nav-links">
    <a href="/" class="nav-link" class:active={activePage === "runs"}><Play size={14} /> Runs</a>
    <a href="/analyze" class="nav-link" class:active={activePage === "analyze"}><BarChart3 size={14} /> Analyze</a>
    <a href="/leaderboard" class="nav-link" class:active={activePage === "leaderboard"}><Trophy size={14} /> Leaderboard</a>

    <!-- Catalogue dropdown -->
    <div
      class="dropdown"
      class:open={catalogueOpen}
      onmouseenter={() => (catalogueOpen = true)}
      onmouseleave={() => (catalogueOpen = false)}
      role="none"
    >
      <button
        class="nav-link dropdown-trigger"
        class:active={activePage === "library" || activePage === "datasets"}
        onclick={toggleCatalogue}
        aria-haspopup="true"
        aria-expanded={catalogueOpen}
      >
        <BookOpen size={14} /> Catalogue <ChevronDown size={12} />
      </button>
      {#if catalogueOpen}
        <div class="dropdown-menu" role="menu">
          <a
            href="/library"
            class="dropdown-item"
            class:active={activePage === "library"}
            onclick={closeCatalogue}
            role="menuitem"
          >
            <LibraryIcon size={14} /> Library
          </a>
          <a
            href="/datasets"
            class="dropdown-item"
            class:active={activePage === "datasets"}
            onclick={closeCatalogue}
            role="menuitem"
          >
            <DatabaseIcon size={14} /> Datasets
          </a>
        </div>
      {/if}
    </div>

    <a href="/review/queue" class="nav-link" class:active={activePage === "review"}><ClipboardCheck size={14} /> Review</a>
    <a href="/evolution" class="nav-link" class:active={activePage === "evolution"}><Dna size={14} /> Evolution</a>
    <button
      type="button"
      class="nav-link nav-link-button"
      onclick={() => paletteStore.open()}
      aria-label="Open search palette"
    ><Search size={14} /> Search</button>
  </div>

  <form class="search-form" onsubmit={handleSearchSubmit}>
    <input
      type="search"
      class="search-input"
      placeholder="Search tasks…"
      bind:value={searchQuery}
      aria-label="Search tasks"
    />
    <button type="submit" class="search-btn" aria-label="Submit search">
      <Search size={14} />
    </button>
  </form>
</nav>

<style>
  .navbar {
    position: sticky;
    top: 0;
    z-index: 100;
    height: 48px;
    display: flex;
    align-items: center;
    gap: var(--space-lg);
    padding: 0 var(--space-lg);
    background: var(--card);
    border-bottom: 1px solid var(--card-border);
    box-shadow: var(--shadow-sm);
  }

  .brand {
    font-family: var(--font-heading);
    font-size: 1rem;
    font-weight: 700;
    color: var(--forest);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .brand:hover {
    color: var(--forest-hover);
  }

  .nav-links {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    flex: 1;
    min-width: 0;
  }

  .nav-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-2);
    padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-sm);
    transition: color var(--transition-fast), background var(--transition-fast);
    white-space: nowrap;
    border: none;
    background: none;
    cursor: pointer;
    line-height: 1.5;
    font-family: var(--font-body);
  }

  .nav-link:hover,
  .nav-link.active {
    color: var(--forest);
    background: var(--forest-light);
  }

  .nav-link-button {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
    padding: inherit;
  }

  /* Dropdown */
  .dropdown {
    position: relative;
  }

  .dropdown-trigger {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
  }

  .dropdown-menu {
    position: absolute;
    /* No vertical gap: the menu must abut the trigger so the cursor stays inside
       .dropdown while moving between them (otherwise onmouseleave fires and the
       menu closes mid-transit). Visual separation comes from border + shadow. */
    top: 100%;
    left: 0;
    min-width: 140px;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    z-index: 200;
    overflow: hidden;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-sm) var(--space-md);
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-2);
    transition: color var(--transition-fast), background var(--transition-fast);
  }

  .dropdown-item:hover,
  .dropdown-item.active {
    color: var(--forest);
    background: var(--forest-light);
  }

  /* Search */
  .search-form {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    margin-left: auto;
    flex-shrink: 0;
  }

  .search-input {
    height: 30px;
    padding: 0 var(--space-sm);
    font-size: 0.8125rem;
    font-family: var(--font-body);
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    outline: none;
    width: 180px;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .search-input:focus {
    border-color: var(--forest);
    box-shadow: 0 0 0 2px var(--forest-light);
  }

  .search-input::placeholder {
    color: var(--text-3);
  }

  .search-btn {
    height: 30px;
    width: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--forest);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background var(--transition-fast);
    flex-shrink: 0;
  }

  .search-btn:hover {
    background: var(--forest-hover);
  }

  @media (max-width: 1100px) {
    .search-form {
      display: none;
    }
  }

  @media (max-width: 760px) {
    .navbar {
      gap: var(--space-md);
      padding: 0 var(--space-sm);
      overflow-x: auto;
      overflow-y: visible;
      scrollbar-width: thin;
    }

    .nav-links {
      flex: 0 0 auto;
    }

    .nav-link {
      font-size: 0.8rem;
      padding: var(--space-xs);
    }

    .dropdown-menu {
      position: fixed;
      top: var(--navbar-height);
      left: var(--space-sm);
    }
  }
</style>
