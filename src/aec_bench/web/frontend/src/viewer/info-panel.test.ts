// ABOUTME: Tests for the Viewer InfoPanel — Related section links and icon rendering.
// ABOUTME: Complements the existing panel tests for Task/Score/Cost/Artefacts sections.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import InfoPanel from "./InfoPanel.svelte";
import type { ViewerMeta } from "../lib/types";

function buildTrial(overrides: Partial<ViewerMeta> = {}): ViewerMeta {
  return {
    trial_id: "trial-001",
    experiment_id: "exp-a",
    dataset_id: "voltage-drop-core@1",
    task_id: "electrical/voltage-drop/easy",
    model: "claude-sonnet-4-6",
    adapter: "rlm",
    reward: 0.875,
    reward_class: "reward-mid",
    steps: [],
    is_rlm_trial: false,
    adapter_type: "other",
    artefacts: [],
    annotation: null,
    total_errors: 0,
    tokens_in: null,
    tokens_out: null,
    total_tokens: null,
    cost_usd: null,
    siblings: [],
    prev_trial: null,
    next_trial: null,
    back_url: "/",
    has_trajectory: false,
    ...overrides,
  };
}

describe("InfoPanel — Related section", () => {
  it("renders a Related heading", () => {
    render(InfoPanel, {
      props: { trial: buildTrial(), artefacts: [], openModal: () => {} },
    });
    expect(screen.getByText("Related")).toBeInTheDocument();
  });

  it("renders the Template link pointing to /library/<discipline>/<template>", () => {
    render(InfoPanel, {
      props: { trial: buildTrial(), artefacts: [], openModal: () => {} },
    });
    const link = screen.getByRole("link", { name: /Template: electrical\/voltage-drop/i });
    expect(link).toHaveAttribute("href", "/library/electrical/voltage-drop");
  });

  it("renders the Dataset link when dataset_id is present", () => {
    render(InfoPanel, {
      props: { trial: buildTrial(), artefacts: [], openModal: () => {} },
    });
    const link = screen.getByRole("link", { name: /Dataset: voltage-drop-core v1/i });
    expect(link).toHaveAttribute("href", "/datasets/voltage-drop-core/1");
  });

  it("hides the Dataset link when dataset_id is null", () => {
    render(InfoPanel, {
      props: {
        trial: buildTrial({ dataset_id: null }),
        artefacts: [],
        openModal: () => {},
      },
    });
    expect(screen.queryByRole("link", { name: /Dataset:/i })).toBeNull();
  });

  it("hides the Dataset link when dataset_id has no '@' separator", () => {
    render(InfoPanel, {
      props: {
        trial: buildTrial({ dataset_id: "no-at-separator" }),
        artefacts: [],
        openModal: () => {},
      },
    });
    expect(screen.queryByRole("link", { name: /Dataset:/i })).toBeNull();
  });

  it("renders the Experiment link pointing to /?experiment=<id>", () => {
    render(InfoPanel, {
      props: { trial: buildTrial(), artefacts: [], openModal: () => {} },
    });
    const link = screen.getByRole("link", { name: /Experiment: exp-a/i });
    expect(link).toHaveAttribute("href", "/?experiment=exp-a");
  });

  it("renders the Review link pointing to /review/trials/<trial_id>", () => {
    render(InfoPanel, {
      props: { trial: buildTrial(), artefacts: [], openModal: () => {} },
    });
    const link = screen.getByRole("link", { name: /Review this trial/i });
    expect(link).toHaveAttribute("href", "/review/trials/trial-001");
  });

  it("hides the Template link when task_id has fewer than 2 segments", () => {
    render(InfoPanel, {
      props: {
        trial: buildTrial({ task_id: "orphan-task" }),
        artefacts: [],
        openModal: () => {},
      },
    });
    expect(screen.queryByRole("link", { name: /Template:/i })).toBeNull();
  });
});
