<!-- ABOUTME: Root application component with client-side pathname router and navigation shell. -->
<!-- ABOUTME: All page components are rendered within this shell based on window.location.pathname. -->
<script lang="ts">
  import "./lib/theme.css";
  import NavBar from "./lib/components/NavBar.svelte";
  import Leaderboard from "./pages/Leaderboard.svelte";
  import Datasets from "./pages/Datasets.svelte";
  import DatasetDetail from "./pages/DatasetDetail.svelte";
  import Library from "./pages/Library.svelte";
  import LibraryDetail from "./pages/LibraryDetail.svelte";
  import Search from "./pages/Search.svelte";
  import ReviewQueue from "./pages/ReviewQueue.svelte";
  import ReviewTrial from "./pages/ReviewTrial.svelte";
  import Viewer from "./pages/Viewer.svelte";
  import Evolution from "./pages/Evolution.svelte";
  import EvolutionDetail from "./pages/EvolutionDetail.svelte";
  import Analyze from "./pages/Analyze.svelte";
  import Runs from "./pages/Runs.svelte";
  import SearchPalette from "./lib/components/SearchPalette.svelte";
  import { paletteStore } from "./lib/stores/palette.svelte";
  import { EVALUATE_PRESET, COMPARE_PRESET, LEADERBOARD_PRESET } from "./analyze/presets";

  let currentPath = $state(window.location.pathname);

  // Redirect stale /triage?... bookmarks to /?... client-side.
  // Also redirects legacy /evaluate and /compare to /analyze with matching presets,
  // and /leaderboard?dataset=X to /analyze with the scorecard preset.
  $effect(() => {
    if (currentPath === "/triage") {
      const search = window.location.search;
      window.history.replaceState({}, "", `/${search}`);
      currentPath = "/";
      return;
    }
    if (currentPath === "/evaluate" || currentPath === "/compare") {
      const preset = currentPath === "/compare"
        ? presetToQueryString(COMPARE_PRESET)
        : presetToQueryString(EVALUATE_PRESET);
      const existing = window.location.search.startsWith("?")
        ? window.location.search.slice(1)
        : window.location.search;
      const merged = existing ? `${preset}&${existing}` : preset;
      window.history.replaceState({}, "", `/analyze?${merged}`);
      currentPath = "/analyze";
      return;
    }
    if (currentPath === "/leaderboard" && window.location.search.includes("dataset=")) {
      const search = window.location.search.slice(1);
      const preset = presetToQueryString(LEADERBOARD_PRESET);
      window.history.replaceState({}, "", `/analyze?${preset}&${search}`);
      currentPath = "/analyze";
      return;
    }
    if (currentPath.startsWith("/evolution/swarm/")) {
      const ws = currentPath.substring("/evolution/swarm/".length);
      const existingSearch = window.location.search.startsWith("?")
        ? window.location.search.slice(1)
        : window.location.search;
      const merged = existingSearch ? `tab=swarm&${existingSearch}` : "tab=swarm";
      window.history.replaceState({}, "", `/evolution/${ws}?${merged}`);
      currentPath = `/evolution/${ws}`;
      return;
    }
    if (currentPath.startsWith("/review/internal/")) {
      const rest = currentPath.substring("/review/internal/".length);
      const search = window.location.search;
      window.history.replaceState({}, "", `/review/${rest}${search}`);
      currentPath = `/review/${rest}`;
      return;
    }
  });

  // Convert a preset object into a URL query string fragment (no leading "?").
  // Always emits all four pivot keys explicitly so redirect URLs are self-describing.
  function presetToQueryString(preset: typeof EVALUATE_PRESET): string {
    const parts = [
      `rows=${preset.rows}`,
      `cols=${preset.cols}`,
      `metrics=${preset.metrics.join(",")}`,
    ];
    if (preset.delta) parts.push("delta=true");
    return parts.join("&");
  }

  function isEditableTarget(el: Element | null): boolean {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return true;
    return el.closest("[contenteditable]") !== null;
  }

  // Update currentPath when the browser history changes (back/forward navigation)
  $effect(() => {
    function onPopState() {
      currentPath = window.location.pathname;
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  });

  // Global ⌘K / Ctrl+K / "/" keybind to open the command palette.
  $effect(() => {
    function onKey(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        paletteStore.toggle();
        return;
      }
      // "/" opens palette only when no input or contenteditable is focused.
      if (e.key === "/" && !isEditableTarget(document.activeElement)) {
        e.preventDefault();
        paletteStore.open();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function getActivePage(path: string): string {
    if (path === "/") return "runs";
    if (path.startsWith("/viewer")) return "viewer";
    if (path.startsWith("/analyze")) return "analyze";
    if (path.startsWith("/leaderboard")) return "leaderboard";
    if (path.startsWith("/library")) return "library";
    if (path.startsWith("/datasets")) return "datasets";
    if (path.startsWith("/search")) return "search";
    if (path.startsWith("/review")) return "review";
    if (path.startsWith("/evolution")) return "evolution";
    return "runs";
  }

  // Match a path pattern, returning extracted params or null if no match.
  // Supports :param segments (e.g. /viewer/:experiment/:trial).
  function matchRoute(
    pattern: string,
    path: string
  ): Record<string, string> | null {
    const patternParts = pattern.split("/").filter(Boolean);
    const pathParts = path.split("/").filter(Boolean);
    if (patternParts.length !== pathParts.length) return null;
    const params: Record<string, string> = {};
    for (let i = 0; i < patternParts.length; i++) {
      if (patternParts[i].startsWith(":")) {
        params[patternParts[i].slice(1)] = decodeURIComponent(pathParts[i]);
      } else if (patternParts[i] !== pathParts[i]) {
        return null;
      }
    }
    return params;
  }

  type Route = {
    pattern: string;
    label: string;
  };

  const routes: Route[] = [
    { pattern: "/", label: "Runs" },
    { pattern: "/viewer/:experiment/:trial", label: "Viewer" },
    { pattern: "/analyze", label: "Analyze" },
    { pattern: "/leaderboard", label: "Leaderboard" },
    { pattern: "/library", label: "Library" },
    { pattern: "/library/:discipline/:templateId", label: "Library Detail" },
    { pattern: "/datasets", label: "Datasets" },
    { pattern: "/datasets/:name/:version", label: "Dataset Detail" },
    { pattern: "/search", label: "Search" },
    { pattern: "/review/queue", label: "Review Queue" },
    { pattern: "/review/trials/:trialId", label: "Review Trial" },
    { pattern: "/evolution", label: "Evolution" },
    { pattern: "/evolution/:workspace", label: "Evolution Workspace" },
  ];

  let activeRoute = $derived.by(() => {
    for (const route of routes) {
      const params = matchRoute(route.pattern, currentPath);
      if (params !== null) {
        return { ...route, params };
      }
    }
    return null;
  });

  let isFullViewport = $derived(
    activeRoute?.pattern === "/viewer/:experiment/:trial" ||
    activeRoute?.pattern === "/evolution/:workspace"
  );
</script>

<NavBar activePage={getActivePage(currentPath)} />

{#if isFullViewport && activeRoute}
  {#if activeRoute.pattern === "/viewer/:experiment/:trial"}
    <Viewer
      experiment={activeRoute.params.experiment}
      trial={activeRoute.params.trial}
    />
  {:else if activeRoute.pattern === "/evolution/:workspace"}
    <EvolutionDetail workspace={activeRoute.params.workspace} />
  {/if}
{:else}
  <main class="app-content">
    {#if activeRoute?.pattern === "/"}
      <Runs />
    {:else if activeRoute?.pattern === "/analyze"}
      <Analyze />
    {:else if activeRoute?.pattern === "/leaderboard"}
      <Leaderboard />
    {:else if activeRoute?.pattern === "/library"}
      <Library />
    {:else if activeRoute?.pattern === "/library/:discipline/:templateId"}
      <LibraryDetail
        discipline={activeRoute.params.discipline}
        templateId={activeRoute.params.templateId}
      />
    {:else if activeRoute?.pattern === "/datasets"}
      <Datasets />
    {:else if activeRoute?.pattern === "/datasets/:name/:version"}
      <DatasetDetail
        name={activeRoute.params.name}
        version={activeRoute.params.version}
      />
    {:else if activeRoute?.pattern === "/search"}
      <Search />
    {:else if activeRoute?.pattern === "/review/queue"}
      <ReviewQueue />
    {:else if activeRoute?.pattern === "/review/trials/:trialId"}
      <ReviewTrial trialId={activeRoute.params.trialId} />
    {:else if activeRoute?.pattern === "/evolution"}
      <Evolution />
    {:else}
      <div class="placeholder-page"><h2>Not Found</h2><p>Page not found</p></div>
    {/if}
  </main>
{/if}

<SearchPalette />

<style>
  .app-content {
    max-width: 1400px;
    margin: 0 auto;
    padding: var(--space-lg);
  }

  .placeholder-page {
    text-align: center;
    padding: var(--space-xl) 0;
    color: var(--text-3);
  }

  .placeholder-page h2 {
    margin-bottom: var(--space-sm);
  }
</style>
