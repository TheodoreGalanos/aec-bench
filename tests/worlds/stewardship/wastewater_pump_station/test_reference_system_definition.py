# ABOUTME: Tests the closed ASW-8 descriptor, artifact binding, and current actor interface.
# ABOUTME: Proves scenario overrides and unusable temporal capability fail before a run starts.

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
    pump_station_actor_capabilities,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationAvailabilityInterval,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
    PumpStationReferenceSystemError,
    bundled_reference_system_root,
    list_reference_system_ids,
    load_reference_system,
)


def test_registered_reference_system_binds_exact_artifacts_and_versions() -> None:
    system = load_reference_system()

    assert system.descriptor_id == PUMP_STATION_REFERENCE_SYSTEM_ID
    assert system.station_data_profile_id == "AU-NSW-LH-SYN-SPS-v2"
    assert system.descriptor["record_versions"] == {
        "authority_policy": "pump-station-authority-policy.v4",
        "receipt": "pump-station-transition-receipt.v4",
        "snapshot": "pump-station-state-snapshot.v4",
        "state": "pump-station-stewardship-state.v4",
        "transition_rules": "pump-station-transition-rules.v4",
        "world_manifest": "pump-station-world-run.v2",
    }
    assert list_reference_system_ids() == (
        PUMP_STATION_REFERENCE_SYSTEM_ID,
        PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
    )
    assert system.event_schedule.disclosed_through_calendar_seconds == 226_800
    assert system.opening_state["calendar_seconds"] == 21_600
    assert system.temporal_template["station_data_profile_id"] == system.station_data_profile_id


def test_rs2_changes_only_the_declared_maintenance_window_conditions() -> None:
    rs1 = load_reference_system()
    rs2 = load_reference_system(reference_system_id=PUMP_STATION_REFERENCE_SYSTEM_RS2_ID)

    assert rs2.event_schedule.resource_windows == (
        PumpStationAvailabilityInterval(21_600, 61_200),
        PumpStationAvailabilityInterval(108_000, 144_000),
        PumpStationAvailabilityInterval(165_600, 226_800),
    )
    assert rs1.event_schedule.service_requirements == rs2.event_schedule.service_requirements
    assert rs1.event_schedule.baseline_assignments == rs2.event_schedule.baseline_assignments
    assert rs1.station_data_profile_id == rs2.station_data_profile_id
    assert rs1.opening_state["pumps"] == rs2.opening_state["pumps"]
    assert rs1.opening_state["environment"] == rs2.opening_state["environment"]
    assert rs1.opening_state["backlog"] == rs2.opening_state["backlog"]
    assert rs1.temporal_template["documents"] == rs2.temporal_template["documents"]
    for field_name in (
        "actor_interface_version",
        "actor_observation_schema",
        "actor_projection_policy",
        "information_boundary",
        "evaluation_version",
        "verification_version",
    ):
        assert rs1.descriptor[field_name] == rs2.descriptor[field_name]


def test_unknown_reference_system_or_changed_artifact_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(PumpStationReferenceSystemError) as unknown:
        load_reference_system(reference_system_id="pump-station-reference-system.unknown.v1")
    assert unknown.value.code == "unknown-reference-system"

    root = Path(shutil.copytree(bundled_reference_system_root(), tmp_path / "reference-system"))
    schedule_path = root / "event-schedule.json"
    schedule_path.write_bytes(schedule_path.read_bytes().replace(b"226800", b"226801"))
    with pytest.raises(PumpStationReferenceSystemError) as changed:
        load_reference_system(root=root)
    assert changed.value.code == "reference-system-content-drift"


def test_actor_interface_has_exact_closed_catalogue_and_backlog_binding() -> None:
    catalogue = pump_station_actor_capabilities(
        task_world_id="wastewater-pump-station-stewardship.v1",
        temporal_repository_verified=True,
    )

    assert tuple(action.name for action in catalogue.actions) == PUMP_STATION_ACTOR_ACTION_NAMES
    assert len(catalogue.actions) == 14
    assert "transfer_duty" not in PUMP_STATION_ACTOR_ACTION_NAMES
    assert "request_conditional_deferral" not in PUMP_STATION_ACTOR_ACTION_NAMES
    assert "request_duty_assignment" in PUMP_STATION_ACTOR_ACTION_NAMES
    work_starts = {
        "request_inspection",
        "request_obstruction_clearance",
        "request_functional_check",
        "request_post_maintenance_verification",
    }
    for action in catalogue.actions:
        if action.name in work_starts:
            required = action.input_schema["required"]
            assert isinstance(required, list)
            assert "backlog_item_id" in required


def test_actor_interface_requires_verified_temporal_repository() -> None:
    with pytest.raises(PumpStationReferenceSystemError) as raised:
        pump_station_actor_capabilities(
            task_world_id="wastewater-pump-station-stewardship.v1",
            temporal_repository_verified=False,
        )
    assert raised.value.code == "temporal-capability"
