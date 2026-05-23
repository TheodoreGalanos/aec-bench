// ABOUTME: Composition tests for the Runs page — rail, stats, chips, list all present.
// ABOUTME: Uses jsdom; backend is mocked via vi.mock on api.ts.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/svelte";
import App from "../App.svelte";
import "@testing-library/jest-dom/vitest";

// triageMock must be hoisted so vi.mock factory (which is hoisted) can reference it.
const { triageMock } = vi.hoisted(() => ({
  triageMock: vi.fn(async () => ({
    trials: [
      {
        trial_id: "trial-001",
        experiment_id: "exp-04-14",
        task_id: "electrical/voltage-drop/easy",
        model: "claude-sonnet-4-6",
        adapter: "rlm",
        discipline: "electrical",
        reward: 0.875,
        reward_class: "reward-mid",
        annotation_icon: "",
        annotation_verdict: "",
      },
    ],
    trial_count: 1,
    annotations: {},
    filters: {},
    experiments: ["exp-04-14"],
    models: ["claude-sonnet-4-6"],
  })),
}));

vi.mock("../lib/api", () => ({
  fetchDashboard: vi.fn(async () => ({
    experiments: [
      {
        experiment_id: "exp-04-14",
        trial_count: 5,
        mean_reward: 0.8,
        models: ["claude-sonnet-4-6"],
        disciplines: ["electrical"],
        adapters: ["rlm"],
      },
    ],
    total_experiments: 1,
    total_trials: 5,
    mean_reward: 0.8,
    annotated_count: 0,
  })),
  fetchTriage: triageMock,
  fetchReviewQueue: vi.fn(async () => ({ assignments: {} })),
  fetchReviewTrial: vi.fn(async () => ({ bundle: {} })),
}));

import Runs from "./Runs.svelte";

describe("Runs page", () => {
  beforeEach(() => {
    history.replaceState({}, "", "/");
    triageMock.mockClear();
  });

  it("renders rail, stats, and trial list", async () => {
    render(Runs);
    await waitFor(() => expect(screen.getByText("exp-04-14")).toBeInTheDocument());
    expect(screen.getByText(/experiments/i)).toBeInTheDocument();
    expect(screen.getByText("trial-001")).toBeInTheDocument();
  });

  it("re-fetches trials when an experiment is selected in the rail", async () => {
    render(Runs);
    await waitFor(() => expect(screen.getByText("exp-04-14")).toBeInTheDocument());
    const callsBefore = triageMock.mock.calls.length;

    await fireEvent.click(screen.getByText("exp-04-14"));

    await waitFor(() =>
      expect(triageMock.mock.calls.length).toBeGreaterThan(callsBefore),
    );
    const lastCall = (triageMock.mock.calls.at(-1) as [Record<string, any>] | undefined)?.[0];
    expect(lastCall?.experiment).toBe("exp-04-14");
  });

  it("re-fetches trials when a filter chip is removed", async () => {
    history.replaceState({}, "", "/?experiment=exp-04-14");
    render(Runs);
    await waitFor(() => expect(screen.getByText(/experiment:/i)).toBeInTheDocument());
    const callsBefore = triageMock.mock.calls.length;

    await fireEvent.click(screen.getByLabelText(/remove experiment filter/i));

    await waitFor(() =>
      expect(triageMock.mock.calls.length).toBeGreaterThan(callsBefore),
    );
    const lastCall = (triageMock.mock.calls.at(-1) as [Record<string, any>] | undefined)?.[0];
    expect(lastCall?.experiment).toBeUndefined();
  });

  it("navigates to the viewer when a trial row is clicked", async () => {
    render(Runs);
    await waitFor(() => expect(screen.getByText("trial-001")).toBeInTheDocument());
    const pushStateSpy = vi.spyOn(window.history, "pushState");

    await fireEvent.click(screen.getByText("trial-001"));

    const pushedUrl = pushStateSpy.mock.calls.at(-1)?.[2];
    expect(pushedUrl).toBe("/viewer/exp-04-14/trial-001");
    pushStateSpy.mockRestore();
  });
});

describe("App routing", () => {
  it("redirects /triage?experiment=X to /?experiment=X", async () => {
    history.replaceState({}, "", "/triage?experiment=exp-a&model=haiku");
    render(App);
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("?experiment=exp-a&model=haiku");
    });
  });
});

describe("App routing (Review URL cleanup redirect)", () => {
  it("redirects /review/internal/queue to /review/queue", async () => {
    history.replaceState({}, "", "/review/internal/queue");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/review/queue"));
  });

  it("redirects /review/internal/trials/:id to /review/trials/:id preserving query", async () => {
    history.replaceState({}, "", "/review/internal/trials/trial-001?reviewer_id=rev-a");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/review/trials/trial-001"));
    expect(window.location.search).toContain("reviewer_id=rev-a");
  });
});
