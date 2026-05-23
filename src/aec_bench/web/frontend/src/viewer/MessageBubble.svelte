<!-- ABOUTME: Renders a single trajectory message with role-based styling for assistant, tool_call, tool_result, and system. -->
<!-- ABOUTME: Supports markdown rendering via marked, dark code blocks, and collapsible long outputs with role labels. -->
<script lang="ts">
  import { marked } from "marked";
  import type { TrajectoryMessage } from "../lib/types";
  import CollapsibleOutput from "./CollapsibleOutput.svelte";
  import { measureMinWidth, getDefaultLineHeight } from "../lib/pretext-service";

  interface Props {
    message: TrajectoryMessage;
    containerWidth?: number;
  }

  let { message, containerWidth = 600 }: Props = $props();

  let role: string = $derived(message.role ?? "unknown");
  let content: string = $derived(message.content ?? "");
  let toolName: string = $derived(message.tool_name ?? message.name ?? "");
  let command: string = $derived(message.command ?? message.input ?? "");
  let stdout: string = $derived(message.stdout ?? message.output ?? "");
  let stderr: string = $derived(message.stderr ?? "");
  let exitCode: number | null = $derived(message.exit_code ?? null);
  let media: string[] = $derived(message.media ?? []);

  function renderMarkdown(text: string): string {
    try {
      return marked.parse(text, { async: false }) as string;
    } catch {
      return text;
    }
  }

  let isSystemRole = $derived(role === "system");
  let isLongAssistant = $derived(role === "assistant" && content.length > 500);
  let isLongToolResult = $derived(role === "tool_result" && stdout.length > 400);

  // Determine result tint class based on exit code
  let resultTint = $derived.by(() => {
    if (role !== "tool_result") return "";
    if (exitCode === null) return "";
    return exitCode === 0 ? "result-ok" : "result-err";
  });

  // Role label mapping for trajectory context hints
  let roleLabel = $derived.by(() => {
    if (role === "system") return "System prompt";
    if (role === "assistant") return "Model output";
    if (role === "tool_call") return "Tool invocation";
    if (role === "tool_result") return "Tool output";
    return role;
  });

  // Avatar letter and colour class
  let avatarLetter = $derived.by(() => {
    if (role === "system") return "S";
    if (role === "assistant") return "A";
    if (role === "tool_call") return "T";
    if (role === "tool_result") return "R";
    if (role === "user") return "U";
    return "?";
  });

  let avatarClass = $derived.by(() => {
    if (role === "assistant") return "avatar-assistant";
    if (role === "tool_call" || role === "tool") return "avatar-tool";
    if (role === "tool_result" || role === "result") return "avatar-result";
    if (role === "user") return "avatar-user";
    if (role === "system") return "avatar-system";
    return "avatar-system";
  });

  // Shrinkwrap: short assistant messages get a tight-fitting width instead of
  // filling the full container. Returns null to skip shrinkwrapping.
  let shrinkwrapWidth = $derived.by(() => {
    if (role !== "assistant") return null;
    if (content.length > 500) return null;
    if (content.length === 0) return null;

    const lineHeight = getDefaultLineHeight("body");
    const bubbleMax = containerWidth - 80; // avatar + gaps
    const minW = measureMinWidth(content, "body", bubbleMax, lineHeight);

    // Only shrinkwrap if significantly smaller than container
    if (minW >= bubbleMax * 0.7) return null;
    return minW + 28; // +28 for padding (14px each side)
  });
</script>

