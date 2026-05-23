// ABOUTME: Pure TypeScript playback state machine for trajectory replay.
// ABOUTME: Handles timing, message sequencing, scrubbing, and variable diffing.

import type { StepSummary, TrajectoryMessage } from "../../lib/types";
import { measureText, getDefaultLineHeight } from "../../lib/pretext-service";
import type { FontPreset } from "../../lib/pretext-service";

const DEFAULT_MS_PER_MESSAGE = 1500;
const MIN_STEP_DURATION_MS = 2000;

export interface ReplayMessage {
  step: number;
  indexInStep: number;
  cumulativeMs: number;
  durationMs: number;
  message: TrajectoryMessage;
  predictedHeight: number;
}

export interface StepTiming {
  step: number;
  startMs: number;
  endMs: number;
  durationMs: number;
  toolName: string;
  errorCount: number;
  metadata: Record<string, any> | null;
  label?: string;
}

export interface ReplaySequence {
  messages: ReplayMessage[];
  stepTimings: StepTiming[];
  totalMs: number;
  cumulativeHeights: number[];
  stepContentDensity: Map<number, number>;
}

export interface ReplayPosition {
  messageIndex: number;
  step: number;
  elapsedMs: number;
  finished: boolean;
}

export interface VariableDiff {
  added: string[];
  changed: string[];
  removed: string[];
}

/**
 * Estimates the rendered height of a single message bubble given a container width.
 * Uses text measurement for content height and adds padding.
 */
function measureMessageHeight(msg: TrajectoryMessage, containerWidth: number): number {
  const role = (msg.role ?? "") as string;
  const font: FontPreset = (role === "assistant" || role === "system" || role === "user") ? "body" : "mono";
  const lineHeight = getDefaultLineHeight(font);
  const text = role === "tool_result"
    ? (msg.stdout ?? msg.output ?? msg.content ?? "")
    : role === "tool_call"
      ? (msg.command ?? msg.input ?? msg.content ?? "")
      : (msg.content ?? "");
  if (!text) return 40; // minimum height for empty messages
  const measured = measureText(String(text), font, containerWidth, lineHeight);
  return measured.height + 28; // + padding
}

/**
 * Build a human-readable label for a replay step.
 * Prefers template section from metadata, then a content preview
 * from the first assistant message, then falls back to tool name.
 */
function computeStepLabel(
  step: StepSummary,
  msgs: TrajectoryMessage[],
): string {
  const meta = step.metadata;
  if (meta?.template_progress?.current_section) {
    return meta.template_progress.current_section;
  }
  if (step.tool_name === "repl" && msgs.length > 0) {
    const assistantMsg = msgs.find((m) => m.role === "assistant");
    if (assistantMsg?.content && typeof assistantMsg.content === "string") {
      const preview = assistantMsg.content
        .slice(0, 35)
        .replace(/\n/g, " ")
        .trim();
      return preview + (assistantMsg.content.length > 35 ? "…" : "");
    }
  }
  return step.tool_name || step.description || `Step ${step.step}`;
}

export function buildReplaySequence(
  steps: StepSummary[],
  stepMessages: Map<number, TrajectoryMessage[]>,
  containerWidth: number = 500,
): ReplaySequence {
  const messages: ReplayMessage[] = [];
  const stepTimings: StepTiming[] = [];
  let cumulativeMs = 0;

  for (const step of steps) {
    const msgs = stepMessages.get(step.step) ?? [];
    const msgCount = Math.max(msgs.length, 1);
    const stepDuration =
      step.duration_ms ??
      Math.max(DEFAULT_MS_PER_MESSAGE * msgCount, MIN_STEP_DURATION_MS);

    stepTimings.push({
      step: step.step,
      startMs: cumulativeMs,
      endMs: cumulativeMs + stepDuration,
      durationMs: stepDuration,
      toolName: step.tool_name,
      errorCount: step.error_count,
      metadata: step.metadata,
      label: computeStepLabel(step, msgs),
    });

    const msgDuration = msgs.length > 0 ? stepDuration / msgs.length : stepDuration;

    for (let i = 0; i < msgs.length; i++) {
      const predictedHeight = measureMessageHeight(msgs[i], containerWidth);
      messages.push({
        step: step.step,
        indexInStep: i,
        cumulativeMs: cumulativeMs + i * msgDuration,
        durationMs: msgDuration,
        message: msgs[i],
        predictedHeight,
      });
    }

    cumulativeMs += stepDuration;
  }

  const cumulativeHeights: number[] = [];
  let cumH = 0;
  for (const msg of messages) {
    cumH += msg.predictedHeight;
    cumulativeHeights.push(cumH);
  }

  const stepContentDensity = new Map<number, number>();
  for (const msg of messages) {
    const prev = stepContentDensity.get(msg.step) ?? 0;
    stepContentDensity.set(msg.step, prev + msg.predictedHeight);
  }

  return { messages, stepTimings, totalMs: cumulativeMs, cumulativeHeights, stepContentDensity };
}

export function getPositionAtTime(
  sequence: ReplaySequence,
  elapsedMs: number,
): ReplayPosition {
  if (sequence.messages.length === 0) {
    return { messageIndex: 0, step: 0, elapsedMs, finished: true };
  }

  const clamped = Math.min(elapsedMs, sequence.totalMs);
  let messageIndex = 0;

  for (let i = 0; i < sequence.messages.length; i++) {
    if (sequence.messages[i].cumulativeMs <= clamped) {
      messageIndex = i;
    } else {
      break;
    }
  }

  const step = sequence.messages[messageIndex].step;
  const finished = clamped >= sequence.totalMs;

  return { messageIndex, step, elapsedMs: clamped, finished };
}

export function computeVariableDiff(
  prev: Record<string, any>,
  curr: Record<string, any>,
): VariableDiff {
  const added: string[] = [];
  const changed: string[] = [];
  const removed: string[] = [];

  for (const key of Object.keys(curr)) {
    if (!(key in prev)) {
      added.push(key);
    } else if (JSON.stringify(prev[key]) !== JSON.stringify(curr[key])) {
      changed.push(key);
    }
  }

  for (const key of Object.keys(prev)) {
    if (!(key in curr)) {
      removed.push(key);
    }
  }

  return { added, changed, removed };
}

export function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export function getStepAtTime(
  stepTimings: StepTiming[],
  elapsedMs: number,
): number {
  for (let i = stepTimings.length - 1; i >= 0; i--) {
    if (stepTimings[i].startMs <= elapsedMs) {
      return stepTimings[i].step;
    }
  }
  return 0;
}
