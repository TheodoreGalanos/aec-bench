# ABOUTME: Tests strict canonical serialization for durable pump-station artifacts.
# ABOUTME: Proves complete task records round-trip and malformed stored data fails closed.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from world_run_support import create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationStewardshipState,
    PumpStationWorldRunError,
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_COMMAND_VERSION_V4,
    PUMP_STATION_SERIALIZATION_VERSION,
    PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
    PumpStationCommandV4,
    PumpStationWorldRunCommit,
    PumpStationWorldRunCommitV2,
)


def _actor_command(
    arguments_json: str,
    *,
    session_id: str = "session-v4",
    agent_tenure_id: str = "tenure-v4",
    actor_view_id: str = "view-v4",
    information_set_id: str = "information-v4",
) -> PumpStationCommandV4:
    return PumpStationCommandV4(
        command_version=PUMP_STATION_COMMAND_VERSION_V4,
        kind="actor",
        request_id="request-v4-invalid",
        request_content_id="1" * 64,
        action_name="continue_operation",
        arguments_json=arguments_json,
        task_world_id="wastewater-pump-station-stewardship.v1",
        run_id="run-v4",
        episode_id="episode-v4",
        world_branch_id="branch-v4",
        based_on_sequence=0,
        base_state_id="state-v4-0",
        base_commit_id="commit-v4-0",
        session_id=session_id,
        agent_tenure_id=agent_tenure_id,
        actor_view_id=actor_view_id,
        information_set_id=information_set_id,
    )


def test_complete_state_round_trips_as_canonical_task_owned_json(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")

    payload = pump_station_artifact_bytes(run.state)
    restored = load_pump_station_artifact(
        payload,
        PumpStationStewardshipState,
    )

    assert restored == run.state
    assert pump_station_artifact_bytes(restored) == payload
    assert payload.endswith(b"\n")


def test_stored_state_rejects_unknown_fields_and_types(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    document = json.loads(pump_station_artifact_bytes(run.state))
    document["unexpected"] = "not permitted"

    with pytest.raises(PumpStationWorldRunError, match="artifact-shape"):
        load_pump_station_artifact(
            json.dumps(document).encode(),
            PumpStationStewardshipState,
        )

    document = json.loads(pump_station_artifact_bytes(run.state))
    document["$type"] = "DifferentWorldState"
    with pytest.raises(PumpStationWorldRunError, match="artifact-type"):
        load_pump_station_artifact(
            json.dumps(document).encode(),
            PumpStationStewardshipState,
        )

    document = json.loads(pump_station_artifact_bytes(run.state))
    document["physical"]["pumps"][0]["condition"]["obstruction"] = "NaN"
    with pytest.raises(PumpStationWorldRunError, match="artifact-type"):
        load_pump_station_artifact(
            json.dumps(document).encode(),
            PumpStationStewardshipState,
        )


def test_v4_command_and_commit_round_trip_under_their_own_profile() -> None:
    command = PumpStationCommandV4(
        command_version=PUMP_STATION_COMMAND_VERSION_V4,
        kind="actor",
        request_id="request-v4-001",
        request_content_id="1" * 64,
        action_name="continue_operation",
        arguments_json='{"reason":"Continue to the next event."}',
        task_world_id="wastewater-pump-station-stewardship.v1",
        run_id="run-v4",
        episode_id="episode-v4",
        world_branch_id="branch-v4",
        based_on_sequence=0,
        base_state_id="state-v4-0",
        base_commit_id="commit-v4-0",
        session_id="session-v4",
        agent_tenure_id="tenure-v4",
        actor_view_id="view-v4",
        information_set_id="information-v4",
    )
    commit = PumpStationWorldRunCommitV2(
        serialization_version=PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
        run_id="run-v4",
        sequence=1,
        parent_commit_id="commit-v4-0",
        state_id="state-v4-1",
        request_id=command.request_id,
        command_content_id="2" * 64,
        proposal_content_id="3" * 64,
        information_set_content_id="4" * 64,
        receipt_content_id="5" * 64,
    )

    command_payload = pump_station_artifact_bytes(command)
    commit_payload = pump_station_artifact_bytes(commit)

    assert command_payload == pump_station_artifact_bytes(command, record_profile="v4")
    assert commit_payload == pump_station_artifact_bytes(commit, record_profile="v4")
    assert load_pump_station_artifact(command_payload, PumpStationCommandV4) == command
    assert (
        load_pump_station_artifact(
            commit_payload,
            PumpStationWorldRunCommit | PumpStationWorldRunCommitV2,
        )
        == commit
    )


def test_commit_union_keeps_the_legacy_record_exact() -> None:
    legacy = PumpStationWorldRunCommit(
        serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
        run_id="run-v1",
        sequence=0,
        parent_commit_id=None,
        state_id="state-v1",
        proposal_id=None,
        proposal_content_id=None,
        information_set_content_id=None,
        receipt_content_id=None,
        event_batch_content_id=None,
    )

    payload = pump_station_artifact_bytes(legacy)

    assert (
        load_pump_station_artifact(
            payload,
            PumpStationWorldRunCommit | PumpStationWorldRunCommitV2,
        )
        == legacy
    )


def test_v4_command_rejects_noncanonical_or_duplicate_arguments() -> None:
    with pytest.raises(PumpStationWorldRunError, match="canonical-json"):
        _actor_command('{"reason": "spacing differs"}')
    with pytest.raises(PumpStationWorldRunError, match="duplicate field"):
        _actor_command('{"reason":"one","reason":"two"}')

    for nonstandard_json in (
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
    ):
        with pytest.raises(PumpStationWorldRunError, match="canonical-json"):
            _actor_command(nonstandard_json)


@pytest.mark.parametrize(
    "empty_field",
    (
        "session_id",
        "agent_tenure_id",
        "actor_view_id",
        "information_set_id",
    ),
)
def test_v4_actor_command_rejects_empty_active_binding_fields(
    empty_field: str,
) -> None:
    with pytest.raises(PumpStationWorldRunError, match=empty_field):
        _actor_command(
            '{"reason":"Continue to the next event."}',
            session_id="" if empty_field == "session_id" else "session-v4",
            agent_tenure_id=("" if empty_field == "agent_tenure_id" else "tenure-v4"),
            actor_view_id="" if empty_field == "actor_view_id" else "view-v4",
            information_set_id=("" if empty_field == "information_set_id" else "information-v4"),
        )


def test_v4_control_command_rejects_empty_authority() -> None:
    with pytest.raises(PumpStationWorldRunError, match="authority_id"):
        PumpStationCommandV4(
            command_version=PUMP_STATION_COMMAND_VERSION_V4,
            kind="common_boundary",
            request_id="request-v4-empty-authority",
            request_content_id="1" * 64,
            action_name="common_boundary_control",
            arguments_json='{"available":false}',
            task_world_id="wastewater-pump-station-stewardship.v1",
            run_id="run-v4",
            episode_id="episode-v4",
            world_branch_id="branch-v4",
            based_on_sequence=0,
            base_state_id="state-v4-0",
            base_commit_id="commit-v4-0",
            authority_id="",
        )
