// ABOUTME: Tests for EvolutionHeader — back link, workspace dropdown, run dropdown, tab strip.
// ABOUTME: Verifies every control emits the right callback with the right value.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import EvolutionHeader from "./EvolutionHeader.svelte";

const workspaces = [
  { name: "voltage-drop-evo-2", path: "voltage-drop-evo-2" },
  { name: "voltage-drop-evo-1", path: "voltage-drop-evo-1" },
  { name: "heat-load-evo", path: "heat-load-evo" },
];

const runs = [
  { run_id: "20260412-0317", strategy: "hill_climb", cycles: 5, best_score: 0.9, final_score: 0.9 },
  { run_id: "20260411-0200", strategy: "qd", cycles: 3, best_score: 0.8, final_score: 0.8 },
];

describe("EvolutionHeader", () => {
  it("renders the back link to /evolution", () => {
    render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: false,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const back = screen.getByRole("link", { name: /workspaces/i });
    expect(back).toHaveAttribute("href", "/evolution");
  });

  it("lists workspaces most-recent first", () => {
    render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: false,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const select = screen.getByLabelText(/workspace/i) as HTMLSelectElement;
    const names = Array.from(select.options).map((o) => o.value);
    // localeCompare reverse sort: evo-2 before evo-1, then heat-load-evo
    expect(names[0]).toBe("voltage-drop-evo-2");
  });

  it("calls onWorkspaceChange when a different workspace is picked", async () => {
    const handler = vi.fn();
    render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: false,
        onWorkspaceChange: handler,
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const select = screen.getByLabelText(/workspace/i) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "heat-load-evo" } });
    expect(handler).toHaveBeenCalledWith("heat-load-evo");
  });

  it("renders three tabs without swarm", () => {
    const { container } = render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: false,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const tabs = container.querySelectorAll(".tab");
    expect(tabs.length).toBe(3);
    expect(Array.from(tabs).map((t) => t.textContent?.trim())).toEqual(["Cycles", "Archive", "Graveyard"]);
  });

  it("renders four tabs with swarm", () => {
    const { container } = render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: true,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const tabs = container.querySelectorAll(".tab");
    expect(tabs.length).toBe(4);
    expect(tabs[3].textContent?.trim()).toBe("Swarm");
  });

  it("applies active class to the active tab", () => {
    const { container } = render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "archive",
        hasSwarm: false,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: () => {},
      },
    });
    const active = container.querySelector(".tab.active");
    expect(active?.textContent?.trim()).toBe("Archive");
  });

  it("calls onTabChange when a tab is clicked", async () => {
    const handler = vi.fn();
    render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: true,
        onWorkspaceChange: () => {},
        onRunChange: () => {},
        onTabChange: handler,
      },
    });
    await fireEvent.click(screen.getByText("Swarm"));
    expect(handler).toHaveBeenCalledWith("swarm");
  });

  it("calls onRunChange when a run is picked", async () => {
    const handler = vi.fn();
    render(EvolutionHeader, {
      props: {
        workspace: "voltage-drop-evo-1",
        workspaces,
        runs,
        activeRunId: "20260412-0317",
        activeTab: "cycles",
        hasSwarm: false,
        onWorkspaceChange: () => {},
        onRunChange: handler,
        onTabChange: () => {},
      },
    });
    const select = screen.getByLabelText(/run/i) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "20260411-0200" } });
    expect(handler).toHaveBeenCalledWith("20260411-0200");
  });
});
