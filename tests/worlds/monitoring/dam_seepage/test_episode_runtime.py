# ABOUTME: Proves the dam seepage episode host preserves actor decisions and exact retries.
# ABOUTME: Keeps task evaluation outside the live actor transition.

from __future__ import annotations

import pytest

from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldInterfaceError,
)
from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.world import SeepageAction, evaluate
from aec_bench.worlds.runtime.episode import EpisodeStatus

_BASE_PROFILE_ID = "synthetic-rising-seepage"


def _profile() -> DamSeepageProfile:
    definition = dam_seepage_world_definition()
    reference = next(profile for profile in definition.profiles if profile.profile_id == _BASE_PROFILE_ID)
    loaded = definition.load_profile(reference)
    assert isinstance(loaded.value, DamSeepageProfile)
    return loaded.value


def _invoke(
    host: DamSeepageEpisodeHost,
    *,
    request_id: str,
    decision_id: str,
    action: SeepageAction,
) -> WorldActorActionResult:
    return host.invoke(
        WorldActorActionRequest(
            request_id=request_id,
            decision_id=decision_id,
            action_name=action.value,
            arguments={},
        )
    )


def test_dam_episode_host_preserves_exact_retry_stale_decision_and_external_evaluation() -> None:
    host = DamSeepageEpisodeHost(profile=_profile())
    catalogue = host.capabilities()
    opening = host.observe()

    assert catalogue.task_world_id == "dam-seepage-monitoring"
    assert {action.name for action in catalogue.actions} == {action.value for action in SeepageAction}
    assert all(action.input_schema["additionalProperties"] is False for action in catalogue.actions)
    assert opening.view["profile_id"] == opening.view["monitoring_point_id"] == "SEEP-WEIR-01"
    assert opening.view["instrument_condition"] is None
    assert "required_response" not in opening.view

    checked_request = WorldActorActionRequest(
        request_id="check-system",
        decision_id=opening.decision_id,
        action_name=SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
        arguments={},
    )
    checked = host.invoke(checked_request)
    assert checked.status == "applied"
    assert host.invoke(checked_request) == checked

    with pytest.raises(WorldInterfaceError, match="actor-request-id-conflict"):
        host.invoke(checked_request.model_copy(update={"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value}))

    stale = _invoke(
        host,
        request_id="stale-reading",
        decision_id=opening.decision_id,
        action=SeepageAction.RECORD_CONFIRMATION_READING,
    )
    assert stale.status == "rejected"
    assert stale.task_receipt["code"] == "decision-stale"

    current = host.observe()
    for index, action in enumerate(
        (
            SeepageAction.RECORD_CONFIRMATION_READING,
            SeepageAction.RECORD_CONFIRMATION_READING,
            SeepageAction.INSPECT_DOWNSTREAM_AREA,
            SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW,
        ),
        start=1,
    ):
        result = _invoke(
            host,
            request_id=f"complete-{index}",
            decision_id=current.decision_id,
            action=action,
        )
        if result.next_observation is not None:
            current = result.next_observation

    assert result.terminated
    assert result.reason == "assessment-submitted"
    assert host.status is EpisodeStatus.TERMINATED
    assert evaluate(host.state).successful
    assert len(host.recorder.steps) == 5
    assert (
        host.invoke(
            WorldActorActionRequest(
                request_id="complete-4",
                decision_id=current.decision_id,
                action_name=SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
                arguments={},
            )
        )
        == result
    )
    with pytest.raises(WorldInterfaceError, match="world-finished"):
        host.observe()
