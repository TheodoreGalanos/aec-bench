<!-- ABOUTME: Center panel for trajectory replay showing messages appearing one by one during playback. -->
<!-- ABOUTME: Renders role-based avatars, step dividers, fade-in animations, and a completion summary card. -->
<script lang="ts">
  import type { ReplayMessage } from "./replay-engine";
  import { formatTime } from "./replay-engine";
  import { measureMinWidth, getDefaultLineHeight } from "../../lib/pretext-service";

  interface Props {
    visibleMessages: ReplayMessage[];
    currentStep: number;
    finished: boolean;
    reward: number;
    totalMs: number;
    tokensTotal: number;
    costTotal: number;
    totalSteps: number;
    containerWidth?: number;
    cumulativeHeights?: number[];
  }

  let {
    visibleMessages,
    currentStep,
    finished,
    reward,
    totalMs,
    tokensTotal,
    costTotal,
    totalSteps,
    containerWidth = 500,
    cumulativeHeights,
  }: Props = $props();

  let chatEl: HTMLDivElement | undefined = $state(undefined);

  // Auto-scroll to the predicted position of the last visible message when new messages appear.
  // Falls back to scrollHeight when pre-computed heights are unavailable.
  $effect(() => {
    const _len = visibleMessages.length;
    const _fin = finished;
    if (chatEl && cumulativeHeights && visibleMessages.length > 0) {
      const lastIdx = visibleMessages.length - 1;
      chatEl.scrollTop = cumulativeHeights[lastIdx] ?? 0;
    } else if (chatEl) {
      chatEl.scrollTop = chatEl.scrollHeight;
    }
  });

  // Avatar letter per role
  function avatarLetter(role: string): string {
    if (role === "assistant") return "A";
    if (role === "tool_call") return "T";
    if (role === "tool_result") return "R";
    if (role === "user") return "U";
    if (role === "system") return "S";
    return "?";
  }

  // CSS class for the avatar circle
  function avatarClass(role: string): string {
    if (role === "assistant") return "avatar-assistant";
    if (role === "tool_call") return "avatar-tool";
    if (role === "tool_result") return "avatar-result";
    if (role === "user") return "avatar-user";
    return "avatar-system";
  }

  // Short label shown in bubble header
  function roleLabel(msg: ReplayMessage): string {
    const role = msg.message.role ?? "";
    if (role === "assistant") return "Model output";
    if (role === "tool_call") return "Tool invocation";
    if (role === "tool_result") return "Tool output";
    if (role === "system") return "System";
    if (role === "user") return "User";
    return role;
  }

  // Extract a meaningful command name for the spinner
  function commandName(msg: ReplayMessage): string {
    const m = msg.message;
    const cmd = m.command ?? m.input ?? m.content ?? "";
    // Extract first line or first ~40 chars as the command preview
    const firstLine = cmd.split("\n")[0].trim();
    if (firstLine.length <= 50) return firstLine;
    return firstLine.slice(0, 47) + "...";
  }

  // Role flag for top-right corner of each bubble
  function roleFlag(role: string): { label: string; cls: string } {
    if (role === "assistant") return { label: "Reasoning", cls: "flag-reasoning" };
    if (role === "tool_call") return { label: "Execution", cls: "flag-execution" };
    if (role === "tool_result") return { label: "Output", cls: "flag-output" };
    if (role === "system") return { label: "System", cls: "flag-system" };
    return { label: "", cls: "" };
  }

  // Derive primary display text for the message
  function messageContent(msg: ReplayMessage): string {
    const m = msg.message;
    // tool_result: prefer stdout, fall back to output then content
    if (m.role === "tool_result") {
      return m.stdout ?? m.output ?? m.content ?? "";
    }
    // tool_call: prefer command/input, fall back to content
    if (m.role === "tool_call") {
      return m.command ?? m.input ?? m.content ?? "";
    }
    return m.content ?? "";
  }

  // Determine reward colour class for summary card
  function rewardClass(r: number): string {
    if (r >= 0.9) return "reward-perfect";
    if (r <= 0.1) return "reward-zero";
    return "reward-mid";
  }

  // Detect when a new step begins (compare to previous message's step)
  function isStepStart(index: number): boolean {
    if (index === 0) return true;
    return visibleMessages[index].step !== visibleMessages[index - 1].step;
  }

  // Compute shrinkwrap width for short assistant messages.
  // Returns null when shrinkwrapping should not apply.
  function bubbleShrinkwrap(rm: ReplayMessage): number | null {
    const role = rm.message.role ?? "";
    if (role !== "assistant") return null;
    const text = messageContent(rm);
    if (!text || text.length > 500) return null;

    const lineHeight = getDefaultLineHeight("body");
    const bubbleMax = containerWidth - 60; // replay has smaller avatar/gaps
    const minW = measureMinWidth(text, "body", bubbleMax, lineHeight);
    if (minW >= bubbleMax * 0.7) return null;
    return minW + 24; // +24 for replay padding
  }
