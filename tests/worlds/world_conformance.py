# ABOUTME: Provides reusable behavioral assertions for real interactive-world functions.
# ABOUTME: Keeps task actions, observations, codecs, and evaluation behind explicit callbacks.

from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy

from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition, TransitionResult


def assert_world_conformance[StateT, ObservationT, ActionT, OutputT, EvaluationT](
    *,
    initial_state: Callable[[int], StateT],
    observe: Callable[[StateT], ObservationT],
    transition: Callable[[StateT, ActionT], TransitionResult[StateT, OutputT]],
    actions: Sequence[ActionT],
    invalid_action: ActionT,
    assert_observation_safe: Callable[[ObservationT], None],
    round_trip_action: Callable[[ActionT], ActionT] | None = None,
    round_trip_observation: Callable[[ObservationT], ObservationT] | None = None,
    evaluate: Callable[[StateT], EvaluationT] | None = None,
    seed: int = 0,
) -> StateT:
    """Assert shared semantics without imposing a production class hierarchy."""
    initial = initial_state(seed)
    repeated_initial = initial_state(seed)
    assert initial == repeated_initial

    observation = observe(initial)
    assert observation == observe(repeated_initial)
    assert_observation_safe(observation)
    if round_trip_observation is not None:
        assert round_trip_observation(observation) == observation

    state_before_rejection = deepcopy(initial)
    rejection = transition(initial, invalid_action)
    assert isinstance(rejection, ActionRejected)
    assert initial == state_before_rejection
    observation_after_rejection = observe(initial)
    assert observation_after_rejection == observation
    assert_observation_safe(observation_after_rejection)

    first_state = initial
    repeated_state = repeated_initial
    final_transition: Transition[StateT, OutputT] | None = None
    for action in actions:
        selected_action = round_trip_action(action) if round_trip_action is not None else action
        assert selected_action == action
        first_result = transition(first_state, selected_action)
        repeated_result = transition(repeated_state, selected_action)
        assert isinstance(first_result, Transition)
        assert isinstance(repeated_result, Transition)
        assert first_result == repeated_result
        first_state = first_result.state
        repeated_state = repeated_result.state
        final_transition = first_result

    assert first_state == repeated_state
    final_observation = observe(first_state)
    assert final_observation == observe(repeated_state)
    assert_observation_safe(final_observation)
    if round_trip_observation is not None:
        assert round_trip_observation(final_observation) == final_observation
    if evaluate is not None:
        assert evaluate(first_state) == evaluate(repeated_state)

    if final_transition is not None and final_transition.terminated:
        after_termination = transition(first_state, actions[0])
        assert isinstance(after_termination, ActionRejected)
        assert after_termination.code == "world-terminated"

    return first_state
