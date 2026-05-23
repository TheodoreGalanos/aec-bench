// ABOUTME: Unit tests for the trajectory replay engine.
// ABOUTME: Tests timing, message sequencing, scrubbing, and variable diffing.

import { describe, it, expect, vi } from "vitest";

vi.mock("../../lib/pretext-service", () => ({
  measureText: vi.fn().mockReturnValue({ height: 48, lineCount: 2 }),
  getDefaultLineHeight: vi.fn().mockReturnValue(24),
  FONT_STRINGS: { body: "15px test", mono: "13px test", heading: "15px test" },
}));
import {
  buildReplaySequence,
  getPositionAtTime,
  computeVariableDiff,
  type ReplayMessage,
  type ReplayPosition,
  type StepTiming,
} from "./replay-engine";
import type { StepSummary, TrajectoryMessage } from "../../lib/types";

// --- Helpers ---

function makeStep(step: number, durationMs: number, toolName = "bash"): StepSummary {
  return {
    step,
    status: "success",
    description: `Step ${step}`,
    tool_name: toolName,
    duration_ms: durationMs,
    error_count: 0,
    metadata: null,
    call_type: null,
    output_summary: null,
  };
}

function makeMessages(count: number): TrajectoryMessage[] {
  return Array.from({ length: count }, (_, i) => ({
    role: i % 2 === 0 ? "assistant" : "tool_result",
    content: `Message ${i}`,
  }));
}

// --- buildReplaySequence ---

describe("buildReplaySequence", () => {
  it("returns empty for no steps", () => {
    const result = buildReplaySequence([], new Map());
    expect(result.messages).toHaveLength(0);
    expect(result.totalMs).toBe(0);
  });

  it("builds flat message list from multiple steps", () => {
    const steps = [makeStep(0, 2000), makeStep(1, 3000)];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(2));
    messages.set(1, makeMessages(3));
    const result = buildReplaySequence(steps, messages);
    expect(result.messages).toHaveLength(5);
    expect(result.totalMs).toBe(5000);
  });

  it("spaces messages proportionally within a step", () => {
    const steps = [makeStep(0, 4000)];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(4));
    const result = buildReplaySequence(steps, messages);
    // 4 messages over 4000ms = 1000ms each
    expect(result.messages[0].cumulativeMs).toBe(0);
    expect(result.messages[1].cumulativeMs).toBe(1000);
    expect(result.messages[2].cumulativeMs).toBe(2000);
    expect(result.messages[3].cumulativeMs).toBe(3000);
  });

  it("handles steps with null duration_ms (scales by message count)", () => {
    const steps: StepSummary[] = [{
      step: 0, status: "success", description: "", tool_name: "bash",
      duration_ms: null, error_count: 0, metadata: null,
      call_type: null, output_summary: null,
    }];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(1));
    const result = buildReplaySequence(steps, messages);
    // 1 message => max(1500 * 1, 2000) = 2000ms
    expect(result.totalMs).toBe(2000);
  });

  it("scales null duration by message count for multi-message steps", () => {
    const steps: StepSummary[] = [{
      step: 0, status: "success", description: "", tool_name: "repl",
      duration_ms: null, error_count: 0, metadata: null,
      call_type: null, output_summary: null,
    }];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(4));
    const result = buildReplaySequence(steps, messages);
    // 4 messages => max(1500 * 4, 2000) = 6000ms
    expect(result.totalMs).toBe(6000);
  });

  it("populates label from template_progress metadata", () => {
    const steps: StepSummary[] = [{
      step: 0, status: "success", description: "desc", tool_name: "repl",
      duration_ms: 2000, error_count: 0,
      metadata: { template_progress: { current_section: "Fee Summary" } },
      call_type: null, output_summary: null,
    }];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(1));
    const result = buildReplaySequence(steps, messages);
    expect(result.stepTimings[0].label).toBe("Fee Summary");
  });

  it("populates label from assistant content preview for repl steps", () => {
    const steps: StepSummary[] = [{
      step: 0, status: "success", description: "desc", tool_name: "repl",
      duration_ms: 2000, error_count: 0, metadata: null,
      call_type: null, output_summary: null,
    }];
    const msgs: TrajectoryMessage[] = [
      { role: "assistant", content: "Calculating the total impedance for the circuit branch" },
    ];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, msgs);
    const result = buildReplaySequence(steps, messages);
    expect(result.stepTimings[0].label).toBe("Calculating the total impedance for…");
  });

  it("falls back to tool name for label when no metadata or assistant content", () => {
    const steps = [makeStep(0, 2000, "bash")];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(1));
    const result = buildReplaySequence(steps, messages);
    expect(result.stepTimings[0].label).toBe("bash");
  });

  it("handles steps with no cached messages (skipped)", () => {
    const steps = [makeStep(0, 2000), makeStep(1, 3000)];
    const messages = new Map<number, TrajectoryMessage[]>();
    messages.set(0, makeMessages(2));
    // step 1 not in map
    const result = buildReplaySequence(steps, messages);
    expect(result.messages).toHaveLength(2);
    expect(result.totalMs).toBe(5000); // total still includes step 1 duration
  });

  it("includes predictedHeight on each ReplayMessage", () => {
    const steps = [makeStep(1, 3000)];
    const msgs = new Map();
    msgs.set(1, makeMessages(2));
    const seq = buildReplaySequence(steps, msgs, 500);
    for (const msg of seq.messages) {
      expect(msg.predictedHeight).toBeGreaterThan(0);
    }
  });

  it("builds cumulativeHeights array with correct length", () => {
    const steps = [makeStep(1, 3000)];
    const msgs = new Map();
    msgs.set(1, makeMessages(3));
    const seq = buildReplaySequence(steps, msgs, 500);
    expect(seq.cumulativeHeights).toHaveLength(3);
    expect(seq.cumulativeHeights[2]).toBeGreaterThan(seq.cumulativeHeights[0]);
  });

  it("builds stepContentDensity map", () => {
    const steps = [makeStep(1, 3000), makeStep(2, 2000)];
    const msgs = new Map();
    msgs.set(1, makeMessages(3));
    msgs.set(2, makeMessages(1));
    const seq = buildReplaySequence(steps, msgs, 500);
    expect(seq.stepContentDensity.size).toBe(2);
    expect(seq.stepContentDensity.get(1)).toBeGreaterThan(0);
  });
});

