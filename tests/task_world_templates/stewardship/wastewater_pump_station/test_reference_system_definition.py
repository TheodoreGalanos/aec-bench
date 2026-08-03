# ABOUTME: Tests the closed ASW-8 descriptor, artifact binding, and actor interface v2.
# ABOUTME: Proves scenario overrides and unusable temporal capability fail before a run starts.

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
    PUMP_STATION_ACTOR_INTERFACE_VERSION_V2,
    pump_station_actor_capabilities_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldState,
    create_asw_8_world_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationPoolReservation,
    PumpStationPoolReservationStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PumpStationReferenceSystemError,
    bundled_reference_system_root,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationResourceKind,
    PumpStationResourceReservation,
    PumpStationStewardshipState,
    PumpStationWorkResources,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    create_rich_work_reference_state,
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
    assert system.event_schedule["disclosed_through_calendar_seconds"] == 226_800
    assert system.opening_state["calendar_seconds"] == 21_600
    assert system.temporal_template["station_data_profile_id"] == system.station_data_profile_id


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


def test_actor_interface_v2_has_exact_closed_catalogue_and_backlog_binding() -> None:
    catalogue = pump_station_actor_capabilities_v2(
        task_world_id="wastewater-pump-station-stewardship.v1",
        temporal_repository_verified=True,
    )

    assert catalogue.interface_version == PUMP_STATION_ACTOR_INTERFACE_VERSION_V2
    assert tuple(action.name for action in catalogue.actions) == PUMP_STATION_ACTOR_ACTION_NAMES_V2
    assert len(catalogue.actions) == 14
    assert "transfer_duty" not in PUMP_STATION_ACTOR_ACTION_NAMES_V2
    assert "request_conditional_deferral" not in PUMP_STATION_ACTOR_ACTION_NAMES_V2
    assert "transfer_duty" in PUMP_STATION_ACTOR_ACTION_NAMES
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


def test_actor_interface_v2_requires_verified_temporal_repository() -> None:
    with pytest.raises(PumpStationReferenceSystemError) as raised:
        pump_station_actor_capabilities_v2(
            task_world_id="wastewater-pump-station-stewardship.v1",
            temporal_repository_verified=False,
        )
    assert raised.value.code == "temporal-capability"


def test_v4_uses_the_existing_stewardship_state_envelope() -> None:
    state = create_asw_8_world_state()

    assert cast(object, PumpStationCoupledWorldState) is PumpStationStewardshipState
    assert type(cast(object, state)) is PumpStationStewardshipState
    assert state.state_version == "pump-station-stewardship-state.v4"

    with pytest.raises(ValueError, match="version 4 requires resource pools"):
        replace(
            state,
            resources=cast(
                Any,
                PumpStationWorkResources(
                    access_window_seconds=0,
                    repair_kit_available=False,
                    available_intervention_slots=0,
                ),
            ),
        )


def test_state_resource_profiles_reject_every_mixed_form() -> None:
    coupled = create_asw_8_world_state()
    legacy = create_rich_work_reference_state(
        pump_station_model_from_package(load_reference_package()),
    )
    legacy_reservation = PumpStationResourceReservation(
        reservation_id="legacy-access-001",
        kind=PumpStationResourceKind.ACCESS,
        process_id="legacy-process-001",
        created_sequence=0,
    )
    pool_reservation = PumpStationPoolReservation(
        reservation_id="pool-access-001",
        pool_id="field-access-slot",
        quantity=1,
        process_id="pool-process-001",
        target_id="pump-b",
        status=PumpStationPoolReservationStatus.RESERVED,
        created_at_calendar_seconds=coupled.calendar_seconds,
        released_at_calendar_seconds=None,
        retain_on_suspension=False,
        prior_reservation_id=None,
        disposition=None,
    )

    with pytest.raises(ValueError, match="version 4 process or reservation profile differs"):
        replace(
            coupled,
            resource_reservations=cast(Any, (legacy_reservation,)),
        )
    with pytest.raises(ValueError, match="version 1 to 3 requires legacy state records"):
        replace(
            legacy,
            resources=cast(Any, coupled.resources),
        )
    with pytest.raises(ValueError, match="version 1 to 3 requires legacy state records"):
        replace(
            legacy,
            resource_reservations=cast(Any, (pool_reservation,)),
        )
