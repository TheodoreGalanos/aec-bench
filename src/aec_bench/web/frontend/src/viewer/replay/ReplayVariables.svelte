<!-- ABOUTME: Right panel for trajectory replay showing current RLM variable state and scratchpad. -->
<!-- ABOUTME: Split vertically: top half shows current variables with change highlights, bottom half shows scratchpad. -->
<script lang="ts">
  const REPL_COMMANDS = new Set([
    "cat", "cd", "cp", "echo", "find", "grep", "head", "ls", "mkdir", "mv",
    "pwd", "rm", "sed", "tail", "touch", "wc", "python", "python3", "pip",
    "node", "npm", "git", "curl", "wget",
  ]);

  interface Props {
    currentVariables: Record<string, any>;
    currentScratchpad: Record<string, any>;
    currentStep: number;
    fullState: Record<string, any>;
    fullScratchpad: Record<string, any>;
    oninspect: (title: string, content: string) => void;
  }

  let { currentVariables, currentScratchpad, currentStep, fullState, fullScratchpad, oninspect }: Props = $props();

  // Track which keys were recently changed for fade animation
  let recentlyChanged: Map<string, "added" | "changed"> = $state(new Map());
  let prevTrackedStep = -1;
  let prevVarKeys = new Set<string>();
  let fadeTimer: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    // Only react when the step actually changes — avoids infinite loops
    if (currentStep === prevTrackedStep) return;
    prevTrackedStep = currentStep;

    // Detect added/changed keys by comparing with previous snapshot
    const updated = new Map<string, "added" | "changed">();
    for (const key of Object.keys(currentVariables)) {
      if (!prevVarKeys.has(key)) {
        updated.set(key, "added");
      } else {
        updated.set(key, "changed");
      }
    }
    prevVarKeys = new Set(Object.keys(currentVariables));

    if (updated.size === 0) return;
    recentlyChanged = updated;

    // Clear highlights after 2s
    if (fadeTimer) clearTimeout(fadeTimer);
    fadeTimer = setTimeout(() => {
      recentlyChanged = new Map();
    }, 2000);
  });

  function isFunction(value: any): boolean {
    if (value === null || value === undefined) return false;
    if (typeof value === "object" && value.type === "function") return true;
    if (typeof value === "string" && value.startsWith("function")) return true;
    return false;
  }

  function isReplCommand(key: string): boolean {
    return REPL_COMMANDS.has(key);
  }

  function shouldFilter(key: string, value: any): boolean {
    return isFunction(value) || isReplCommand(key);
  }

  function truncate(raw: any, maxLen = 50): string {
    if (raw === null || raw === undefined) return "null";
    if (typeof raw === "number" || typeof raw === "boolean") return String(raw);
    if (typeof raw === "string") {
      if (raw.length <= maxLen) return `"${raw}"`;
      return `"${raw.slice(0, maxLen)}…" (${raw.length})`;
    }
    if (Array.isArray(raw)) {
      return `list(${raw.length})`;
    }
    if (typeof raw === "object") {
      const keys = Object.keys(raw);
      if (keys.length <= 3) return `{${keys.join(", ")}}`;
      return `{${keys.slice(0, 2).join(", ")}, …} (${keys.length})`;
    }
    return String(raw).slice(0, maxLen);
  }

  let filteredVars = $derived(
    Object.entries(currentVariables).filter(([key, value]) => !shouldFilter(key, value)),
  );

  function formatValue(value: any): string {
    if (typeof value === "string") return value;
    return JSON.stringify(value);
  }

  function formatFullValue(value: any): string {
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  // Expand state removed — clicking now opens a modal via oninspect callback

  let scratchpadEntries = $derived(
    Object.entries(currentScratchpad),
  );

  function handleVarClick(key: string): void {
    const fullValue = fullState[key] ?? currentVariables[key];
    oninspect(`Variable: ${key}`, formatFullValue(fullValue));
  }

  function handleScratchpadClick(key: string): void {
    const fullValue = fullScratchpad[key] ?? currentScratchpad[key];
    oninspect(`Scratchpad: ${key}`, formatFullValue(fullValue));
  }
</script>

<div class="variables-panel" data-testid="replay-variables">
  <!-- Top half: current state -->
  <div class="current-state" data-testid="variables-current-state">
    <div class="section-header">Variables</div>
    {#if filteredVars.length === 0}
      <div class="empty-msg">No variables</div>
    {:else}
      <div class="var-list">
        {#each filteredVars as [key, value]}
          {@const changeType = recentlyChanged.get(key)}
          <!-- svelte-ignore a11y_interactive_supports_focus -->
          <div
            class="var-row"
            class:changed={changeType !== undefined}
            class:expandable={true}
            role="button"
            data-testid="var-row-{key}"
            onclick={() => handleVarClick(key)}
            onkeydown={(e) => { if (e.key === "Enter" || e.key === " ") handleVarClick(key); }}
          >
            <span class="var-key">{key}</span>
            <span class="var-eq">=</span>
            <span class="var-value" title={formatValue(value)}>{truncate(value)}</span>
            {#if changeType !== undefined}
              <span class="change-badge" class:badge-new={changeType === "added"}>
                {changeType === "added" ? "NEW" : "CHANGED"}
              </span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Bottom half: scratchpad -->
  <div class="scratchpad-panel" data-testid="variables-scratchpad">
    <div class="section-header">Scratchpad</div>
    {#if scratchpadEntries.length === 0}
      <div class="empty-msg">No scratchpad</div>
    {:else}
      <div class="var-list">
        {#each scratchpadEntries as [key, value]}
          <!-- svelte-ignore a11y_interactive_supports_focus -->
          <div
            class="var-row expandable"
            role="button"
            data-testid="scratchpad-row-{key}"
            onclick={() => handleScratchpadClick(key)}
            onkeydown={(e) => { if (e.key === "Enter" || e.key === " ") handleScratchpadClick(key); }}
          >
            <span class="var-key">{key}</span>
            <span class="var-eq">=</span>
            <span class="var-value" title={formatValue(value)}>{truncate(value)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .variables-panel {
    width: 280px;
    min-width: 280px;
    background: #1e1e1e;
    border-left: 1px solid #40403E;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .section-header {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #91918D;
    padding: 4px var(--space-sm) 2px;
    flex-shrink: 0;
  }

  .current-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-bottom: 1px solid #40403E;
  }

  .var-list {
    flex: 1;
    overflow-y: auto;
    padding: 2px 0;
  }

  .var-row {
    display: flex;
    align-items: baseline;
    gap: 3px;
    padding: 2px var(--space-sm);
    border-left: 3px solid transparent;
    transition: border-color 0.3s ease, background 0.3s ease;
  }

  .var-row.expandable {
    cursor: pointer;
  }

  .var-row.expandable:hover {
    background: #262625;
  }

  .var-row.changed {
    border-left-color: #61AAF2;
    background: rgba(97, 170, 242, 0.1);
  }

  .var-key {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: #4a6741;
    flex-shrink: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 80px;
  }

  .var-eq {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: #91918D;
    flex-shrink: 0;
  }

  .var-value {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: #E5E4DF;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .change-badge {
    font-size: 0.58rem;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    background: #4a6741;
    color: white;
    flex-shrink: 0;
    letter-spacing: 0.04em;
  }

  .change-badge.badge-new {
    background: #61AAF2;
  }

  .scratchpad-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .empty-msg {
    font-size: 0.72rem;
    color: #91918D;
    padding: var(--space-sm);
    font-style: italic;
  }
</style>
