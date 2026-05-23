// ABOUTME: Unit tests for viewer RLM state sub-components: TemplateProgress, VariableList, ScratchpadList.
// ABOUTME: Verifies progress rendering, section fill marks, variable new-badges, and scratchpad key listing.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import TemplateProgress from "./TemplateProgress.svelte";
import VariableList from "./VariableList.svelte";
import ScratchpadList from "./ScratchpadList.svelte";

// ---------------------------------------------------------------------------
// TemplateProgress
// ---------------------------------------------------------------------------

describe("TemplateProgress", () => {
  const sections = [
    { id: "intro", filled: true },
    { id: "scope", filled: true },
    { id: "methodology", filled: true },
    { id: "analysis", filled: false },
    { id: "results", filled: false },
    { id: "conclusions", filled: false },
    { id: "references", filled: false },
    { id: "appendix_a", filled: false },
    { id: "appendix_b", filled: false },
  ];

  it("renders progress text with completed / total", () => {
    render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    expect(screen.getByTestId("progress-text")).toHaveTextContent("3 / 9 sections");
  });

  it("renders progress bar track", () => {
    const { container } = render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    expect(container.querySelector(".progress-track")).toBeInTheDocument();
  });

  it("renders progress fill with correct width", () => {
    const { container } = render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    const fill = container.querySelector(".progress-fill") as HTMLElement;
    expect(fill).toBeInTheDocument();
    // 3/9 = 33.33...%
    expect(fill.style.width).toContain("33.");
  });

  it("marks filled sections with checkmark", () => {
    render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    const introItem = screen.getByTestId("section-intro");
    expect(introItem).toHaveClass("filled");
  });

  it("marks unfilled sections without filled class", () => {
    render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    const analysisItem = screen.getByTestId("section-analysis");
    expect(analysisItem).not.toHaveClass("filled");
  });

  it("renders all section names", () => {
    render(TemplateProgress, {
      props: { completed: 3, total: 9, sections },
    });
    expect(screen.getByText("intro")).toBeInTheDocument();
    expect(screen.getByText("scope")).toBeInTheDocument();
    expect(screen.getByText("methodology")).toBeInTheDocument();
    expect(screen.getByText("analysis")).toBeInTheDocument();
    expect(screen.getByText("results")).toBeInTheDocument();
    expect(screen.getByText("conclusions")).toBeInTheDocument();
  });

  it("renders 0% width when completed is 0", () => {
    const { container } = render(TemplateProgress, {
      props: { completed: 0, total: 5, sections: [] },
    });
    const fill = container.querySelector(".progress-fill") as HTMLElement;
    expect(fill.style.width).toBe("0%");
  });

  it("renders 100% width when all completed", () => {
    const { container } = render(TemplateProgress, {
      props: { completed: 9, total: 9, sections },
    });
    const fill = container.querySelector(".progress-fill") as HTMLElement;
    expect(fill.style.width).toBe("100%");
  });
});

// ---------------------------------------------------------------------------
// VariableList
// ---------------------------------------------------------------------------

describe("VariableList", () => {
  const variables = [
    { name: "cable_size", type: "number", isNew: false },
    { name: "voltage_drop", type: "number", isNew: true },
    { name: "config", type: "object", isNew: false },
  ];

  it("renders all variable names", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    expect(screen.getByText("cable_size")).toBeInTheDocument();
    expect(screen.getByText("voltage_drop")).toBeInTheDocument();
    expect(screen.getByText("config")).toBeInTheDocument();
  });

  it("renders type hints for variables", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    // "number" appears twice (cable_size, voltage_drop) and "object" once
    const numberEls = screen.getAllByText("number");
    expect(numberEls.length).toBe(2);
    expect(screen.getByText("object")).toBeInTheDocument();
  });

  it("highlights new variables with is-new class", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    const vdItem = screen.getByTestId("variable-voltage_drop");
    expect(vdItem).toHaveClass("is-new");
  });

  it("renders new badge for new variables", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    expect(screen.getByTestId("new-badge-voltage_drop")).toBeInTheDocument();
    expect(screen.getByTestId("new-badge-voltage_drop")).toHaveTextContent("new");
  });

  it("does not render new badge for existing variables", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    expect(screen.queryByTestId("new-badge-cable_size")).not.toBeInTheDocument();
  });

  it("calls onselect when a variable is clicked", async () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables, onselect } });
    await fireEvent.click(screen.getByTestId("variable-cable_size"));
    expect(onselect).toHaveBeenCalledWith("cable_size");
  });

  it("renders empty hint when no variables", () => {
    const onselect = vi.fn();
    render(VariableList, { props: { variables: [], onselect } });
    expect(screen.getByText("No variables tracked.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ScratchpadList
// ---------------------------------------------------------------------------

describe("ScratchpadList", () => {
  const keys = ["notes", "calculations", "assumptions"];

  it("renders all scratchpad keys", () => {
    const onselect = vi.fn();
    render(ScratchpadList, { props: { keys, onselect } });
    expect(screen.getByText("notes")).toBeInTheDocument();
    expect(screen.getByText("calculations")).toBeInTheDocument();
    expect(screen.getByText("assumptions")).toBeInTheDocument();
  });

  it("calls onselect when a key is clicked", async () => {
    const onselect = vi.fn();
    render(ScratchpadList, { props: { keys, onselect } });
    await fireEvent.click(screen.getByTestId("scratchpad-notes"));
    expect(onselect).toHaveBeenCalledWith("notes");
  });

  it("renders empty hint when no keys", () => {
    const onselect = vi.fn();
    render(ScratchpadList, { props: { keys: [], onselect } });
    expect(screen.getByText("No scratchpad entries.")).toBeInTheDocument();
  });

  it("renders each key with mono font class", () => {
    const onselect = vi.fn();
    const { container } = render(ScratchpadList, { props: { keys, onselect } });
    const keyElements = container.querySelectorAll(".key-name");
    expect(keyElements.length).toBe(3);
  });
});
