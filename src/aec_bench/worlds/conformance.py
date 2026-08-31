# ABOUTME: Provides reusable conformance checks for task-owned interactive worlds.
# ABOUTME: Keeps world behavior behind explicit callbacks and checks every required world guarantee.

from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition, TransitionResult

REQUIRED_GUARANTEES = frozenset(
    {
        "identity_and_profile_versions",
        "initial_state_serialization",
        "observation_valid_for_state",
        "accepted_transition_returns_new_state",
        "prior_state_not_mutated",
        "rejected_action_preserves_state",
        "terminal_state_rejects_actor_actions",
        "deterministic_replay",
        "recorded_action_order",
        "actor_visible_projection",
        "state_and_observation_size_bounds",
        "task_owned_evaluation",
    }
)


@dataclass(frozen=True, slots=True)
class WorldConformanceScenario:
    """One owner-supplied scenario used by the shared conformance checks."""

    initial_state: Callable[[int], Any]
    observe: Callable[[Any], Any]
    transition: Callable[[Any, Any], TransitionResult[Any, Any]]
    actions: Sequence[Any]
    invalid_action: Any
    assert_observation_safe: Callable[[Any], None]
    assert_state_valid: Callable[[Any], None] | None = None
    round_trip_action: Callable[[Any], Any] | None = None
    round_trip_observation: Callable[[Any], Any] | None = None
    evaluate: Callable[[Any], Any] | None = None
    state_codec: Callable[[Any], bytes] | None = None
    state_decoder: Callable[[bytes], Any] | None = None
    observation_codec: Callable[[Any], bytes] | None = None
    observation_decoder: Callable[[bytes], Any] | None = None
    state_size_bound: int | None = None
    observation_size_bound: int | None = None
    assert_owner_conformance: Callable[[int], None] | None = None


@dataclass(frozen=True, slots=True)
class WorldConformanceCase:
    """One explicit world case exposed to pytest and the installed CLI."""

    world_key: str
    scenario: Callable[[int], WorldConformanceScenario]
    requires_terminal_rejection: bool = False


def world_conformance_case(world_key: str) -> WorldConformanceCase:
    """Resolve one world case from the generated owner descriptors."""

    from aec_bench.worlds.generated_catalogue import WORLD_DESCRIPTORS

    cases = tuple(descriptor.load_conformance_case() for descriptor in WORLD_DESCRIPTORS)
    for loaded in cases:
        if not isinstance(loaded, WorldConformanceCase):
            raise TypeError("world conformance entry point must return WorldConformanceCase")
        case = loaded
        if case.world_key == world_key:
            return case
    known = ", ".join(loaded.world_key for loaded in cases if isinstance(loaded, WorldConformanceCase))
    raise KeyError(f"unknown world conformance key: {world_key}. Known: {known}")


def assert_world_conformance[StateT, ObservationT, ActionT, OutputT, EvaluationT](
    *,
    initial_state: Callable[[int], StateT],
    observe: Callable[[StateT], ObservationT],
    transition: Callable[[StateT, ActionT], TransitionResult[StateT, OutputT]],
    actions: Sequence[ActionT],
    invalid_action: ActionT,
    assert_state_valid: Callable[[StateT], None] | None = None,
    assert_observation_safe: Callable[[ObservationT], None],
    round_trip_action: Callable[[ActionT], ActionT] | None = None,
    round_trip_observation: Callable[[ObservationT], ObservationT] | None = None,
    evaluate: Callable[[StateT], EvaluationT] | None = None,
    state_codec: Callable[[StateT], bytes] | None = None,
    state_decoder: Callable[[bytes], StateT] | None = None,
    observation_codec: Callable[[ObservationT], bytes] | None = None,
    observation_decoder: Callable[[bytes], ObservationT] | None = None,
    state_size_bound: int | None = None,
    observation_size_bound: int | None = None,
    assert_owner_conformance: Callable[[int], None] | None = None,
    require_terminal_rejection: bool = False,
    seed: int = 0,
) -> StateT:
    """Assert deterministic transitions and safe accepted and rejected actions."""

    initial = initial_state(seed)
    repeated_initial = initial_state(seed)
    if assert_state_valid is not None:
        assert_state_valid(initial)
        assert_state_valid(repeated_initial)
    assert initial == repeated_initial

    observation = observe(initial)
    assert observation == observe(repeated_initial)
    assert_observation_safe(observation)
    if state_codec is not None:
        encoded_state = state_codec(initial)
        assert isinstance(encoded_state, bytes)
        if state_decoder is not None:
            assert state_decoder(encoded_state) == initial
        if state_size_bound is not None:
            assert len(encoded_state) <= state_size_bound
    if observation_codec is not None:
        encoded_observation = observation_codec(observation)
        assert isinstance(encoded_observation, bytes)
        if observation_decoder is not None:
            assert observation_decoder(encoded_observation) == observation
        if observation_size_bound is not None:
            assert len(encoded_observation) <= observation_size_bound
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
        prior_first_state = deepcopy(first_state)
        first_result = transition(first_state, selected_action)
        repeated_result = transition(repeated_state, selected_action)
        assert isinstance(first_result, Transition)
        assert isinstance(repeated_result, Transition)
        assert first_result.state != first_state
        assert first_state == prior_first_state
        if assert_state_valid is not None:
            assert_state_valid(first_result.state)
        assert first_result == repeated_result
        first_state = first_result.state
        repeated_state = repeated_result.state
        final_transition = first_result

    assert first_state == repeated_state
    final_observation = observe(first_state)
    assert final_observation == observe(repeated_state)
    assert_observation_safe(final_observation)
    if state_codec is not None:
        encoded_state = state_codec(first_state)
        assert isinstance(encoded_state, bytes)
        if state_decoder is not None:
            assert state_decoder(encoded_state) == first_state
        if state_size_bound is not None:
            assert len(encoded_state) <= state_size_bound
    if observation_codec is not None:
        encoded_observation = observation_codec(final_observation)
        assert isinstance(encoded_observation, bytes)
        if observation_decoder is not None:
            assert observation_decoder(encoded_observation) == final_observation
        if observation_size_bound is not None:
            assert len(encoded_observation) <= observation_size_bound
    if round_trip_observation is not None:
        assert round_trip_observation(final_observation) == final_observation
    if evaluate is not None:
        assert evaluate(first_state) == evaluate(repeated_state)

    if require_terminal_rejection and assert_owner_conformance is None:
        assert final_transition is not None and final_transition.terminated
    if final_transition is not None and final_transition.terminated:
        after_termination = transition(first_state, actions[0])
        assert isinstance(after_termination, ActionRejected)
        assert after_termination.code == "world-terminated"
    if assert_owner_conformance is not None:
        assert_owner_conformance(seed)

    return first_state


