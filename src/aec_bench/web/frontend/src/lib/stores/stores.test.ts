// ABOUTME: Unit tests for the viewer Svelte store.
// ABOUTME: Verifies initial state, state updates, step caching, and loading state.

import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";

import {
  viewerStore,
  resetViewer,
  setActiveStep,
  cacheStepMessages,
  setViewerLoading,
  setViewerTrial,
  setRlmState,
} from "./viewer";

import type { ViewerMeta } from "../types";

// ---------------------------------------------------------------------------
// Viewer store
// ---------------------------------------------------------------------------

describe("viewerStore", () => {
  beforeEach(() => {
    resetViewer();
  });

  it("starts with null trial", () => {
    const state = get(viewerStore);
    expect(state.trial).toBeNull();
  });

  it("starts with empty steps array", () => {
    const state = get(viewerStore);
    expect(state.steps).toEqual([]);
  });

  it("starts with activeStep 0", () => {
    const state = get(viewerStore);
    expect(state.activeStep).toBe(0);
  });

  it("starts with empty stepMessages map", () => {
    const state = get(viewerStore);
    expect(state.stepMessages.size).toBe(0);
  });

  it("starts with null rlm state", () => {
    const state = get(viewerStore);
    expect(state.rlm).toBeNull();
  });

  it("setActiveStep(3) updates activeStep to 3", () => {
    setActiveStep(3);
    const state = get(viewerStore);
    expect(state.activeStep).toBe(3);
  });

  it("cacheStepMessages stores messages for the given step", () => {
    const msgs = [{ role: "user", content: "hello" }];
    cacheStepMessages(0, msgs);
    const state = get(viewerStore);
    expect(state.stepMessages.get(0)).toEqual(msgs);
  });

  it("cacheStepMessages does NOT overwrite an existing cache entry", () => {
    const original = [{ role: "user", content: "original" }];
    const different = [{ role: "user", content: "different" }];
    cacheStepMessages(0, original);
    cacheStepMessages(0, different);
    const state = get(viewerStore);
    expect(state.stepMessages.get(0)).toEqual(original);
  });

  it("setViewerTrial sets trial and steps", () => {
    const trial = {
      trial_id: "t1",
      experiment_id: "exp-01",
      task_id: "voltage-drop",
      model: "claude-sonnet-4-6",
      adapter: "anthropic",
      reward: 0.9,
      reward_class: "reward-good",
      steps: [
        {
          step: 1,
          status: "done",
          description: "First step",
          tool_name: "bash",
          duration_ms: 100,
          error_count: 0,
          metadata: null,
        },
        {
          step: 2,
          status: "done",
          description: "Second step",
          tool_name: "bash",
          duration_ms: 200,
          error_count: 0,
          metadata: null,
        },
      ],
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
    } satisfies ViewerMeta;

    setViewerTrial(trial);
    const state = get(viewerStore);
    expect(state.trial).toEqual(trial);
    expect(state.steps).toHaveLength(2);
  });

  it("setViewerTrial sets activeStep to the first step's step number", () => {
    const trial = {
      trial_id: "t2",
      experiment_id: "exp-01",
      task_id: "voltage-drop",
      model: "claude-sonnet-4-6",
      adapter: "anthropic",
      reward: 1.0,
      reward_class: "reward-perfect",
      steps: [
        {
          step: 5,
          status: "done",
          description: "Step five",
          tool_name: "bash",
          duration_ms: 50,
          error_count: 0,
          metadata: null,
        },
      ],
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
    } satisfies ViewerMeta;

    setViewerTrial(trial);
    const state = get(viewerStore);
    expect(state.activeStep).toBe(5);
  });

  it("setViewerLoading updates the loading key", () => {
    setViewerLoading("meta", true);
    expect(get(viewerStore).loading.meta).toBe(true);
    setViewerLoading("meta", false);
    expect(get(viewerStore).loading.meta).toBe(false);
  });

  it("setRlmState updates rlm state", () => {
    const rlmState = { symbolic_state: { x: 1 }, scratchpad_data: { note: "test" } };
    setRlmState(rlmState);
    expect(get(viewerStore).rlm).toEqual(rlmState);
  });

  it("resetViewer restores initial state", () => {
    setActiveStep(7);
    cacheStepMessages(2, [{ role: "user" }]);
    resetViewer();
    const state = get(viewerStore);
    expect(state.trial).toBeNull();
    expect(state.activeStep).toBe(0);
    expect(state.stepMessages.size).toBe(0);
  });
});

