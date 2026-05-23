<!-- ABOUTME: Full Viewer page assembling all 12 sub-components into a 3-column layout with scroll containment. -->
<!-- ABOUTME: Fetches trial metadata, lazily loads step messages, and supports RLM state panel for RLM trials. -->
<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { waitForFonts, clearCache } from "../lib/pretext-service";
  import {
    viewerStore,
    resetViewer,
    setViewerTrial,
    setActiveStep,
    cacheStepMessages,
    setRlmState,
    setLambdaRlmState,
    setViewerLoading,
  } from "../lib/stores/viewer";
  import {
    fetchViewerMeta,
    fetchViewerStep,
    fetchViewerState,
    submitAnnotation,
  } from "../lib/api";
  import Modal from "../lib/components/Modal.svelte";
  import ViewerTopBar from "../viewer/ViewerTopBar.svelte";
  import StatsBar from "../viewer/StatsBar.svelte";
  import StepList from "../viewer/StepList.svelte";
  import MessagePane from "../viewer/MessagePane.svelte";
  import RlmStatePanel from "../viewer/RlmStatePanel.svelte";
  import LambdaRlmStatePanel from "../viewer/LambdaRlmStatePanel.svelte";
  import InfoPanel from "../viewer/InfoPanel.svelte";
  import Skeleton from "../lib/components/Skeleton.svelte";
  import TrajectoryReplay from "../viewer/replay/TrajectoryReplay.svelte";

  interface Props {
    experiment: string;
    trial: string;
  }

  let { experiment, trial }: Props = $props();

  // Replay overlay state
  let replayOpen = $state(false);

  function openReplay() { replayOpen = true; }
  function closeReplay() { replayOpen = false; }

  // Content modal state (for subcalls, variables, scratchpad)
  let modalOpen = $state(false);
  let modalTitle = $state("");
  let modalContent = $state("");

  function openModal(title: string, content: string) {
    modalTitle = title;
    modalContent = content;
    modalOpen = true;
  }

  function closeModal() {
    modalOpen = false;
  }

  // Notes modal state (for annotation notes)
  let notesModalOpen = $state(false);
  let notesText = $state("");

  function openNotesModal() {
    notesText = storeValue.trial?.annotation?.notes ?? "";
    notesModalOpen = true;
  }

  function closeNotesModal() {
    notesModalOpen = false;
  }

  async function saveNote() {
    if (!storeValue.trial) return;
    await submitAnnotation({
      trial_id: trial,
      experiment_id: experiment,
      verdict: "note",
      notes: notesText,
    });
    const updatedMeta = await fetchViewerMeta(experiment, trial);
    setViewerTrial(updatedMeta);
    notesModalOpen = false;
  }

  let keybindHelpOpen = $state(false);

  // Tracks whether the active step was set by a click (vs scroll-sync) so
  // the MessagePane knows when to programmatically scroll to that step.
  let scrollToStep = $state(-1);

  // Keyboard shortcut map for annotations (n handled separately — opens modal)
  const keyToVerdict: Record<string, string> = {
    "1": "pass",
    "2": "fail",
    "3": "defer",
  };

  function handleKeydown(event: KeyboardEvent) {
    if (replayOpen) return; // Let replay handle its own keyboard shortcuts

    // Escape always works — close any modal
    if (event.key === "Escape") {
      if (notesModalOpen) { closeNotesModal(); return; }
      if (modalOpen) { closeModal(); return; }
      return;
    }

    // Block all other shortcuts when a modal is open or typing in an input
    if (modalOpen || notesModalOpen) return;
    const target = event.target as HTMLElement;
    if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
      return;
    }

    // Step navigation: j/k or arrows
    if (event.key === "j" || event.key === "ArrowDown") {
      event.preventDefault();
      navigateStep(1);
      return;
    }
    if (event.key === "k" || event.key === "ArrowUp") {
      event.preventDefault();
      navigateStep(-1);
      return;
    }

    // Replay: p
    if (event.key === "p" && storeValue.trial?.has_trajectory) {
      event.preventDefault();
      openReplay();
      return;
    }

    // Notes modal: n
    if (event.key === "n") {
      event.preventDefault();
      openNotesModal();
      return;
    }

    // Undo annotation: x
    if (event.key === "x") {
      event.preventDefault();
      handleClearAnnotation();
      return;
    }

    // Annotation shortcuts: 1/2/3
    const verdict = keyToVerdict[event.key];
    if (verdict) {
      event.preventDefault();
      handleAnnotate(verdict);
    }
  }

  function navigateStep(direction: number) {
    const state = storeValue;
    if (!state || state.steps.length === 0) return;
    const currentIndex = state.steps.findIndex((s) => s.step === state.activeStep);
    const nextIndex = currentIndex + direction;
    if (nextIndex >= 0 && nextIndex < state.steps.length) {
      const nextStepNum = state.steps[nextIndex].step;
      handleStepSelect(nextStepNum);
    }
  }

  // Subscribe to store
  let storeValue = $state($viewerStore);
  const unsubscribe = viewerStore.subscribe((v) => {
    storeValue = v;
  });

  onDestroy(() => {
    unsubscribe();
    clearCache();
  });

  // Load step messages lazily
  async function loadStepMessages(stepNum: number) {
    if (storeValue.stepMessages.has(stepNum)) return;
    setViewerLoading("step", true);
    try {
      const stepData = await fetchViewerStep(experiment, trial, stepNum);
      cacheStepMessages(stepNum, stepData.messages);
    } catch {
      // Step data unavailable — leave uncached so the pane shows the empty message
    } finally {
      setViewerLoading("step", false);
    }
  }

  // Preload a window of steps around the given step (±PRELOAD_WINDOW)
  const PRELOAD_WINDOW = 3;
  function preloadStepsAround(stepNum: number) {
    const allSteps = storeValue.steps;
    const idx = allSteps.findIndex((s) => s.step === stepNum);
    if (idx < 0) return;
    const start = Math.max(0, idx - PRELOAD_WINDOW);
    const end = Math.min(allSteps.length, idx + PRELOAD_WINDOW + 1);
    for (let i = start; i < end; i++) {
      loadStepMessages(allSteps[i].step);
    }
  }

  function handleStepSelect(stepNum: number) {
    setActiveStep(stepNum);
    preloadStepsAround(stepNum);
    // Signal the MessagePane to scroll to this step
    scrollToStep = stepNum;
  }

  function handleStepVisible(stepNum: number) {
    // Scroll-sync: update active step and preload messages ahead
    setActiveStep(stepNum);
    preloadStepsAround(stepNum);
  }

  async function handleAnnotate(verdict: string) {
    if (!storeValue.trial) return;
    // "note" opens the notes modal instead of submitting directly
    if (verdict === "note") {
      openNotesModal();
      return;
    }
    try {
      await submitAnnotation({
        trial_id: trial,
        experiment_id: experiment,
        verdict,
      });
      // Re-fetch meta to update annotation display
      const updatedMeta = await fetchViewerMeta(experiment, trial);
      setViewerTrial(updatedMeta);
    } catch {
      // Annotation failed — leave current state unchanged
    }
  }

  async function handleClearAnnotation() {
    if (!storeValue.trial) return;
    try {
      await submitAnnotation({
        trial_id: trial,
        experiment_id: experiment,
        verdict: "defer",
        notes: "",
      });
      const updatedMeta = await fetchViewerMeta(experiment, trial);
      setViewerTrial(updatedMeta);
    } catch {
      // Clear failed
    }
  }

  onMount(async () => {
    await waitForFonts();
    resetViewer();
    setViewerLoading("meta", true);

    try {
      const meta = await fetchViewerMeta(experiment, trial);
      setViewerTrial(meta);

      // Preload the first batch of steps so the user never sees "No messages loaded"
      const initialBatch = meta.steps.slice(0, PRELOAD_WINDOW * 2 + 1);
      await Promise.all(initialBatch.map((s) => loadStepMessages(s.step)));

      // Load adapter-specific state
      if (meta.adapter_type === "lambda-rlm") {
        try {
          const stateResp = await fetchViewerState(experiment, trial);
          setLambdaRlmState({ plan_state: stateResp.plan_state ?? null });
        } catch {
          // Lambda-RLM state unavailable
        }
      } else if (meta.adapter_type === "rlm") {
        try {
          const rlmState = await fetchViewerState(experiment, trial);
          setRlmState(rlmState);
        } catch {
          // RLM state unavailable — leave null
        }
      }
    } catch {
      // Meta fetch failed — component renders with null trial
    } finally {
      setViewerLoading("meta", false);
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="viewer-layout" data-testid="viewer-layout">
  {#if storeValue.loading.meta && !storeValue.trial}
    <div class="viewer-loading">
      <Skeleton height="48px" />
      <Skeleton height="40px" />
      <div class="loading-columns">
        <Skeleton height="100%" width="220px" />
        <Skeleton height="100%" />
        <Skeleton height="100%" width="280px" />
      </div>
    </div>
  {:else if storeValue.trial}
    <ViewerTopBar
      experimentId={storeValue.trial.experiment_id}
      trialId={storeValue.trial.trial_id}
      backUrl={storeValue.trial.back_url}
      prevTrial={storeValue.trial.prev_trial}
      nextTrial={storeValue.trial.next_trial}
      hasTrajectory={storeValue.trial.has_trajectory ?? false}
      onreplay={openReplay}
    />

    <StatsBar
      reward={storeValue.trial.reward}
      rewardClass={storeValue.trial.reward_class}
      totalSteps={storeValue.steps.length}
      totalErrors={storeValue.trial.total_errors}
      tokensIn={storeValue.trial.tokens_in}
      tokensOut={storeValue.trial.tokens_out}
      totalTokens={storeValue.trial.total_tokens}
      costUsd={storeValue.trial.cost_usd}
      adapterType={storeValue.trial.adapter_type ?? "other"}
      annotation={storeValue.trial.annotation}
      experimentId={experiment}
      trialId={trial}
      activeStep={storeValue.activeStep}
      steps={storeValue.steps}
      onAnnotate={handleAnnotate}
    />

    <div class="viewer-columns">
      <div class="col-steps">
        <StepList
          steps={storeValue.steps}
          activeStep={storeValue.activeStep}
          onselect={handleStepSelect}
        />
      </div>

      <div class="col-messages">
        <MessagePane
          steps={storeValue.steps}
          activeStep={storeValue.activeStep}
          stepMessages={storeValue.stepMessages}
          loading={storeValue.loading.step}
          isRlm={storeValue.trial.is_rlm_trial}
          onStepVisible={handleStepVisible}
          {scrollToStep}
          {openModal}
        />
      </div>

      <div class="col-side">
        {#if storeValue.trial.adapter_type === "lambda-rlm"}
          <LambdaRlmStatePanel
            steps={storeValue.steps}
            activeStep={storeValue.activeStep}
            planState={storeValue.lambdaRlm}
            openModal={openModal}
          />
        {:else if storeValue.trial.adapter_type === "rlm"}
          <RlmStatePanel
            steps={storeValue.steps}
            activeStep={storeValue.activeStep}
            rlmState={storeValue.rlm}
            {openModal}
          />
        {:else}
          <InfoPanel
            trial={storeValue.trial}
            artefacts={storeValue.trial.artefacts}
            {openModal}
          />
        {/if}
      </div>
    </div>
  {:else}
    <div class="viewer-error">
      <h2>Trial not found</h2>
      <p>Could not load trial <code>{trial}</code> from experiment <code>{experiment}</code>.</p>
    </div>
  {/if}
</div>

<Modal open={modalOpen} title={modalTitle} onclose={closeModal}>
  <pre class="modal-pre">{modalContent}</pre>
</Modal>

<!-- Notes modal with textarea -->
<Modal open={notesModalOpen} title="Add Note" onclose={closeNotesModal}>
  <div class="notes-form">
    <textarea
      class="notes-textarea"
      bind:value={notesText}
      placeholder="Write your notes here..."
      rows="6"
    ></textarea>
    <div class="notes-actions">
      <button class="notes-cancel" onclick={closeNotesModal}>Cancel</button>
      <button class="notes-save" onclick={saveNote}>Save Note</button>
    </div>
  </div>
</Modal>

{#if replayOpen && storeValue.trial}
  <TrajectoryReplay
    experimentId={experiment}
    trialId={trial}
    steps={storeValue.steps}
    stepMessages={storeValue.stepMessages}
    isRlmTrial={storeValue.trial.adapter_type !== "other"}
    reward={storeValue.trial.reward}
    taskId={storeValue.trial.task_id}
    model={storeValue.trial.model}
    tokensIn={storeValue.trial.tokens_in}
    tokensOut={storeValue.trial.tokens_out}
    costUsd={storeValue.trial.cost_usd}
    rlmState={storeValue.rlm}
    onclose={closeReplay}
  />
{/if}

<!-- Keybind help tooltip -->
<div class="keybind-help" title="Keyboard shortcuts">
  <button class="keybind-toggle" onclick={() => { keybindHelpOpen = !keybindHelpOpen; }}>?</button>
  {#if keybindHelpOpen}
    <div class="keybind-panel">
      <div class="keybind-title">Keyboard Shortcuts</div>
      <div class="keybind-row"><kbd>j</kbd> / <kbd>&#8595;</kbd> <span>Next step</span></div>
      <div class="keybind-row"><kbd>k</kbd> / <kbd>&#8593;</kbd> <span>Previous step</span></div>
      <div class="keybind-row"><kbd>1</kbd> <span>Pass</span></div>
      <div class="keybind-row"><kbd>2</kbd> <span>Fail</span></div>
      <div class="keybind-row"><kbd>3</kbd> <span>Defer</span></div>
      <div class="keybind-row"><kbd>n</kbd> <span>Add note</span></div>
      <div class="keybind-row"><kbd>x</kbd> <span>Clear annotation</span></div>
      <div class="keybind-row"><kbd>Esc</kbd> <span>Close modal</span></div>
    </div>
  {/if}
</div>

<style>
  .viewer-layout {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 48px);
    overflow: hidden;
  }

  .viewer-columns {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow-x: auto;
    overflow-y: hidden;
  }

  .col-steps {
    width: 220px;
    min-width: 220px;
    flex-shrink: 0;
    border-right: 1px solid var(--card-border);
    overflow-y: auto;
    height: 100%;
    background: var(--card);
  }

  .col-messages {
    flex: 1;
    min-width: 300px;
    overflow: hidden;
    height: 100%;
    background: var(--bg);
  }

  .col-side {
    width: 280px;
    min-width: 280px;
    flex-shrink: 0;
    border-left: 1px solid var(--card-border);
    overflow-y: auto;
    height: 100%;
    background: var(--card);
  }

  .viewer-loading {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-lg);
    height: 100%;
  }

  .loading-columns {
    display: flex;
    flex: 1;
    gap: var(--space-sm);
  }

  .viewer-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-3);
    text-align: center;
    padding: var(--space-xl);
  }

  .viewer-error h2 {
    margin-bottom: var(--space-sm);
    color: var(--text-2);
  }

  .viewer-error code {
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
  }

  .modal-pre {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 60vh;
    overflow-y: auto;
    background: var(--code-bg);
    color: var(--code-text);
    padding: var(--space-md);
    border-radius: var(--radius-md);
    border: 1px solid var(--code-border);
  }

  /* Responsive breakpoints matching old viewer */
  @media (max-width: 1200px) {
    .viewer-columns {
      flex-direction: column;
      height: auto;
      overflow: visible;
    }

    .col-steps {
      width: 100%;
      min-width: auto;
      max-height: 200px;
      border-right: none;
      border-bottom: 1px solid var(--card-border);
    }

    .col-side {
      width: 100%;
      min-width: auto;
      border-left: none;
      border-top: 1px solid var(--card-border);
    }
  }

  /* Notes modal */
  .notes-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .notes-textarea {
    width: 100%;
    font-family: var(--font-body);
    font-size: 0.9rem;
    padding: var(--space-md);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    background: var(--bg);
    color: var(--text);
    resize: vertical;
  }

  .notes-textarea:focus {
    outline: none;
    border-color: var(--forest);
  }

  .notes-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-sm);
  }

  .notes-cancel, .notes-save {
    font-family: var(--font-body);
    font-size: 0.85rem;
    font-weight: 600;
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-sm);
    cursor: pointer;
    border: none;
    transition: all var(--transition-fast);
  }

  .notes-cancel {
    background: var(--bg-alt);
    color: var(--text-2);
  }

  .notes-cancel:hover { background: var(--card-border); }

  .notes-save {
    background: var(--forest);
    color: white;
  }

  .notes-save:hover { background: var(--forest-hover); }

  /* Keybind help */
  .keybind-help {
    position: fixed;
    bottom: var(--space-md);
    right: var(--space-md);
    z-index: 50;
  }

  .keybind-toggle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 1px solid var(--card-border);
    background: var(--card);
    color: var(--text-2);
    font-weight: 700;
    font-size: 0.85rem;
    cursor: pointer;
    box-shadow: var(--shadow-md);
    transition: all var(--transition-fast);
  }

  .keybind-toggle:hover {
    background: var(--forest);
    color: white;
    border-color: var(--forest);
  }

  .keybind-panel {
    position: absolute;
    bottom: 40px;
    right: 0;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    padding: var(--space-md);
    min-width: 220px;
    animation: slideUp 150ms ease;
  }

  .keybind-title {
    font-family: var(--font-heading);
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: var(--space-sm);
    padding-bottom: var(--space-xs);
    border-bottom: 1px solid var(--card-border);
  }

  .keybind-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 3px 0;
    font-size: 0.8rem;
    color: var(--text-2);
  }

  .keybind-row :global(kbd) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 20px;
    padding: 0 4px;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 700;
    background: var(--bg-alt);
    border: 1px solid var(--card-border);
    border-radius: 3px;
    color: var(--text);
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