</script>

<div class="replay-chat" bind:this={chatEl} data-testid="replay-chat">
  <div class="visibility-legend" data-testid="visibility-legend">
    <span class="legend-item"><span class="legend-dot legend-model"></span> Model reasoning</span>
    <span class="legend-item"><span class="legend-dot legend-tool-exec"></span> Tool execution</span>
    <span class="legend-item"><span class="legend-dot legend-tool-output"></span> Tool output</span>
  </div>

  {#each visibleMessages as rm, i (rm.step + "-" + rm.indexInStep)}
    {#if isStepStart(i)}
      <div class="step-divider" data-testid="step-divider-{rm.step}">
        <span class="divider-line"></span>
        <span class="divider-label">Step {rm.step} · {formatTime(rm.cumulativeMs)}</span>
        <span class="divider-line"></span>
      </div>
    {/if}

    {@const flag = roleFlag(rm.message.role ?? "")}
    {@const shrink = bubbleShrinkwrap(rm)}
    <div
      class="replay-message role-{rm.message.role ?? 'unknown'}"
      data-testid="replay-message-{rm.step}-{rm.indexInStep}"
    >
      <div class="bubble-row">
        <div class="role-avatar {avatarClass(rm.message.role ?? '')}">
          {avatarLetter(rm.message.role ?? "")}
        </div>
        <div
          class="bubble-body"
          data-shrinkwrap={shrink !== null ? "" : undefined}
          style:max-width={shrink !== null ? `${shrink}px` : undefined}
        >
          <div class="bubble-header">
            <span class="role-label-text {rm.message.role === 'tool_call' ? 'tool-label' : ''}">
              {roleLabel(rm)}
            </span>
            {#if flag.label}
              <span class="role-flag {flag.cls}">{flag.label}</span>
            {/if}
          </div>
          {#if messageContent(rm)}
            <div class="bubble-content">{messageContent(rm)}</div>
          {/if}
        </div>
      </div>
    </div>

    {#if rm.message.role === "tool_call" && i === visibleMessages.length - 1 && !finished}
      <div class="tool-spinner" data-testid="tool-spinner">
        <span class="spinner-dot"></span>
        Executing: {commandName(rm)}
      </div>
    {/if}
  {/each}

  {#if finished}
    <div class="summary-card" data-testid="replay-summary-card">
      <div class="summary-title">Run complete</div>
      <div class="summary-stats">
        <div class="summary-stat">
          <span class="stat-key">Reward</span>
          <span class="stat-value {rewardClass(reward)}">{(reward * 100).toFixed(0)}%</span>
        </div>
        <div class="summary-stat">
          <span class="stat-key">Time</span>
          <span class="stat-value">{formatTime(totalMs)}</span>
        </div>
        <div class="summary-stat">
          <span class="stat-key">Tokens</span>
          <span class="stat-value">{tokensTotal.toLocaleString()}</span>
        </div>
        <div class="summary-stat">
          <span class="stat-key">Cost</span>
          <span class="stat-value">${costTotal.toFixed(2)}</span>
        </div>
        <div class="summary-stat">
          <span class="stat-key">Steps</span>
          <span class="stat-value">{totalSteps}</span>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .replay-chat {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 var(--space-md) var(--space-md);
    scroll-behavior: smooth;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  /* Visibility legend at top of chat */
  .visibility-legend {
    display: flex;
    gap: var(--space-md);
    padding: 4px var(--space-md);
    font-size: 0.68rem;
    color: #91918D;
    border-bottom: 1px solid #40403E;
    flex-shrink: 0;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }

  .legend-dot.legend-model {
    background: #4a6741;
  }

  .legend-dot.legend-tool-exec {
    background: #D4A27F;
  }

  .legend-dot.legend-tool-output {
    background: #61AAF2;
  }

  /* Fade-in entrance for each new message */
  @keyframes messageEnter {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .replay-message {
    animation: messageEnter 200ms ease-out;
    margin-bottom: var(--space-sm);
  }

  /* Avatar + content row */
  .bubble-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }

  /* Role avatars matching MessageBubble palette */
  .role-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    min-width: 28px;
    border-radius: 50%;
    color: #fff;
    font-family: var(--font-heading);
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .avatar-assistant { background: #4a6741; }
  .avatar-tool { background: #b87333; }
  .avatar-result { background: #3cb2b1; }
  .avatar-user { background: #7c5cbf; }
  .avatar-system { background: #91918D; }

  .bubble-body {
    flex: 1;
    min-width: 0;
    background: #2a2a28;
    border: 1px solid #40403E;
    border-radius: var(--radius-md);
    padding: 8px 12px;
  }

  .bubble-body[data-shrinkwrap] {
    flex: 0 1 auto;
  }

  /* Model reasoning: green left border, dark green-tinted background */
  .role-assistant .bubble-body {
    border-left: 3px solid #4a6741;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    background: #1a2a1a;
  }

  /* Tool execution (what agent runs): copper left border, dark warm background */
  .role-tool_call .bubble-body {
    border-left: 3px solid #D4A27F;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    background: #2a2218;
  }

  /* Tool output (what agent sees back): blue left border, dark blue-tinted background */
  .role-tool_result .bubble-body {
    border-left: 3px solid #61AAF2;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    background: #1a1e2a;
  }

  /* System messages: dimmed */
  .role-system .bubble-body {
    border-left: 3px solid #91918D;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    background: #1e1e1e;
    opacity: 0.8;
  }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: 4px;
  }

  .role-flag {
    margin-left: auto;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 1px 6px;
    border-radius: 3px;
  }

  .flag-reasoning {
    background: rgba(74, 103, 65, 0.2);
    color: #4a6741;
  }

  .flag-execution {
    background: rgba(212, 162, 127, 0.2);
    color: #D4A27F;
  }

  .flag-output {
    background: rgba(97, 170, 242, 0.2);
    color: #61AAF2;
  }

  .flag-system {
    background: rgba(145, 145, 141, 0.15);
    color: #91918D;
  }

  .role-label-text {
    font-size: 0.7rem;
    font-weight: 600;
    color: #91918D;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  /* Tool labels use mono font and copper colour */
  .tool-label {
    font-family: var(--font-mono);
    text-transform: none;
    color: #b87333;
    font-weight: 600;
  }

  .bubble-content {
    font-size: 0.83rem;
    line-height: 1.55;
    color: #E5E4DF;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--font-mono);
    overflow: hidden;
    /* Truncate very long tool outputs to keep the chat scannable */
    max-height: 200px;
    overflow-y: auto;
  }

  /* Assistant gets regular body font, not mono */
  .role-assistant .bubble-content,
  .role-system .bubble-content,
  .role-user .bubble-content {
    font-family: var(--font-body);
  }

  /* Step divider */
  .step-divider {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin: var(--space-md) 0 var(--space-sm);
    padding: 0 2px;
  }

  .divider-line {
    flex: 1;
    height: 1px;
    background: #40403E;
  }

  .divider-label {
    font-size: 0.68rem;
    font-family: var(--font-mono);
    color: #91918D;
    white-space: nowrap;
    letter-spacing: 0.03em;
  }

  /* Completion summary card */
  .summary-card {
    margin-top: var(--space-lg);
    background: #2a2a28;
    border: 1px solid #40403E;
    border-radius: var(--radius-md);
    padding: var(--space-md) var(--space-lg);
    animation: messageEnter 300ms ease-out;
  }

  .summary-title {
    font-family: var(--font-heading);
    font-size: 0.85rem;
    font-weight: 700;
    color: #BFBFBA;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: var(--space-md);
  }

  .summary-stats {
    display: flex;
    gap: var(--space-lg);
    flex-wrap: wrap;
  }

  .summary-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-key {
    font-size: 0.68rem;
    color: #91918D;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .stat-value {
    font-family: var(--font-mono);
    font-size: 1rem;
    font-weight: 700;
    color: #E5E4DF;
  }

  /* Reward colour classes matching the shared interface palette */
  .reward-perfect { color: #61AAF2; }
  .reward-zero { color: #BF4D43; }
  .reward-mid { color: #D4A27F; }

  /* Tool call spinner shown while waiting for result */
  .tool-spinner {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 0 8px 44px;
    color: #91918D;
    font-size: 0.78rem;
    font-style: italic;
    animation: fadeIn 0.3s ease-out;
  }

  .spinner-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #61AAF2;
    animation: pulse 1s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(0.8); }
    50% { opacity: 1; transform: scale(1.2); }
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
</style>
