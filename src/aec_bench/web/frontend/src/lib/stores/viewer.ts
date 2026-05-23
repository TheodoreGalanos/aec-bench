// ABOUTME: Svelte writable store for viewer page state: trial metadata, steps, active step, and RLM state.
// ABOUTME: Provides helper functions for updating state while preserving cached step messages.

import { writable } from "svelte/store";
import type { ViewerMeta, ViewerState, LambdaRlmState, TrajectoryMessage, StepSummary } from "../types";

interface ViewerStoreState {
  trial: ViewerMeta | null;
  steps: StepSummary[];
  activeStep: number;
  stepMessages: Map<number, TrajectoryMessage[]>;
  rlm: ViewerState | null;
  lambdaRlm: LambdaRlmState | null;
  loading: { meta: boolean; step: boolean };
}

const initialState: ViewerStoreState = {
  trial: null,
  steps: [],
  activeStep: 0,
  stepMessages: new Map(),
  rlm: null,
  lambdaRlm: null,
  loading: { meta: false, step: false },
};

export const viewerStore = writable<ViewerStoreState>({ ...initialState, stepMessages: new Map() });

export function resetViewer(): void {
  viewerStore.set({ ...initialState, stepMessages: new Map() });
}

export function setActiveStep(n: number): void {
  viewerStore.update((s) => ({ ...s, activeStep: n }));
}

export function cacheStepMessages(step: number, messages: TrajectoryMessage[]): void {
  viewerStore.update((s) => {
    // Do not overwrite an existing cache entry for this step
    if (s.stepMessages.has(step)) return s;
    const updated = new Map(s.stepMessages);
    updated.set(step, messages);
    return { ...s, stepMessages: updated };
  });
}

export function setViewerLoading(key: "meta" | "step", value: boolean): void {
  viewerStore.update((s) => ({ ...s, loading: { ...s.loading, [key]: value } }));
}

export function setViewerTrial(trial: ViewerMeta): void {
  viewerStore.update((s) => ({
    ...s,
    trial,
    steps: trial.steps,
    activeStep: trial.steps.length > 0 ? trial.steps[0].step : 0,
  }));
}

export function setRlmState(state: ViewerState | null): void {
  viewerStore.update((s) => ({ ...s, rlm: state }));
}

export function setLambdaRlmState(state: LambdaRlmState | null): void {
  viewerStore.update((s) => ({ ...s, lambdaRlm: state }));
}
