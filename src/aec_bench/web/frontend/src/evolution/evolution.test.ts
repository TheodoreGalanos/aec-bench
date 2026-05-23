// ABOUTME: Unit tests for evolution page components (list and workspace explorer).
// ABOUTME: Mocks the API module and verifies rendering of content, empty states, and loading behaviour.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

vi.mock("../lib/api");

import * as api from "../lib/api";
import Evolution from "../pages/Evolution.svelte";

// ---------------------------------------------------------------------------
// Mock data fixtures
// ---------------------------------------------------------------------------

const mockWorkspacesData = {
  workspaces: [
    {
      name: "Voltage Drop Evolution",
      path: "voltage-drop-evo",
      cycles: 2,
      best_score: 0.65,
      final_score: 0.45,
      model: "au.anthropic.claude-sonnet-4-6",
    },
  ],
};

const emptyWorkspacesData = {
  workspaces: [],
};

// ---------------------------------------------------------------------------
// Evolution list page
// ---------------------------------------------------------------------------

describe("Evolution list page", () => {
  beforeEach(() => {
    vi.mocked(api.fetchEvolutionWorkspaces).mockResolvedValue(mockWorkspacesData);
  });

  it("renders workspace name in card", async () => {
    render(Evolution);
    await waitFor(() => {
      expect(screen.getByText("Voltage Drop Evolution")).toBeInTheDocument();
    });
  });

  it("renders cycle count", async () => {
    render(Evolution);
    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("renders best score", async () => {
    render(Evolution);
    await waitFor(() => {
      // best_score renders via .toFixed(2) — not as a percentage
      expect(screen.getByText("0.65")).toBeInTheDocument();
    });
  });

  it("shows empty state when no workspaces", async () => {
    vi.mocked(api.fetchEvolutionWorkspaces).mockResolvedValueOnce(emptyWorkspacesData);
    render(Evolution);
    await waitFor(() => {
      expect(screen.getByText("No evolution workspaces found.")).toBeInTheDocument();
    });
  });

  it("calls fetchEvolutionWorkspaces on mount", async () => {
    render(Evolution);
    await waitFor(() => {
      expect(vi.mocked(api.fetchEvolutionWorkspaces)).toHaveBeenCalled();
    });
  });

  it("renders page heading", () => {
    render(Evolution);
    expect(screen.getByText("Evolution")).toBeInTheDocument();
  });
});
