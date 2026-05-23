// ABOUTME: Tests for the Analyze filter/pivot store — URL parsing, serialisation, mutation.
// ABOUTME: Pure logic tests for the helpers; instance tests run in jsdom.

import { describe, it, expect } from "vitest";

import {
  parseAnalyzeStateFromQuery,
  analyzeStateToQuery,
  type AnalyzeState,
  AnalyzeStore,
} from "./analyze.svelte";

describe("analyze state parsing", () => {
  it("returns defaults for an empty query", () => {
    expect(parseAnalyzeStateFromQuery("")).toEqual({
      rows: "adapter",
      cols: "task_type",
      metrics: ["mean_reward"],
      delta: false,
    });
  });

  it("parses a full query string", () => {
    const s = parseAnalyzeStateFromQuery(
      "?rows=task_type&cols=model&metrics=mean_reward&delta=true&experiment=exp-a&dataset=ds@1",
    );
    expect(s).toEqual({
      rows: "task_type",
      cols: "model",
      metrics: ["mean_reward"],
      delta: true,
      experiment: "exp-a",
      dataset: "ds@1",
    });
  });

  it("parses comma-separated multi-metric", () => {
    const s = parseAnalyzeStateFromQuery(
      "?rows=model&cols=none&metrics=mean_reward,perfect_pct,cost",
    );
    expect(s.metrics).toEqual(["mean_reward", "perfect_pct", "cost"]);
  });

  it("rejects unknown metric tokens silently (filters them out)", () => {
    const s = parseAnalyzeStateFromQuery("?rows=model&cols=none&metrics=mean_reward,wat");
    expect(s.metrics).toEqual(["mean_reward"]);
  });
});

describe("analyze state serialisation", () => {
  it("omits default values", () => {
    const s: AnalyzeState = {
      rows: "adapter",
      cols: "task_type",
      metrics: ["mean_reward"],
      delta: false,
    };
    expect(analyzeStateToQuery(s)).toBe("");
  });

  it("serialises multi-metric as comma-separated", () => {
    const s: AnalyzeState = {
      rows: "model",
      cols: "none",
      metrics: ["mean_reward", "perfect_pct"],
      delta: false,
    };
    expect(analyzeStateToQuery(s)).toBe("?rows=model&cols=none&metrics=mean_reward,perfect_pct");
  });

  it("round-trips a delta-enabled state", () => {
    const s: AnalyzeState = {
      rows: "task_type",
      cols: "model",
      metrics: ["mean_reward"],
      delta: true,
      experiment: "exp-a",
    };
    const q = analyzeStateToQuery(s);
    expect(parseAnalyzeStateFromQuery(q)).toEqual(s);
  });

  it("serializes metrics when only scope changes but user chose non-default metrics", () => {
    const s: AnalyzeState = {
      rows: "adapter",     // default
      cols: "task_type",   // default
      metrics: ["mean_reward", "perfect_pct"],   // non-default
      delta: false,        // default
      experiment: "exp-a",
    };
    const q = analyzeStateToQuery(s);
    expect(q).toContain("metrics=mean_reward,perfect_pct");
    expect(q).toContain("experiment=exp-a");
  });
});

describe("AnalyzeStore mutation", () => {
  it("setPivot updates rows/cols/metrics and syncs URL", () => {
    history.replaceState({}, "", "/analyze");
    const store = new AnalyzeStore();
    store.loadFromCurrentUrl();
    store.setPivot({ rows: "task_type", cols: "model", metrics: ["mean_reward"], delta: true });
    expect(store.state.rows).toBe("task_type");
    expect(store.state.cols).toBe("model");
    expect(store.state.delta).toBe(true);
    expect(window.location.search).toBe("?rows=task_type&cols=model&metrics=mean_reward&delta=true");
  });

  it("setScope patches only the scope fields", () => {
    history.replaceState({}, "", "/analyze");
    const store = new AnalyzeStore();
    store.loadFromCurrentUrl();
    store.setScope({ experiment: "exp-a" });
    expect(store.state.experiment).toBe("exp-a");
    expect(window.location.search).toBe("?experiment=exp-a");
  });

  it("clearScope removes all scope filters but preserves pivot state", () => {
    history.replaceState({}, "", "/analyze?rows=task_type&cols=model&experiment=exp-a&model=haiku");
    const store = new AnalyzeStore();
    store.loadFromCurrentUrl();
    store.clearScope();
    expect(store.state.experiment).toBeUndefined();
    expect(store.state.model).toBeUndefined();
    expect(store.state.rows).toBe("task_type");
    expect(store.state.cols).toBe("model");
  });

  it("setPivot normalises delta to false when cols is 'none'", () => {
    history.replaceState({}, "", "/analyze");
    const store = new AnalyzeStore();
    store.loadFromCurrentUrl();
    store.setPivot({ rows: "model", cols: "none", metrics: ["mean_reward"], delta: true });
    expect(store.state.delta).toBe(false);
    expect(window.location.search).not.toContain("delta=");
  });
});
