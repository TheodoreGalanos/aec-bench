// ABOUTME: Unit tests for the virtual scroller layout model.
// ABOUTME: Covers buildLayoutItems, getTotalHeight, getVisibleRange, getOffsetForStep, and correctItemHeight.

import { describe, it, expect, vi } from "vitest";

vi.mock("../lib/pretext-service", () => ({
  measureText: vi.fn().mockReturnValue({ height: 48, lineCount: 2 }),
  getDefaultLineHeight: vi.fn().mockReturnValue(24),
  FONT_STRINGS: { body: "15px test", mono: "13px test", heading: "15px test" },
}));

import {
  STEP_HEADER_HEIGHT,
  SUBCALL_BAR_HEIGHT,
  MESSAGE_PADDING,
  STEP_SECTION_GAP,
  COLLAPSIBLE_PRE_PADDING,
  COLLAPSIBLE_BORDER,
  COLLAPSIBLE_LABEL_HEIGHT,
  BUBBLE_HEADER_HEIGHT,
  BUBBLE_MARGIN,
  LONG_ASSISTANT_THRESHOLD,
  SYSTEM_MAX_HEIGHT,
  ASSISTANT_MAX_HEIGHT,
  TOOL_CONTENT_MAX_HEIGHT,
  STDOUT_MAX_HEIGHT,
  STDERR_MAX_HEIGHT,
  STDERR_MARGIN_TOP,
  TOOL_COMMAND_CHROME,
  measureCollapsibleBlock,
  estimateMessageHeight,
  buildLayoutItems,
  getTotalHeight,
  getVisibleRange,
  getOffsetForStep,
  correctItemHeight,
  type LayoutItem,
} from "./virtual-layout";

import { measureText } from "../lib/pretext-service";
import type { StepSummary, TrajectoryMessage } from "../lib/types";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const makeStep = (step: number, metadata: Record<string, any> | null = null): StepSummary => ({
  step,
  status: "success",
  description: `Step ${step}`,
  tool_name: "bash",
  duration_ms: 100,
  error_count: 0,
  metadata,
});

const makeMessage = (role: string, content: string = "hello world"): TrajectoryMessage => ({
  role,
  content,
});

const makeToolCallMessage = (): TrajectoryMessage => ({
  role: "tool_call",
  command: "bash -c ls",
  content: null,
});

const makeToolResultMessage = (): TrajectoryMessage => ({
  role: "tool_result",
  stdout: "file1.txt\nfile2.txt",
  content: null,
});

const makeToolResultWithStderr = (): TrajectoryMessage => ({
  role: "tool_result",
  stdout: "file1.txt\nfile2.txt",
  stderr: "warning: something happened",
  content: null,
});

const makeToolCallWithContent = (): TrajectoryMessage => ({
  role: "tool_call",
  command: "bash -c ls",
  content: "Some tool call body content here",
});

const makeLongContent = (): string => "x".repeat(600);

const makeSystemMessage = (): TrajectoryMessage => ({
  role: "system",
  content: "You are a helpful assistant.",
});

// Total per-message chrome: body padding + border + header + margin
const MSG_CHROME = MESSAGE_PADDING + BUBBLE_HEADER_HEIGHT + BUBBLE_MARGIN;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

describe("constants", () => {
  it("STEP_HEADER_HEIGHT is 44", () => {
    expect(STEP_HEADER_HEIGHT).toBe(44);
  });

  it("SUBCALL_BAR_HEIGHT is 36", () => {
    expect(SUBCALL_BAR_HEIGHT).toBe(36);
  });

  it("MESSAGE_PADDING is 28", () => {
    expect(MESSAGE_PADDING).toBe(28);
  });

  it("STEP_SECTION_GAP is 24", () => {
    expect(STEP_SECTION_GAP).toBe(24);
  });
});

// ---------------------------------------------------------------------------
// buildLayoutItems — step headers
// ---------------------------------------------------------------------------

