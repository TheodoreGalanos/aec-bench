// ABOUTME: Tests for the generic ResultTable pivot renderer.
// ABOUTME: Covers cell rendering, totals, delta column, multi-metric, cell-click drill.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import ResultTable from "./ResultTable.svelte";
import type { AnalyzeData } from "../lib/types";

const singleMetric: AnalyzeData = {
  rows_dim: "adapter",
  cols_dim: "task_type",
  metrics: ["mean_reward"],
  delta_enabled: false,
  row_labels: ["rlm", "tool_loop"],
  col_labels: ["string-sizing", "voltage-drop"],
  cells: {
    "rlm|string-sizing": { mean_reward: 0.5, count: 1 },
    "rlm|voltage-drop": { mean_reward: 1.0, count: 1 },
    "tool_loop|voltage-drop": { mean_reward: 0.0, count: 1 },
  },
  row_totals: {
    "rlm": { mean_reward: 0.75, count: 2 },
    "tool_loop": { mean_reward: 0.0, count: 1 },
  },
  col_totals: {
    "string-sizing": { mean_reward: 0.5, count: 1 },
    "voltage-drop": { mean_reward: 0.5, count: 2 },
  },
  grand_total: { mean_reward: 0.5, count: 3 },
};

describe("ResultTable", () => {
  it("renders a cell per (row, col) intersection", () => {
    render(ResultTable, { props: { data: singleMetric } });
    expect(screen.getByText("rlm")).toBeInTheDocument();
    expect(screen.getByText("tool_loop")).toBeInTheDocument();
    expect(screen.getByText("voltage-drop")).toBeInTheDocument();
    expect(screen.getByText("string-sizing")).toBeInTheDocument();
    // mean values are rendered to 3dp
    expect(screen.getByText("1.000")).toBeInTheDocument();
    // "0.500" appears in multiple cells (cell, col total, grand total) — use getAllByText
    expect(screen.getAllByText("0.500").length).toBeGreaterThanOrEqual(1);
    // "0.000" appears in both the cell and the row total — use getAllByText
    expect(screen.getAllByText("0.000").length).toBeGreaterThanOrEqual(1);
  });

  it("renders an em-dash for missing cells", () => {
    render(ResultTable, { props: { data: singleMetric } });
    // tool_loop has no string-sizing cell → em-dash
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("renders row totals, col totals, and grand total", () => {
    const { container } = render(ResultTable, { props: { data: singleMetric } });
    const rows = container.querySelectorAll("tr");
    // Last row is the column-totals row; it contains "0.500" three times (string-sizing col total,
    // voltage-drop col total, and grand total).
    expect(rows[rows.length - 1].textContent).toContain("0.500");
    // Row totals are in the rightmost column; rlm's row ends with 0.750
    expect(screen.getByText("0.750")).toBeInTheDocument();
  });

  it("calls onCellClick with (rowLabel, colLabel) when a data cell is clicked", async () => {
    const handler = vi.fn();
    render(ResultTable, { props: { data: singleMetric, onCellClick: handler } });
    await fireEvent.click(screen.getByText("1.000"));
    expect(handler).toHaveBeenCalledWith("rlm", "voltage-drop");
  });

  it("renders a delta column when data.delta_enabled is true", () => {
    const deltaData: AnalyzeData = {
      ...singleMetric,
      delta_enabled: true,
      row_deltas: { "rlm": 0.5, "tool_loop": -0.3 },
    };
    render(ResultTable, { props: { data: deltaData } });
    expect(screen.getByText("Δ")).toBeInTheDocument();
    expect(screen.getByText("+0.500")).toBeInTheDocument();
    expect(screen.getByText("-0.300")).toBeInTheDocument();
  });

  it("renders one column per metric when cols_dim is 'none'", () => {
    const multi: AnalyzeData = {
      rows_dim: "model",
      cols_dim: "none",
      metrics: ["mean_reward", "perfect_pct", "count"],
      delta_enabled: false,
      row_labels: ["sonnet"],
      col_labels: [],
      cells: {},
      row_totals: {
        "sonnet": { mean_reward: 0.7, perfect_pct: 0.33, count: 9 },
      },
      col_totals: {},
      grand_total: { mean_reward: 0.7, perfect_pct: 0.33, count: 9 },
    };
    const { container } = render(ResultTable, { props: { data: multi } });
    // Column headers include the three metric labels.
    expect(screen.getByText(/mean reward/i)).toBeInTheDocument();
    expect(screen.getByText(/perfect %/i)).toBeInTheDocument();
    expect(screen.getByText(/count/i)).toBeInTheDocument();
    // The sonnet row includes all three metric values.
    const sonnetRow = Array.from(container.querySelectorAll("tr")).find(
      (r) => r.textContent?.includes("sonnet"),
    );
    expect(sonnetRow?.textContent).toContain("0.700");
    expect(sonnetRow?.textContent).toContain("33%");
    expect(sonnetRow?.textContent).toContain("9");
  });
});
