<!-- ABOUTME: Three preset chips above the pivot picker (Evaluate, Compare, Leaderboard). -->
<!-- ABOUTME: Each emits onApply(pivot) with the matching rows/cols/metrics/delta shape. -->
<script lang="ts">
  import type { PivotPatch } from "../lib/stores/analyze.svelte";
  import { EVALUATE_PRESET, COMPARE_PRESET, LEADERBOARD_PRESET } from "./presets";
  import FlaskConical from "lucide-svelte/icons/flask-conical";
  import ArrowLeftRight from "lucide-svelte/icons/arrow-left-right";
  import Trophy from "lucide-svelte/icons/trophy";

  type Props = { onApply: (pivot: PivotPatch) => void };
  let { onApply }: Props = $props();
</script>

<div class="presets">
  <span class="presets-label">Presets:</span>
  <button type="button" onclick={() => onApply(EVALUATE_PRESET)}><FlaskConical size={13} /> Evaluate</button>
  <button type="button" onclick={() => onApply(COMPARE_PRESET)}><ArrowLeftRight size={13} /> Compare</button>
  <button type="button" onclick={() => onApply(LEADERBOARD_PRESET)}><Trophy size={13} /> Leaderboard</button>
</div>

<style>
  .presets {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-lg);
    border-bottom: 1px solid var(--card-border);
  }
  .presets-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-3);
  }
  button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-xs) var(--space-md);
    border: 1px solid var(--card-border);
    border-radius: 999px;
    background: var(--bg-alt);
    font-size: 0.82rem;
    cursor: pointer;
  }
  button:hover {
    background: var(--card);
  }
</style>
