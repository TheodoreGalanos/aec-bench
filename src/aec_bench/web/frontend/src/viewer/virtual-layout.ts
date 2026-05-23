// ABOUTME: Pure TypeScript layout model for virtual scrolling in the trajectory viewer.
// ABOUTME: Provides height estimation, offset calculation, visible range detection, and height correction.

import { measureText, getDefaultLineHeight } from "../lib/pretext-service";
import type { FontPreset } from "../lib/pretext-service";
import type { StepSummary, TrajectoryMessage } from "../lib/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const STEP_HEADER_HEIGHT = 44;
export const SUBCALL_BAR_HEIGHT = 36;
export const MESSAGE_PADDING = 28; // vertical padding + border
export const STEP_SECTION_GAP = 24; // margin-bottom on .step-section

// CollapsibleOutput chrome — mirrors CSS in CollapsibleOutput.svelte
export const COLLAPSIBLE_PRE_PADDING = 32; // var(--space-md) * 2 = 16px top + 16px bottom
export const COLLAPSIBLE_BORDER = 2; // 1px top + 1px bottom
export const COLLAPSIBLE_LABEL_HEIGHT = 24; // label row: font + padding + border-bottom

// Collapse thresholds — must match MessageBubble.svelte rendering decisions
export const LONG_ASSISTANT_THRESHOLD = 500;
export const SYSTEM_MAX_HEIGHT = 150;
export const ASSISTANT_MAX_HEIGHT = 300;
export const TOOL_CONTENT_MAX_HEIGHT = 300;
export const STDOUT_MAX_HEIGHT = 300;
export const STDERR_MAX_HEIGHT = 200;
export const STDERR_MARGIN_TOP = 8; // .stderr-block margin-top
export const TOOL_COMMAND_CHROME = 24; // tool-command-wrapper margin + pre padding
export const BUBBLE_HEADER_HEIGHT = 20; // role label row + margin-bottom
export const BUBBLE_MARGIN = 8; // .message-bubble margin-bottom

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LayoutItem =
  | { type: "step-header"; step: number; height: number; offset: number }
  | { type: "message"; step: number; index: number; height: number; offset: number; message: TrajectoryMessage }
  | { type: "subcall-bar"; step: number; height: number; offset: number };

// ---------------------------------------------------------------------------
// Text extraction helpers
// ---------------------------------------------------------------------------

function extractMessageText(message: TrajectoryMessage): string {
  const role = message.role as string;
  if (role === "tool_result") {
    return String(message.stdout ?? message.output ?? message.content ?? "");
  }
  if (role === "tool_call") {
    return String(message.command ?? message.input ?? message.content ?? "");
  }
  return String(message.content ?? "");
}

function selectFont(role: string): FontPreset {
  if (role === "tool_call" || role === "tool_result") {
    return "mono";
  }
  return "body";
}

// ---------------------------------------------------------------------------
// measureCollapsibleBlock
// ---------------------------------------------------------------------------

/**
 * Predicts the rendered height of a CollapsibleOutput block, accounting for
 * CSS max-height clipping. When measured text exceeds maxHeight the block
 * renders at maxHeight + chrome; otherwise at measured height + chrome.
 */
export function measureCollapsibleBlock(
  text: string,
  font: FontPreset,
  maxWidth: number,
  maxHeight: number,
  hasLabel: boolean,
): number {
  if (!text) return 0;
  const lineHeight = getDefaultLineHeight(font);
  const measured = measureText(text, font, maxWidth, lineHeight);
  const chrome =
    COLLAPSIBLE_PRE_PADDING + COLLAPSIBLE_BORDER + (hasLabel ? COLLAPSIBLE_LABEL_HEIGHT : 0);

  if (measured.height > maxHeight) {
    return maxHeight + chrome;
  }
  return measured.height + chrome;
}

// ---------------------------------------------------------------------------
// estimateMessageHeight
// ---------------------------------------------------------------------------

/**
 * Predicts the rendered height of a single trajectory message by mirroring
 * the rendering tree in MessageBubble.svelte. Accounts for CollapsibleOutput
 * clipping and multi-block messages (tool_call command + content,
 * tool_result stdout + stderr).
 */
