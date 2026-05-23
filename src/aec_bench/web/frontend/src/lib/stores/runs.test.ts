// ABOUTME: Tests for the Runs filter store — URL parsing, serialisation, mutation.
// ABOUTME: Pure logic tests; no DOM required for the parser/serializer pair.

import { describe, it, expect } from "vitest";
import {
  parseRunsFilterFromQuery,
  runsFilterToQuery,
  type RunsFilter,
} from "./runs.svelte";

describe("runs filter URL parsing", () => {
  it("returns an empty filter for an empty query string", () => {
    expect(parseRunsFilterFromQuery("")).toEqual({});
  });

  it("parses a full filter from a query string", () => {
    const f = parseRunsFilterFromQuery(
      "?experiment=exp-a&model=sonnet&adapter=rlm&task_type=voltage-drop&annotated=true&reward_min=0.2&reward_max=0.8",
    );
    expect(f).toEqual({
      experiment: "exp-a",
      model: "sonnet",
      adapter: "rlm",
      task_type: "voltage-drop",
      annotated: true,
      reward_min: 0.2,
      reward_max: 0.8,
    });
  });

  it("ignores unknown query params", () => {
    const f = parseRunsFilterFromQuery("?experiment=exp-a&garbage=1");
    expect(f).toEqual({ experiment: "exp-a" });
  });

  it("treats invalid numeric reward bounds as absent", () => {
    const f = parseRunsFilterFromQuery("?reward_min=abc&reward_max=");
    expect(f).toEqual({});
  });
});

describe("runs filter serialisation", () => {
  it("serialises an empty filter to an empty query string", () => {
    expect(runsFilterToQuery({})).toBe("");
  });

  it("round-trips a populated filter", () => {
    const f: RunsFilter = {
      experiment: "exp-a",
      annotated: true,
      reward_min: 0.5,
    };
    const q = runsFilterToQuery(f);
    expect(parseRunsFilterFromQuery(q)).toEqual(f);
  });

  it("omits undefined fields from the query string", () => {
    expect(runsFilterToQuery({ experiment: undefined, model: "haiku" }))
      .toBe("?model=haiku");
  });
});

import { RunsStore } from "./runs.svelte";

describe("RunsStore", () => {
  it("patchFilter merges and replaces the URL", () => {
    history.replaceState({}, "", "/?model=haiku");
    const store = new RunsStore();
    store.loadFromCurrentUrl();
    store.patchFilter({ adapter: "rlm" });

    expect(store.filter).toEqual({ model: "haiku", adapter: "rlm" });
    expect(window.location.search).toBe("?model=haiku&adapter=rlm");
  });

  it("removeKey strips a single field from the URL", () => {
    history.replaceState({}, "", "/?experiment=exp-a&model=haiku");
    const store = new RunsStore();
    store.loadFromCurrentUrl();
    store.removeKey("experiment");

    expect(store.filter).toEqual({ model: "haiku" });
    expect(window.location.search).toBe("?model=haiku");
  });

  it("clear empties the URL search string", () => {
    history.replaceState({}, "", "/?experiment=exp-a");
    const store = new RunsStore();
    store.loadFromCurrentUrl();
    store.clear();

    expect(store.filter).toEqual({});
    expect(window.location.search).toBe("");
  });

  it("patchFilter strips undefined fields from the active filter", () => {
    history.replaceState({}, "", "/?model=haiku&adapter=rlm");
    const store = new RunsStore();
    store.loadFromCurrentUrl();
    store.patchFilter({ adapter: undefined });

    expect(store.filter).toEqual({ model: "haiku" });
    expect("adapter" in store.filter).toBe(false);
    expect(window.location.search).toBe("?model=haiku");
  });
});
