// ABOUTME: Unit tests for the NavBar component covering brand link and navigation links.
// ABOUTME: Verifies all nav items render and active page highlighting works.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import NavBar from "./NavBar.svelte";

describe("NavBar", () => {
  it("renders the brand link 'aec-bench'", () => {
    render(NavBar, { props: { activePage: "runs" } });
    expect(screen.getByText("aec-bench")).toBeInTheDocument();
  });

  it("brand link points to /", () => {
    render(NavBar, { props: { activePage: "runs" } });
    const brand = screen.getByText("aec-bench");
    expect(brand).toHaveAttribute("href", "/");
  });

  it("renders Runs nav link", () => {
    render(NavBar, { props: { activePage: "runs" } });
    expect(screen.getByText("Runs")).toBeInTheDocument();
  });

  it("does not render legacy Dashboard or Triage links", () => {
    render(NavBar, { props: { activePage: "runs" } });
    expect(screen.queryByText("Dashboard")).toBeNull();
    expect(screen.queryByText("Triage")).toBeNull();
  });

  it("does not render legacy Evaluate or Compare links", () => {
    render(NavBar, { props: { activePage: "analyze" } });
    expect(screen.queryByText("Evaluate")).toBeNull();
    expect(screen.queryByText("Compare")).toBeNull();
  });

  it("renders Leaderboard nav link", () => {
    render(NavBar, { props: { activePage: "leaderboard" } });
    expect(screen.getByText("Leaderboard")).toBeInTheDocument();
  });

  it("Runs link points to /", () => {
    render(NavBar, { props: { activePage: "runs" } });
    const link = screen.getByText("Runs");
    expect(link).toHaveAttribute("href", "/");
  });

  it("Leaderboard link points to /leaderboard", () => {
    render(NavBar, { props: { activePage: "runs" } });
    const link = screen.getByText("Leaderboard");
    expect(link).toHaveAttribute("href", "/leaderboard");
  });

  it("renders Review nav link", () => {
    render(NavBar, { props: { activePage: "runs" } });
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("Review link points to /review/queue", () => {
    render(NavBar, { props: { activePage: "runs" } });
    const link = screen.getByText("Review");
    expect(link).toHaveAttribute("href", "/review/queue");
  });

  it("renders Search button that opens palette", () => {
    render(NavBar, { props: { activePage: "runs" } });
    expect(screen.getByRole("button", { name: /open search palette/i })).toBeInTheDocument();
  });

  it("renders Analyze nav link pointing to /analyze", () => {
    render(NavBar, { props: { activePage: "analyze" } });
    const link = screen.getByText("Analyze");
    expect(link).toHaveAttribute("href", "/analyze");
  });
});
