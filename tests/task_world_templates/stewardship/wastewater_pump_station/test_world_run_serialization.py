# ABOUTME: Tests strict canonical serialization for durable pump-station artifacts.
# ABOUTME: Proves complete task records round-trip and malformed stored data fails closed.

from __future__ import annotations

import json

import pytest
from world_run_support import create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationStewardshipState,
    PumpStationWorldRunError,
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)


def test_complete_state_round_trips_as_canonical_task_owned_json(tmp_path) -> None:
    run = create_world_run(tmp_path / "run")

    payload = pump_station_artifact_bytes(run.state)
    restored = load_pump_station_artifact(
        payload,
        PumpStationStewardshipState,
    )

    assert restored == run.state
    assert pump_station_artifact_bytes(restored) == payload
    assert payload.endswith(b"\n")


def test_stored_state_rejects_unknown_fields_and_types(tmp_path) -> None:
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
