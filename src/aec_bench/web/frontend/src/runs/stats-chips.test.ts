// ABOUTME: Tests for the StatsStrip and FilterChips components on the Runs page.
// ABOUTME: Covers stat rendering, chip removal callbacks, and empty states.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import StatsStrip from "./StatsStrip.svelte";
import FilterChips from "./FilterChips.svelte";
import type { RunsFilter } from "../lib/stores/runs.svelte";

describe("StatsStrip", () => {
  it("renders the four stat values", () => {
    render(StatsStrip, {
      props: {
        totalExperiments: 12,
        totalTrials: 874,
        meanReward: 0.731,
        annotatedCount: 41,
      },
    });
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("874")).toBeInTheDocument();
    expect(screen.getByText(/0\.731/)).toBeInTheDocument();
    expect(screen.getByText("41")).toBeInTheDocument();
  });

  it("shows an em-dash when meanReward is NaN", () => {
    render(StatsStrip, {
      props: { totalExperiments: 0, totalTrials: 0, meanReward: NaN, annotatedCount: 0 },
    });
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("FilterChips", () => {
  it("renders no chips for an empty filter", () => {
    const { container } = render(FilterChips, { props: { filter: {} } });
    expect(container.querySelectorAll(".chip").length).toBe(0);
  });

  it("renders one chip per active filter key", () => {
    const filter: RunsFilter = {
      experiment: "exp-a",
      adapter: "rlm",
      annotated: true,
    };
    const { container } = render(FilterChips, { props: { filter } });
    const chips = container.querySelectorAll(".chip");
    expect(chips.length).toBe(3);

    // Each chip's textContent should contain both label and value, regardless of span structure.
    const texts = Array.from(chips).map((c) => c.textContent?.replace(/\s+/g, " ").trim() ?? "");
    expect(texts.some((t) => t.includes("experiment:") && t.includes("exp-a"))).toBe(true);
    expect(texts.some((t) => t.includes("adapter:") && t.includes("rlm"))).toBe(true);
    expect(texts.some((t) => t.includes("annotated:") && t.includes("true"))).toBe(true);
  });

  it("calls onRemove with the removed key when chip × is clicked", async () => {
    const handler = vi.fn();
    render(FilterChips, {
      props: { filter: { experiment: "exp-a" }, onRemove: handler },
    });
    await fireEvent.click(screen.getByLabelText(/remove experiment filter/i));
    expect(handler).toHaveBeenCalledWith("experiment");
  });

  it("renders reward_min and reward_max as chips with two-decimal formatting", () => {
    const filter: RunsFilter = { reward_min: 0.5, reward_max: 0.85 };
    const { container } = render(FilterChips, { props: { filter } });
    const texts = Array.from(container.querySelectorAll(".chip")).map(
      (c) => c.textContent?.replace(/\s+/g, " ").trim() ?? "",
    );
    expect(texts.some((t) => t.includes("reward ≥") && t.includes("0.50"))).toBe(true);
    expect(texts.some((t) => t.includes("reward ≤") && t.includes("0.85"))).toBe(true);
  });
});
