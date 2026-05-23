// ABOUTME: Tests for LambdaRlmStatePanel and SectionPipeline components.
// ABOUTME: Validates section pipeline rendering, phase dot states, and modal interactions.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";
import SectionPipeline from "./SectionPipeline.svelte";
import LambdaRlmStatePanel from "./LambdaRlmStatePanel.svelte";
import type { StepSummary, LambdaRlmState } from "../lib/types";

describe("SectionPipeline", () => {
  const baseSections = [
    {
      id: "background",
      phases: { extract: "done", review: "done", generate: "done" },
      skipped: false,
      current: false,
    },
    {
      id: "methodology",
      phases: { extract: "done", review: "active", generate: "pending" },
      skipped: false,
      current: true,
    },
    {
      id: "fee_summary",
      phases: { extract: "pending", review: "pending", generate: "pending" },
      skipped: true,
      current: false,
    },
  ];

  it("renders all section rows", () => {
    const onselect = vi.fn();
    render(SectionPipeline, { props: { sections: baseSections, onselect } });

    expect(screen.getByTestId("section-row-background")).toBeTruthy();
    expect(screen.getByTestId("section-row-methodology")).toBeTruthy();
    expect(screen.getByTestId("section-row-fee_summary")).toBeTruthy();
  });

  it("calls onselect when section clicked", async () => {
    const onselect = vi.fn();
    render(SectionPipeline, { props: { sections: baseSections, onselect } });

    await fireEvent.click(screen.getByTestId("section-row-background"));
    expect(onselect).toHaveBeenCalledWith("background");
  });

  it("shows dots for active sections and dashes for skipped", () => {
    const onselect = vi.fn();
    render(SectionPipeline, { props: { sections: baseSections, onselect } });

    const bgRow = screen.getByTestId("section-row-background");
    const dots = bgRow.querySelectorAll(".dot");
    expect(dots.length).toBe(3);

    const skippedRow = screen.getByTestId("section-row-fee_summary");
    const dashes = skippedRow.querySelectorAll(".dash");
    expect(dashes.length).toBe(2);
  });
});

describe("LambdaRlmStatePanel", () => {
  const mockPlanState = {
    phase: "generate",
    current_section: "methodology",
    llm_calls: 5,
    estimated_calls: 12,
    tokens_used: 15000,
    estimated_tokens: 53000,
    extractions: {
      background: { brief: { location: "Highway" } },
      methodology: { brief: { approach: "CHR" } },
    },
    reviews: {
      background: { status: "pass", gaps: [], risks: [] },
    },
    sections: {
      background: "Background content here...",
    },
  };

  const mockSteps: StepSummary[] = [
    {
      step: 1,
      status: "success",
      description: "generate",
      tool_name: "generate",
      duration_ms: null,
      error_count: 0,
      metadata: {
        phase: "generate",
        section_id: "methodology",
        plan_state: mockPlanState,
        template_progress: {
          completed: 1,
          total: 2,
          section_list: [
            { id: "background", filled: true },
            { id: "methodology", filled: false },
          ],
        },
      },
      call_type: "main",
      output_summary: null,
    },
  ];

  const mockLambdaState: LambdaRlmState = {
    plan_state: mockPlanState,
  };

  it("renders stats line when plan state available", () => {
    const openModal = vi.fn();
    render(LambdaRlmStatePanel, {
      props: {
        steps: mockSteps,
        activeStep: 1,
        planState: mockLambdaState,
        openModal,
      },
    });

    expect(screen.getByTestId("lambda-stats")).toBeTruthy();
  });

  it("shows empty message when no plan state", () => {
    const openModal = vi.fn();
    render(LambdaRlmStatePanel, {
      props: {
        steps: [],
        activeStep: 0,
        planState: null,
        openModal,
      },
    });

    expect(screen.getByText("Select a step to view pipeline state.")).toBeTruthy();
  });

  it("renders section pipeline", () => {
    const openModal = vi.fn();
    render(LambdaRlmStatePanel, {
      props: {
        steps: mockSteps,
        activeStep: 1,
        planState: mockLambdaState,
        openModal,
      },
    });

    expect(screen.getByTestId("section-pipeline")).toBeTruthy();
  });

  it("opens modal with section detail on click", async () => {
    const openModal = vi.fn();
    render(LambdaRlmStatePanel, {
      props: {
        steps: mockSteps,
        activeStep: 1,
        planState: mockLambdaState,
        openModal,
      },
    });

    await fireEvent.click(screen.getByTestId("section-row-background"));
    expect(openModal).toHaveBeenCalledTimes(1);
    expect(openModal.mock.calls[0][0]).toBe("Section: background");
    expect(openModal.mock.calls[0][1]).toContain("Extraction");
    expect(openModal.mock.calls[0][1]).toContain("Review");
  });
});