describe("buildLayoutItems — step headers", () => {
  it("creates a step-header item for each step", () => {
    const steps = [makeStep(1), makeStep(2), makeStep(3)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, []],
      [2, []],
      [3, []],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const headers = items.filter((i) => i.type === "step-header");
    expect(headers.length).toBe(3);
  });

  it("step-header items have fixed height of STEP_HEADER_HEIGHT", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const header = items.find((i) => i.type === "step-header");
    expect(header?.height).toBe(STEP_HEADER_HEIGHT);
  });

  it("step-header items carry the correct step number", () => {
    const steps = [makeStep(5), makeStep(10)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [5, []],
      [10, []],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const headers = items.filter((i) => i.type === "step-header");
    expect(headers[0].step).toBe(5);
    expect(headers[1].step).toBe(10);
  });

  it("first step-header starts at offset 0", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const header = items.find((i) => i.type === "step-header");
    expect(header?.offset).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// buildLayoutItems — message items
// ---------------------------------------------------------------------------

describe("buildLayoutItems — message items", () => {
  it("creates a message item for each message in a step", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("user"), makeMessage("assistant"), makeMessage("assistant")]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const messages = items.filter((i) => i.type === "message");
    expect(messages.length).toBe(3);
  });

  it("message items have height = measured.height + full chrome", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant", "some content")]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msg = items.find((i) => i.type === "message");
    // measureText mock returns height: 48; + MSG_CHROME (56) = 104
    expect(msg?.height).toBe(48 + MSG_CHROME);
  });

  it("message items carry step and index", () => {
    const steps = [makeStep(2)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [2, [makeMessage("user"), makeMessage("assistant")]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const messages = items.filter((i) => i.type === "message");
    expect(messages[0].step).toBe(2);
    expect(messages[0].index).toBe(0);
    expect(messages[1].step).toBe(2);
    expect(messages[1].index).toBe(1);
  });

  it("message items carry the original TrajectoryMessage", () => {
    const msg: TrajectoryMessage = makeMessage("user", "check this");
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, [msg]]]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgItem = items.find((i) => i.type === "message");
    expect(msgItem?.message).toBe(msg);
  });

  it("uses body font for assistant messages", () => {
    vi.mocked(measureText).mockClear();

    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant", "answer")]],
    ]);

    buildLayoutItems(steps, stepMessages, 800, false);
    expect(measureText).toHaveBeenCalledWith(
      expect.any(String),
      "body",
      expect.any(Number),
      expect.any(Number),
    );
  });

  it("uses mono font for tool_call messages", () => {
    vi.mocked(measureText).mockClear();

    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeToolCallMessage()]],
    ]);

    buildLayoutItems(steps, stepMessages, 800, false);
    expect(measureText).toHaveBeenCalledWith(
      expect.any(String),
      "mono",
      expect.any(Number),
      expect.any(Number),
    );
  });

  it("uses mono font for tool_result messages", () => {
    vi.mocked(measureText).mockClear();

    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeToolResultMessage()]],
    ]);

    buildLayoutItems(steps, stepMessages, 800, false);
    expect(measureText).toHaveBeenCalledWith(
      expect.any(String),
      "mono",
      expect.any(Number),
      expect.any(Number),
    );
  });

  it("uses body font for user messages", () => {
    vi.mocked(measureText).mockClear();

    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("user", "question")]],
    ]);

    buildLayoutItems(steps, stepMessages, 800, false);
    expect(measureText).toHaveBeenCalledWith(
      expect.any(String),
      "body",
      expect.any(Number),
      expect.any(Number),
    );
  });
});

// ---------------------------------------------------------------------------
// buildLayoutItems — subcall bars
// ---------------------------------------------------------------------------

