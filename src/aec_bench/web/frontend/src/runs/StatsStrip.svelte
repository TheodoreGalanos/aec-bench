<!-- ABOUTME: Filter-aware stat pills strip for the Runs page header. -->
<!-- ABOUTME: Pure presentational; parent computes the numbers and passes them in. -->
<script lang="ts">
  import StatPill from "../lib/components/StatPill.svelte";

  type Props = {
    totalExperiments: number;
    totalTrials: number;
    meanReward: number;
    annotatedCount: number;
  };
  let { totalExperiments, totalTrials, meanReward, annotatedCount }: Props = $props();
</script>

<section class="stats-row" aria-label="Filtered statistics">
  <StatPill value={totalExperiments} label="experiments" />
  <StatPill value={totalTrials} label="trials" />
  <StatPill value={Number.isFinite(meanReward) ? meanReward.toFixed(3) : "—"} label="mean reward" />
  <StatPill value={annotatedCount} label="annotated" />
</section>

<style>
  .stats-row {
    display: flex;
    gap: var(--space-md);
    flex-wrap: wrap;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--card-border);
  }
</style>