export function estimateMessageHeight(
  message: TrajectoryMessage,
  bubbleWidth: number,
): number {
  const role = String(message.role ?? "");
  let contentHeight = 0;

  if (role === "system") {
    const content = String(message.content ?? "");
    contentHeight = measureCollapsibleBlock(content, "mono", bubbleWidth, SYSTEM_MAX_HEIGHT, true);
  } else if (role === "assistant") {
    const content = String(message.content ?? "");
    if (content.length > LONG_ASSISTANT_THRESHOLD) {
      contentHeight = measureCollapsibleBlock(
        content, "mono", bubbleWidth, ASSISTANT_MAX_HEIGHT, false,
      );
    } else {
      contentHeight = plainTextHeight(content, "body", bubbleWidth);
    }
  } else if (role === "tool_call") {
    const command = String(message.command ?? message.input ?? "");
    const content = String(message.content ?? "");
    if (command) {
      contentHeight += plainTextHeight(command, "mono", bubbleWidth) + TOOL_COMMAND_CHROME;
    }
    if (content) {
      contentHeight += measureCollapsibleBlock(
        content, "mono", bubbleWidth, TOOL_CONTENT_MAX_HEIGHT, false,
      );
    }
  } else if (role === "tool_result") {
    const stdout = String(message.stdout ?? message.output ?? message.content ?? "");
    const stderr = String(message.stderr ?? "");
    if (stdout) {
      contentHeight += measureCollapsibleBlock(
        stdout, "mono", bubbleWidth, STDOUT_MAX_HEIGHT, false,
      );
    }
    if (stderr) {
      contentHeight +=
        measureCollapsibleBlock(stderr, "mono", bubbleWidth, STDERR_MAX_HEIGHT, true) +
        STDERR_MARGIN_TOP;
    }
  } else {
    // Unknown roles — mirrors MessageBubble fallback branch
    const content = String(message.content ?? "");
    if (content.length > LONG_ASSISTANT_THRESHOLD) {
      contentHeight = measureCollapsibleBlock(
        content, "mono", bubbleWidth, SYSTEM_MAX_HEIGHT, false,
      );
    } else {
      contentHeight = plainTextHeight(content, "body", bubbleWidth);
    }
  }

  return contentHeight + MESSAGE_PADDING + BUBBLE_HEADER_HEIGHT + BUBBLE_MARGIN;
}

function plainTextHeight(text: string, font: FontPreset, maxWidth: number): number {
  if (!text) return 0;
  const lineHeight = getDefaultLineHeight(font);
  return measureText(text, font, maxWidth, lineHeight).height;
}

// ---------------------------------------------------------------------------
// buildLayoutItems
// ---------------------------------------------------------------------------

/**
 * Builds a flat array of layout items from a list of steps and their messages.
 * Each item carries its height and cumulative offset from the top of the list.
 */
export function buildLayoutItems(
  steps: StepSummary[],
  stepMessages: Map<number, TrajectoryMessage[]>,
  containerWidth: number,
  isRlm: boolean,
): LayoutItem[] {
  const items: LayoutItem[] = [];
  let currentOffset = 0;

  // Avatar (28px) + gap (10px) + bubble padding (14px * 2) + border (2px) + outer padding ≈ 80px
  const BUBBLE_HORIZONTAL_CHROME = 80;
  const bubbleWidth = Math.max(100, containerWidth - BUBBLE_HORIZONTAL_CHROME);

  for (const stepSummary of steps) {
    const stepNum = stepSummary.step;

    // Step header
    items.push({
      type: "step-header",
      step: stepNum,
      height: STEP_HEADER_HEIGHT,
      offset: currentOffset,
    });
    currentOffset += STEP_HEADER_HEIGHT;

    // Messages for this step
    const messages = stepMessages.get(stepNum) ?? [];
    for (let i = 0; i < messages.length; i++) {
      const message = messages[i];
      const height = estimateMessageHeight(message, bubbleWidth);

      items.push({
        type: "message",
        step: stepNum,
        index: i,
        height,
        offset: currentOffset,
        message,
      });
      currentOffset += height;
    }

    // Subcall bar — only when isRlm and the step has a non-empty subcalls array
    const subcalls = stepSummary.metadata?.subcalls;
    if (isRlm && Array.isArray(subcalls) && subcalls.length > 0) {
      items.push({
        type: "subcall-bar",
        step: stepNum,
        height: SUBCALL_BAR_HEIGHT,
        offset: currentOffset,
      });
      currentOffset += SUBCALL_BAR_HEIGHT;
    }

    // Gap between steps
    currentOffset += STEP_SECTION_GAP;
  }

  return items;
}