// --- getPositionAtTime ---

describe("getPositionAtTime", () => {
  it("returns first message at time 0", () => {
    const steps = [makeStep(0, 2000)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    msgs.set(0, makeMessages(2));
    const seq = buildReplaySequence(steps, msgs);
    const pos = getPositionAtTime(seq, 0);
    expect(pos.messageIndex).toBe(0);
    expect(pos.step).toBe(0);
  });

  it("advances to second message at midpoint", () => {
    const steps = [makeStep(0, 2000)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    msgs.set(0, makeMessages(2));
    const seq = buildReplaySequence(steps, msgs);
    const pos = getPositionAtTime(seq, 1000);
    expect(pos.messageIndex).toBe(1);
  });

  it("clamps at last message for time past totalMs", () => {
    const steps = [makeStep(0, 2000)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    msgs.set(0, makeMessages(2));
    const seq = buildReplaySequence(steps, msgs);
    const pos = getPositionAtTime(seq, 99999);
    expect(pos.messageIndex).toBe(1);
    expect(pos.finished).toBe(true);
  });

  it("returns correct step for multi-step sequence", () => {
    const steps = [makeStep(0, 1000), makeStep(1, 1000)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    msgs.set(0, makeMessages(1));
    msgs.set(1, makeMessages(1));
    const seq = buildReplaySequence(steps, msgs);
    const pos = getPositionAtTime(seq, 1000);
    expect(pos.step).toBe(1);
  });
});

// --- computeVariableDiff ---

describe("computeVariableDiff", () => {
  it("returns empty diff when both are empty", () => {
    const diff = computeVariableDiff({}, {});
    expect(diff.added).toEqual([]);
    expect(diff.changed).toEqual([]);
    expect(diff.removed).toEqual([]);
  });

  it("detects added variables", () => {
    const diff = computeVariableDiff({}, { cable_size: "6mm²" });
    expect(diff.added).toEqual(["cable_size"]);
  });

  it("detects changed variables", () => {
    const diff = computeVariableDiff(
      { impedance: 5.0 },
      { impedance: 7.41 },
    );
    expect(diff.changed).toEqual(["impedance"]);
  });

  it("detects removed variables", () => {
    const diff = computeVariableDiff(
      { temp: 42 },
      {},
    );
    expect(diff.removed).toEqual(["temp"]);
  });
});
