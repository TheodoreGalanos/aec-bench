<!-- ABOUTME: Full-screen overlay container that orchestrates trajectory replay with rAF playback loop. -->
<!-- ABOUTME: Pre-fetches uncached steps, assembles all replay panels, handles keyboard shortcuts and seek. -->
<script lang="ts">
  import { onMount } from "svelte";
  import type { StepSummary, TrajectoryMessage } from "../../lib/types";
  import type { ReplaySequence, ReplayPosition, ReplayMessage } from "./replay-engine";
  import {
    buildReplaySequence,
    getPositionAtTime,
    computeVariableDiff,
  } from "./replay-engine";
  import { fetchViewerStep } from "../../lib/api";
  import { cacheStepMessages } from "../../lib/stores/viewer";

  import Modal from "../../lib/components/Modal.svelte";
  import ReplayTopBar from "./ReplayTopBar.svelte";
  import ReplayTimeline from "./ReplayTimeline.svelte";
  import ReplayStepOutline from "./ReplayStepOutline.svelte";
  import ReplayChat from "./ReplayChat.svelte";
  import ReplayVariables from "./ReplayVariables.svelte";

  // HistoryEntry is only used internally for variable diff tracking
  interface HistoryEntry {
    step: number;
    key: string;
    value: any;
    type: "added" | "changed" | "removed";
  }

  interface Props {
    experimentId: string;
    trialId: string;
    steps: StepSummary[];
    stepMessages: Map<number, TrajectoryMessage[]>;
    isRlmTrial: boolean;
    reward: number;
    taskId: string;
    model: string;
    tokensIn: number | null;
    tokensOut: number | null;
    costUsd: number | null;
    rlmState: { symbolic_state: Record<string, any>; scratchpad_data: Record<string, any> } | null;
    onclose: () => void;
  }

  let {
    experimentId,
    trialId,
    steps,
    stepMessages,
    isRlmTrial,
    reward,
    taskId,
    model,
    tokensIn,
    tokensOut,
    costUsd,
    rlmState,
    onclose,
  }: Props = $props();

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  let loading = $state(true);
  let loadedCount = $state(0);
  // svelte-ignore state_referenced_locally
  let allMessages: Map<number, TrajectoryMessage[]> = $state(new Map(stepMessages));

  // ---------------------------------------------------------------------------
  // Playback state
  // ---------------------------------------------------------------------------

  let sequence: ReplaySequence | null = $state(null);
  let playing = $state(false);
  let speed = $state(1);
  let elapsedMs = $state(0);
  let lastFrameTime = 0;  // Not reactive — internal to rAF loop
  let rafId: number | null = null;
  let currentPosition: ReplayPosition = $state({
    messageIndex: 0,
    step: 0,
    elapsedMs: 0,
    finished: false,
  });

  // ---------------------------------------------------------------------------
  // Variable tracking (RLM)
  // ---------------------------------------------------------------------------

  let currentVariables: Record<string, any> = $state({});
  let currentScratchpad: Record<string, any> = $state({});
  let variableHistory: HistoryEntry[] = $state([]);
  let lastTrackedStep = $state(-1);

  // Variable inspect modal
  let inspectModalOpen = $state(false);
  let inspectModalTitle = $state("");
  let inspectModalContent = $state("");
  let wasPlayingBeforeInspect = false;

  function handleInspect(title: string, content: string) {
    wasPlayingBeforeInspect = playing;
    playing = false;
    inspectModalTitle = title;
    inspectModalContent = content;
    inspectModalOpen = true;
  }

  function closeInspectModal() {
    inspectModalOpen = false;
    if (wasPlayingBeforeInspect) {
      playing = true;
    }
  }

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  let visibleMessages = $derived.by(
    (): ReplayMessage[] =>
      sequence ? sequence.messages.slice(0, currentPosition.messageIndex + 1) : [],
  );

  let currentStep = $derived(currentPosition.step);

  // ---------------------------------------------------------------------------
  // Overlay element ref for auto-focus
  // ---------------------------------------------------------------------------

  let overlayEl: HTMLDivElement | undefined = $state(undefined);

  // ---------------------------------------------------------------------------
  // Replay body width tracking for shrinkwrap calculations
  // ---------------------------------------------------------------------------

  let replayBodyEl: HTMLDivElement | undefined = $state(undefined);
  let chatWidth = $state(500);

  $effect(() => {
    if (!replayBodyEl) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chatWidth = entry.contentRect.width;
      }
    });
    ro.observe(replayBodyEl);
    return () => ro.disconnect();
  });

  // Auto-focus the overlay when it mounts so keyboard events work
  $effect(() => {
    if (overlayEl) {
      overlayEl.focus();
    }
  });

  // ---------------------------------------------------------------------------
  // Pre-fetch uncached steps on mount
  // ---------------------------------------------------------------------------

  onMount(() => {
    prefetchSteps();
  });

  async function prefetchSteps(): Promise<void> {
    const uncachedSteps = steps.filter((s) => !allMessages.has(s.step));

    if (uncachedSteps.length === 0) {
      // All steps already cached -- skip loading and start immediately
      loadedCount = steps.length;
      loading = false;
      initPlayback();
      return;
    }

    loadedCount = steps.length - uncachedSteps.length;

    // Fetch all uncached steps in parallel
    const fetchPromises = uncachedSteps.map(async (s) => {
      try {
        const data = await fetchViewerStep(experimentId, trialId, s.step);
        allMessages = new Map(allMessages).set(s.step, data.messages);
        cacheStepMessages(s.step, data.messages);
        loadedCount++;
      } catch {
        // On failure, store empty messages so we can continue
        allMessages = new Map(allMessages).set(s.step, []);
        loadedCount++;
      }
    });

    await Promise.all(fetchPromises);
    loading = false;
    initPlayback();
  }

  function initPlayback(): void {
    sequence = buildReplaySequence(steps, allMessages, chatWidth);
    // Build initial variable state (step 0)
    rebuildVariableState(0);
    playing = true;
  }

  // ---------------------------------------------------------------------------
  // Playback loop (requestAnimationFrame)
  // ---------------------------------------------------------------------------

  function startLoop(): void {
    if (rafId !== null) return;
    lastFrameTime = performance.now();
    rafId = requestAnimationFrame(tick);
  }

  function stopLoop(): void {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  $effect(() => {
    if (playing && sequence) {
      startLoop();
    } else {
      stopLoop();
    }
    return () => stopLoop();
  });

  function tick(now: number): void {
    rafId = null;
    if (!sequence || !playing) return;

    const delta = now - lastFrameTime;
    lastFrameTime = now;
    elapsedMs = Math.min(elapsedMs + delta * speed, sequence.totalMs);

    const pos = getPositionAtTime(sequence, elapsedMs);
    currentPosition = pos;

    // Track variable changes at step boundaries
    if (pos.step !== lastTrackedStep) {
      updateVariablesForStep(pos.step);
      lastTrackedStep = pos.step;
    }

    if (pos.finished) {
      playing = false;
      return;
    }

    rafId = requestAnimationFrame(tick);
  }

  // ---------------------------------------------------------------------------
  // Variable tracking
  // ---------------------------------------------------------------------------

  function extractVariables(stepNum: number): Record<string, any> {
    const stepSummary = steps.find((s) => s.step === stepNum);
    if (!stepSummary?.metadata?.variables) return {};

    const raw = stepSummary.metadata.variables;
    const filtered: Record<string, any> = {};

    for (const [key, value] of Object.entries(raw)) {
      // Filter out functions and REPL commands
      if (typeof value === "object" && value !== null && (value as any).type === "function") continue;
      if (typeof value === "string" && value.startsWith("function")) continue;
      filtered[key] = value;
    }

    return filtered;
  }

  function extractScratchpad(stepNum: number): Record<string, any> {
    const stepSummary = steps.find((s) => s.step === stepNum);
    if (!stepSummary?.metadata?.scratchpad) return {};
    const raw = stepSummary.metadata.scratchpad;
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return {};
    return raw as Record<string, any>;
  }

  function updateVariablesForStep(stepNum: number): void {
    const newVars = extractVariables(stepNum);
    const diff = computeVariableDiff(currentVariables, newVars);

    const entries: HistoryEntry[] = [];
    for (const key of diff.added) {
      entries.push({ step: stepNum, key, value: newVars[key], type: "added" });
    }
    for (const key of diff.changed) {
      entries.push({ step: stepNum, key, value: newVars[key], type: "changed" });
    }
    for (const key of diff.removed) {
      entries.push({ step: stepNum, key, value: undefined, type: "removed" });
    }

    if (entries.length > 0) {
      variableHistory = [...variableHistory, ...entries];
    }
    currentVariables = newVars;
    currentScratchpad = extractScratchpad(stepNum);
  }

  function rebuildVariableState(upToMs: number): void {
    // Reset variable tracking
    currentVariables = {};
    currentScratchpad = {};
    variableHistory = [];
    lastTrackedStep = -1;

    if (!sequence) return;

    // Replay variable changes for each step up to the given time
    for (const st of sequence.stepTimings) {
      if (st.startMs > upToMs) break;
      updateVariablesForStep(st.step);
      lastTrackedStep = st.step;
    }
  }

  // ---------------------------------------------------------------------------
  // Seek handler
  // ---------------------------------------------------------------------------

  function handleSeek(ms: number): void {
    if (!sequence) return;
    elapsedMs = Math.max(0, Math.min(ms, sequence.totalMs));
    currentPosition = getPositionAtTime(sequence, elapsedMs);
    rebuildVariableState(elapsedMs);
  }

  // ---------------------------------------------------------------------------
  // Token / cost proportional estimates
  // ---------------------------------------------------------------------------

  function computeTokensAtPosition(pos: ReplayPosition): number {
    const total = (tokensIn ?? 0) + (tokensOut ?? 0);
    if (!sequence || sequence.totalMs === 0) return 0;
    return Math.round(total * (pos.elapsedMs / sequence.totalMs));
  }

  function computeCostAtPosition(pos: ReplayPosition): number {
    const total = costUsd ?? 0;
    if (!sequence || sequence.totalMs === 0) return 0;
    return total * (pos.elapsedMs / sequence.totalMs);
  }

  // ---------------------------------------------------------------------------
  // Speed cycling
  // ---------------------------------------------------------------------------

  const SPEED_STEPS = [1, 2, 5, 10];

  function decreaseSpeed(): void {
    const idx = SPEED_STEPS.indexOf(speed);
    if (idx > 0) {
      speed = SPEED_STEPS[idx - 1];
    }
  }

  function increaseSpeed(): void {
    const idx = SPEED_STEPS.indexOf(speed);
    if (idx < SPEED_STEPS.length - 1) {
      speed = SPEED_STEPS[idx + 1];
    }
  }

  // ---------------------------------------------------------------------------
  // Keyboard shortcuts
  // ---------------------------------------------------------------------------

  function handleKeydown(e: KeyboardEvent): void {
    if (!sequence) return;

    switch (e.key) {
      case " ":
        e.preventDefault();
        playing = !playing;
        break;

      case "ArrowLeft":
        e.preventDefault();
        if (e.shiftKey) {
          // Jump to previous step start
          seekToPreviousStep();
        } else {
          // Jump back one message duration
          jumpBackOneMessage();
        }
        break;

      case "ArrowRight":
        e.preventDefault();
        if (e.shiftKey) {
          // Jump to next step start
          seekToNextStep();
        } else {
          // Jump forward one message duration
          jumpForwardOneMessage();
        }
        break;

      case "[":
        e.preventDefault();
        decreaseSpeed();
        break;

      case "]":
        e.preventDefault();
        increaseSpeed();
        break;

      case "Escape":
        e.preventDefault();
        onclose();
        break;
    }
  }

  function jumpBackOneMessage(): void {
    if (!sequence || sequence.messages.length === 0) return;
    const idx = Math.max(0, currentPosition.messageIndex - 1);
    const targetMs = sequence.messages[idx].cumulativeMs;
    handleSeek(targetMs);
  }

  function jumpForwardOneMessage(): void {
    if (!sequence || sequence.messages.length === 0) return;
    const idx = Math.min(sequence.messages.length - 1, currentPosition.messageIndex + 1);
    const targetMs = sequence.messages[idx].cumulativeMs;
    handleSeek(targetMs);
  }

  function seekToPreviousStep(): void {
    if (!sequence) return;
    const curStepIdx = sequence.stepTimings.findIndex((st) => st.step === currentPosition.step);
    if (curStepIdx > 0) {
      handleSeek(sequence.stepTimings[curStepIdx - 1].startMs);
    } else {
      handleSeek(0);
    }
  }

  function seekToNextStep(): void {
    if (!sequence) return;
    const curStepIdx = sequence.stepTimings.findIndex((st) => st.step === currentPosition.step);
    if (curStepIdx < sequence.stepTimings.length - 1) {
      handleSeek(sequence.stepTimings[curStepIdx + 1].startMs);
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="replay-overlay"
  bind:this={overlayEl}
  onkeydown={handleKeydown}
  tabindex="-1"
  role="dialog"
  aria-modal="true"
  aria-label="Trajectory replay"
  data-testid="replay-overlay"
>
  {#if loading}
    <div class="loading-overlay" data-testid="replay-loading">
      <span class="loading-text">Loading trajectory... {loadedCount}/{steps.length} steps</span>
      <progress value={loadedCount} max={steps.length}></progress>
    </div>
  {:else if sequence}
    <ReplayTopBar
      {taskId}
      {model}
      {currentStep}
      totalSteps={steps.length}
      currentMessage={currentPosition.messageIndex + 1}
      totalMessages={sequence.messages.length}
      {onclose}
    />
    <div class="replay-body" bind:this={replayBodyEl}>
      <ReplayStepOutline
        stepTimings={sequence.stepTimings}
        {currentStep}
        onseek={handleSeek}
      />
      <ReplayChat
        {visibleMessages}
        {currentStep}
        finished={currentPosition.finished}
        {reward}
        totalMs={sequence.totalMs}
        tokensTotal={(tokensIn ?? 0) + (tokensOut ?? 0)}
        costTotal={costUsd ?? 0}
        totalSteps={steps.length}
        containerWidth={chatWidth}
        cumulativeHeights={sequence.cumulativeHeights}
      />
      {#if isRlmTrial}
        <ReplayVariables
          {currentVariables}
          {currentScratchpad}
          {currentStep}
          fullState={rlmState?.symbolic_state ?? {}}
          fullScratchpad={rlmState?.scratchpad_data ?? {}}
          oninspect={handleInspect}
        />
      {/if}
    </div>
    <ReplayTimeline
      {playing}
      {speed}
      {elapsedMs}
      totalMs={sequence.totalMs}
      stepTimings={sequence.stepTimings}
      {currentStep}
      tokensUsed={computeTokensAtPosition(currentPosition)}
      tokensTotal={(tokensIn ?? 0) + (tokensOut ?? 0)}
      costUsed={computeCostAtPosition(currentPosition)}
      costTotal={costUsd ?? 0}
      ontoggleplay={() => { playing = !playing; }}
      onspeedchange={(s) => { speed = s; }}
      onseek={handleSeek}
      stepContentDensity={sequence.stepContentDensity}
    />
  {/if}

  {#if !playing && !loading && sequence && !currentPosition.finished}
    <div class="paused-indicator" data-testid="paused-indicator">
      <span class="paused-icon">&#x23F8;</span> Paused
    </div>
  {/if}
</div>

<Modal open={inspectModalOpen} title={inspectModalTitle} onclose={closeInspectModal} wide>
  <pre class="inspect-content">{inspectModalContent}</pre>
</Modal>

<style>
  /* inspect-content lives inside a Modal (page-level portal), so it uses
     standard theme vars -- not the dark overlay palette. */
  .inspect-content {
    font-family: var(--font-mono, monospace);
    font-size: 0.82rem;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 60vh;
    overflow-y: auto;
    color: var(--text);
    line-height: 1.5;
  }

  .paused-indicator {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.7);
    color: #BFBFBA;
    padding: 8px 20px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    pointer-events: none;
    animation: pauseFadeIn 0.3s ease-out;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .paused-icon {
    font-size: 1.1rem;
  }

  @keyframes pauseFadeIn {
    from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
  }
  .replay-overlay {
    position: fixed;
    inset: 12px;
    z-index: 100;
    background: rgba(0, 0, 0, 0.97);
    border: 1px solid #40403E;
    border-radius: 12px;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
    display: flex;
    flex-direction: column;
    outline: none;
    color: #E5E4DF;
    overflow: hidden;
  }

  .replay-body {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .loading-overlay {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-md);
    color: #BFBFBA;
    font-family: var(--font-mono);
  }

  .loading-text {
    font-size: 0.9rem;
  }

  progress {
    width: 280px;
    height: 6px;
    appearance: none;
    border: none;
    border-radius: 3px;
    overflow: hidden;
  }

  progress::-webkit-progress-bar {
    background: #2a2a28;
    border-radius: 3px;
  }

  progress::-webkit-progress-value {
    background: #4a6741;
    border-radius: 3px;
  }

  progress::-moz-progress-bar {
    background: #4a6741;
    border-radius: 3px;
  }
</style>
