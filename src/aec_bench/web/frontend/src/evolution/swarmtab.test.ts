// ABOUTME: Component tests for EvoSwarmTab — swarm mission control panels.
// ABOUTME: Verifies composition; deeper panel behaviour is tested in swarm/*.test.ts.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

vi.mock("../lib/stores/swarm.svelte", () => ({
  swarmStore: {
    state: null,
    connectionStatus: "disconnected",
    selectedAgentId: null,
    setSwarmState: vi.fn(),
    applyEvent: vi.fn(),
    connectSSE: vi.fn(),
    disconnectSSE: vi.fn(),
    resetSwarmStore: vi.fn(),
    initSwarmStore: vi.fn().mockResolvedValue(undefined),
  },
  SwarmStore: class {},
}));

import EvoSwarmTab from "./EvoSwarmTab.svelte";

describe("EvoSwarmTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("renders a loading placeholder when swarm state is null", () => {
    render(EvoSwarmTab, { props: { workspace: "test-ws", active: true } });
    expect(screen.getByText(/connecting|loading|no swarm/i)).toBeInTheDocument();
  });

  it("does not init the store when active=false (lazy)", async () => {
    const mod = await import("../lib/stores/swarm.svelte");
    render(EvoSwarmTab, { props: { workspace: "test-ws", active: false } });
    expect(mod.swarmStore.initSwarmStore).not.toHaveBeenCalled();
  });

  it("inits the store when active=true", async () => {
    const mod = await import("../lib/stores/swarm.svelte");
    render(EvoSwarmTab, { props: { workspace: "test-ws", active: true } });
    // Allow onMount to run
    await new Promise((r) => setTimeout(r, 0));
    expect(mod.swarmStore.initSwarmStore).toHaveBeenCalledWith("test-ws");
  });

  it("re-initialises when the Swarm tab is deactivated and reactivated", async () => {
    const mod = await import("../lib/stores/swarm.svelte");
    // rerender is returned from render() in @testing-library/svelte v5
    const { rerender } = render(EvoSwarmTab, { props: { workspace: "ws-1", active: true } });
    await new Promise((r) => setTimeout(r, 0));
    expect(mod.swarmStore.initSwarmStore).toHaveBeenCalledTimes(1);

    // Deactivate — should reset the store
    await rerender({ workspace: "ws-1", active: false });
    await new Promise((r) => setTimeout(r, 0));
    expect(mod.swarmStore.resetSwarmStore).toHaveBeenCalled();

    // Reactivate — must call init again (regression: initializedFor must reset on deactivate)
    await rerender({ workspace: "ws-1", active: true });
    await new Promise((r) => setTimeout(r, 0));
    expect(mod.swarmStore.initSwarmStore).toHaveBeenCalledTimes(2);
  });
});
