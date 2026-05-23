// ABOUTME: Unit tests for the DataTable component — headers, rows, sorting, and empty state.
// ABOUTME: Uses @testing-library/svelte with jsdom.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import DataTable from "./DataTable.svelte";
import type { Column } from "./DataTable.svelte";

const columns: Column[] = [
  { key: "name", label: "Name", sortable: true },
  { key: "reward", label: "Reward", sortable: true },
  { key: "model", label: "Model" },
];

const rows = [
  { name: "voltage-drop", reward: 0.875, model: "gpt-4.1-mini" },
  { name: "cable-sizing", reward: 1.0, model: "claude-sonnet-4-6" },
];

// ---------------------------------------------------------------------------
// Column headers
// ---------------------------------------------------------------------------

describe("DataTable headers", () => {
  it("renders all column labels", () => {
    render(DataTable, { props: { columns, rows } });
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Reward")).toBeInTheDocument();
    expect(screen.getByText("Model")).toBeInTheDocument();
  });

  it("applies sortable class on sortable columns", () => {
    const { container } = render(DataTable, { props: { columns, rows } });
    const ths = container.querySelectorAll("th.sortable");
    expect(ths.length).toBe(2);
  });

  it("shows sort indicator on active sort column (asc)", () => {
    render(DataTable, { props: { columns, rows, sortKey: "name", sortDir: "asc" } });
    expect(screen.getByText(/Name\s*▲/)).toBeInTheDocument();
  });

  it("shows sort indicator on active sort column (desc)", () => {
    render(DataTable, { props: { columns, rows, sortKey: "reward", sortDir: "desc" } });
    expect(screen.getByText(/Reward\s*▼/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Row data
// ---------------------------------------------------------------------------

describe("DataTable rows", () => {
  it("renders row data for each row", () => {
    render(DataTable, { props: { columns, rows } });
    expect(screen.getByText("voltage-drop")).toBeInTheDocument();
    expect(screen.getByText("cable-sizing")).toBeInTheDocument();
    expect(screen.getByText("gpt-4.1-mini")).toBeInTheDocument();
  });

  it("renders all cell values", () => {
    render(DataTable, { props: { columns, rows } });
    expect(screen.getByText("0.875")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("DataTable empty state", () => {
  it("shows default empty message when no rows", () => {
    render(DataTable, { props: { columns, rows: [] } });
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("shows custom empty message when provided", () => {
    render(DataTable, { props: { columns, rows: [], emptyMessage: "No trials found." } });
    expect(screen.getByText("No trials found.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Sort interaction
// ---------------------------------------------------------------------------

describe("DataTable sort interaction", () => {
  it("calls onsort with column key when sortable header clicked", async () => {
    const onsort = vi.fn();
    render(DataTable, { props: { columns, rows, onsort } });
    await fireEvent.click(screen.getByText("Name"));
    expect(onsort).toHaveBeenCalledWith("name");
  });

  it("does not call onsort for non-sortable column", async () => {
    const onsort = vi.fn();
    render(DataTable, { props: { columns, rows, onsort } });
    await fireEvent.click(screen.getByText("Model"));
    expect(onsort).not.toHaveBeenCalled();
  });
});
