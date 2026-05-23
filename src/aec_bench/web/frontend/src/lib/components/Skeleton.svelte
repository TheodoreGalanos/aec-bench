<!-- ABOUTME: Loading placeholder with CSS shimmer animation for content while fetching. -->
<!-- ABOUTME: Accepts height, width, and rounded props for flexible usage. -->
<script lang="ts">
  interface Props {
    height?: string;
    width?: string;
    rounded?: boolean;
  }

  let { height = "1rem", width = "100%", rounded = false }: Props = $props();
</script>

<div
  class="skeleton"
  class:rounded
  style:height
  style:width
  role="status"
  aria-label="Loading"
></div>

<style>
  .skeleton {
    background: linear-gradient(
      90deg,
      var(--bg-alt) 25%,
      var(--card-border) 50%,
      var(--bg-alt) 75%
    );
    background-size: 200% 100%;
    border-radius: var(--radius-sm);
    animation: shimmer 1.4s infinite;
  }

  .skeleton.rounded {
    border-radius: 9999px;
  }

  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
</style>
