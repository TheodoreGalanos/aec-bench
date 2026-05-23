// ABOUTME: Unit tests for shared Svelte UI components: Modal, Skeleton, StatPill, RewardBadge, Badge, Card.
// ABOUTME: Uses @testing-library/svelte with jsdom to render components and verify DOM output.

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import Modal from "./Modal.svelte";
import Skeleton from "./Skeleton.svelte";
import StatPill from "./StatPill.svelte";
import RewardBadge from "./RewardBadge.svelte";
import Badge from "./Badge.svelte";
import Card from "./Card.svelte";

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

describe("Modal", () => {
  it("renders title when open is true", () => {
    render(Modal, { props: { open: true, title: "Test Dialog" } });
    expect(screen.getByText("Test Dialog")).toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(Modal, { props: { open: false, title: "Hidden Dialog" } });
    expect(screen.queryByText("Hidden Dialog")).not.toBeInTheDocument();
  });

  it("calls onclose when backdrop is clicked", async () => {
    const onclose = vi.fn();
    render(Modal, { props: { open: true, title: "Closable", onclose } });
    const backdrop = screen.getByTestId("modal-backdrop");
    await fireEvent.click(backdrop);
    expect(onclose).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

describe("Skeleton", () => {
  it("renders with default height", () => {
    const { container } = render(Skeleton, { props: {} });
    const el = container.querySelector(".skeleton") as HTMLElement;
    expect(el).toBeInTheDocument();
    expect(el.style.height).toBe("1rem");
  });

  it("applies custom height and width", () => {
    const { container } = render(Skeleton, { props: { height: "2rem", width: "50%" } });
    const el = container.querySelector(".skeleton") as HTMLElement;
    expect(el.style.height).toBe("2rem");
    expect(el.style.width).toBe("50%");
  });

  it("applies rounded class when rounded prop is true", () => {
    const { container } = render(Skeleton, { props: { rounded: true } });
    expect(container.querySelector(".skeleton.rounded")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// StatPill
// ---------------------------------------------------------------------------

describe("StatPill", () => {
  it("renders the value", () => {
    render(StatPill, { props: { value: 42, label: "Trials" } });
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders the label", () => {
    render(StatPill, { props: { value: 42, label: "Trials" } });
    expect(screen.getByText("Trials")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(StatPill, { props: { value: "0.875", label: "Mean" } });
    expect(screen.getByText("0.875")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// RewardBadge
// ---------------------------------------------------------------------------

describe("RewardBadge", () => {
  it("renders perfect reward as '1.000'", () => {
    render(RewardBadge, { props: { reward: 1.0 } });
    expect(screen.getByText("1.000")).toBeInTheDocument();
  });

  it("applies reward-perfect class for reward >= 1.0", () => {
    const { container } = render(RewardBadge, { props: { reward: 1.0 } });
    expect(container.querySelector(".reward-perfect")).toBeInTheDocument();
  });

  it("applies reward-zero class for reward == 0.0", () => {
    const { container } = render(RewardBadge, { props: { reward: 0.0 } });
    expect(container.querySelector(".reward-zero")).toBeInTheDocument();
  });

  it("applies reward-good class for reward >= 0.8", () => {
    const { container } = render(RewardBadge, { props: { reward: 0.85 } });
    expect(container.querySelector(".reward-good")).toBeInTheDocument();
  });

  it("applies reward-mid class for reward >= 0.5", () => {
    const { container } = render(RewardBadge, { props: { reward: 0.6 } });
    expect(container.querySelector(".reward-mid")).toBeInTheDocument();
  });

  it("applies reward-poor class for reward between 0 and 0.5", () => {
    const { container } = render(RewardBadge, { props: { reward: 0.3 } });
    expect(container.querySelector(".reward-poor")).toBeInTheDocument();
  });

  it("renders three decimal places", () => {
    render(RewardBadge, { props: { reward: 0.756789 } });
    expect(screen.getByText("0.757")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

describe("Badge", () => {
  it("renders the text", () => {
    render(Badge, { props: { text: "electrical" } });
    expect(screen.getByText("electrical")).toBeInTheDocument();
  });

  it("applies badge-rlm class for rlm variant", () => {
    const { container } = render(Badge, { props: { text: "RLM", variant: "rlm" } });
    expect(container.querySelector(".badge-rlm")).toBeInTheDocument();
  });

  it("applies badge-default class when no variant given", () => {
    const { container } = render(Badge, { props: { text: "civil" } });
    expect(container.querySelector(".badge-default")).toBeInTheDocument();
  });

  it("applies badge-model class for model variant", () => {
    const { container } = render(Badge, { props: { text: "gpt-4", variant: "model", colour: "#e4572e" } });
    expect(container.querySelector(".badge-model")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

describe("Card", () => {
  it("renders with .card class", () => {
    const { container } = render(Card, { props: {} });
    expect(container.querySelector(".card")).toBeInTheDocument();
  });

  it("applies hoverable class when hoverable prop is true", () => {
    const { container } = render(Card, { props: { hoverable: true } });
    expect(container.querySelector(".card.hoverable")).toBeInTheDocument();
  });

  it("does not apply hoverable class by default", () => {
    const { container } = render(Card, { props: {} });
    expect(container.querySelector(".card.hoverable")).not.toBeInTheDocument();
  });
});
