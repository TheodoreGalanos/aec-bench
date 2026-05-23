// ABOUTME: Composition tests for the Analyze page — picker, scope, preset, table all wire up.
// ABOUTME: Uses vi.mock on lib/api to stub fetchAnalyze and fetchDashboard. Also covers App routing redirects.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

const analyzeMock = vi.hoisted(() =>
  vi.fn(async () => ({
    rows_dim: "adapter",
    cols_dim: "task_type",
    metrics: ["mean_reward"],
    delta_enabled: false,
    row_labels: ["rlm"],
    col_labels: ["voltage-drop"],
    cells: { "rlm|voltage-drop": { mean_reward: 1.0, count: 1 } },
    row_totals: { "rlm": { mean_reward: 1.0, count: 1 } },
    col_totals: { "voltage-drop": { mean_reward: 1.0, count: 1 } },
    grand_total: { mean_reward: 1.0, count: 1 },
  })),
);
const dashboardMock = vi.hoisted(() =>
  vi.fn(async () => ({
    experiments: [{
      experiment_id: "exp-a",
      trial_count: 1, mean_reward: 1.0,
      models: ["sonnet"], disciplines: ["electrical"], adapters: ["rlm"],
    }],
    total_experiments: 1, total_trials: 1, mean_reward: 1.0, annotated_count: 0,
  })),
);

// Stub other page APIs so redirect tests that briefly mount other pages don't error.
const noopMock = vi.hoisted(() => vi.fn(async () => ({})));
// Leaderboard needs a valid data shape (scorecard_rows array) to avoid render errors.
const leaderboardMock = vi.hoisted(() =>
  vi.fn(async () => ({
    scorecard_rows: [],
    datasets: [],
    models: [],
  })),
);

vi.mock("../lib/api", () => ({
  fetchAnalyze: analyzeMock,
  fetchDashboard: dashboardMock,
  fetchLeaderboard: leaderboardMock,
  fetchRunsList: noopMock,
}));

import Analyze from "./Analyze.svelte";
import App from "../App.svelte";

describe("Analyze page", () => {
  beforeEach(() => {
    history.replaceState({}, "", "/analyze");
    analyzeMock.mockClear();
    dashboardMock.mockClear();
  });

  it("renders picker, scope, preset chips, and the result table", async () => {
    render(Analyze);
    // "rlm" appears in both the adapter option and the table row — any match is fine.
    await waitFor(() => expect(screen.getAllByText("rlm").length).toBeGreaterThan(0));
    expect(screen.getByLabelText(/rows/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/experiment/i)).toBeInTheDocument();
    expect(screen.getByText(/evaluate/i)).toBeInTheDocument();
    // "1.000" appears in the table (data cell, totals) — any match is fine.
    expect(screen.getAllByText("1.000").length).toBeGreaterThan(0);
  });

  it("re-fetches when a preset is applied", async () => {
    render(Analyze);
    await waitFor(() => expect(analyzeMock).toHaveBeenCalled());
    const before = analyzeMock.mock.calls.length;
    await fireEvent.click(screen.getByText(/compare/i));
    await waitFor(() => expect(analyzeMock.mock.calls.length).toBeGreaterThan(before));
    const lastArgs = (analyzeMock.mock.calls.at(-1) as [Record<string, any>] | undefined)?.[0];
    expect(lastArgs?.rows).toBe("task_type");
    expect(lastArgs?.cols).toBe("model");
    expect(lastArgs?.delta).toBe(true);
  });

  it("passes metrics to fetchAnalyze as an array (not a pre-joined string)", async () => {
    // Regression: fetchAnalyze types metrics as AnalyzeMetric[] and joins internally.
    // If the caller pre-joins, fetchAnalyze crashes with "metrics.join is not a function".
    render(Analyze);
    await waitFor(() => expect(analyzeMock).toHaveBeenCalled());
    const firstArgs = (analyzeMock.mock.calls[0] as unknown as
      | [Record<string, any>]
      | undefined)?.[0];
    expect(Array.isArray(firstArgs?.metrics)).toBe(true);
    expect(firstArgs?.metrics).toEqual(["mean_reward"]);
  });

  it("navigates to / with filters when a cell is clicked", async () => {
    const { container } = render(Analyze);
    await waitFor(() => expect(screen.getAllByText("1.000").length).toBeGreaterThan(0));
    const pushStateSpy = vi.spyOn(window.history, "pushState");
    // Click the clickable data cell (role=button), not the total cells.
    const dataCell = container.querySelector("td[role='button']")!;
    await fireEvent.click(dataCell);
    const pushedUrl = pushStateSpy.mock.calls.at(-1)?.[2];
    expect(pushedUrl).toMatch(/^\/\?/);
    expect(pushedUrl).toContain("adapter=rlm");
    expect(pushedUrl).toContain("task_type=voltage-drop");
    pushStateSpy.mockRestore();
  });
});

describe("App routing (Analyze redirects)", () => {
  beforeEach(() => {
    analyzeMock.mockClear();
    dashboardMock.mockClear();
  });

  it("redirects /evaluate?experiment=X to /analyze?rows=adapter&cols=task_type&metrics=mean_reward&experiment=X", async () => {
    history.replaceState({}, "", "/evaluate?experiment=exp-a");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/analyze"));
    expect(window.location.search).toContain("experiment=exp-a");
    expect(window.location.search).toContain("rows=adapter");
  });

  it("redirects /compare?experiment=X to /analyze with the Compare preset", async () => {
    history.replaceState({}, "", "/compare?experiment=exp-a");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/analyze"));
    expect(window.location.search).toContain("rows=task_type");
    expect(window.location.search).toContain("cols=model");
    expect(window.location.search).toContain("delta=true");
  });

  it("redirects /leaderboard?dataset=X to /analyze with the Leaderboard preset", async () => {
    history.replaceState({}, "", "/leaderboard?dataset=electrical-core@1");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/analyze"));
    // Leaderboard preset: rows=model, cols=none, multi-metric
    expect(window.location.search).toContain("rows=model");
    expect(window.location.search).toContain("cols=none");
    expect(window.location.search).toContain("metrics=mean_reward,perfect_pct,zero_pct,count,cost");
    expect(window.location.search).toContain("dataset=electrical-core@1");
  });

  it("does NOT redirect bare /leaderboard (no dataset param)", async () => {
    history.replaceState({}, "", "/leaderboard");
    render(App);
    // Allow any effects to run, then assert no redirect happened.
    await new Promise((r) => setTimeout(r, 50));
    expect(window.location.pathname).toBe("/leaderboard");
  });
});
