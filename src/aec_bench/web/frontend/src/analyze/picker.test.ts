// ABOUTME: Tests for the PivotPicker, ScopeFilters, and PresetChips components.
// ABOUTME: Covers selection callbacks, mutual exclusion of rows/cols, preset application.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import PivotPicker from "./PivotPicker.svelte";
import ScopeFilters from "./ScopeFilters.svelte";
import PresetChips from "./PresetChips.svelte";
import type { AnalyzeState } from "../lib/stores/analyze.svelte";

const baseState: AnalyzeState = {
  rows: "adapter",
  cols: "task_type",
  metrics: ["mean_reward"],
  delta: false,
};

describe("PivotPicker", () => {
  it("calls onChange with new pivot when rows dropdown changes", async () => {
    const handler = vi.fn();
    render(PivotPicker, { props: { state: baseState, onChange: handler } });
    const rowsSelect = screen.getByLabelText(/rows/i) as HTMLSelectElement;
    await fireEvent.change(rowsSelect, { target: { value: "model" } });
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ rows: "model", cols: "task_type" }),
    );
  });

  it("prevents selecting the same value for rows and cols", async () => {
    const handler = vi.fn();
    render(PivotPicker, { props: { state: baseState, onChange: handler } });
    const colsSelect = screen.getByLabelText(/cols/i) as HTMLSelectElement;
    // The "adapter" option in the cols dropdown must be disabled (because rows === "adapter").
    const adapterOption = Array.from(colsSelect.options).find((o) => o.value === "adapter");
    expect(adapterOption?.disabled).toBe(true);
  });

  it("only shows the delta toggle when cols is a dim (not 'none') and single metric", () => {
    const { container: c1 } = render(PivotPicker, {
      props: { state: { ...baseState, cols: "none" }, onChange: vi.fn() },
    });
    expect(c1.querySelector('input[type="checkbox"][name="delta"]')).toBeNull();

    const { container: c2 } = render(PivotPicker, {
      props: { state: baseState, onChange: vi.fn() },
    });
    expect(c2.querySelector('input[type="checkbox"][name="delta"]')).not.toBeNull();
  });
});

describe("ScopeFilters", () => {
  it("calls onScopeChange with the updated field when experiment select changes", async () => {
    const handler = vi.fn();
    render(ScopeFilters, {
      props: {
        state: baseState,
        experiments: ["exp-a", "exp-b"],
        datasets: [],
        models: [],
        adapters: [],
        taskTypes: [],
        onScopeChange: handler,
      },
    });
    const select = screen.getByLabelText(/experiment/i) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "exp-a" } });
    expect(handler).toHaveBeenCalledWith({ experiment: "exp-a" });
  });

  it("passing empty string clears the filter (undefined)", async () => {
    const handler = vi.fn();
    render(ScopeFilters, {
      props: {
        state: { ...baseState, experiment: "exp-a" },
        experiments: ["exp-a"],
        datasets: [],
        models: [],
        adapters: [],
        taskTypes: [],
        onScopeChange: handler,
      },
    });
    const select = screen.getByLabelText(/experiment/i) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "" } });
    expect(handler).toHaveBeenCalledWith({ experiment: undefined });
  });
});

describe("PresetChips", () => {
  it("Evaluate preset applies rows=adapter, cols=task_type, metric=mean_reward", async () => {
    const handler = vi.fn();
    render(PresetChips, { props: { onApply: handler } });
    await fireEvent.click(screen.getByText(/evaluate/i));
    expect(handler).toHaveBeenCalledWith({
      rows: "adapter",
      cols: "task_type",
      metrics: ["mean_reward"],
      delta: false,
    });
  });

  it("Compare preset applies rows=task_type, cols=model, metric=mean_reward, delta=true", async () => {
    const handler = vi.fn();
    render(PresetChips, { props: { onApply: handler } });
    await fireEvent.click(screen.getByText(/compare/i));
    expect(handler).toHaveBeenCalledWith({
      rows: "task_type",
      cols: "model",
      metrics: ["mean_reward"],
      delta: true,
    });
  });

  it("Leaderboard preset applies rows=model, cols=none, multi-metric", async () => {
    const handler = vi.fn();
    render(PresetChips, { props: { onApply: handler } });
    await fireEvent.click(screen.getByText(/leaderboard/i));
    expect(handler).toHaveBeenCalledWith({
      rows: "model",
      cols: "none",
      metrics: ["mean_reward", "perfect_pct", "zero_pct", "count", "cost"],
      delta: false,
    });
  });
});
