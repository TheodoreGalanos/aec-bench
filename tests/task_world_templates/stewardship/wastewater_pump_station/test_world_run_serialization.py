# ABOUTME: Tests strict canonical serialization for current pump-station artifacts.
# ABOUTME: Proves current records round-trip and malformed stored data fails closed.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCommand,
    PumpStationCommandCommit,
    PumpStationWorldRunCommit,
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)


def _run(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="serialization-run",
        episode_id="serialization-episode",
        world_branch_id="serialization-branch",
    )


def test_current_state_round_trips_as_canonical_task_json(tmp_path: Path) -> None:
    run = _run(tmp_path / "run")
    payload = pump_station_artifact_bytes(run.state)

    restored = load_pump_station_artifact(payload, PumpStationStewardshipState)

    assert restored == run.state
    assert pump_station_artifact_bytes(restored) == payload
    assert payload.endswith(b"\n")


def test_current_state_rejects_unknown_fields_types_and_numbers(tmp_path: Path) -> None:
    run = _run(tmp_path / "run")
    document = json.loads(pump_station_artifact_bytes(run.state))
    document["unexpected"] = "not permitted"
    with pytest.raises(PumpStationWorldRunError, match="artifact-shape"):
        load_pump_station_artifact(json.dumps(document).encode(), PumpStationStewardshipState)

    document = json.loads(pump_station_artifact_bytes(run.state))
    document["$type"] = "DifferentWorldState"
    with pytest.raises(PumpStationWorldRunError, match="artifact-type"):
        load_pump_station_artifact(json.dumps(document).encode(), PumpStationStewardshipState)

    document = json.loads(pump_station_artifact_bytes(run.state))
    document["physical"]["pumps"][0]["condition"]["obstruction"] = "NaN"
    with pytest.raises(PumpStationWorldRunError, match="artifact-type"):
        load_pump_station_artifact(json.dumps(document).encode(), PumpStationStewardshipState)


def test_current_command_and_commit_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _run(root)
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="serialization-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Create current serialization evidence."},
        )
    )
    step = run.repository.command_steps()[0]
    commit = run.repository.commits()[1]
    command_payload = pump_station_artifact_bytes(step.command)
    commit_payload = pump_station_artifact_bytes(commit)

    assert load_pump_station_artifact(command_payload, PumpStationCommand) == step.command
    assert (
        load_pump_station_artifact(
            commit_payload,
            PumpStationWorldRunCommit | PumpStationCommandCommit,
        )
        == commit
    )
