# ABOUTME: Tests ASW-8 three-pump physical operation, boundaries, and service accounting.
# ABOUTME: Keeps discrete service units separate from pump-local exposure and test operation.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aec_bench.worlds.runtime.world_logic import Transition
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
    transition_coupled_pump_station,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledOperatingInterval,
    PumpStationInputError,
    PumpStationOperatingDelta,
    PumpStationPumpMode,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    create_opening_physical_state,
)


def _delta(pump_id: str, service: int, test: int, cover: str | None = None) -> PumpStationOperatingDelta:
    return PumpStationOperatingDelta(
        pump_id=pump_id,
        service_runtime_seconds=service,
        test_runtime_seconds=test,
        attributed_outage_episode_id=cover,
    )


def test_v2_compiles_three_pump_model_and_exact_opening_state() -> None:
    model = coupled_pump_station_model_from_package(load_reference_package(profile_id=REFERENCE_PROFILE_V2))
    state = create_opening_physical_state()

    assert model.pump_ids == ("pump-a", "pump-b", "pump-c")
    assert model.maximum_running_pumps == 2
    assert state.calendar_seconds == 21_600
    assert state.service_running_pump_ids == ("pump-c",)
    assert state.test_running_pump_ids == ()
    assert state.pump("pump-a").condition.obstruction == Decimal("0.02039999999998400")
    assert state.pump("pump-b").condition.obstruction == Decimal("0.70")
    assert state.pump("pump-c").condition.obstruction == Decimal("0.00015")
    assert state.boundary("pump-a").mode is PumpStationPumpMode.RUN_IN_SERVICE
    assert state.boundary("pump-b").mode is PumpStationPumpMode.ISOLATED_FOR_WORK
    assert state.boundary("pump-c").mode is PumpStationPumpMode.SERVICE_AVAILABLE


def test_peak_interval_accounts_service_and_collateral_per_pump() -> None:
    model = coupled_pump_station_model_from_package(load_reference_package(profile_id=REFERENCE_PROFILE_V2))
    state = replace(create_opening_physical_state(), calendar_seconds=64_800)
    interval = PumpStationCoupledOperatingInterval(
        start_calendar_seconds=64_800,
        end_calendar_seconds=93_600,
        required_service_scu=2,
        baseline_assignment_pump_ids=("pump-a", "pump-b"),
        actual_assignment_pump_ids=("pump-a", "pump-c"),
        service_running_pump_ids=("pump-a", "pump-c"),
        test_running_pump_ids=(),
        pump_deltas=(
            _delta("pump-a", 28_800, 0),
            _delta("pump-b", 0, 0),
            _delta("pump-c", 28_800, 0, "outage-b-001"),
        ),
    )

    result = transition_coupled_pump_station(model, state, interval)
    assert isinstance(result, Transition)

    assert result.state.pump("pump-c").exposure.runtime_seconds == 28_800
    assert result.state.pump("pump-a").exposure.completed_starts == 2
    assert result.state.pump("pump-c").exposure.completed_starts == 1
    assert result.output.pump_delta("pump-c").collateral_runtime_seconds == 28_800


def test_functional_check_adds_exposure_without_service_or_collateral() -> None:
    model = coupled_pump_station_model_from_package(load_reference_package(profile_id=REFERENCE_PROFILE_V2))
    state = replace(
        create_opening_physical_state().with_boundary_mode(
            "pump-b",
            PumpStationPumpMode.TEST_ONLY,
            "clearance-b-complete",
        ),
        calendar_seconds=122_400,
    )
    interval = PumpStationCoupledOperatingInterval(
        start_calendar_seconds=122_400,
        end_calendar_seconds=126_000,
        required_service_scu=1,
        baseline_assignment_pump_ids=("pump-a",),
        actual_assignment_pump_ids=("pump-a",),
        service_running_pump_ids=("pump-a",),
        test_running_pump_ids=("pump-b",),
        pump_deltas=(
            _delta("pump-a", 3_600, 0),
            _delta("pump-b", 0, 3_600),
            _delta("pump-c", 0, 0),
        ),
    )

    result = transition_coupled_pump_station(model, state, interval)
    assert isinstance(result, Transition)

    assert result.state.pump("pump-b").exposure == result.output.pump_delta("pump-b").closing_exposure
    assert result.state.pump("pump-b").exposure.runtime_seconds == 3_600
    assert result.state.pump("pump-b").exposure.completed_starts == 1
    assert result.output.pump_delta("pump-b").collateral_runtime_seconds == 0


def test_three_physically_running_pumps_fail_closed() -> None:
    with pytest.raises(PumpStationInputError) as raised:
        PumpStationCoupledOperatingInterval(
            start_calendar_seconds=21_600,
            end_calendar_seconds=25_200,
            required_service_scu=2,
            baseline_assignment_pump_ids=("pump-a", "pump-b"),
            actual_assignment_pump_ids=("pump-a", "pump-b"),
            service_running_pump_ids=("pump-a", "pump-b"),
            test_running_pump_ids=("pump-c",),
            pump_deltas=(
                _delta("pump-a", 3_600, 0),
                _delta("pump-b", 3_600, 0),
                _delta("pump-c", 0, 3_600),
            ),
        )

    assert raised.value.code == "coupled-operating-interval"
