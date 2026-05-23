// ABOUTME: Component tests for DetailShell primitive — back link, crumbs, title, subtitle, actions, children.
// ABOUTME: Shared by LibraryDetail, DatasetDetail, ReviewTrial.

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";
import { createRawSnippet } from "svelte";

import DetailShell from "./DetailShell.svelte";

function textSnippet(text: string) {
  return createRawSnippet(() => ({
    render: () => `<span>${text}</span>`,
  }));
}

describe("DetailShell", () => {
  it("renders the back link with the given label and href", () => {
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const back = screen.getByRole("link", { name: /Library/i });
    expect(back).toHaveAttribute("href", "/library");
  });

  it("renders the title as an h1", () => {
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.textContent).toContain("voltage-drop");
  });

  it("renders the subtitle when provided", () => {
    render(DetailShell, {
      props: {
        backHref: "/datasets",
        backLabel: "Datasets",
        title: "voltage-drop-core",
        subtitle: "Baseline electrical benchmark",
        children: textSnippet("page content"),
      },
    });
    expect(screen.getByText("Baseline electrical benchmark")).toBeInTheDocument();
  });

  it("omits the subtitle element when not provided", () => {
    const { container } = render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "t",
        children: textSnippet("page content"),
      },
    });
    expect(container.querySelector(".subtitle")).toBeNull();
  });

  it("renders a single crumb with the / separator", () => {
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        crumbs: [{ label: "electrical" }],
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    expect(screen.getByText("electrical")).toBeInTheDocument();
    // Separator
    expect(screen.getAllByText("/").length).toBeGreaterThanOrEqual(1);
  });

  it("renders a linked crumb when href is provided", () => {
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        crumbs: [{ label: "electrical", href: "/library?discipline=electrical" }],
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const link = screen.getByRole("link", { name: "electrical" });
    expect(link).toHaveAttribute("href", "/library?discipline=electrical");
  });

  it("marks a terminal crumb (no href) with aria-current='page'", () => {
    const { container } = render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        crumbs: [{ label: "electrical" }],
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const current = container.querySelector('[aria-current="page"]');
    expect(current?.textContent).toBe("electrical");
  });

  it("wraps crumbs in <nav aria-label='Breadcrumb'>", () => {
    const { container } = render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "t",
        children: textSnippet("page content"),
      },
    });
    const nav = container.querySelector('nav[aria-label="Breadcrumb"]');
    expect(nav).not.toBeNull();
  });

  it("renders the actions snippet in the top row when provided", () => {
    render(DetailShell, {
      props: {
        backHref: "/datasets",
        backLabel: "Datasets",
        title: "voltage-drop-core",
        actions: textSnippet("v1.0"),
        children: textSnippet("page content"),
      },
    });
    expect(screen.getByText("v1.0")).toBeInTheDocument();
  });

  it("renders the children snippet in .detail-shell-body", () => {
    const { container } = render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "t",
        children: textSnippet("page content"),
      },
    });
    const body = container.querySelector(".detail-shell-body");
    expect(body?.textContent).toContain("page content");
  });

  it("back-link local click preventDefault's and pushes state (SPA nav)", async () => {
    const pushStateSpy = vi.spyOn(window.history, "pushState");
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const back = screen.getByRole("link", { name: /Library/i });
    const clickEvent = new MouseEvent("click", { bubbles: true, cancelable: true });
    back.dispatchEvent(clickEvent);
    expect(clickEvent.defaultPrevented).toBe(true);
    const pushed = pushStateSpy.mock.calls.at(-1)?.[2];
    expect(pushed).toBe("/library");
    pushStateSpy.mockRestore();
  });

  it("back-link modifier click (⌘) does NOT preventDefault (browser handles new tab)", async () => {
    render(DetailShell, {
      props: {
        backHref: "/library",
        backLabel: "Library",
        title: "voltage-drop",
        children: textSnippet("page content"),
      },
    });
    const back = screen.getByRole("link", { name: /Library/i });
    const clickEvent = new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
      metaKey: true,
    });
    back.dispatchEvent(clickEvent);
    expect(clickEvent.defaultPrevented).toBe(false);
  });
});
