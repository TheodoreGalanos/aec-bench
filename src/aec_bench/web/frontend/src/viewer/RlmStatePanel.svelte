<!-- ABOUTME: Scrollable right-column panel displaying RLM-specific state: template progress, variables, and scratchpad. -->
<!-- ABOUTME: Reads metadata from the active step and delegates display to child sub-components. -->
<script lang="ts">
  import type { StepSummary, ViewerState } from "../lib/types";
  import TemplateProgress from "./TemplateProgress.svelte";
  import VariableList from "./VariableList.svelte";
  import ScratchpadList from "./ScratchpadList.svelte";

  interface Props {
    steps: StepSummary[];
    activeStep: number;
    rlmState: ViewerState | null;
    openModal: (title: string, content: string) => void;
  }

  let { steps, activeStep, rlmState, openModal }: Props = $props();

  // REPL command function names that should be filtered out of the variables list.
  // These are injected by the RLM scaffold and do not represent meaningful data variables.
  const REPL_COMMANDS = new Set([
    "CONTEXT", "DOCS", "FILL", "GUIDANCE", "HELP", "NOTE", "READ",
    "RECALL", "RULES", "START", "STATUS", "SUBMIT", "VALIDATE",
    "FINAL_VAR",
  ]);

  let currentStep = $derived(steps.find((s) => s.step === activeStep) ?? null);
  let metadata = $derived(currentStep?.metadata ?? null);

  // Template progress from step metadata
  let templateProgress = $derived.by(() => {
    const tp = metadata?.template_progress;
    if (!tp) return null;
    return {
      completed: tp.completed ?? tp.filled ?? 0,
      total: tp.total ?? tp.sections ?? 0,
      sections: (tp.section_list ?? []).map((s: any) => ({
        id: typeof s === "string" ? s : s.id ?? s.name ?? "unknown",
        filled: typeof s === "string" ? false : !!s.filled,
      })),
    };
  });

  // Variables from per-step metadata.variables (dict of {name: type_string}),
  // with new-variable highlighting from metadata.var_diff.new.
  // Falls back to rlmState.symbolic_state when step metadata is unavailable.
  // Filters out REPL command function names that clutter the list.
  let variables = $derived.by(() => {
    const stepVars = metadata?.variables;
    if (stepVars && typeof stepVars === "object") {
      const newVarNames = new Set<string>(
        Array.isArray(metadata?.var_diff?.new) ? metadata.var_diff.new : []
      );
      return Object.entries(stepVars)
        .filter(([name, typeStr]) => {
          if (REPL_COMMANDS.has(name)) return false;
          const t = typeof typeStr === "string" ? typeStr : String(typeStr);
          if (t === "function" || t.startsWith("function")) return false;
          return true;
        })
        .map(([name, typeStr]) => ({
          name,
          type: typeof typeStr === "string" ? typeStr : String(typeStr),
          isNew: newVarNames.has(name),
        }));
    }
    // Fallback: derive from global symbolic state when step metadata lacks variables
    if (!rlmState?.symbolic_state) return [];
    const state = rlmState.symbolic_state;
    const newVars = new Set(metadata?.new_variables ?? []);
    return Object.entries(state)
      .filter(([name, val]) => {
        if (REPL_COMMANDS.has(name)) return false;
        if (typeof val === "function") return false;
        const t = typeof val === "object" && val !== null ? "object" : typeof val;
        if (t === "function") return false;
        return true;
      })
      .map(([name, val]) => ({
        name,
        type: typeof val === "object" && val !== null ? "object" : typeof val,
        isNew: newVars.has(name),
      }));
  });

  // Scratchpad keys from per-step metadata, falling back to global rlmState
  let scratchpadKeys = $derived.by(() => {
    if (Array.isArray(metadata?.scratchpad_keys)) {
      return metadata.scratchpad_keys as string[];
    }
    return rlmState?.scratchpad_data ? Object.keys(rlmState.scratchpad_data) : [];
  });

  function handleVariableSelect(name: string) {
    // Use global symbolic_state for the full value in the modal
    if (rlmState?.symbolic_state && name in rlmState.symbolic_state) {
      const value = rlmState.symbolic_state[name];
      const formatted = typeof value === "string" ? value : JSON.stringify(value, null, 2);
      openModal(`Variable: ${name}`, formatted);
    } else {
      openModal(`Variable: ${name}`, "(value not available in global state)");
    }
  }

  function handleScratchpadSelect(key: string) {
    // Use global scratchpad_data for the full value in the modal
    if (rlmState?.scratchpad_data && key in rlmState.scratchpad_data) {
      const value = rlmState.scratchpad_data[key];
      const formatted = typeof value === "string" ? value : JSON.stringify(value, null, 2);
      openModal(`Scratchpad: ${key}`, formatted);
    } else {
      openModal(`Scratchpad: ${key}`, "(value not available in global state)");
    }
  }
</script>

<div class="rlm-state-panel" data-testid="rlm-state-panel">
  {#if !metadata}
    <div class="empty-panel">Select a step to view RLM state.</div>
  {:else}
    {#if templateProgress}
      <div class="panel-section">
        <h3 class="panel-heading">Template Progress</h3>
        <TemplateProgress
          completed={templateProgress.completed}
          total={templateProgress.total}
          sections={templateProgress.sections}
        />
      </div>
    {/if}

    <div class="panel-section">
      <h3 class="panel-heading">
        Variables
        {#if variables.length > 0}
          <span class="heading-count">{variables.length}</span>
        {/if}
      </h3>
      <VariableList
        {variables}
        onselect={handleVariableSelect}
      />
    </div>

    {#if scratchpadKeys.length > 0}
      <div class="panel-section">
        <h3 class="panel-heading">
          Scratchpad
          <span class="heading-count">{scratchpadKeys.length}</span>
        </h3>
        <ScratchpadList
          keys={scratchpadKeys}
          onselect={handleScratchpadSelect}
        />
      </div>
    {/if}
  {/if}
</div>

<style>
  .rlm-state-panel {
    overflow-y: auto;
    height: 100%;
    padding: var(--space-md);
    background: var(--card);
  }

  .panel-section {
    margin-bottom: var(--space-lg);
    padding-bottom: var(--space-md);
    border-bottom: 1px solid var(--card-border);
  }

  .panel-section:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .panel-heading {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-family: var(--font-heading);
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--forest);
    margin-bottom: 10px;
  }

  .heading-count {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-3);
    background: var(--bg-alt);
    padding: 0 var(--space-xs);
    border-radius: 9999px;
    border: 1px solid var(--card-border);
  }

  .empty-panel {
    font-size: 0.85rem;
    color: var(--text-3);
    font-style: italic;
    padding: var(--space-lg) var(--space-md);
    text-align: center;
  }
</style>
