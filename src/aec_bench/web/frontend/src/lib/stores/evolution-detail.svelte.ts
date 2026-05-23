// ABOUTME: Svelte 5 runes store for the EvolutionDetail page — tab + run_id, URL-synced.
// ABOUTME: Workspace is set imperatively by the page from the route param; not part of this store.

export type EvolutionTab = "cycles" | "archive" | "graveyard" | "swarm";

export type EvolutionDetailState = {
  tab: EvolutionTab;
  run_id?: string;
};

const DEFAULT_STATE: EvolutionDetailState = { tab: "cycles" };
const VALID_TABS = new Set<EvolutionTab>(["cycles", "archive", "graveyard", "swarm"]);

function isTab(s: string): s is EvolutionTab {
  return VALID_TABS.has(s as EvolutionTab);
}

export function parseEvolutionDetailFromQuery(query: string): EvolutionDetailState {
  const params = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
  const state: EvolutionDetailState = { ...DEFAULT_STATE };
  const rawTab = params.get("tab");
  if (rawTab && isTab(rawTab)) state.tab = rawTab;
  const runId = params.get("run_id");
  if (runId) state.run_id = runId;
  return state;
}

export function evolutionDetailToQuery(state: EvolutionDetailState): string {
  const parts: string[] = [];
  if (state.tab !== DEFAULT_STATE.tab) parts.push(`tab=${encodeURIComponent(state.tab)}`);
  if (state.run_id) parts.push(`run_id=${encodeURIComponent(state.run_id)}`);
  return parts.length > 0 ? `?${parts.join("&")}` : "";
}

export class EvolutionDetailStore {
  state: EvolutionDetailState = $state({ ...DEFAULT_STATE });

  loadFromCurrentUrl(): void {
    if (typeof window === "undefined") return;
    this.state = parseEvolutionDetailFromQuery(window.location.search);
  }

  setTab(tab: EvolutionTab): void {
    this.state = { ...this.state, tab };
    this.#syncUrl();
  }

  setRun(run_id: string): void {
    this.state = { ...this.state, run_id };
    this.#syncUrl();
  }

  clearRun(): void {
    const next = { ...this.state };
    delete next.run_id;
    this.state = next;
    this.#syncUrl();
  }

  #syncUrl(): void {
    if (typeof window === "undefined") return;
    const qs = evolutionDetailToQuery(this.state);
    const url = `${window.location.pathname}${qs}`;
    window.history.replaceState({}, "", url);
  }
}

export const evolutionDetailStore = new EvolutionDetailStore();