def run_world_conformance(case: WorldConformanceCase, *, seed: int = 0) -> dict[str, Any]:
    """Run one explicit case and return a stable CLI result summary."""

    scenario = case.scenario(seed)
    required_callbacks = {
        "assert_state_valid": scenario.assert_state_valid,
        "state_codec": scenario.state_codec,
        "state_decoder": scenario.state_decoder,
        "observation_codec": scenario.observation_codec,
        "observation_decoder": scenario.observation_decoder,
        "assert_owner_conformance": scenario.assert_owner_conformance,
        "evaluate": scenario.evaluate,
    }
    missing = tuple(name for name, callback in required_callbacks.items() if callback is None)
    if missing:
        raise AssertionError(f"world conformance case is missing required proofs: {', '.join(missing)}")
    if scenario.state_size_bound is None or scenario.state_size_bound <= 0:
        raise AssertionError("world conformance case must declare a positive state size bound")
    if scenario.observation_size_bound is None or scenario.observation_size_bound <= 0:
        raise AssertionError("world conformance case must declare a positive observation size bound")
    if not case.requires_terminal_rejection:
        raise AssertionError("world conformance case must require terminal actor-action rejection")
    assert_world_conformance(
        initial_state=scenario.initial_state,
        observe=scenario.observe,
        transition=scenario.transition,
        actions=scenario.actions,
        invalid_action=scenario.invalid_action,
        assert_state_valid=scenario.assert_state_valid,
        assert_observation_safe=scenario.assert_observation_safe,
        round_trip_action=scenario.round_trip_action,
        round_trip_observation=scenario.round_trip_observation,
        evaluate=scenario.evaluate,
        state_codec=scenario.state_codec,
        state_decoder=scenario.state_decoder,
        observation_codec=scenario.observation_codec,
        observation_decoder=scenario.observation_decoder,
        state_size_bound=scenario.state_size_bound,
        observation_size_bound=scenario.observation_size_bound,
        assert_owner_conformance=scenario.assert_owner_conformance,
        require_terminal_rejection=case.requires_terminal_rejection,
        seed=seed,
    )
    proven = [
        "deterministic_initial_state",
        "observation_consistency",
        "valid_observation_projection",
        "observation_valid_for_state",
        "accepted_transition_returns_new_state",
        "prior_state_not_mutated",
        "rejected_action_preserves_state",
        "terminal_state_rejects_actor_actions",
        "deterministic_replay",
        "recorded_action_order",
        "actor_visible_projection",
        "task_owned_evaluation",
    ]
    proven.extend(
        (
            "valid_state",
            "state_serialization",
            "initial_state_serialization",
            "observation_serialization",
            "state_and_observation_size_bounds",
        )
    )
    if scenario.round_trip_action is not None:
        proven.append("action_round_trip")
    if scenario.round_trip_observation is not None:
        proven.append("observation_round_trip")
    return {"world_key": case.world_key, "proven": proven}


__all__ = (
    "WorldConformanceCase",
    "WorldConformanceScenario",
    "REQUIRED_GUARANTEES",
    "assert_world_conformance",
    "run_world_conformance",
    "world_conformance_case",
)