// ---------------------------------------------------------------------------
// getTotalHeight
// ---------------------------------------------------------------------------

/**
 * Returns the total scrollable height of the layout.
 */
export function getTotalHeight(items: LayoutItem[]): number {
  if (items.length === 0) return 0;
  const last = items[items.length - 1];
  return last.offset + last.height + STEP_SECTION_GAP;
}

// ---------------------------------------------------------------------------
// getVisibleRange
// ---------------------------------------------------------------------------

/**
 * Returns the start and end indices (end exclusive) of items visible within
 * the given viewport. Binary search is used to find the first visible item;
 * a linear scan finds the last.
 */
export function getVisibleRange(
  items: LayoutItem[],
  scrollTop: number,
  viewportHeight: number,
  overscan: number,
): { startIndex: number; endIndex: number } {
  if (items.length === 0) {
    return { startIndex: 0, endIndex: 0 };
  }

  const visibleTop = scrollTop - overscan;
  const visibleBottom = scrollTop + viewportHeight + overscan;

  // Binary search for first item where offset + height > visibleTop
  let lo = 0;
  let hi = items.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    const item = items[mid];
    if (item.offset + item.height > visibleTop) {
      hi = mid;
    } else {
      lo = mid + 1;
    }
  }

  const startIndex = Math.max(0, lo);

  // Linear scan for end index
  let endIndex = startIndex;
  while (endIndex < items.length && items[endIndex].offset < visibleBottom) {
    endIndex++;
  }

  return {
    startIndex,
    endIndex: Math.min(endIndex, items.length),
  };
}

// ---------------------------------------------------------------------------
// getOffsetForStep
// ---------------------------------------------------------------------------

/**
 * Returns the pixel offset of the first step-header item matching the given
 * step number, or -1 if no such item exists.
 */
export function getOffsetForStep(items: LayoutItem[], step: number): number {
  const found = items.find((item) => item.type === "step-header" && item.step === step);
  return found !== undefined ? found.offset : -1;
}

// ---------------------------------------------------------------------------
// correctItemHeight
// ---------------------------------------------------------------------------

/**
 * Returns a new items array with the height of the item at itemIndex updated
 * to actualHeight, and all subsequent offsets adjusted accordingly.
 * Returns the original array unchanged when |delta| < 8px.
 */
export function correctItemHeight(
  items: LayoutItem[],
  itemIndex: number,
  actualHeight: number,
): LayoutItem[] {
  const currentHeight = items[itemIndex].height;
  const delta = actualHeight - currentHeight;

  if (Math.abs(delta) < 8) {
    return items;
  }

  const corrected = [...items];

  // Replace the item at itemIndex with updated height
  corrected[itemIndex] = { ...corrected[itemIndex], height: actualHeight };

  // Rebuild offsets from itemIndex + 1 onward
  for (let i = itemIndex + 1; i < corrected.length; i++) {
    corrected[i] = { ...corrected[i], offset: corrected[i].offset + delta };
  }

  return corrected;
}

// ---------------------------------------------------------------------------
// applyHeightOverrides
// ---------------------------------------------------------------------------

/**
 * Rebuilds the layout items array using measured heights from the overrides map.
 * Keys are item keys (e.g. "msg-1-0", "step-header-1") matching the output of
 * the component's itemKey function. Items without overrides keep their predicted
 * heights. Returns the original array when the override map is empty.
 */
export function applyHeightOverrides(
  items: LayoutItem[],
  overrides: Map<string, number>,
  keyFn: (item: LayoutItem) => string,
): LayoutItem[] {
  if (overrides.size === 0) return items;

  const result: LayoutItem[] = [];
  let cumulativeDelta = 0;

  for (const item of items) {
    const key = keyFn(item);
    const measured = overrides.get(key);
    let height = item.height;

    if (measured !== undefined && Math.abs(measured - item.height) >= 4) {
      cumulativeDelta += measured - item.height;
      height = measured;
    }

    result.push({ ...item, height, offset: item.offset + cumulativeDelta });
  }

  return result;
}
