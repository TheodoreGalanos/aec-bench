<!-- ABOUTME: Colour-coded badge for displaying reward scores with threshold-based styling. -->
<!-- ABOUTME: Maps reward values to reward CSS variables for consistent visual encoding. -->
<script lang="ts">
  type RewardClass = "reward-perfect" | "reward-good" | "reward-mid" | "reward-poor" | "reward-zero";
  type Size = "sm" | "md";

  interface Props {
    reward: number;
    size?: Size;
  }

  let { reward, size = "md" }: Props = $props();

  function getRewardClass(r: number): RewardClass {
    if (r >= 1.0) return "reward-perfect";
    if (r >= 0.8) return "reward-good";
    if (r >= 0.5) return "reward-mid";
    if (r <= 0.0) return "reward-zero";
    return "reward-poor";
  }

  let rewardClass = $derived(getRewardClass(reward));
</script>

<span class="reward-badge {rewardClass} size-{size}">
  {reward.toFixed(3)}
</span>

<style>
  .reward-badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-weight: 700;
    border-radius: var(--radius-sm);
    letter-spacing: 0.02em;
  }

  .size-md {
    font-size: 0.875rem;
    padding: 2px var(--space-sm);
  }

  .size-sm {
    font-size: 0.75rem;
    padding: 1px var(--space-xs);
  }

  .reward-perfect {
    color: var(--reward-perfect);
    background: var(--reward-perfect-bg);
  }

  .reward-good {
    color: var(--reward-good);
    background: var(--reward-good-bg);
  }

  .reward-mid {
    color: var(--reward-mid);
    background: var(--reward-mid-bg);
  }

  .reward-poor {
    color: var(--reward-poor);
    background: var(--reward-poor-bg);
  }

  .reward-zero {
    color: var(--reward-zero);
    background: var(--reward-zero-bg);
  }
</style>
