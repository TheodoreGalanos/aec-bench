// ABOUTME: Svelte 5 runes-based reactive class for the Swarm Mission Control dashboard.
// ABOUTME: Manages state from snapshot + incremental SSE events with connection lifecycle.

import type { SwarmState, SwarmEvent } from "../types";
import { fetchSwarmState } from "../api";

export type ConnectionStatus = "disconnected" | "connecting" | "live" | "post-mortem";

export class SwarmStore {
  state: SwarmState | null = $state(null);
  connectionStatus: ConnectionStatus = $state("disconnected");
  selectedAgentId: string | null = $state(null);

  #eventSource: EventSource | null = null;
  #lastSeq = -1;

  setSwarmState(s: SwarmState): void {
    this.state = s;
    if (s.events.length > 0) {
      this.#lastSeq = Math.max(...s.events.map((e) => e.sequence_number));
    }
  }

  applyEvent(event: SwarmEvent): void {
    const prev = this.state;
    if (!prev) return;

    const state = { ...prev };
    state.events = [...prev.events, event].slice(-20);
    this.#lastSeq = event.sequence_number;

    const aid = event.agent_id;
    if (aid) {
      state.agents = prev.agents.map((a) => {
        if (a.agent_id !== aid) return a;
        const agent = { ...a };
        switch (event.event_type) {
          case "eval_completed":
            agent.eval_count += 1;
            if ((event.payload.score ?? 0) > agent.best_score) {
              agent.best_score = event.payload.score;
            }
            break;
          case "budget_spent":
            agent.budget_consumed_usd += event.payload.cost_usd ?? 0;
            break;
          case "agent_retired":
            agent.status = "retired";
            break;
          case "agent_pivoting":
            agent.status = "pivoting";
            break;
          case "agent_restarted":
            agent.status = "active";
            agent.restart_count += 1;
            break;
        }
        return agent;
      });
    }

    state.total_evals = state.agents.reduce((sum, a) => sum + a.eval_count, 0);
    state.best_score = Math.max(...state.agents.map((a) => a.best_score), 0);
    state.budget = {
      ...prev.budget,
      total_spent_usd: state.agents.reduce((sum, a) => sum + a.budget_consumed_usd, 0),
      spend_percentage:
        prev.budget.max_cost_usd > 0
          ? state.agents.reduce((sum, a) => sum + a.budget_consumed_usd, 0) / prev.budget.max_cost_usd
          : 1.0,
    };

    if (event.event_type === "swarm_completed") {
      state.status = "completed";
      this.connectionStatus = "post-mortem";
    }

    this.state = state;
  }

  connectSSE(workspace: string): void {
    this.disconnectSSE();
    this.connectionStatus = "connecting";

    const url = `/api/evolution/swarm/${workspace}/events/stream`;
    this.#eventSource = new EventSource(url);

    this.#eventSource.onopen = () => {
      this.connectionStatus = "live";
    };

    this.#eventSource.onmessage = (msg) => {
      try {
        const event: SwarmEvent = JSON.parse(msg.data);
        this.applyEvent(event);
      } catch {
        // Ignore malformed events
      }
    };

    this.#eventSource.onerror = () => {
      this.connectionStatus = "connecting";
    };
  }

  disconnectSSE(): void {
    if (this.#eventSource) {
      this.#eventSource.close();
      this.#eventSource = null;
    }
  }

  resetSwarmStore(): void {
    this.disconnectSSE();
    this.state = null;
    this.connectionStatus = "disconnected";
    this.selectedAgentId = null;
    this.#lastSeq = -1;
  }

  async initSwarmStore(workspace: string): Promise<void> {
    const s = await fetchSwarmState(workspace);
    this.setSwarmState(s);

    if (s.status === "active") {
      this.connectSSE(workspace);
    } else {
      this.connectionStatus = "post-mortem";
    }
  }
}

export const swarmStore = new SwarmStore();
