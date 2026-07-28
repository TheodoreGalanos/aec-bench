# ABOUTME: Unit-tests deterministic wastewater pump-station state changes and observations.
# ABOUTME: Covers independent clocks, degradation, duty transfer, resources, and interventions.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ClearanceFinding,
    ObstructionFinding,
    OperatingInterval,
    PumpCondition,
    PumpIntervention,
    PumpInterventionKind,
    PumpStationChangeKind,
    PumpStationEnvironment,
    PumpStationInputError,
    PumpStationModel,
    PumpStationResources,
    PumpStationState,
    advance_pump_station,
    apply_pump_intervention,
    assess_pump_station,
    initial_pump_station_state,
    inspect_pump,
    load_reference_package,
    pump_station_model_from_package,
    transfer_duty_to_standby,
)


def _model_and_state() -> tuple[PumpStationModel, PumpStationState]:
    model = pump_station_model_from_package(load_reference_package())
    return model, initial_pump_station_state(model)


def _assessment_environment(*, isolated: bool = False) -> PumpStationEnvironment:
    return PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=isolated,
    )


def test_operating_interval_advances_distinct_clocks_and_latent_condition() -> None:
    model, state = _model_and_state()

    result = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=3_600_000,
            duty_runtime_seconds=3_600_000,
            duty_completed_starts=500,
            environment=_assessment_environment(),
        ),
    )

    pump_a = result.state.pump("pump-a")
    pump_b = result.state.pump("pump-b")
    assert result.state.calendar_seconds == 3_600_000
    assert result.previous_state == state
    assert result.change_kind is PumpStationChangeKind.OPERATING_INTERVAL
    assert pump_a.exposure.runtime_seconds == 3_600_000
    assert pump_a.exposure.completed_starts == 500
    assert pump_a.condition == PumpCondition(
        obstruction=Decimal("0.32499999998400000"),
        clearance_loss=Decimal("0.11999999998800000"),
    )
    assert pump_b.exposure.runtime_seconds == 0
    assert pump_b.exposure.completed_starts == 0
    assert pump_b.condition == PumpCondition.clean()
    assert result.capability.review_required is False
    assert result.capability.operating_flow_m3_s == pytest.approx(
        0.02339426856122102,
        abs=1e-15,
    )


def test_isolation_advances_calendar_without_pump_exposure() -> None:
    model, state = _model_and_state()

    result = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=86_400,
            duty_runtime_seconds=0,
            duty_completed_starts=0,
            environment=_assessment_environment(isolated=True),
        ),
    )

    assert result.state.calendar_seconds == 86_400
    assert result.state.pumps == state.pumps
    assert result.observation.active_pump_flow_m3_s == Decimal("0.0000")
    assert result.observation.runtime_meter_seconds == 0
    assert result.hydraulic_balance.inflow_m3_s == pytest.approx(0.0155)
    assert result.hydraulic_balance.pump_flow_m3_s == 0.0
    assert result.hydraulic_balance.net_wet_well_inflow_m3_s == pytest.approx(0.0155)


def test_duty_transfer_preserves_prior_exposure_and_moves_future_exposure() -> None:
    model, state = _model_and_state()
    pump_a_result = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=60,
            duty_runtime_seconds=60,
            duty_completed_starts=1,
            environment=_assessment_environment(),
        ),
    )

    transferred = transfer_duty_to_standby(
        model,
        pump_a_result.state,
        _assessment_environment(),
    )
    pump_b_result = advance_pump_station(
        model,
        transferred.state,
        OperatingInterval(
            elapsed_seconds=120,
            duty_runtime_seconds=120,
            duty_completed_starts=1,
            environment=_assessment_environment(),
        ),
    )

    assert pump_b_result.state.duty_pump_id == "pump-b"
    assert transferred.previous_state == pump_a_result.state
    assert transferred.change_kind is PumpStationChangeKind.DUTY_TRANSFER
    assert pump_b_result.state.standby_pump_id == "pump-a"
    assert pump_b_result.state.duty_transfer_count == 1
    assert pump_b_result.state.pump("pump-a") == pump_a_result.state.pump("pump-a")
    assert pump_b_result.state.pump("pump-b").exposure.runtime_seconds == 120
    assert pump_b_result.state.pump("pump-b").exposure.completed_starts == 1
    with pytest.raises(PumpStationInputError, match="duty-transfer-limit"):
        transfer_duty_to_standby(
            model,
            pump_b_result.state,
            _assessment_environment(),
        )


@pytest.mark.parametrize(
    ("kind", "before", "after"),
    [
        (
            PumpInterventionKind.CLEAR_OBSTRUCTION,
            PumpCondition(
                obstruction=Decimal("0.65"),
                clearance_loss=Decimal("0.10"),
            ),
            PumpCondition(
                obstruction=Decimal("0.0975"),
                clearance_loss=Decimal("0.10"),
            ),
        ),
        (
            PumpInterventionKind.REPAIR_CLEARANCE,
            PumpCondition(
                obstruction=Decimal("0.50"),
                clearance_loss=Decimal("0.50"),
            ),
            PumpCondition(
                obstruction=Decimal("0.50"),
                clearance_loss=Decimal("0.0500"),
            ),
        ),
    ],
)
def test_intervention_changes_only_its_target_mechanism(
    kind: PumpInterventionKind,
    before: PumpCondition,
    after: PumpCondition,
) -> None:
    model, state = _model_and_state()
    pump_a = replace(
        state.pump("pump-a"),
        condition=before,
    )
    state = state.with_pump(pump_a)
    resources = PumpStationResources(
        access_window_seconds=14_400,
        repair_kit_available=True,
        available_intervention_slots=1,
    )

    result = apply_pump_intervention(
        model,
        state,
        PumpIntervention(kind=kind, pump_id="pump-a"),
        resources,
        _assessment_environment(),
    )

    assert result.state.pump("pump-a").condition == after
    assert result.previous_state == state
    assert result.change_kind is (
        PumpStationChangeKind.CLEAR_OBSTRUCTION
        if kind is PumpInterventionKind.CLEAR_OBSTRUCTION
        else PumpStationChangeKind.REPAIR_CLEARANCE
    )
    assert result.state.pump("pump-a").exposure == state.pump("pump-a").exposure
    assert result.state.calendar_seconds == state.calendar_seconds
    assert result.state.pump("pump-b") == state.pump("pump-b")


