<!-- ABOUTME: Top bar for the trajectory replay overlay showing trial info, step/message counters, and close button. -->
<!-- ABOUTME: Displays task ID, model, current progress counters, and a close button to exit the replay. -->
<script lang="ts">
  interface Props {
    taskId: string;
    model: string;
    currentStep: number;
    totalSteps: number;
    currentMessage: number;
    totalMessages: number;
    onclose: () => void;
  }

  let {
    taskId,
    model,
    currentStep,
    totalSteps,
    currentMessage,
    totalMessages,
    onclose,
  }: Props = $props();
</script>

<div class="replay-topbar" data-testid="replay-topbar">
  <div class="topbar-left">
    <span class="replay-title" data-testid="replay-title">Trajectory Replay</span>
    <span class="trial-info" data-testid="trial-info">
      <span class="task-id">{taskId}</span>
      <span class="divider">·</span>
      <span class="model">{model}</span>
    </span>
  </div>

  <div class="topbar-right">
    <span class="counters" data-testid="replay-counters">
      Step {currentStep}/{totalSteps} · Message {currentMessage}/{totalMessages}
    </span>
    <button
      class="close-btn"
      onclick={onclose}
      data-testid="replay-close"
      aria-label="Close replay"
    >
      Close
    </button>
  </div>
</div>

<style>
  .replay-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-md);
    background: #1e1e1e;
    border-bottom: 1px solid #40403E;
    flex-shrink: 0;
    min-height: 48px;
    gap: var(--space-md);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    overflow: hidden;
  }

  .replay-title {
    font-family: var(--font-heading, var(--font-sans));
    font-size: 1rem;
    font-weight: 700;
    color: #E5E4DF;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .trial-info {
    display: flex;
    align-items: center;
    gap: 4px;
    overflow: hidden;
    color: #BFBFBA;
    font-size: 0.82rem;
  }

  .task-id {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .divider {
    color: #91918D;
    flex-shrink: 0;
  }

  .model {
    color: #BFBFBA;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-style: italic;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    flex-shrink: 0;
  }

  .counters {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: #BFBFBA;
    white-space: nowrap;
  }

  .close-btn {
    padding: 4px var(--space-sm);
    border-radius: var(--radius-sm);
    border: none;
    background: #BF4D43;
    color: white;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: filter 120ms ease;
    white-space: nowrap;
  }

  .close-btn:hover {
    filter: brightness(1.15);
  }

  .close-btn:focus-visible {
    outline: 2px solid #BF4D43;
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }
</style>
