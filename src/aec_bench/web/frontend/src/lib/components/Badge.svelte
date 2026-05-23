<!-- ABOUTME: Generic tag badge with variant support for default, RLM, and model types. -->
<!-- ABOUTME: Model variant uses a colour prop with color-mix for accessible background tinting. -->
<script lang="ts">
  export type Variant = "default" | "rlm" | "lambda-rlm" | "model";

  interface Props {
    text: string;
    variant?: Variant;
    colour?: string;
  }

  let { text, variant = "default", colour }: Props = $props();

  let styleAttr = $derived(
    variant === "model" && colour
      ? `--badge-color: ${colour}; background: color-mix(in srgb, ${colour} 15%, transparent); color: ${colour};`
      : ""
  );
</script>

<span
  class="badge badge-{variant}"
  style={styleAttr}
>
  {text}
</span>

<style>
  .badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px var(--space-sm);
    border-radius: 9999px;
    line-height: 1.5;
    white-space: nowrap;
  }

  .badge-default {
    background: var(--bg-alt);
    color: var(--text-2);
    border: 1px solid var(--card-border);
  }

  .badge-rlm {
    background: var(--forest);
    color: #fff;
  }

  /* .badge-model uses inline style from the colour prop */
  .badge-model {
    border: none;
  }

  .badge-lambda-rlm {
    background: color-mix(in srgb, var(--forest) 80%, #7c3aed);
    color: #fff;
  }
</style>
