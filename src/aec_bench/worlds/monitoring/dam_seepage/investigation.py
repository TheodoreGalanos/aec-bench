# ABOUTME: Loads the authored synthetic investigation scenarios under the dam world owner.
# ABOUTME: Computes a private minimum-cost bound from the task transition and evaluation rules.

from __future__ import annotations

from pathlib import Path

from aec_bench.worlds.monitoring.dam_seepage.world import (
    SeepageScenario,
    SeepageState,
    available_actions,
    evaluate,
    initial_state,
    transition,
)
from aec_bench.worlds.runtime.world_logic import Transition


def investigation_scenarios() -> tuple[SeepageScenario, ...]:
    """Return a matched routine/fault pair and a separate urgent fault case.

    Deadlines and credits are declared experimental constraints, not dam safety limits.
    The matched pair has identical opening observations and different correct responses.
    """
    return tuple(
        SeepageScenario.model_validate_json(Path(__file__).with_name(profile + ".json").read_bytes())
        for profile in ("investigation-routine", "investigation-fault", "investigation-urgent-fault")
    )


def minimum_successful_investigation_cost(scenario: SeepageScenario) -> int | None:
    """Private perfect-information lower bound, not an achievable observation-policy oracle."""
    pending = [initial_state(scenario)]
    seen: set[SeepageState] = set()
    costs: list[int] = []
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        seen.add(state)
        if state.response is not None:
            if evaluate(state).successful:
                costs.append(state.investigation_spent)
            continue
        for action in available_actions(state):
            result = transition(state, action)
            if isinstance(result, Transition):
                pending.append(result.state)
    return min(costs) if costs else None
