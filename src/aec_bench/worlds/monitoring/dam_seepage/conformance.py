# ABOUTME: Supplies the dam seepage scenario for the shared world conformance kit.
# ABOUTME: Keeps task-specific actions, projection rules, and evaluation with the dam owner.

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pydantic import TypeAdapter

from aec_bench.worlds.conformance import WorldConformanceCase, WorldConformanceScenario
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile, dam_seepage_world_definition
from aec_bench.worlds.monitoring.dam_seepage.world import (
    SeepageAction,
    SeepageActionResult,
    SeepageObservation,
    SeepageScenario,
    SeepageState,
    evaluate,
    observe,
    transition,
)
from aec_bench.worlds.runtime.episode import (
    ActionSubmission,
    Episode,
    EpisodeFunctions,
    MemoryEpisodeRecorder,
)
from aec_bench.worlds.runtime.world_logic import ActionRejected

_PROFILE_ID = "synthetic-rising-seepage"
_STATE_ADAPTER = TypeAdapter(SeepageState)
_OBSERVATION_ADAPTER = TypeAdapter(SeepageObservation)


def _profile() -> DamSeepageProfile:
    definition = dam_seepage_world_definition()
    reference = next(profile for profile in definition.profiles if profile.profile_id == _PROFILE_ID)
    loaded = definition.load_profile(reference)
    if not isinstance(loaded.value, DamSeepageProfile):
        raise TypeError("dam seepage conformance profile has an unexpected type")
    return loaded.value


def _assert_actor_safe(observation: SeepageObservation) -> None:
    assert not hasattr(observation, "scenario")
    assert not hasattr(observation, "required_response")
    assert 1 <= len(observation.readings) <= 4


def _assert_state_valid(state: SeepageState) -> None:
    assert isinstance(state, SeepageState)
    assert state.scenario.task_world_id == "dam-seepage-monitoring"


def _state_codec(state: SeepageState) -> bytes:
    return _STATE_ADAPTER.dump_json(state)


def _observation_codec(observation: SeepageObservation) -> bytes:
    return _OBSERVATION_ADAPTER.dump_json(observation)


def _state_decoder(encoded: bytes) -> SeepageState:
    return _STATE_ADAPTER.validate_json(encoded)


def _observation_decoder(encoded: bytes) -> SeepageObservation:
    return _OBSERVATION_ADAPTER.validate_json(encoded)


def _actions() -> tuple[SeepageAction, ...]:
    return (
        SeepageAction.CHECK_MEASUREMENT_SYSTEM,
        SeepageAction.INSPECT_DOWNSTREAM_AREA,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.INSPECT_DOWNSTREAM_AREA,
        SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW,
    )


def _opening_state() -> SeepageState:
    profile = _profile()
    return SeepageState(
        scenario=SeepageScenario.model_validate(profile.opening_state.scenario),
        reading_index=profile.opening_state.reading_index,
        measurement_system_checked=profile.opening_state.measurement_system_checked,
        inspected_reading_indexes=profile.opening_state.inspected_reading_indexes,
        response=profile.opening_state.response,
    )


@dataclass(frozen=True, slots=True)
class _RecordedDamEpisode:
    final_state: SeepageState
    recorder: MemoryEpisodeRecorder[SeepageState, SeepageObservation, SeepageAction, SeepageActionResult]


def _record_episode() -> _RecordedDamEpisode:
    recorder: MemoryEpisodeRecorder[SeepageState, SeepageObservation, SeepageAction, SeepageActionResult] = (
        MemoryEpisodeRecorder()
    )
    episode = Episode[SeepageState, SeepageObservation, SeepageAction, SeepageActionResult, object](
        episode_id="dam-conformance-episode",
        actor_id="dam-conformance-actor",
        state=_opening_state(),
        functions=EpisodeFunctions(observe=observe, transition=transition),
        recorder=recorder,
        decision_id_factory=lambda _state, step: f"dam-conformance-decision-{step}",
    )
    for action in _actions():
        decision = episode.current_decision()
        reply = episode.submit(ActionSubmission(decision_id=decision.decision_id, action=action))
        assert reply.accepted
    return _RecordedDamEpisode(final_state=episode.state, recorder=recorder)


def _assert_owner_conformance(_seed: int) -> None:
    first = _record_episode()
    second = _record_episode()
    assert tuple(step.action for step in first.recorder.steps) == _actions()
    assert first.final_state == second.final_state
    assert first.recorder.steps == second.recorder.steps
    rejected = transition(first.final_state, _actions()[0])
    assert isinstance(rejected, ActionRejected)
    assert rejected.code == "world-terminated"
    evaluation = evaluate(first.final_state)
    assert evaluation.assessment_submitted
    assert evaluation.successful


def _scenario(_seed: int) -> WorldConformanceScenario:
    return WorldConformanceScenario(
        initial_state=lambda _seed: _opening_state(),
        observe=observe,
        transition=transition,
        actions=_actions(),
        invalid_action=cast(SeepageAction, "unsupported"),
        assert_observation_safe=_assert_actor_safe,
        assert_state_valid=_assert_state_valid,
        round_trip_action=lambda action: SeepageAction(action.value),
        evaluate=evaluate,
        state_codec=_state_codec,
        state_decoder=_state_decoder,
        observation_codec=_observation_codec,
        observation_decoder=_observation_decoder,
        state_size_bound=20_000,
        observation_size_bound=20_000,
        assert_owner_conformance=_assert_owner_conformance,
    )


WORLD_CONFORMANCE_CASE = WorldConformanceCase(
    world_key="monitoring/dam-seepage",
    scenario=_scenario,
    requires_terminal_rejection=True,
)


def world_conformance_case() -> WorldConformanceCase:
    """Return the maintained dam seepage conformance case."""

    return WORLD_CONFORMANCE_CASE


__all__ = ("WORLD_CONFORMANCE_CASE", "world_conformance_case")
