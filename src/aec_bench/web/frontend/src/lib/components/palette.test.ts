// ABOUTME: Tests for the SearchPalette overlay and its open/close state store.
// ABOUTME: Covers store toggle, keybind handling, focus management, and result rendering.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import { paletteStore } from "../stores/palette.svelte";
import SearchPalette from "./SearchPalette.svelte";

describe("paletteStore", () => {
  beforeEach(() => paletteStore.close());

  it("opens and closes", () => {
    expect(paletteStore.isOpen).toBe(false);
    paletteStore.open();
    expect(paletteStore.isOpen).toBe(true);
    paletteStore.close();
    expect(paletteStore.isOpen).toBe(false);
  });

  it("toggles", () => {
    paletteStore.toggle();
    expect(paletteStore.isOpen).toBe(true);
    paletteStore.toggle();
    expect(paletteStore.isOpen).toBe(false);
  });
});

describe("SearchPalette", () => {
  beforeEach(() => paletteStore.close());

  it("renders nothing when closed", () => {
    const { container } = render(SearchPalette);
    expect(container.querySelector(".palette-overlay")).toBeNull();
  });

  it("renders the input when opened", async () => {
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    expect(await screen.findByPlaceholderText(/what are you looking for/i)).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(paletteStore.isOpen).toBe(false);
  });

  it("ignores stale fetchSearch responses (race condition)", async () => {
    const api = await import("../api");
    // Two deferred promises; we control when each resolves.
    let resolveSlow!: (v: unknown) => void;
    let resolveFast!: (v: unknown) => void;
    const slow = new Promise((r) => (resolveSlow = r));
    const fast = new Promise((r) => (resolveFast = r));

    const spy = vi.spyOn(api, "fetchSearch")
      .mockReturnValueOnce(slow as any)
      .mockReturnValueOnce(fast as any);

    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);

    // Fire first (slow) fetch by typing "a".
    await fireEvent.input(input, { target: { value: "a" } });
    // Fire second (fast) fetch by typing "ab" — increments fetchSeq.
    await fireEvent.input(input, { target: { value: "ab" } });

    // Resolve fast first (newer response): it should win and render "new".
    resolveFast({
      query: "ab",
      template_results: [{ task_id: "discipline/new", discipline: "discipline" }],
      dataset_results: [],
      trial_results: [],
      experiment_results: [],
      workspace_results: [],
      total_results: 1,
    });
    // Then resolve slow (older response): it must be discarded by fetchSeq guard.
    resolveSlow({
      query: "a",
      template_results: [{ task_id: "discipline/old", discipline: "discipline" }],
      dataset_results: [],
      trial_results: [],
      experiment_results: [],
      workspace_results: [],
      total_results: 1,
    });

    // Flush microtasks so both .then() callbacks run.
    await new Promise((r) => setTimeout(r, 0));

    // The result list must reflect the NEWER query only.
    expect(screen.getByText("discipline/new")).toBeInTheDocument();
    expect(screen.queryByText("discipline/old")).toBeNull();

    spy.mockRestore();
  });

  it("traps Tab inside the input when palette is open", async () => {
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);
    const tabEvent = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    input.dispatchEvent(tabEvent);
    expect(tabEvent.defaultPrevented).toBe(true);
  });
});

describe("SearchPalette — extended groups", () => {
  beforeEach(() => paletteStore.close());

  it("renders experiment results with /?experiment= drill target", async () => {
    const api = await import("../api");
    const spy = vi.spyOn(api, "fetchSearch").mockResolvedValueOnce({
      query: "alpha",
      template_results: [],
      dataset_results: [],
      trial_results: [],
      experiment_results: [
        { experiment_id: "exp-alpha", trial_count: 2, mean_reward: 0.75 },
      ],
      workspace_results: [],
      total_results: 1,
    });
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);
    await fireEvent.input(input, { target: { value: "alpha" } });

    await screen.findByText(/exp-alpha/);
    const link = screen.getByText(/exp-alpha/).closest(".palette-item") as HTMLElement;
    // Sole result must be the active-descendant (activeIndex defaults to 0).
    expect(link).toHaveAttribute("aria-selected", "true");
    // Label shows n=<count>
    expect(link.textContent).toContain("n=2");

    spy.mockRestore();
  });

  it("renders workspace results with /evolution/ drill target", async () => {
    const api = await import("../api");
    const spy = vi.spyOn(api, "fetchSearch").mockResolvedValueOnce({
      query: "voltage",
      template_results: [],
      dataset_results: [],
      trial_results: [],
      experiment_results: [],
      workspace_results: [
        { name: "voltage-drop-evo", path: "voltage-drop-evo", has_swarm: false },
      ],
      total_results: 1,
    });
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);
    await fireEvent.input(input, { target: { value: "voltage" } });

    await screen.findByText("voltage-drop-evo");
    expect(screen.getByText("Workspace")).toBeInTheDocument();

    spy.mockRestore();
  });

  it("renders trial results with /viewer/ drill target", async () => {
    const api = await import("../api");
    const spy = vi.spyOn(api, "fetchSearch").mockResolvedValueOnce({
      query: "qv",
      template_results: [],
      dataset_results: [],
      trial_results: [
        {
          trial_id: "qv-droop__abc",
          experiment_id: "exp-a",
          task_id: "electrical/qv-droop/easy",
          model: "gpt-4.1-mini",
          reward: 1.0,
        },
      ],
      experiment_results: [],
      workspace_results: [],
      total_results: 1,
    });
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);
    await fireEvent.input(input, { target: { value: "qv" } });

    await screen.findByText(/qv-droop__abc/);
    const text = screen.getByText(/qv-droop__abc/).closest(".palette-item")?.textContent ?? "";
    // Label format: "<trial_id> · <model>"
    expect(text).toContain("qv-droop__abc");
    expect(text).toContain("gpt-4.1-mini");
    // Kind column shows "Trial"
    expect(screen.getByText("Trial")).toBeInTheDocument();

    spy.mockRestore();
  });

  it("renders groups in fixed order: Templates · Datasets · Experiments · Workspaces · Trials", async () => {
    const api = await import("../api");
    const spy = vi.spyOn(api, "fetchSearch").mockResolvedValueOnce({
      query: "a",
      template_results: [{ task_id: "electrical/one", discipline: "electrical", description: "", tags: [], standards: [] }] as any,
      dataset_results: [{ name: "ds-one", version: "1", summary: "", task_count: 0, domains: [] }] as any,
      trial_results: [{ trial_id: "t-one", experiment_id: "exp-a", task_id: "t/a", model: "m", reward: 1.0 }],
      experiment_results: [{ experiment_id: "exp-a", trial_count: 1, mean_reward: 1.0 }],
      workspace_results: [{ name: "ws-one", path: "ws-one", has_swarm: false }],
      total_results: 5,
    });
    render(SearchPalette);
    paletteStore.open();
    await Promise.resolve();
    const input = await screen.findByPlaceholderText(/what are you looking for/i);
    await fireEvent.input(input, { target: { value: "a" } });

    await screen.findByText(/t-one/);

    // Read the rendered kind labels in document order
    const kindElements = Array.from(document.querySelectorAll(".palette-kind"));
    const kinds = kindElements.map((el) => el.textContent?.trim());
    expect(kinds).toEqual(["Template", "Dataset", "Experiment", "Workspace", "Trial"]);

    spy.mockRestore();
  });
});
