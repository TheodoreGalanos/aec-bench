// ABOUTME: Component tests for EvoCyclesTab — cycle bar + file tree + content viewer composition.
// ABOUTME: Focused on prop-passing; internal components are tested separately.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import EvoCyclesTab from "./EvoCyclesTab.svelte";
import type { EvolutionData, EvolutionTreeData, FileContent, FileDiff } from "../lib/types";

const data: EvolutionData = {
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
};

describe("EvoCyclesTab", () => {
  it("renders the workspace cycle bar when data is present", () => {
    render(EvoCyclesTab, {
      props: {
        data,
        treeData: null,
        fileContent: null,
        fileDiff: null,
        activeCycle: 1,
        activeFile: null,
        viewMode: "content" as const,
        loadingTree: false,
        loadingFile: false,
        onCycleChange: () => {},
        onFileSelect: () => {},
        onViewModeChange: () => {},
      },
    });
    // Cycle bar renders cycle numbers
    expect(screen.getByText(/1/)).toBeInTheDocument();
  });

  it("renders a placeholder message when data is null", () => {
    render(EvoCyclesTab, {
      props: {
        data: null,
        treeData: null,
        fileContent: null,
        fileDiff: null,
        activeCycle: 0,
        activeFile: null,
        viewMode: "content" as const,
        loadingTree: false,
        loadingFile: false,
        onCycleChange: () => {},
        onFileSelect: () => {},
        onViewModeChange: () => {},
      },
    });
    expect(screen.getByText("Loading cycles…")).toBeInTheDocument();
  });
});
