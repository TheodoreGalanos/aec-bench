// ABOUTME: Svelte 5 runes-based filter store for the Runs landing page.
// ABOUTME: URL is the source of truth; helpers parse, serialise, and mutate filter state.

export type RunsFilter = {
  experiment?: string;
  model?: string;
  adapter?: string;
  task_type?: string;
  annotated?: boolean;
  reward_min?: number;
  reward_max?: number;
};

const STRING_KEYS = ["experiment", "model", "adapter", "task_type"] as const;
const NUMBER_KEYS = ["reward_min", "reward_max"] as const;

export function parseRunsFilterFromQuery(query: string): RunsFilter {
  const params = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
  const filter: RunsFilter = {};

  for (const key of STRING_KEYS) {
    const value = params.get(key);
    if (value !== null && value !== "") {
      filter[key] = value;
    }
  }
  for (const key of NUMBER_KEYS) {
    const raw = params.get(key);
    if (raw === null || raw === "") continue;
    const num = Number(raw);
    if (Number.isFinite(num)) {
      filter[key] = num;
    }
  }
  if (params.get("annotated") === "true") {
    filter.annotated = true;
  } else if (params.get("annotated") === "false") {
    filter.annotated = false;
  }
  return filter;
}

export function runsFilterToQuery(filter: RunsFilter): string {
  const params = new URLSearchParams();
  for (const key of STRING_KEYS) {
    const v = filter[key];
    if (v !== undefined && v !== "") params.set(key, v);
  }
  for (const key of NUMBER_KEYS) {
    const v = filter[key];
    if (v !== undefined && Number.isFinite(v)) params.set(key, String(v));
  }
  if (filter.annotated !== undefined) {
    params.set("annotated", filter.annotated ? "true" : "false");
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export class RunsStore {
  filter: RunsFilter = $state({});

  setFilter(next: RunsFilter): void {
    this.filter = { ...next };
    this.#syncUrl(true);
  }

  patchFilter(patch: Partial<RunsFilter>): void {
    const merged = { ...this.filter, ...patch };
    const clean: RunsFilter = {};
    for (const [k, v] of Object.entries(merged)) {
      if (v !== undefined) {
        (clean as Record<string, unknown>)[k] = v;
      }
    }
    this.filter = clean;
    this.#syncUrl(false);
  }

  removeKey(key: keyof RunsFilter): void {
    const next = { ...this.filter };
    delete next[key];
    this.filter = next;
    this.#syncUrl(false);
  }

  clear(): void {
    this.filter = {};
    this.#syncUrl(true);
  }

  loadFromCurrentUrl(): void {
    if (typeof window === "undefined") return;
    this.filter = parseRunsFilterFromQuery(window.location.search);
  }

  #syncUrl(push: boolean): void {
    if (typeof window === "undefined") return;
    const qs = runsFilterToQuery(this.filter);
    const url = `${window.location.pathname}${qs}`;
    if (push) {
      window.history.pushState({}, "", url);
    } else {
      window.history.replaceState({}, "", url);
    }
  }
}

export const runsStore = new RunsStore();