def test_clearance_repair_requires_access_kit_and_one_available_slot() -> None:
    model, state = _model_and_state()
    intervention = PumpIntervention(
        kind=PumpInterventionKind.REPAIR_CLEARANCE,
        pump_id="pump-a",
    )
    insufficient_resources = (
        PumpStationResources(
            access_window_seconds=0,
            repair_kit_available=True,
            available_intervention_slots=1,
        ),
        PumpStationResources(
            access_window_seconds=14_400,
            repair_kit_available=False,
            available_intervention_slots=1,
        ),
        PumpStationResources(
            access_window_seconds=14_400,
            repair_kit_available=True,
            available_intervention_slots=0,
        ),
    )

    for resources in insufficient_resources:
        with pytest.raises(PumpStationInputError, match="intervention-resources"):
            apply_pump_intervention(
                model,
                state,
                intervention,
                resources,
                _assessment_environment(),
            )

    assert state == initial_pump_station_state(model)


def test_interval_rejects_exposure_that_cannot_occur() -> None:
    environment = _assessment_environment(isolated=True)

    with pytest.raises(PumpStationInputError, match="operating-interval"):
        OperatingInterval(
            elapsed_seconds=60,
            duty_runtime_seconds=60,
            duty_completed_starts=1,
            environment=environment,
        )


def test_environment_inflow_changes_the_physical_hydraulic_balance() -> None:
    model, state = _model_and_state()
    lower_inflow = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=60,
            duty_runtime_seconds=60,
            duty_completed_starts=1,
            environment=PumpStationEnvironment(
                inflow_m3_s=Decimal("0.0050"),
                wet_well_level_m=Decimal("1.65"),
                isolated=False,
            ),
        ),
    )
    higher_inflow = advance_pump_station(
        model,
        state,
        OperatingInterval(
            elapsed_seconds=60,
            duty_runtime_seconds=60,
            duty_completed_starts=1,
            environment=PumpStationEnvironment(
                inflow_m3_s=Decimal("0.0090"),
                wet_well_level_m=Decimal("1.65"),
                isolated=False,
            ),
        ),
    )

    assert lower_inflow.hydraulic_balance.pump_flow_m3_s == (higher_inflow.hydraulic_balance.pump_flow_m3_s)
    assert (
        higher_inflow.hydraulic_balance.net_wet_well_inflow_m3_s
        - lower_inflow.hydraulic_balance.net_wet_well_inflow_m3_s
    ) == pytest.approx(0.004)


@pytest.mark.parametrize(
    ("condition", "obstruction_finding", "clearance_finding"),
    [
        (
            PumpCondition(
                obstruction=Decimal("0.249"),
                clearance_loss=Decimal("0.249"),
            ),
            ObstructionFinding.NO_MATERIAL_CONFIRMED,
            ClearanceFinding.CLEARANCE_LOSS_LOW,
        ),
        (
            PumpCondition(
                obstruction=Decimal("0.25"),
                clearance_loss=Decimal("0.25"),
            ),
            ObstructionFinding.MATERIAL_PRESENT,
            ClearanceFinding.CLEARANCE_LOSS_MODERATE,
        ),
        (
            PumpCondition(
                obstruction=Decimal("0.60"),
                clearance_loss=Decimal("0.60"),
            ),
            ObstructionFinding.SUBSTANTIAL_MATERIAL_PRESENT,
            ClearanceFinding.CLEARANCE_LOSS_HIGH,
        ),
    ],
)
def test_inspection_maps_latent_condition_without_changing_state(
    condition: PumpCondition,
    obstruction_finding: ObstructionFinding,
    clearance_finding: ClearanceFinding,
) -> None:
    model, state = _model_and_state()
    state = state.with_pump(
        replace(
            state.pump("pump-a"),
            condition=condition,
        )
    )

    observation = inspect_pump(model, state, "pump-a")

    assert observation.obstruction_finding is obstruction_finding
    assert observation.clearance_finding is clearance_finding
    assert state.pump("pump-a").condition == condition


def test_quantized_flow_does_not_disclose_latent_mechanism_mix() -> None:
    model, clean_state = _model_and_state()
    obstruction_state = clean_state.with_pump(
        replace(
            clean_state.pump("pump-a"),
            condition=PumpCondition(
                obstruction=Decimal("0.65"),
                clearance_loss=Decimal("0.10"),
            ),
        )
    )
    clearance_state = clean_state.with_pump(
        replace(
            clean_state.pump("pump-a"),
            condition=PumpCondition(
                obstruction=Decimal("0.25"),
                clearance_loss=Decimal("0.742300"),
            ),
        )
    )

    obstruction_result = assess_pump_station(
        model,
        obstruction_state,
        _assessment_environment(),
    )
    clearance_result = assess_pump_station(
        model,
        clearance_state,
        _assessment_environment(),
    )

    assert obstruction_result.state.pump("pump-a").condition != (clearance_result.state.pump("pump-a").condition)
    assert obstruction_result.observation.active_pump_flow_m3_s == (clearance_result.observation.active_pump_flow_m3_s)
