<!-- ABOUTME: Thin wrapper around VirtualMessagePane that tracks container width for accurate height prediction. -->
<!-- ABOUTME: Delegates all scroll, render, and observer logic to VirtualMessagePane. -->
<script lang="ts">
  import type { StepSummary, TrajectoryMessage } from "../lib/types";
  import VirtualMessagePane from "./VirtualMessagePane.svelte";

  interface Props {
    steps: StepSummary[];
    activeStep: number;
    stepMessages: Map<number, TrajectoryMessage[]>;
    loading: boolean;
    isRlm: boolean;
    onStepVisible: (stepNum: number) => void;
    openModal: (title: string, content: string) => void;
    scrollToStep?: number;
  }

  let { steps, activeStep, stepMessages, loading, isRlm, onStepVisible, openModal, scrollToStep = -1 }: Props = $props();

  let paneEl: HTMLElement | undefined = $state(undefined);
  let paneWidth = $state(600);

  $effect(() => {
    if (!paneEl) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        paneWidth = entry.contentRect.width;
      }
    });
    ro.observe(paneEl);
    return () => ro.disconnect();
  });
</script>

<div class="message-pane" bind:this={paneEl}>
  <VirtualMessagePane
    {steps}
    {activeStep}
    {stepMessages}
    {loading}
    {isRlm}
    {onStepVisible}
    {openModal}
    {scrollToStep}
    containerWidth={paneWidth}
  />
</div>

<style>
  .message-pane {
    height: 100%;
    overflow: hidden;
  }
</style>
