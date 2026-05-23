<!-- src/viewer/replay/ReplayTimeline.svelte -->
<!-- ABOUTME: Video-editor-style timeline bar for trajectory replay. -->
<!-- ABOUTME: Scrubber with step segments, play/pause, speed controls, time/token counters. -->
<script lang="ts">
  import type { StepTiming } from "./replay-engine";
  import { formatTime } from "./replay-engine";

  interface Props {
    playing: boolean;
    speed: number;
    elapsedMs: number;
    totalMs: number;
    stepTimings: StepTiming[];
    currentStep: number;
    tokensUsed: number;
    tokensTotal: number;
    costUsed: number;
    costTotal: number;
    ontoggleplay: () => void;
    onspeedchange: (speed: number) => void;
    onseek: (ms: number) => void;
    stepContentDensity?: Map<number, number>;
  }

  let {
    playing, speed, elapsedMs, totalMs, stepTimings, currentStep,
    tokensUsed, tokensTotal, costUsed, costTotal,
    ontoggleplay, onspeedchange, onseek,
    stepContentDensity,
  }: Props = $props();

  let maxDensity = $derived.by(() => {
    if (!stepContentDensity || stepContentDensity.size === 0) return 1;
    let max = 0;
    for (const v of stepContentDensity.values()) {
      if (v > max) max = v;
    }
    return max || 1;
  });

  const SPEEDS = [1, 2, 5, 10];

  let scrubberEl: HTMLDivElement | null = $state(null);
  let isDragging = $state(false);

  let progress = $derived(totalMs > 0 ? (elapsedMs / totalMs) * 100 : 0);

  function handleScrubberClick(e: MouseEvent) {
    if (!scrubberEl || totalMs === 0) return;
    const rect = scrubberEl.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onseek(fraction * totalMs);
  }

  function handleScrubberDrag(e: MouseEvent) {
    if (!isDragging || !scrubberEl || totalMs === 0) return;
    const rect = scrubberEl.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onseek(fraction * totalMs);
  }

  function startDrag(e: MouseEvent) {
    isDragging = true;
    handleScrubberDrag(e);
    window.addEventListener("mousemove", handleScrubberDrag);
    window.addEventListener("mouseup", stopDrag);
  }

  function stopDrag() {
    isDragging = false;
    window.removeEventListener("mousemove", handleScrubberDrag);
    window.removeEventListener("mouseup", stopDrag);
  }
</script>

<div class="timeline-bar">
  <div class="timeline-controls">
    <button class="play-btn" onclick={ontoggleplay} title={playing ? "Pause" : "Play"}>
      {playing ? "⏸" : "▶"}
    </button>

    <div class="speed-selector">
      {#each SPEEDS as s}
        <button
          class="speed-pill"
          class:active={speed === s}
          onclick={() => onspeedchange(s)}
        >{s}x</button>
      {/each}
    </div>

    <span class="time-display">{formatTime(elapsedMs)} / {formatTime(totalMs)}</span>
  </div>

  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="scrubber"
    bind:this={scrubberEl}
    onclick={handleScrubberClick}
    onmousedown={startDrag}
  >
    <div class="scrubber-bg">
      {#each stepTimings as st}
        {@const widthPct = totalMs > 0 ? (st.durationMs / totalMs) * 100 : 0}
        <div
          class="step-segment"
          class:active={st.step === currentStep}
          class:has-error={st.errorCount > 0}
          style="width: {widthPct}%"
          title="Step {st.step}: {st.toolName} ({(st.durationMs / 1000).toFixed(1)}s)"
        >
          {#if widthPct > 4}
            <span class="step-label">{st.step}</span>
          {/if}
          {#if st.errorCount > 0}
            <span class="error-dot"></span>
          {/if}
          {#if stepContentDensity}
            {@const density = stepContentDensity.get(st.step) ?? 0}
            {@const barHeight = Math.max(1, Math.round((density / maxDensity) * 6))}
            <div class="density-bar" style="height: {barHeight}px;"></div>
          {/if}
        </div>
      {/each}
    </div>
    <div class="scrubber-progress" style="width: {progress}%"></div>
    <div class="scrubber-playhead" style="left: {progress}%"></div>
  </div>

  <div class="timeline-stats">
    <span class="stat-label">{tokensUsed.toLocaleString()} / {tokensTotal.toLocaleString()} tok</span>
    <span class="stat-label">${costUsed.toFixed(2)} / ${costTotal.toFixed(2)}</span>
  </div>
</div>

<style>
  .timeline-bar {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    background: #1e1e1e;
    border-top: 1px solid #40403E;
  }

  .timeline-controls {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    flex-shrink: 0;
  }

  .play-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #4a6741;
    color: white;
    border: none;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: 120ms ease;
  }

  .play-btn:hover {
    filter: brightness(1.15);
  }

  .speed-selector {
    display: flex;
    gap: 2px;
  }

  .speed-pill {
    background: #2a2a28;
    color: #91918D;
    border: 1px solid #40403E;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: 0.72rem;
    cursor: pointer;
    font-family: var(--font-mono);
    transition: 120ms ease;
  }

  .speed-pill.active {
    background: #4a6741;
    color: white;
    border-color: #4a6741;
  }

  .time-display {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: #BFBFBA;
    min-width: 90px;
  }

  .scrubber {
    flex: 1;
    height: 24px;
    position: relative;
    cursor: pointer;
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .scrubber-bg {
    position: absolute;
    inset: 0;
    display: flex;
    background: #2a2a28;
    border-radius: var(--radius-sm);
  }

  .step-segment {
    position: relative;
    height: 100%;
    border-right: 1px solid #40403E;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 120ms ease;
  }

  .step-segment.active {
    background: rgba(74, 103, 65, 0.15);
  }

  .step-label {
    font-size: 0.6rem;
    color: #91918D;
    font-family: var(--font-mono);
    pointer-events: none;
  }

  .error-dot {
    position: absolute;
    top: 3px;
    right: 3px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #BF4D43;
  }

  .density-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(74, 103, 65, 0.2);
    pointer-events: none;
  }

  .scrubber-progress {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: rgba(74, 103, 65, 0.3);
    pointer-events: none;
    transition: width 0.05s linear;
  }

  .scrubber-playhead {
    position: absolute;
    top: 0;
    width: 2px;
    height: 100%;
    background: #4a6741;
    pointer-events: none;
    transition: left 0.05s linear;
  }

  .timeline-stats {
    display: flex;
    flex-direction: column;
    gap: 1px;
    flex-shrink: 0;
    min-width: 120px;
    text-align: right;
  }

  .stat-label {
    font-size: 0.68rem;
    color: #91918D;
    font-family: var(--font-mono);
  }
</style>
