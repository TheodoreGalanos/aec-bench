# ABOUTME: Applies deterministic wastewater pump-station physics to immutable state.
# ABOUTME: Consumes validated package data without file access, persistence, or authority logic.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import NoReturn, cast

from aec_bench.task_world_templates.continual.world_logic import (
    ActionRejected,
    Transition,
    TransitionResult,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    DegradationParameters,
    PumpCondition,
    PumpExposure,
    PumpState,
    PumpStationCoupledModel,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationInputError,
    PumpStationOperatingDelta,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    FrozenJsonValue,
    ReferencePackage,
)


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationInputError(code, detail)


def _mapping(value: object, label: str) -> Mapping[str, FrozenJsonValue]:
    if not isinstance(value, Mapping):
        _fail("reference-package-data", f"{label} is not an object")
    return cast(Mapping[str, FrozenJsonValue], value)


def _sequence(value: object, label: str) -> Sequence[FrozenJsonValue]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        _fail("reference-package-data", f"{label} is not a sequence")
    return cast(Sequence[FrozenJsonValue], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        _fail("reference-package-data", f"{label} is not text")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int):
        _fail("reference-package-data", f"{label} is not numeric")
    try:
        return Decimal(value)
    except ArithmeticError:
        _fail("reference-package-data", f"{label} is not a decimal")


def _integer(value: object, label: str) -> int:
    number = _decimal(value, label)
    if number != number.to_integral_value():
        _fail("reference-package-data", f"{label} is not an integer")
    return int(number)


def _parameter_values(member: Mapping[str, FrozenJsonValue]) -> dict[str, FrozenJsonValue]:
    values: dict[str, FrozenJsonValue] = {}
    for index, item in enumerate(_sequence(member.get("parameters"), "parameters")):
        parameter = _mapping(item, f"parameters[{index}]")
        identity = _text(parameter.get("identity"), f"parameters[{index}].identity")
        values[identity] = parameter["value"]
    return values


def coupled_pump_station_model_from_package(package: ReferencePackage) -> PumpStationCoupledModel:
    """Compile the strict ASW-8 coupled topology and copied degradation values."""
    if package.profile_id != "AU-NSW-LH-SYN-SPS-v2":
        _fail("reference-package-profile", "the coupled model requires the v2 station-data profile")
    member = package.physical_member
    asset = _mapping(member.get("asset"), "asset")
    raw_pump_ids = _sequence(asset.get("component_ids"), "asset.component_ids")
    if len(raw_pump_ids) != 3:
        _fail("reference-package-data", "the coupled asset must contain three pumps")
    pump_ids = cast(
        tuple[str, str, str],
        tuple(_text(value, "asset.component_ids") for value in raw_pump_ids),
    )
    values = _parameter_values(member)

    def decimal_parameter(identity: str) -> Decimal:
        try:
            value = values[identity]
        except KeyError:
            _fail("reference-package-data", f"missing parameter {identity}")
        return _decimal(value, identity)

    return PumpStationCoupledModel(
        profile_id=package.profile_id,
        asset_id=_text(asset.get("asset_id"), "asset.asset_id"),
        pump_ids=pump_ids,
        maximum_running_pumps=_integer(asset.get("maximum_running_pumps"), "maximum_running_pumps"),
        service_capacity_units_per_running_pump=_integer(
            asset.get("service_capacity_units_per_running_pump"),
            "service_capacity_units_per_running_pump",
        ),
        test_running_service_capacity_units=_integer(
            asset.get("test_running_service_capacity_units"),
            "test_running_service_capacity_units",
        ),
        degradation=DegradationParameters(
            obstruction_runtime_rate=decimal_parameter("mechanism.r_o_runtime"),
            obstruction_start_rate=decimal_parameter("mechanism.r_o_start"),
            clearance_runtime_rate=decimal_parameter("mechanism.r_c_runtime"),
        ),
    )


def _progress_coupled_condition(
    model: PumpStationCoupledModel,
    condition: PumpCondition,
    runtime_seconds: int,
    starts: int,
) -> PumpCondition:
    degradation = model.degradation
    return PumpCondition(
        obstruction=min(
            Decimal(1),
            condition.obstruction
            + degradation.obstruction_runtime_rate * runtime_seconds
            + degradation.obstruction_start_rate * starts,
        ),
        clearance_loss=min(
            Decimal(1),
            condition.clearance_loss + degradation.clearance_runtime_rate * runtime_seconds,
        ),
    )


def transition_coupled_pump_station(
    model: PumpStationCoupledModel,
    state: PumpStationCoupledPhysicalState,
    interval: PumpStationCoupledOperatingInterval,
) -> TransitionResult[PumpStationCoupledPhysicalState, PumpStationCoupledOperatingInterval]:
    """Apply one coupled physical interval without persistence or authority logic."""
    try:
        if tuple(pump.pump_id for pump in state.pumps) != model.pump_ids:
            _fail("coupled-state", "pump identities or order differ from the model")
        if state.calendar_seconds != interval.start_calendar_seconds:
            _fail("coupled-operating-interval", "interval must start at current world time")
        if not set(interval.service_running_pump_ids) <= set(interval.actual_assignment_pump_ids):
            _fail("coupled-operating-interval", "service-running pumps must be assigned")
        for pump_id in interval.service_running_pump_ids:
            if not state.availability(pump_id).run_eligible:
                _fail("coupled-operating-interval", f"{pump_id} is not service-run eligible")
        for pump_id in interval.test_running_pump_ids:
            if not state.availability(pump_id).test_eligible:
                _fail("coupled-operating-interval", f"{pump_id} is not test eligible")

        prior_running = set(state.service_running_pump_ids) | set(state.test_running_pump_ids)
        next_running = set(interval.service_running_pump_ids) | set(interval.test_running_pump_ids)
        updated_pumps: list[PumpState] = []
        updated_deltas: list[PumpStationOperatingDelta] = []
        for pump in state.pumps:
            requested = interval.pump_delta(pump.pump_id)
            starts = requested.start_added or int(pump.pump_id in next_running and pump.pump_id not in prior_running)
            runtime = requested.total_runtime_seconds
            closing_exposure = PumpExposure(
                runtime_seconds=pump.exposure.runtime_seconds + runtime,
                completed_starts=pump.exposure.completed_starts + starts,
            )
            closing_condition = _progress_coupled_condition(model, pump.condition, runtime, starts)
            updated_pumps.append(replace(pump, exposure=closing_exposure, condition=closing_condition))
            updated_deltas.append(
                replace(
                    requested,
                    start_added=starts,
                    opening_exposure=pump.exposure,
                    closing_exposure=closing_exposure,
                    opening_condition=pump.condition,
                    closing_condition=closing_condition,
                )
            )
    except PumpStationInputError as error:
        _code, _separator, detail = str(error).partition(": ")
        return ActionRejected(error.code, detail or str(error))
    updated_state = PumpStationCoupledPhysicalState(
        calendar_seconds=interval.end_calendar_seconds,
        pumps=cast(tuple[PumpState, PumpState, PumpState], tuple(updated_pumps)),
        pump_boundaries=state.pump_boundaries,
        common_boundary=state.common_boundary,
        service_running_pump_ids=interval.service_running_pump_ids,
        test_running_pump_ids=interval.test_running_pump_ids,
    )
    updated_interval = replace(
        interval,
        pump_deltas=cast(
            tuple[PumpStationOperatingDelta, PumpStationOperatingDelta, PumpStationOperatingDelta],
            tuple(updated_deltas),
        ),
    )
    return Transition(
        state=updated_state,
        output=updated_interval,
    )
