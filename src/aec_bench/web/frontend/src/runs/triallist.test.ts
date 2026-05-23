// ABOUTME: Component tests for the TrialList table — rows render, click navigates.
// ABOUTME: Uses @testing-library/svelte with jsdom.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import TrialList from "./TrialList.svelte";
import type { TrialRow } from "../lib/types";

const rows: TrialRow[] = [
  {
    trial_id: "trial-001",
    experiment_id: "exp-a",
    task_id: "electrical/voltage-drop/easy",
    model: "claude-sonnet-4-6",
    adapter: "rlm",
    discipline: "electrical",
    reward: 0.875,
    reward_class: "reward-mid",
    annotation_icon: "",
    annotation_verdict: "",
  },
];

describe("TrialList", () => {
  it("renders a row per trial", () => {
    render(TrialList, { props: { trials: rows } });
    expect(screen.getByText("trial-001")).toBeInTheDocument();
    expect(screen.getByText("electrical/voltage-drop/easy")).toBeInTheDocument();
  });

  it("calls onTrialClick with experiment+trial when a row is clicked", async () => {
    const handler = vi.fn();
    render(TrialList, { props: { trials: rows, onTrialClick: handler } });
    await fireEvent.click(screen.getByText("trial-001"));
    expect(handler).toHaveBeenCalledWith("exp-a", "trial-001");
  });

  it("renders the empty-state message when trials is empty", () => {
    render(TrialList, { props: { trials: [] } });
    expect(screen.getByText(/no trials/i)).toBeInTheDocument();
  });

  it("renders model and adapter as Badge components", () => {
    const { container } = render(TrialList, { props: { trials: rows } });
    // Two badge instances (model + adapter) should be present in the row.
    expect(container.querySelectorAll(".badge").length).toBeGreaterThanOrEqual(2);
  });

  it("renders an em-dash when annotation fields are empty", () => {
    render(TrialList, { props: { trials: rows } });
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("calls onTrialClick when Space is pressed on a row", async () => {
    const handler = vi.fn();
    const { container } = render(TrialList, { props: { trials: rows, onTrialClick: handler } });
    const row = container.querySelector("tr.row") as HTMLElement;
    await fireEvent.keyDown(row, { key: " " });
    expect(handler).toHaveBeenCalledWith("exp-a", "trial-001");
  });

  it("renders both rows when two trials share a trial_id across different experiments", () => {
    const shared: TrialRow[] = [
      { ...rows[0], trial_id: "shared-id", experiment_id: "exp-a" },
      { ...rows[0], trial_id: "shared-id", experiment_id: "exp-b" },
    ];
    const { container } = render(TrialList, { props: { trials: shared } });
    // Both rows must render; Svelte would crash with each_key_duplicate
    // if the {#each} key is just trial.trial_id.
    expect(container.querySelectorAll("tr.row").length).toBe(2);
  });
});
