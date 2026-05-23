// ABOUTME: Tests for the experiments rail and its RailItem cards.
// ABOUTME: Covers click-to-select, active highlight, filter input, and collapse toggle.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import RailItem from "./RailItem.svelte";
import ExperimentsRail from "./ExperimentsRail.svelte";
import type { ExperimentSummary } from "../lib/types";

const exp: ExperimentSummary = {
  experiment_id: "exp-2026-04-14",
  trial_count: 87,
  mean_reward: 0.81,
  models: ["claude-sonnet-4-6"],
  disciplines: ["electrical"],
  adapters: ["rlm"],
};

describe("RailItem", () => {
  it("renders the experiment id and trial count", () => {
    render(RailItem, { props: { experiment: exp } });
    expect(screen.getByText("exp-2026-04-14")).toBeInTheDocument();
    expect(screen.getByText(/87/)).toBeInTheDocument();
  });

  it("calls onSelect with the experiment id when clicked", async () => {
    const handler = vi.fn();
    render(RailItem, { props: { experiment: exp, onSelect: handler } });
    await fireEvent.click(screen.getByRole("link"));
    expect(handler).toHaveBeenCalledWith("exp-2026-04-14");
  });

  it("marks the item as current when active=true", () => {
    const { container } = render(RailItem, {
      props: { experiment: exp, active: true },
    });
    const link = container.querySelector("a.rail-item") as HTMLAnchorElement;
    expect(link).not.toBeNull();
    expect(link.classList.contains("active")).toBe(true);
    expect(link.getAttribute("aria-current")).toBe("page");
  });

  it("does not intercept middle-click auxclick events", async () => {
    const handler = vi.fn();
    const { container } = render(RailItem, {
      props: { experiment: exp, onSelect: handler },
    });
    const link = container.querySelector("a.rail-item") as HTMLAnchorElement;
    const clickEvent = new MouseEvent("auxclick", { bubbles: true, cancelable: true, button: 1 });
    link.dispatchEvent(clickEvent);
    expect(clickEvent.defaultPrevented).toBe(false);
    expect(handler).not.toHaveBeenCalled();
  });
});

const experiments: ExperimentSummary[] = [
  { ...exp, experiment_id: "exp-04-14" },
  {
    ...exp,
    experiment_id: "exp-04-13",
    trial_count: 50,
    mean_reward: 0.55,
  },
  {
    ...exp,
    experiment_id: "exp-04-12",
    trial_count: 22,
    mean_reward: 0.10,
  },
];

describe("ExperimentsRail", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders a card per experiment", () => {
    render(ExperimentsRail, { props: { experiments } });
    expect(screen.getByText("exp-04-14")).toBeInTheDocument();
    expect(screen.getByText("exp-04-13")).toBeInTheDocument();
    expect(screen.getByText("exp-04-12")).toBeInTheDocument();
  });

  it("highlights the active experiment", () => {
    const { container } = render(ExperimentsRail, {
      props: { experiments, activeExperimentId: "exp-04-13" },
    });
    const active = container.querySelectorAll(".rail-item.active");
    expect(active.length).toBe(1);
    expect(active[0].textContent).toContain("exp-04-13");
  });

  it("filters cards by the rail filter input", async () => {
    render(ExperimentsRail, { props: { experiments } });
    const input = screen.getByPlaceholderText(/filter/i) as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "04-13" } });
    expect(screen.queryByText("exp-04-14")).toBeNull();
    expect(screen.getByText("exp-04-13")).toBeInTheDocument();
  });

  it("persists collapsed state to localStorage", async () => {
    const { container } = render(ExperimentsRail, { props: { experiments } });
    const toggle = screen.getByRole("button", { name: /collapse/i });
    await fireEvent.click(toggle);
    expect(container.querySelector(".rail.collapsed")).not.toBeNull();
    expect(localStorage.getItem("runs.rail.collapsed")).toBe("true");
  });
});
