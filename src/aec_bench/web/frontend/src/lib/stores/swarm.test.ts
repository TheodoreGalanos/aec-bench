// ABOUTME: Tests for the swarm store reactive state management.
// ABOUTME: Verifies event application, budget tracking, state transitions, and selectedAgentId.

import { describe, it, expect, beforeEach } from "vitest";
import { SwarmStore } from "./swarm.svelte";
import type { SwarmState, SwarmEvent } from "../types";

function makeState(overrides?: Partial<SwarmState>): SwarmState {
  return {
    run_id: "abc123",
    workspace: "test",
    status: "active",
    agents: [
      {
        agent_id: "agent-0",
        model: "sonnet-4.6",
        status: "active",
        eval_count: 2,
        best_score: 0.5,
        budget_consumed_usd: 1.0,
        restart_count: 0,
        nudge: "",
      },
    ],
    budget: {
      max_cost_usd: 5.0,
      total_spent_usd: 1.0,
      spend_percentage: 0.2,
      phase: "exploring",
    },
    centroids: [],
    lineage: [],
    notes: [],
    consolidation_reports: [],
    events: [],
    total_evals: 2,
    best_score: 0.5,
    elapsed_seconds: 60.0,
    ...overrides,
  };
}

describe("SwarmStore", () => {
  let store: SwarmStore;

  beforeEach(() => {
    store = new SwarmStore();
  });

  it("starts with null state", () => {
    expect(store.state).toBeNull();
    expect(store.connectionStatus).toBe("disconnected");
    expect(store.selectedAgentId).toBeNull();
  });

  it("setSwarmState loads a snapshot", () => {
    const state = makeState();
    store.setSwarmState(state);
    expect(store.state).toEqual(state);
  });

  it("applyEvent increments eval count for eval_completed", () => {
    store.setSwarmState(makeState());

    const event: SwarmEvent = {
      event_type: "eval_completed",
      timestamp: "2026-04-08T02:21:00Z",
      agent_id: "agent-0",
      payload: { score: 0.9, version: "evo-2" },
      sequence_number: 5,
    };

    store.applyEvent(event);

    const state = store.state!;
    const agent = state.agents.find((a) => a.agent_id === "agent-0");
    expect(agent?.eval_count).toBe(3);
    expect(agent?.best_score).toBe(0.9);
    expect(state.total_evals).toBe(3);
    expect(state.best_score).toBe(0.9);
  });

  it("applyEvent adds event to events list", () => {
    store.setSwarmState(makeState());

    store.applyEvent({
      event_type: "agent_pivoting",
      timestamp: "2026-04-08T02:22:00Z",
      agent_id: "agent-0",
      payload: {},
      sequence_number: 6,
    });

    const state = store.state!;
    expect(state.events.length).toBe(1);
    expect(state.events[0].event_type).toBe("agent_pivoting");
  });

  it("applyEvent updates agent status on retirement", () => {
    store.setSwarmState(makeState());

    store.applyEvent({
      event_type: "agent_retired",
      timestamp: "2026-04-08T02:23:00Z",
      agent_id: "agent-0",
      payload: {},
      sequence_number: 7,
    });

    const state = store.state!;
    expect(state.agents[0].status).toBe("retired");
  });

  it("applyEvent tracks budget_spent", () => {
    store.setSwarmState(makeState());

    store.applyEvent({
      event_type: "budget_spent",
      timestamp: "2026-04-08T02:24:00Z",
      agent_id: "agent-0",
      payload: { cost_usd: 1.5 },
      sequence_number: 8,
    });

    const s = store.state!;
    expect(s.agents[0].budget_consumed_usd).toBe(2.5);
    expect(s.budget.total_spent_usd).toBe(2.5);
    expect(s.budget.spend_percentage).toBeCloseTo(0.5);
  });

  it("applyEvent handles swarm_completed and sets connectionStatus to post-mortem", () => {
    store.setSwarmState(makeState());

    store.applyEvent({
      event_type: "swarm_completed",
      timestamp: "2026-04-08T02:25:00Z",
      agent_id: null,
      payload: {},
      sequence_number: 10,
    });

    expect(store.state?.status).toBe("completed");
    expect(store.connectionStatus).toBe("post-mortem");
  });

  it("resetSwarmStore clears state, connectionStatus, and selectedAgentId", () => {
    store.setSwarmState(makeState());
    store.selectedAgentId = "agent-0";
    store.resetSwarmStore();
    expect(store.state).toBeNull();
    expect(store.connectionStatus).toBe("disconnected");
    expect(store.selectedAgentId).toBeNull();
  });

  it("selectedAgentId can be set and cleared", () => {
    expect(store.selectedAgentId).toBeNull();
    store.selectedAgentId = "agent-42";
    expect(store.selectedAgentId).toBe("agent-42");
    store.selectedAgentId = null;
    expect(store.selectedAgentId).toBeNull();
  });
});