describe("buildLayoutItems — subcall bars", () => {
  it("does not add subcall-bar when isRlm is false", () => {
    const steps = [
      makeStep(1, { subcalls: [{ id: "sc1" }] }),
    ];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const bars = items.filter((i) => i.type === "subcall-bar");
    expect(bars.length).toBe(0);
  });

  it("does not add subcall-bar when isRlm is true but step has no subcalls", () => {
    const steps = [makeStep(1)]; // metadata is null
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, true);
    const bars = items.filter((i) => i.type === "subcall-bar");
    expect(bars.length).toBe(0);
  });

  it("does not add subcall-bar when isRlm is true and subcalls is empty array", () => {
    const steps = [makeStep(1, { subcalls: [] })];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, true);
    const bars = items.filter((i) => i.type === "subcall-bar");
    expect(bars.length).toBe(0);
  });

  it("adds subcall-bar when isRlm is true AND step has subcalls array", () => {
    const steps = [makeStep(1, { subcalls: [{ id: "sc1" }] })];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, true);
    const bars = items.filter((i) => i.type === "subcall-bar");
    expect(bars.length).toBe(1);
  });

  it("subcall-bar has fixed height of SUBCALL_BAR_HEIGHT", () => {
    const steps = [makeStep(1, { subcalls: [{ id: "sc1" }] })];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, true);
    const bar = items.find((i) => i.type === "subcall-bar");
    expect(bar?.height).toBe(SUBCALL_BAR_HEIGHT);
  });

  it("subcall-bar carries the correct step number", () => {
    const steps = [makeStep(3, { subcalls: [{ id: "sc1" }] })];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[3, []]]);

    const items = buildLayoutItems(steps, stepMessages, 800, true);
    const bar = items.find((i) => i.type === "subcall-bar");
    expect(bar?.step).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// buildLayoutItems — cumulative offsets
// ---------------------------------------------------------------------------

