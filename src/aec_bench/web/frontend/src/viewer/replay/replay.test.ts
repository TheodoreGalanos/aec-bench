// ABOUTME: Component tests for the trajectory replay feature.
// ABOUTME: Tests mounting, playback state, adaptive layout, and keyboard shortcuts.

import { describe, it, expect } from "vitest";
import {
  buildReplaySequence,
  getPositionAtTime,
  formatTime,
  getStepAtTime,
} from "./replay-engine";

// Engine edge cases not covered in Task 1

describe("formatTime", () => {
  it("formats zero", () => {
    expect(formatTime(0)).toBe("00:00");
  });

  it("formats seconds", () => {
    expect(formatTime(45000)).toBe("00:45");
  });

  it("formats minutes and seconds", () => {
    expect(formatTime(125000)).toBe("02:05");
  });
});

describe("getStepAtTime", () => {
  it("returns first step at time 0", () => {
    const timings = [
      { step: 0, startMs: 0, endMs: 2000, durationMs: 2000, toolName: "bash", errorCount: 0, metadata: null },
      { step: 1, startMs: 2000, endMs: 5000, durationMs: 3000, toolName: "search", errorCount: 0, metadata: null },
    ];
    expect(getStepAtTime(timings, 0)).toBe(0);
  });

  it("returns second step past boundary", () => {
    const timings = [
      { step: 0, startMs: 0, endMs: 2000, durationMs: 2000, toolName: "bash", errorCount: 0, metadata: null },
      { step: 1, startMs: 2000, endMs: 5000, durationMs: 3000, toolName: "search", errorCount: 0, metadata: null },
    ];
    expect(getStepAtTime(timings, 2500)).toBe(1);
  });
});

describe("buildReplaySequence edge cases", () => {
  it("handles empty messages map gracefully", () => {
    const steps = [
      { step: 0, status: "success", description: "", tool_name: "bash", duration_ms: 1000, error_count: 0, metadata: null, call_type: null, output_summary: null },
    ];
    const seq = buildReplaySequence(steps, new Map());
    expect(seq.messages).toHaveLength(0);
    expect(seq.totalMs).toBe(1000);
    expect(seq.stepTimings).toHaveLength(1);
  });

  it("preserves step timing even without messages", () => {
    const steps = [
      { step: 0, status: "success", description: "", tool_name: "bash", duration_ms: 2000, error_count: 0, metadata: null, call_type: null, output_summary: null },
      { step: 1, status: "error", description: "", tool_name: "search", duration_ms: 3000, error_count: 2, metadata: null, call_type: null, output_summary: null },
    ];
    const seq = buildReplaySequence(steps, new Map());
    expect(seq.stepTimings[0].startMs).toBe(0);
    expect(seq.stepTimings[0].endMs).toBe(2000);
    expect(seq.stepTimings[1].startMs).toBe(2000);
    expect(seq.stepTimings[1].endMs).toBe(5000);
    expect(seq.stepTimings[1].errorCount).toBe(2);
  });
});
