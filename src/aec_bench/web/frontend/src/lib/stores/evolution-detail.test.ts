// ABOUTME: Tests for EvolutionDetailStore — URL parse, serialize, tab/run mutation.
// ABOUTME: Mirrors the pattern of runs.svelte.ts and analyze.svelte.ts tests.

import { describe, it, expect } from "vitest";

import {
  parseEvolutionDetailFromQuery,
  evolutionDetailToQuery,
  type EvolutionDetailState,
  EvolutionDetailStore,
} from "./evolution-detail.svelte";

describe("evolution-detail parsing", () => {
  it("returns defaults for empty query", () => {
    expect(parseEvolutionDetailFromQuery("")).toEqual({ tab: "cycles" });
  });

  it("parses tab and run_id", () => {
    expect(parseEvolutionDetailFromQuery("?tab=archive&run_id=20260412-0317")).toEqual({
      tab: "archive",
      run_id: "20260412-0317",
    });
  });

  it("ignores unknown tab values", () => {
    expect(parseEvolutionDetailFromQuery("?tab=bogus")).toEqual({ tab: "cycles" });
  });

  it("accepts all four valid tabs", () => {
    for (const tab of ["cycles", "archive", "graveyard", "swarm"] as const) {
      expect(parseEvolutionDetailFromQuery(`?tab=${tab}`).tab).toBe(tab);
    }
  });
});

describe("evolution-detail serialisation", () => {
  it("omits default tab and absent run_id", () => {
    expect(evolutionDetailToQuery({ tab: "cycles" })).toBe("");
  });

  it("serialises a non-default tab", () => {
    expect(evolutionDetailToQuery({ tab: "swarm" })).toBe("?tab=swarm");
  });

  it("serialises run_id alone", () => {
    expect(evolutionDetailToQuery({ tab: "cycles", run_id: "r1" })).toBe("?run_id=r1");
  });

  it("serialises both", () => {
    expect(evolutionDetailToQuery({ tab: "archive", run_id: "r1" }))
      .toBe("?tab=archive&run_id=r1");
  });
});

describe("EvolutionDetailStore", () => {
  it("setTab updates state and replaces URL", () => {
    history.replaceState({}, "", "/evolution/ws-a");
    const store = new EvolutionDetailStore();
    store.loadFromCurrentUrl();
    store.setTab("archive");

    expect(store.state.tab).toBe("archive");
    expect(window.location.search).toBe("?tab=archive");
  });

  it("setRun updates state and replaces URL", () => {
    history.replaceState({}, "", "/evolution/ws-a");
    const store = new EvolutionDetailStore();
    store.loadFromCurrentUrl();
    store.setRun("r1");

    expect(store.state.run_id).toBe("r1");
    expect(window.location.search).toBe("?run_id=r1");
  });

  it("clearRun removes run_id", () => {
    history.replaceState({}, "", "/evolution/ws-a?run_id=r1");
    const store = new EvolutionDetailStore();
    store.loadFromCurrentUrl();
    store.clearRun();

    expect(store.state.run_id).toBeUndefined();
    expect(window.location.search).toBe("");
  });
});