describe("buildLayoutItems — cumulative offsets", () => {
  it("offsets are monotonically increasing", () => {
    const steps = [makeStep(1), makeStep(2)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("user"), makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    for (let i = 1; i < items.length; i++) {
      expect(items[i].offset).toBeGreaterThan(items[i - 1].offset);
    }
  });

  it("second step header offset equals sum of first step items + STEP_SECTION_GAP", () => {
    const steps = [makeStep(1), makeStep(2)];
    // Step 1 has 1 message, step 2 has 0 messages
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, []],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const header1 = items.find((i) => i.type === "step-header" && i.step === 1)!;
    const msgItem = items.find((i) => i.type === "message")!;
    const header2 = items.find((i) => i.type === "step-header" && i.step === 2)!;

    const expectedOffset = header1.offset + STEP_HEADER_HEIGHT + msgItem.height + STEP_SECTION_GAP;
    expect(header2.offset).toBe(expectedOffset);
  });

  it("returns empty array when no steps", () => {
    const items = buildLayoutItems([], new Map(), 800, false);
    expect(items).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getTotalHeight
// ---------------------------------------------------------------------------

describe("getTotalHeight", () => {
  it("returns 0 for empty items array", () => {
    expect(getTotalHeight([])).toBe(0);
  });

  it("returns positive value for non-empty items", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    expect(getTotalHeight(items)).toBeGreaterThan(0);
  });

  it("equals last item offset + last item height + STEP_SECTION_GAP", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const last = items[items.length - 1];
    expect(getTotalHeight(items)).toBe(last.offset + last.height + STEP_SECTION_GAP);
  });
});

// ---------------------------------------------------------------------------
// getVisibleRange
// ---------------------------------------------------------------------------

describe("getVisibleRange", () => {
  it("returns startIndex=0 at scrollTop=0", () => {
    const steps = [makeStep(1), makeStep(2), makeStep(3)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
      [3, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);

    const { startIndex } = getVisibleRange(items, 0, 600, 0);
    expect(startIndex).toBe(0);
  });

  it("endIndex is exclusive and > startIndex", () => {
    const steps = [makeStep(1), makeStep(2)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);

    const { startIndex, endIndex } = getVisibleRange(items, 0, 600, 0);
    expect(endIndex).toBeGreaterThan(startIndex);
  });

  it("shifts visible window when scrollTop increases", () => {
    const steps = [makeStep(1), makeStep(2), makeStep(3), makeStep(4), makeStep(5)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant"), makeMessage("user")]],
      [2, [makeMessage("assistant"), makeMessage("user")]],
      [3, [makeMessage("assistant"), makeMessage("user")]],
      [4, [makeMessage("assistant"), makeMessage("user")]],
      [5, [makeMessage("assistant"), makeMessage("user")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const totalHeight = getTotalHeight(items);

    const { startIndex: startAtTop } = getVisibleRange(items, 0, 200, 0);
    const { startIndex: startAtBottom } = getVisibleRange(items, totalHeight - 200, 200, 0);

    expect(startAtBottom).toBeGreaterThan(startAtTop);
  });

  it("overscan expands the returned range", () => {
    const steps = [makeStep(1), makeStep(2), makeStep(3)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
      [3, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);

    const withoutOverscan = getVisibleRange(items, 0, 100, 0);
    const withOverscan = getVisibleRange(items, 0, 100, 300);

    expect(withOverscan.endIndex).toBeGreaterThanOrEqual(withoutOverscan.endIndex);
  });

  it("returns { startIndex: 0, endIndex: 0 } for empty items", () => {
    const result = getVisibleRange([], 0, 600, 0);
    expect(result.startIndex).toBe(0);
    expect(result.endIndex).toBe(0);
  });

  it("clamps startIndex to 0", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const { startIndex } = getVisibleRange(items, 0, 600, 200);
    expect(startIndex).toBeGreaterThanOrEqual(0);
  });

  it("clamps endIndex to items.length", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const { endIndex } = getVisibleRange(items, 0, 600, 200);
    expect(endIndex).toBeLessThanOrEqual(items.length);
  });
});

// ---------------------------------------------------------------------------
// getOffsetForStep
// ---------------------------------------------------------------------------

describe("getOffsetForStep", () => {
  it("returns 0 for the first step", () => {
    const steps = [makeStep(1), makeStep(2)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    expect(getOffsetForStep(items, 1)).toBe(0);
  });

  it("returns a positive offset for a later step", () => {
    const steps = [makeStep(1), makeStep(2)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
      [2, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    expect(getOffsetForStep(items, 2)).toBeGreaterThan(0);
  });

  it("returns -1 for a step that does not exist in items", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([[1, []]]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    expect(getOffsetForStep(items, 99)).toBe(-1);
  });

  it("returns -1 for empty items", () => {
    expect(getOffsetForStep([], 1)).toBe(-1);
  });
});

// ---------------------------------------------------------------------------
// collapse-aware constants
// ---------------------------------------------------------------------------

describe("collapse-aware constants", () => {
  it("COLLAPSIBLE_PRE_PADDING is 32", () => {
    expect(COLLAPSIBLE_PRE_PADDING).toBe(32);
  });

  it("COLLAPSIBLE_BORDER is 2", () => {
    expect(COLLAPSIBLE_BORDER).toBe(2);
  });

  it("COLLAPSIBLE_LABEL_HEIGHT is 24", () => {
    expect(COLLAPSIBLE_LABEL_HEIGHT).toBe(24);
  });

  it("LONG_ASSISTANT_THRESHOLD is 500", () => {
    expect(LONG_ASSISTANT_THRESHOLD).toBe(500);
  });

  it("SYSTEM_MAX_HEIGHT is 150", () => {
    expect(SYSTEM_MAX_HEIGHT).toBe(150);
  });

  it("ASSISTANT_MAX_HEIGHT is 300", () => {
    expect(ASSISTANT_MAX_HEIGHT).toBe(300);
  });

  it("STDOUT_MAX_HEIGHT is 300", () => {
    expect(STDOUT_MAX_HEIGHT).toBe(300);
  });

  it("STDERR_MAX_HEIGHT is 200", () => {
    expect(STDERR_MAX_HEIGHT).toBe(200);
  });
});

// ---------------------------------------------------------------------------
// measureCollapsibleBlock
// ---------------------------------------------------------------------------

describe("measureCollapsibleBlock", () => {
  const CHROME = COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER; // 34

  it("returns measured height + chrome when NOT overflowing", () => {
    // mock returns height: 48 which is < 300
    const result = measureCollapsibleBlock("short text", "mono", 600, 300, false);
    expect(result).toBe(48 + CHROME);
  });

  it("caps at maxHeight + chrome when overflowing", () => {
    // Simulate long text with height 800
    vi.mocked(measureText).mockReturnValueOnce({ height: 800, lineCount: 40 });
    const result = measureCollapsibleBlock("very long text", "mono", 600, 300, false);
    expect(result).toBe(300 + CHROME);
  });

  it("adds COLLAPSIBLE_LABEL_HEIGHT when hasLabel is true", () => {
    const result = measureCollapsibleBlock("some text", "mono", 600, 300, true);
    expect(result).toBe(48 + CHROME + COLLAPSIBLE_LABEL_HEIGHT);
  });

  it("caps at maxHeight + chrome + label when overflowing with label", () => {
    vi.mocked(measureText).mockReturnValueOnce({ height: 800, lineCount: 40 });
    const result = measureCollapsibleBlock("long text", "mono", 600, 150, true);
    expect(result).toBe(150 + CHROME + COLLAPSIBLE_LABEL_HEIGHT);
  });

  it("returns 0 for empty text", () => {
    const result = measureCollapsibleBlock("", "mono", 600, 300, false);
    expect(result).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// estimateMessageHeight
// ---------------------------------------------------------------------------

describe("estimateMessageHeight", () => {
  it("short assistant uses plain text height + MSG_CHROME", () => {
    const msg = makeMessage("assistant", "short answer");
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(48 + MSG_CHROME);
  });

  it("long assistant uses collapsible with maxHeight=300", () => {
    vi.mocked(measureText).mockReturnValueOnce({ height: 900, lineCount: 45 });
    const msg = makeMessage("assistant", makeLongContent());
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(300 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER + MSG_CHROME);
  });

  it("system role uses collapsible with maxHeight=150 and label", () => {
    vi.mocked(measureText).mockReturnValueOnce({ height: 500, lineCount: 25 });
    const msg = makeSystemMessage();
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(
      SYSTEM_MAX_HEIGHT + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER +
      COLLAPSIBLE_LABEL_HEIGHT + MSG_CHROME,
    );
  });

  it("system role with short content does not clip", () => {
    // mock returns height: 48, which is < 150 (SYSTEM_MAX_HEIGHT)
    const msg = makeSystemMessage();
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(
      48 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER +
      COLLAPSIBLE_LABEL_HEIGHT + MSG_CHROME,
    );
  });

  it("tool_call with command only includes command chrome", () => {
    const msg = makeToolCallMessage(); // command only, content is null
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(48 + TOOL_COMMAND_CHROME + MSG_CHROME);
  });

  it("tool_call with command + content sums both blocks", () => {
    const msg = makeToolCallWithContent();
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(
      (48 + TOOL_COMMAND_CHROME) +
      (48 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER) +
      MSG_CHROME,
    );
  });

  it("tool_result with stdout uses collapsible", () => {
    const msg = makeToolResultMessage(); // stdout only
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(48 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER + MSG_CHROME);
  });

  it("tool_result with stdout + stderr sums both blocks", () => {
    const msg = makeToolResultWithStderr();
    const height = estimateMessageHeight(msg, 720);
    const stdoutBlock = 48 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER;
    const stderrBlock = 48 + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER +
      COLLAPSIBLE_LABEL_HEIGHT + STDERR_MARGIN_TOP;
    expect(height).toBe(stdoutBlock + stderrBlock + MSG_CHROME);
  });

  it("tool_result with long stdout caps at STDOUT_MAX_HEIGHT", () => {
    vi.mocked(measureText).mockReturnValueOnce({ height: 5000, lineCount: 250 });
    const msg = makeToolResultMessage();
    const height = estimateMessageHeight(msg, 720);
    expect(height).toBe(
      STDOUT_MAX_HEIGHT + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER + MSG_CHROME,
    );
  });
});

// ---------------------------------------------------------------------------
// buildLayoutItems — collapse-aware heights
// ---------------------------------------------------------------------------

describe("buildLayoutItems — collapse-aware heights", () => {
  it("long tool_result gets capped height instead of full text height", () => {
    // Make measureText return a huge height for the first message measurement
    vi.mocked(measureText).mockReturnValueOnce({ height: 5000, lineCount: 250 });

    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeToolResultMessage()]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msg = items.find((i) => i.type === "message");

    // Should be capped at STDOUT_MAX_HEIGHT + chrome, NOT 5000 + MSG_CHROME
    expect(msg?.height).toBe(
      STDOUT_MAX_HEIGHT + COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER + MSG_CHROME,
    );
    expect(msg?.height).toBeLessThan(1000); // sanity: way less than 5000+28
  });

  it("short assistant still uses plain text height", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant", "short")]],
    ]);

    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msg = items.find((i) => i.type === "message");
    expect(msg?.height).toBe(48 + MSG_CHROME);
  });
});

// ---------------------------------------------------------------------------
// correctItemHeight
// ---------------------------------------------------------------------------

describe("correctItemHeight", () => {
  it("replaces the height of the specified item", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant"), makeMessage("user")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgIndex = items.findIndex((i) => i.type === "message");
    const newHeight = items[msgIndex].height + 100;

    const corrected = correctItemHeight(items, msgIndex, newHeight);
    expect(corrected[msgIndex].height).toBe(newHeight);
  });

  it("propagates updated offsets to all items after the corrected one", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant"), makeMessage("user")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgIndex = items.findIndex((i) => i.type === "message");
    const delta = 100;
    const oldHeight = items[msgIndex].height;
    const oldNextOffset = items[msgIndex + 1]?.offset;

    const corrected = correctItemHeight(items, msgIndex, oldHeight + delta);
    const newNextOffset = corrected[msgIndex + 1]?.offset;

    if (oldNextOffset !== undefined && newNextOffset !== undefined) {
      expect(newNextOffset).toBe(oldNextOffset + delta);
    }
  });

  it("does not mutate the original items array", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgIndex = items.findIndex((i) => i.type === "message");
    const originalHeight = items[msgIndex].height;

    correctItemHeight(items, msgIndex, originalHeight + 100);

    expect(items[msgIndex].height).toBe(originalHeight);
  });

  it("skips update when delta is less than 8px absolute", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgIndex = items.findIndex((i) => i.type === "message");
    const originalHeight = items[msgIndex].height;

    // Delta of 4 is below the 8px threshold
    const corrected = correctItemHeight(items, msgIndex, originalHeight + 4);

    // Should return original items unchanged (same reference or same values)
    expect(corrected[msgIndex].height).toBe(originalHeight);
  });

  it("applies update when delta equals exactly 8px", () => {
    const steps = [makeStep(1)];
    const stepMessages = new Map<number, TrajectoryMessage[]>([
      [1, [makeMessage("assistant")]],
    ]);
    const items = buildLayoutItems(steps, stepMessages, 800, false);
    const msgIndex = items.findIndex((i) => i.type === "message");
    const originalHeight = items[msgIndex].height;

    const corrected = correctItemHeight(items, msgIndex, originalHeight + 8);
    expect(corrected[msgIndex].height).toBe(originalHeight + 8);
  });
});
