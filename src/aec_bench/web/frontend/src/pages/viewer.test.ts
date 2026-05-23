// ABOUTME: Unit tests for the Viewer page component.
// ABOUTME: Mocks the API client to verify rendering of trial metadata, step list, reward badge, RLM panel, and fetch behaviour.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";
import Viewer from "./Viewer.svelte";
import * as api from "../lib/api";
import { resetViewer } from "../lib/stores/viewer";

vi.mock("../lib/api");

// Mock pretext-service so VirtualMessagePane's buildLayoutItems does not
// attempt to use HTMLCanvasElement in jsdom (canvas is not implemented there).
vi.mock("../lib/pretext-service", () => ({
  measureText: vi.fn().mockReturnValue({ height: 48, lineCount: 2 }),
  getDefaultLineHeight: vi.fn().mockReturnValue(24),
  FONT_STRINGS: { body: "15px test", mono: "13px test", heading: "15px test" },
  waitForFonts: vi.fn().mockResolvedValue(undefined),
  clearCache: vi.fn(),
}));

// ---------------------------------------------------------------------------
// jsdom polyfills for browser APIs not available in test environment
// ---------------------------------------------------------------------------

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string = "";
  readonly thresholds: ReadonlyArray<number> = [];
  constructor(
    _callback: IntersectionObserverCallback,
    _options?: IntersectionObserverInit,
  ) {}
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

class MockResizeObserver {
  constructor(_callback: ResizeObserverCallback) {}
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal("ResizeObserver", MockResizeObserver);

// ---------------------------------------------------------------------------
// Mock data fixtures
// ---------------------------------------------------------------------------

const mockSteps = [
  {
    step: 1,
    status: "success",
    description: "read_instruction",
    tool_name: "read_file",
    duration_ms: 120,
    error_count: 0,
    metadata: null,
  },
  {
    step: 2,
    status: "success",
    description: "compute",
    tool_name: "python",
    duration_ms: 340,
    error_count: 0,
    metadata: null,
  },
];

const mockViewerMeta = {
  trial_id: "trial-abc-123",
  experiment_id: "exp-electrical-01",
  task_id: "electrical/voltage-drop",
  model: "claude-sonnet",
  adapter: "tool_loop",
  reward: 1.0,
  reward_class: "reward-perfect",
  steps: mockSteps,
  is_rlm_trial: false,
  adapter_type: "other",
  artefacts: [],
  annotation: null,
  total_errors: 0,
  tokens_in: 1500,
  tokens_out: 800,
  total_tokens: 2300,
  cost_usd: 0.56,
  siblings: [],
  prev_trial: null,
  next_trial: null,
  back_url: "/",
  has_trajectory: true,
};

const mockStepData = {
  step_num: 1,
  messages: [{ role: "user", content: "Hello" }],
};

const mockRlmMeta = {
  ...mockViewerMeta,
  trial_id: "trial-rlm-456",
  is_rlm_trial: true,
  adapter: "rlm",
  adapter_type: "rlm",
  steps: [
    {
      step: 1,
      status: "success",
      description: "rlm_step",
      tool_name: "read_file",
      duration_ms: 200,
      error_count: 0,
      metadata: {
        template_progress: { completed: 3, total: 9, section_list: [] },
        new_variables: ["cable_size"],
      },
    },
  ],
};

const mockRlmState = {
  symbolic_state: { cable_size: "4mm2", voltage: 230 },
  scratchpad_data: { notes: "Check AS3008 table" },
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  resetViewer();
  vi.mocked(api.fetchViewerMeta).mockResolvedValue(mockViewerMeta);
  vi.mocked(api.fetchViewerStep).mockResolvedValue(mockStepData);
  vi.mocked(api.fetchViewerState).mockResolvedValue(mockRlmState);
});

// ---------------------------------------------------------------------------
// Trial metadata
// ---------------------------------------------------------------------------

describe("Viewer trial metadata", () => {
  it("fetches and renders trial_id after load", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(screen.getByText("trial-abc-123")).toBeInTheDocument();
    });
  });

  it("renders experiment_id in the top bar", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(screen.getByText("exp-electrical-01")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Step list
// ---------------------------------------------------------------------------

describe("Viewer step list", () => {
  it("renders step buttons for each step", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(screen.getByTestId("step-1")).toBeInTheDocument();
      expect(screen.getByTestId("step-2")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Reward badge
// ---------------------------------------------------------------------------

describe("Viewer reward badge", () => {
  it("renders reward value 1.000", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      // Reward badge appears in both StatsBar and InfoPanel
      const badges = screen.getAllByText("1.000");
      expect(badges.length).toBeGreaterThan(0);
    });
  });
});

// ---------------------------------------------------------------------------
// RLM panel behaviour
// ---------------------------------------------------------------------------

describe("Viewer RLM panel", () => {
  it("does NOT show RLM panel for non-RLM trial", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(screen.getByTestId("viewer-topbar")).toBeInTheDocument();
    });
    expect(screen.queryByText("Template Progress")).not.toBeInTheDocument();
  });

  it("DOES show RLM data for RLM trial", async () => {
    vi.mocked(api.fetchViewerMeta).mockResolvedValueOnce(mockRlmMeta);
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-rlm-456" } });
    await waitFor(() => {
      expect(screen.getByTestId("rlm-state-panel")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Template Progress")).toBeInTheDocument();
    });
  });

  it("fetches RLM state for RLM trials", async () => {
    vi.mocked(api.fetchViewerMeta).mockResolvedValueOnce(mockRlmMeta);
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-rlm-456" } });
    await waitFor(() => {
      expect(vi.mocked(api.fetchViewerState)).toHaveBeenCalledWith(
        "exp-electrical-01",
        "trial-rlm-456"
      );
    });
  });

  it("does NOT fetch RLM state for non-RLM trials", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(screen.getByTestId("viewer-topbar")).toBeInTheDocument();
    });
    expect(vi.mocked(api.fetchViewerState)).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// API call on mount
// ---------------------------------------------------------------------------

describe("Viewer API", () => {
  it("calls fetchViewerMeta on mount", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(vi.mocked(api.fetchViewerMeta)).toHaveBeenCalledWith(
        "exp-electrical-01",
        "trial-abc-123"
      );
    });
  });

  it("calls fetchViewerStep for the first step on mount", async () => {
    render(Viewer, { props: { experiment: "exp-electrical-01", trial: "trial-abc-123" } });
    await waitFor(() => {
      expect(vi.mocked(api.fetchViewerStep)).toHaveBeenCalledWith(
        "exp-electrical-01",
        "trial-abc-123",
        1
      );
    });
  });
});
