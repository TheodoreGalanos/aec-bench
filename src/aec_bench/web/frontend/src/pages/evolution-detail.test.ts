// ABOUTME: Composition tests for EvolutionDetail — header, tabs, state wiring.
// ABOUTME: Mocks lib/api + swarm store so tabs render without live network or SSE.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

const evolutionMock = vi.hoisted(() =>
  vi.fn(async () => ({
    workspace_name: "voltage-drop-evo",
    model: "claude-sonnet-4-6",
    strategy: "hill_climb",
    total_cycles: 3,
    converged: false,
    best_score: 0.9,
    final_score: 0.9,
    cycles: [
      { cycle: 1, version_tag: "evo-1", score: 0.5, prompt_diff: "", skills_added: [], skills_modified: [], skills_removed: [], skill_diffs: {}, evolver_reasoning: "" },
    ],
  })),
);
const runsMock = vi.hoisted(() =>
  vi.fn(async () => ({ runs: [{ run_id: "20260412-0317", strategy: "hill_climb", cycles: 3, best_score: 0.9, final_score: 0.9 }] })),
);
const workspacesMock = vi.hoisted(() =>
  vi.fn(async () => ({
    workspaces: [
      { name: "voltage-drop-evo", path: "voltage-drop-evo", run_id: "", strategy: "hill_climb", cycles: 3, best_score: 0.9, final_score: 0.9, model: "claude", has_swarm: false },
    ],
  })),
);
const graveyardMock = vi.hoisted(() => vi.fn(async () => ({ entries: [], total: 0 })));
const archiveMock = vi.hoisted(() => vi.fn(async () => ({ summary: { size: 0, coverage: 0, n_centroids: 0, best_reward: 0, mean_reward: 0, disciplines: [], task_ids: [], bd_dimensions: [] }, points_2d: [] })));
const treeMock = vi.hoisted(() => vi.fn(async () => ({ version: "evo-1", tree: [] })));

vi.mock("../lib/api", () => ({
  fetchEvolutionData: evolutionMock,
  fetchEvolutionRuns: runsMock,
  fetchEvolutionWorkspaces: workspacesMock,
  fetchEvolutionGraveyard: graveyardMock,
  fetchEvolutionArchive: archiveMock,
  fetchEvolutionTree: treeMock,
  fetchEvolutionFile: vi.fn(),
  fetchEvolutionDiff: vi.fn(),
}));

vi.mock("../lib/stores/swarm.svelte", () => ({
  swarmStore: {
    state: null,
    connectionStatus: "disconnected",
    selectedAgentId: null,
    initSwarmStore: vi.fn().mockResolvedValue(undefined),
    resetSwarmStore: vi.fn(),
  },
  SwarmStore: class {},
}));

import EvolutionDetail from "./EvolutionDetail.svelte";

describe("EvolutionDetail", () => {
  beforeEach(() => {
    history.replaceState({}, "", "/evolution/voltage-drop-evo");
  });

  it("renders header + Cycles tab by default", async () => {
    render(EvolutionDetail, { props: { workspace: "voltage-drop-evo" } });
    await waitFor(() => expect(screen.getByText("Cycles")).toBeInTheDocument());
    // The workspace dropdown is a <select> with aria-label="Workspace"
    expect(screen.getByRole("combobox", { name: /workspace/i })).toBeInTheDocument();
  });

  it("switches to Archive tab when clicked and updates URL", async () => {
    render(EvolutionDetail, { props: { workspace: "voltage-drop-evo" } });
    await waitFor(() => expect(screen.getByText("Archive")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Archive"));
    await waitFor(() => expect(window.location.search).toBe("?tab=archive"));
  });

  it("shows the Swarm tab when the workspace has_swarm", async () => {
    workspacesMock.mockResolvedValueOnce({
      workspaces: [
        { name: "with-swarm", path: "with-swarm", run_id: "", strategy: "qd", cycles: 1, best_score: 0.5, final_score: 0.5, model: "x", has_swarm: true },
      ],
    });
    render(EvolutionDetail, { props: { workspace: "with-swarm" } });
    await waitFor(() => expect(screen.getByText("Swarm")).toBeInTheDocument());
  });
});

import App from "../App.svelte";

describe("App routing (Evolution swarm redirect)", () => {
  it("redirects /evolution/swarm/:ws to /evolution/:ws?tab=swarm", async () => {
    history.replaceState({}, "", "/evolution/swarm/voltage-drop-evo");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/evolution/voltage-drop-evo"));
    expect(window.location.search).toBe("?tab=swarm");
  });

  it("preserves query params when redirecting from /evolution/swarm/:ws", async () => {
    history.replaceState({}, "", "/evolution/swarm/voltage-drop-evo?run_id=r1");
    render(App);
    await waitFor(() => expect(window.location.pathname).toBe("/evolution/voltage-drop-evo"));
    expect(window.location.search).toContain("tab=swarm");
    expect(window.location.search).toContain("run_id=r1");
  });
});
