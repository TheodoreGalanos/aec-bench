// ABOUTME: Unit tests for viewer layout sub-components: ViewerTopBar, StatsBar, StepList.
// ABOUTME: Verifies rendering of trial titles, nav links, stat pills, step lists, and active highlighting.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import ViewerTopBar from "./ViewerTopBar.svelte";
import StatsBar from "./StatsBar.svelte";
import StepList from "./StepList.svelte";

// ---------------------------------------------------------------------------
// ViewerTopBar
// ---------------------------------------------------------------------------

describe("ViewerTopBar", () => {
  it("renders the trial title", () => {
    render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: null,
        nextTrial: null,
      },
    });
    expect(screen.getByTestId("trial-title")).toHaveTextContent("trial-abc");
  });

  it("renders the experiment ID", () => {
    render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: null,
        nextTrial: null,
      },
    });
    expect(screen.getByText("exp-01")).toBeInTheDocument();
  });

  it("renders Back link with correct href", () => {
    render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: null,
        nextTrial: null,
      },
    });
    const backLink = screen.getByText(/Back/);
    expect(backLink).toBeInTheDocument();
    expect(backLink.closest("a")).toHaveAttribute("href", "/");
  });

  it("renders prev trial nav link when prevTrial provided", () => {
    render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: "trial-prev",
        nextTrial: null,
      },
    });
    const prev = screen.getByTestId("prev-trial");
    expect(prev).toHaveAttribute("href", "/viewer/exp-01/trial-prev");
  });

  it("renders next trial nav link when nextTrial provided", () => {
    render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: null,
        nextTrial: "trial-next",
      },
    });
    const next = screen.getByTestId("next-trial");
    expect(next).toHaveAttribute("href", "/viewer/exp-01/trial-next");
  });

  it("disables prev arrow when prevTrial is null", () => {
    const { container } = render(ViewerTopBar, {
      props: {
        experimentId: "exp-01",
        trialId: "trial-abc",
        backUrl: "/",
        prevTrial: null,
        nextTrial: null,
      },
    });
    expect(screen.queryByTestId("prev-trial")).not.toBeInTheDocument();
    expect(container.querySelector(".nav-arrow.disabled")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// StatsBar
// ---------------------------------------------------------------------------

describe("StatsBar", () => {
  const baseProps = {
    reward: 0.85,
    rewardClass: "reward-good",
    totalSteps: 12,
    totalErrors: 2,
    tokensIn: 5000,
    tokensOut: 1200,
    totalTokens: 6200,
    costUsd: null as number | null,
    adapterType: "other",
    annotation: null,
    experimentId: "exp-01",
    trialId: "trial-abc",
    activeStep: -1,
    steps: [],
  };

  it("renders reward badge with formatted value", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.getByText("0.850")).toBeInTheDocument();
  });

  it("renders total steps stat pill", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("steps")).toBeInTheDocument();
  });

  it("renders total errors stat pill", () => {
    render(StatsBar, { props: baseProps });
    const errorsLabel = screen.getByText("errors");
    expect(errorsLabel).toBeInTheDocument();
    const pill = errorsLabel.closest(".stat-pill");
    expect(pill).toBeInTheDocument();
    expect(pill?.textContent).toContain("2");
  });

  it("renders tokens stat pill when totalTokens provided", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.getByText("6.2k")).toBeInTheDocument();
    expect(screen.getByText("tokens")).toBeInTheDocument();
  });

  it("does not render tokens when totalTokens is null", () => {
    render(StatsBar, { props: { ...baseProps, totalTokens: null } });
    expect(screen.queryByText("tokens")).not.toBeInTheDocument();
  });

  it("renders cost pill when costUsd provided", () => {
    render(StatsBar, { props: { ...baseProps, costUsd: 0.56 } });
    expect(screen.getByText("$0.56")).toBeInTheDocument();
  });

  it("does not render cost pill when costUsd is null", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.queryByText("cost")).not.toBeInTheDocument();
  });

  it("renders RLM badge when adapterType is rlm", () => {
    render(StatsBar, { props: { ...baseProps, adapterType: "rlm" } });
    expect(screen.getByText("RLM")).toBeInTheDocument();
  });

  it("renders lambda-RLM badge when adapterType is lambda-rlm", () => {
    render(StatsBar, { props: { ...baseProps, adapterType: "lambda-rlm" } });
    expect(screen.getByText("\u03bb-RLM")).toBeInTheDocument();
  });

  it("does not render adapter badge when adapterType is other", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.queryByText("RLM")).not.toBeInTheDocument();
    expect(screen.queryByText("\u03bb-RLM")).not.toBeInTheDocument();
  });

  it("renders RLM per-step metrics when step has token metadata", () => {
    const rlmStep = {
      step: 1, status: "success", description: "init", tool_name: "read_file",
      duration_ms: 100, error_count: 0,
      metadata: { tokens: { call_input: 45231, cache_read: 772030, cost_cumulative: 0.56 } },
      call_type: null, output_summary: null,
    };
    render(StatsBar, {
      props: { ...baseProps, adapterType: "rlm", activeStep: 1, steps: [rlmStep] },
    });
    expect(screen.getByTestId("rlm-metrics")).toBeInTheDocument();
    expect(screen.getByTestId("rlm-metrics").textContent).toContain("45.2k");
  });

  it("does not render RLM metrics for non-RLM trial", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.queryByTestId("rlm-metrics")).not.toBeInTheDocument();
  });

  it("renders annotation verdict when annotation exists", () => {
    render(StatsBar, {
      props: {
        ...baseProps,
        annotation: { verdict: "pass", notes: "", timestamp: "2025-01-01" },
      },
    });
    expect(screen.getByTestId("annotation-verdict")).toHaveTextContent("pass");
  });

  it("renders annotation buttons", () => {
    render(StatsBar, { props: baseProps });
    expect(screen.getByTestId("annotate-pass")).toBeInTheDocument();
    expect(screen.getByTestId("annotate-fail")).toBeInTheDocument();
    expect(screen.getByTestId("annotate-defer")).toBeInTheDocument();
    expect(screen.getByTestId("annotate-note")).toBeInTheDocument();
  });

  it("calls onAnnotate when button clicked", async () => {
    const onAnnotate = vi.fn();
    render(StatsBar, { props: { ...baseProps, onAnnotate } });
    await fireEvent.click(screen.getByTestId("annotate-pass"));
    expect(onAnnotate).toHaveBeenCalledWith("pass");
  });
});

