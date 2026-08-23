# ABOUTME: Proves dam seepage monitoring behavior, actor visibility, and shared World conformance.
# ABOUTME: Checks that poor judgment is evaluated rather than blocked by the live transition.

from __future__ import annotations

from typing import cast

from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DownstreamCondition,
    InstrumentCondition,
    SeepageAction,
    SeepageObservation,
    SeepageResponse,
    available_actions,
    evaluate,
    initial_state,
    observe,
    transition,
)
from aec_bench.worlds.runtime.episode import (
    ActionSubmission,
    Episode,
    EpisodeFunctions,
    EpisodeStatus,
    MemoryEpisodeRecorder,
)
from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition
from tests.worlds.world_conformance import assert_world_conformance


_BASE_PROFILE_ID = "synthetic-rising-seepage"


def _profile() -> DamSeepageProfile:
    definition = dam_seepage_world_definition()
    reference = next(profile for profile in definition.profiles if profile.profile_id == _BASE_PROFILE_ID)
    loaded = definition.load_profile(reference)
    assert isinstance(loaded.value, DamSeepageProfile)
    return loaded.value


def _assert_actor_safe(observation: SeepageObservation) -> None:
    assert not hasattr(observation, "scenario")
    assert not hasattr(observation, "required_response")
    assert 1 <= len(observation.readings) <= 4


def test_dam_seepage_world_conforms_to_shared_behavior() -> None:
    profile = _profile()
    final_state = assert_world_conformance(
        initial_state=lambda _seed: initial_state(profile.scenario),
        observe=observe,
        transition=transition,
        actions=(
            SeepageAction.CHECK_MEASUREMENT_SYSTEM,
            SeepageAction.INSPECT_DOWNSTREAM_AREA,
            SeepageAction.RECORD_CONFIRMATION_READING,
            SeepageAction.RECORD_CONFIRMATION_READING,
            SeepageAction.RECORD_CONFIRMATION_READING,
            SeepageAction.INSPECT_DOWNSTREAM_AREA,
            SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW,
        ),
        invalid_action=cast(SeepageAction, "unsupported"),
        assert_observation_safe=_assert_actor_safe,
        round_trip_action=lambda action: SeepageAction(action.value),
        evaluate=evaluate,
    )

    result = evaluate(final_state)
    assert result.required_response is SeepageResponse.ENGINEERING_REVIEW
    assert result.evidence_complete
    assert result.successful


def test_observation_reveals_only_requested_monitoring_evidence() -> None:
    state = _profile().opening_state
    opening = observe(state)

    assert len(opening.readings) == 1
    assert opening.readings[0].downstream_condition is None
    assert opening.instrument_condition is None
    assert opening.scheduled_readings_remaining == 3

    checked = transition(state, SeepageAction.CHECK_MEASUREMENT_SYSTEM)
    assert isinstance(checked, Transition)
    checked_view = observe(checked.state)
    assert checked_view.instrument_condition is InstrumentCondition.SERVICEABLE
    assert len(checked_view.readings) == 1

    advanced = transition(checked.state, SeepageAction.RECORD_CONFIRMATION_READING)
    assert isinstance(advanced, Transition)
    assert len(observe(advanced.state).readings) == 2

    inspected = transition(advanced.state, SeepageAction.INSPECT_DOWNSTREAM_AREA)
    assert isinstance(inspected, Transition)
    inspected_view = observe(inspected.state)
    assert inspected_view.readings[0].downstream_condition is None
    assert inspected_view.readings[1].downstream_condition is DownstreamCondition.CLEAR


def test_world_accepts_judgment_then_evaluation_checks_it() -> None:
    state = _profile().opening_state
    for _ in range(3):
        advanced = transition(state, SeepageAction.RECORD_CONFIRMATION_READING)
        assert isinstance(advanced, Transition)
        state = advanced.state
    checked = transition(state, SeepageAction.CHECK_MEASUREMENT_SYSTEM)
    assert isinstance(checked, Transition)
    inspected = transition(checked.state, SeepageAction.INSPECT_DOWNSTREAM_AREA)
    assert isinstance(inspected, Transition)

    submitted = transition(inspected.state, SeepageAction.CONTINUE_ROUTINE_SURVEILLANCE)

    assert isinstance(submitted, Transition)
    assert submitted.terminated
    result = evaluate(submitted.state)
    assert result.evidence_complete
    assert not result.response_correct
    assert not result.successful


def test_supported_escalation_does_not_require_waiting_for_later_reading() -> None:
    state = _profile().opening_state
    for _ in range(2):
        advanced = transition(state, SeepageAction.RECORD_CONFIRMATION_READING)
        assert isinstance(advanced, Transition)
        state = advanced.state
    inspected = transition(state, SeepageAction.INSPECT_DOWNSTREAM_AREA)
    assert isinstance(inspected, Transition)
    assert observe(inspected.state).readings[-1].downstream_condition is DownstreamCondition.CLOUDY

    submitted = transition(inspected.state, SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW)

    assert isinstance(submitted, Transition)
    result = evaluate(submitted.state)
    assert not result.all_scheduled_readings_reviewed
    assert result.evidence_complete
    assert result.successful


def test_unavailable_actions_are_rejected_without_state_change() -> None:
    state = _profile().opening_state
    checked = transition(state, SeepageAction.CHECK_MEASUREMENT_SYSTEM)
    assert isinstance(checked, Transition)

    repeated = transition(checked.state, SeepageAction.CHECK_MEASUREMENT_SYSTEM)

    assert repeated == ActionRejected("action-unavailable", "the measurement system was already checked")
    assert observe(checked.state).instrument_condition is InstrumentCondition.SERVICEABLE


def test_dam_seepage_world_runs_through_shared_episode_shell() -> None:
    profile = _profile()
    recorder = MemoryEpisodeRecorder()
    episode = Episode(
        episode_id="seepage-episode",
        actor_id="monitoring-engineer",
        state=profile.opening_state,
        functions=EpisodeFunctions(
            observe=observe,
            transition=transition,
            available_actions=available_actions,
        ),
        recorder=recorder,
        decision_id_factory=lambda _state, step: f"decision-{step}",
    )
    actions = (
        SeepageAction.CHECK_MEASUREMENT_SYSTEM,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.RECORD_CONFIRMATION_READING,
        SeepageAction.INSPECT_DOWNSTREAM_AREA,
        SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW,
    )

    for action in actions:
        decision = episode.current_decision()
        assert action in decision.available_actions
        reply = episode.submit(ActionSubmission(decision_id=decision.decision_id, action=action))
        assert reply.accepted

    assert episode.status is EpisodeStatus.TERMINATED
    assert len(recorder.steps) == len(actions)
    assert recorder.finished is not None
    assert evaluate(episode.state).successful