<div class="message-bubble role-{role} {resultTint}" data-testid="message-{role}">
  <div class="bubble-row">
    <div class="role-avatar {avatarClass}">{avatarLetter}</div>

    <div
      class="bubble-body"
      data-shrinkwrap={shrinkwrapWidth !== null ? "" : undefined}
      style:max-width={shrinkwrapWidth !== null ? `${shrinkwrapWidth}px` : undefined}
    >
      {#if role === "system"}
        <div class="bubble-header">
          <span class="role-label">System</span>
          <span class="role-hint">{roleLabel}</span>
        </div>
        <CollapsibleOutput content={content} maxHeight={150} label="system prompt" containerWidth={containerWidth - 80} />

      {:else if role === "assistant"}
        <div class="bubble-header">
          <span class="role-label">Assistant</span>
          <span class="role-hint">{roleLabel}</span>
        </div>
        {#if isLongAssistant}
          <CollapsibleOutput content={content} maxHeight={300} containerWidth={containerWidth - 80} />
        {:else}
          <div class="bubble-content markdown">
            {@html renderMarkdown(content)}
          </div>
        {/if}

      {:else if role === "tool_call"}
        <div class="bubble-header">
          <span class="role-label tool-label">{toolName}</span>
          <span class="role-hint">{roleLabel}</span>
        </div>
        {#if command}
          <div class="tool-command-wrapper">
            <pre class="tool-command"><code>{command}</code></pre>
          </div>
        {/if}
        {#if content}
          <CollapsibleOutput content={content} maxHeight={300} containerWidth={containerWidth - 80} />
        {/if}

      {:else if role === "tool_result"}
        <div class="bubble-header">
          <span class="role-label tool-label">{toolName || "Result"}</span>
          {#if exitCode !== null}
            <span class="exit-code" class:exit-ok={exitCode === 0} class:exit-err={exitCode !== 0} data-testid="exit-code">
              exit {exitCode}
            </span>
          {/if}
          <span class="role-hint">{roleLabel}</span>
        </div>
        {#if stdout}
          <CollapsibleOutput content={stdout} maxHeight={300} containerWidth={containerWidth - 80} />
        {/if}
        {#if stderr}
          <div class="stderr-block">
            <CollapsibleOutput content={stderr} maxHeight={200} label="stderr" containerWidth={containerWidth - 80} />
          </div>
        {/if}

      {:else}
        <div class="bubble-header">
          <span class="role-label">{role}</span>
          <span class="role-hint">{roleLabel}</span>
        </div>
        {#if isSystemRole || content.length > 500}
          <CollapsibleOutput content={content} maxHeight={150} containerWidth={containerWidth - 80} />
        {:else if content}
          <div class="bubble-content">{content}</div>
        {/if}
      {/if}

      {#if media.length > 0}
        <div class="media-row">
          {#each media as src}
            <img class="media-img" {src} alt="Attached media" />
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  /* Outer bubble container */
  .message-bubble {
    margin-bottom: var(--space-sm);
    border-radius: 0;
    transition: box-shadow var(--transition-fast);
  }

  /* Avatar + content row layout matching old viewer */
  .bubble-row {
    display: flex;
    gap: 10px;
  }

  /* Role avatars matching old viewer palette */
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

  .avatar-assistant { background: var(--green); }
  .avatar-tool { background: var(--copper); }
  .avatar-result { background: var(--teal); }
  .avatar-user { background: var(--violet); }
  .avatar-system { background: var(--text-3); }

  .bubble-body {
    flex: 1;
    min-width: 0;
  }

  .bubble-body[data-shrinkwrap] {
    flex: 0 1 auto;
  }

  /* Role-specific content backgrounds */
  .role-assistant .bubble-body {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    padding: 10px 14px;
  }

  .role-system .bubble-body {
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    padding: 10px 14px;
    opacity: 0.85;
  }

  .role-tool_call .bubble-body {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    padding: 10px 14px;
  }

  .role-tool_result .bubble-body {
    border-left: 3px solid var(--teal);
    padding: 10px 14px;
    background: var(--card);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
  }

  /* Result tint overrides for tool_result */
  .result-ok .bubble-body {
    background: var(--result-ok-bg);
    border-left-color: var(--forest);
  }

  .result-err .bubble-body {
    background: var(--result-err-bg);
    border-left-color: var(--reward-zero);
  }

  .role-unknown .bubble-body {
    background: var(--card);
    border: 1px dashed var(--card-border);
    border-radius: var(--radius-md);
    padding: 10px 14px;
  }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-xs);
  }

  .role-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .role-hint {
    font-size: 0.68rem;
    color: var(--text-3);
    font-style: italic;
    opacity: 0.6;
    margin-left: auto;
  }

  .tool-label {
    font-family: var(--font-mono);
    text-transform: none;
    color: var(--copper);
    font-weight: 600;
  }

  .bubble-content {
    font-size: 0.85rem;
    line-height: 1.6;
    color: var(--text);
  }

  /* Basic markdown rendering styles */
  .bubble-content :global(p) {
    margin: var(--space-xs) 0;
  }

  .bubble-content :global(code) {
    font-family: var(--font-mono);
    font-size: 0.85em;
    background: var(--code-bg);
    color: var(--code-text);
    padding: 1px 5px;
    border-radius: 3px;
  }

  .bubble-content :global(pre) {
    background: var(--code-bg);
    color: var(--code-text);
    padding: var(--space-md);
    border-radius: var(--radius-md);
    border: 1px solid var(--code-border);
    overflow-x: auto;
    margin: var(--space-sm) 0;
  }

  .bubble-content :global(pre code) {
    background: transparent;
    padding: 0;
    border-radius: 0;
  }

  .tool-command-wrapper {
    margin: 0 0 var(--space-sm);
  }

  .tool-command {
    margin: 0;
    padding: var(--space-sm) var(--space-md);
    background: var(--code-bg);
    color: var(--code-text);
    border: 1px solid var(--code-border);
    border-radius: var(--radius-md);
    font-size: 0.82rem;
    overflow-x: auto;
  }

  .tool-command code {
    font-family: var(--font-mono);
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--code-text);
  }

  .exit-code {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 700;
    padding: 1px var(--space-sm);
    border-radius: 9999px;
  }

  .exit-ok {
    color: var(--forest);
    background: var(--forest-light);
  }

  .exit-err {
    color: var(--reward-zero);
    background: var(--reward-zero-bg);
  }

  .stderr-block {
    margin-top: var(--space-sm);
  }

  .media-row {
    display: flex;
    gap: var(--space-sm);
    flex-wrap: wrap;
    margin-top: var(--space-sm);
  }

  .media-img {
    max-width: 300px;
    max-height: 200px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--card-border);
    object-fit: contain;
    cursor: pointer;
    transition: box-shadow var(--transition-fast);
  }

  .media-img:hover {
    box-shadow: var(--shadow-md);
  }
</style>
