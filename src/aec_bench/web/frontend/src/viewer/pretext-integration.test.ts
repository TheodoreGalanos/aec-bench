// ABOUTME: Integration tests verifying pretext service works end-to-end with layout model.
// ABOUTME: Tests that virtual layout produces consistent results and handles edge cases.

import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";

// Mock canvas for jsdom
beforeAll(() => {
  const mockGetContext = function (contextId: string) {
    if (contextId !== "2d") return null;
    return {
      measureText: (text: string) => ({ width: text.length * 8 }),
      font: "",
    } as unknown as CanvasRenderingContext2D;
  };
  HTMLCanvasElement.prototype.getContext =
    mockGetContext as typeof HTMLCanvasElement.prototype.getContext;
});

import { measureText, measureMinWidth, clearCache, getDefaultLineHeight } from "../lib/pretext-service";
import { buildLayoutItems, getTotalHeight, getVisibleRange, getOffsetForStep } from "./virtual-layout";
import type { StepSummary, TrajectoryMessage } from "../lib/types";

beforeEach(() => {
  clearCache();
});

function makeStep(step: number, toolName = "bash"): StepSummary {
  return {
    step,
    status: "success",
    description: `Step ${step}`,
    tool_name: toolName,
    duration_ms: 1000,
    error_count: 0,
    metadata: null,
  } as StepSummary;
}

function makeMsg(role: string, content: string): TrajectoryMessage {
  return { role, content } as TrajectoryMessage;
}

describe("pretext integration", () => {
  it("measureText and layout model produce consistent total heights", () => {
    const steps = [makeStep(1)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    msgs.set(1, [
      makeMsg("assistant", "Hello world"),
      makeMsg("tool_call", "echo test"),
      makeMsg("tool_result", "test output"),
    ]);

    const items = buildLayoutItems(steps, msgs, 600, false);
    const totalHeight = getTotalHeight(items);
    expect(totalHeight).toBeGreaterThan(0);

    for (const item of items) {
      expect(item.height).toBeGreaterThan(0);
    }
  });

  it("visible range covers first screen for scrollTop=0", () => {
    const steps = Array.from({ length: 10 }, (_, i) => makeStep(i + 1));
    const msgs = new Map<number, TrajectoryMessage[]>();
    for (const step of steps) {
      msgs.set(step.step, [
        makeMsg("assistant", `Response for step ${step.step} with some content`),
        makeMsg("tool_call", `command_${step.step}`),
      ]);
    }

    const items = buildLayoutItems(steps, msgs, 600, false);
    const { startIndex, endIndex } = getVisibleRange(items, 0, 800, 200);

    expect(startIndex).toBe(0);
    expect(endIndex).toBeGreaterThan(0);
    expect(endIndex).toBeLessThanOrEqual(items.length);
  });

  it("shrinkwrap returns smaller width for short text", () => {
    const shortWidth = measureMinWidth("OK", "body", 600, getDefaultLineHeight("body"));
    const longWidth = measureMinWidth(
      "This is a much longer message that should require more horizontal space to display properly",
      "body",
      600,
      getDefaultLineHeight("body"),
    );
    expect(shortWidth).toBeLessThan(longWidth);
  });

  it("handles empty trajectory gracefully", () => {
    const items = buildLayoutItems([], new Map(), 600, false);
    expect(items).toHaveLength(0);
    expect(getTotalHeight(items)).toBe(0);

    const { startIndex, endIndex } = getVisibleRange(items, 0, 800, 200);
    expect(startIndex).toBe(0);
    expect(endIndex).toBe(0);
  });

  it("handles steps with no messages", () => {
    const steps = [makeStep(1)];
    const msgs = new Map<number, TrajectoryMessage[]>();

    const items = buildLayoutItems(steps, msgs, 600, false);
    expect(items).toHaveLength(1);
    expect(items[0].type).toBe("step-header");
  });

  it("getOffsetForStep returns correct offset for middle step", () => {
    const steps = [makeStep(1), makeStep(2), makeStep(3)];
    const msgs = new Map<number, TrajectoryMessage[]>();
    for (const step of steps) {
      msgs.set(step.step, [makeMsg("assistant", `Step ${step.step} content`)]);
    }

    const items = buildLayoutItems(steps, msgs, 600, false);
    const offset1 = getOffsetForStep(items, 1);
    const offset2 = getOffsetForStep(items, 2);
    const offset3 = getOffsetForStep(items, 3);

    expect(offset1).toBe(0);
    expect(offset2).toBeGreaterThan(offset1);
    expect(offset3).toBeGreaterThan(offset2);
  });
});
