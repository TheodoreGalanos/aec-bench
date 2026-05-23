<!-- ABOUTME: Shared header primitive for non-full-viewport detail pages. -->
<!-- ABOUTME: Renders back link + optional breadcrumbs + title + subtitle + actions + children. -->
<script lang="ts">
  import { ChevronLeft } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface Crumb {
    label: string;
    href?: string;
  }

  interface Props {
    backHref: string;
    backLabel: string;
    crumbs?: Crumb[];
    title: string;
    subtitle?: string;
    actions?: Snippet;
    children: Snippet;
  }

  let {
    backHref,
    backLabel,
    crumbs,
    title,
    subtitle,
    actions,
    children,
  }: Props = $props();

  // SPA-navigate on local click; let browser handle modifier + middle clicks.
  // Matches the project-wide pattern used by RailItem and the other back-link call-sites.
  function handleNavClick(e: MouseEvent, href: string) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    window.history.pushState({}, "", href);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
</script>

<header class="detail-shell-header">
  <nav class="crumbs" aria-label="Breadcrumb">
    <a class="back" href={backHref} onclick={(e) => handleNavClick(e, backHref)}>
      <ChevronLeft size={14} aria-hidden="true" />
      <span>{backLabel}</span>
    </a>
    {#each crumbs ?? [] as c (c.href ?? c.label)}
      <span class="crumb-sep" aria-hidden="true">/</span>
      {#if c.href}
        <a class="crumb" href={c.href} onclick={(e) => handleNavClick(e, c.href!)}>{c.label}</a>
      {:else}
        <span class="crumb crumb-current" aria-current="page">{c.label}</span>
      {/if}
    {/each}
  </nav>

  <div class="title-row">
    <h1 class="title">{title}</h1>
    {#if actions}
      <div class="actions">{@render actions()}</div>
    {/if}
  </div>

  {#if subtitle}
    <p class="subtitle">{subtitle}</p>
  {/if}
</header>

<div class="detail-shell-body">
  {@render children()}
</div>

<style>
  .detail-shell-header {
    margin-bottom: var(--space-lg);
  }

  .crumbs {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    flex-wrap: wrap;
    font-size: 0.82rem;
    color: var(--text-3);
    margin-bottom: var(--space-sm);
  }

  .back {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--forest);
    text-decoration: none;
    font-weight: 500;
  }
  .back:hover {
    text-decoration: underline;
  }
  .back:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .crumb-sep {
    color: var(--text-3);
    user-select: none;
  }

  .crumb {
    color: var(--text-2);
    text-decoration: none;
  }
  .crumb:hover {
    color: var(--text);
    text-decoration: underline;
  }
  .crumb:focus-visible {
    outline: 2px solid var(--forest);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .crumb-current {
    color: var(--text);
    font-weight: 500;
  }

  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    flex-wrap: wrap;
  }

  .title {
    font-family: var(--font-heading);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
    word-break: break-word;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .subtitle {
    font-size: 0.95rem;
    color: var(--text-2);
    margin: var(--space-xs) 0 0 0;
  }

  .detail-shell-body {
    display: block;
  }
</style>