// ---------------------------------------------------------------------------
// StepList
// ---------------------------------------------------------------------------

describe("StepList", () => {
  const steps = [
    { step: 1, status: "success", description: "Init", tool_name: "bash", duration_ms: 120, error_count: 0, metadata: null, call_type: null, output_summary: null },
    { step: 2, status: "error", description: "Run calc", tool_name: "python", duration_ms: 3400, error_count: 2, metadata: null, call_type: null, output_summary: null },
    {
      step: 3,
      status: "success",
      description: "Fill section",
      tool_name: "write",
      duration_ms: null,
      error_count: 0,
      metadata: { template_progress: { completed: 3, total: 9 } },
      call_type: null,
      output_summary: null,
    },
  ];

  it("renders all step items", () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    expect(screen.getByTestId("step-1")).toBeInTheDocument();
    expect(screen.getByTestId("step-2")).toBeInTheDocument();
    expect(screen.getByTestId("step-3")).toBeInTheDocument();
  });

  it("highlights the active step", () => {
    const onselect = vi.fn();
    const { container } = render(StepList, { props: { steps, activeStep: 1, onselect } });
    const activeItem = screen.getByTestId("step-1");
    expect(activeItem).toHaveClass("active");
  });

  it("shows error styling for error steps", () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    const errorItem = screen.getByTestId("step-2");
    expect(errorItem).toHaveClass("error");
  });

  it("calls onselect when step is clicked", async () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    await fireEvent.click(screen.getByTestId("step-2"));
    expect(onselect).toHaveBeenCalledWith(2);
  });

  it("shows template progress hint when metadata present", () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    expect(screen.getByText("3/9 sections")).toBeInTheDocument();
  });

  it("renders tool name for each step", () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    expect(screen.getByText("bash")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("write")).toBeInTheDocument();
  });

  it("renders formatted duration", () => {
    const onselect = vi.fn();
    render(StepList, { props: { steps, activeStep: 1, onselect } });
    expect(screen.getByText("120ms")).toBeInTheDocument();
    expect(screen.getByText("3.4s")).toBeInTheDocument();
  });
});
