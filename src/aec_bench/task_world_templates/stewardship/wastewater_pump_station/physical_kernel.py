# ABOUTME: Applies deterministic wastewater pump-station physics to immutable state.
# ABOUTME: Consumes validated package data without file access, persistence, or authority logic.

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from typing import NoReturn, cast

from aec_bench.task_world_templates.continual.world_logic import (
    ActionRejected,
    Transition,
    TransitionResult,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    ClearanceFinding,
    DegradationParameters,
    ExposureLimits,
    FluidProperties,
    ForceMainParameters,
    InflowParameters,
    InterventionParameters,
    ObservationParameters,
    ObstructionFinding,
    OperatingInterval,
    PumpCapability,
    PumpCondition,
    PumpCurveParameters,
    PumpExposure,
    PumpInspectionObservation,
    PumpIntervention,
    PumpInterventionKind,
    PumpState,
    PumpStationChangeKind,
    PumpStationCoupledModel,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationEnvironment,
    PumpStationHydraulicBalance,
    PumpStationInputError,
    PumpStationModel,
    PumpStationObservation,
    PumpStationOperatingDelta,
    PumpStationResourceRequirements,
    PumpStationResources,
    PumpStationResult,
    PumpStationState,
    WetWellGeometry,
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


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        _fail("reference-package-data", f"{label} is not boolean")
    return value


def _parameter_values(member: Mapping[str, FrozenJsonValue]) -> dict[str, FrozenJsonValue]:
    values: dict[str, FrozenJsonValue] = {}
    for index, item in enumerate(_sequence(member.get("parameters"), "parameters")):
        parameter = _mapping(item, f"parameters[{index}]")
        identity = _text(parameter.get("identity"), f"parameters[{index}].identity")
        values[identity] = parameter["value"]
    return values


def _inspection_band_edges(
    member: Mapping[str, FrozenJsonValue],
) -> tuple[Decimal, Decimal]:
    for index, item in enumerate(_sequence(member.get("composites"), "composites")):
        composite = _mapping(item, f"composites[{index}]")
        if composite.get("identity") != "observation.inspection_band_edges":
            continue
        members = _sequence(
            composite.get("members"),
            "observation.inspection_band_edges.members",
        )
        if len(members) != 2:
            _fail(
                "reference-package-data",
                "inspection band edges must contain two values",
            )
        return (
            _decimal(members[0], "inspection lower threshold"),
            _decimal(members[1], "inspection upper threshold"),
        )
    _fail("reference-package-data", "inspection band edges are missing")


def pump_station_model_from_package(package: ReferencePackage) -> PumpStationModel:
    """Compile typed pump-station physics from validated package data."""
    member = package.physical_member
    asset = _mapping(member.get("asset"), "asset")
    pump_ids_value = _sequence(asset.get("component_ids"), "asset.component_ids")
    if len(pump_ids_value) != 2:
        _fail("reference-package-data", "asset must contain two pumps")
    pump_ids = (
        _text(pump_ids_value[0], "asset.component_ids[0]"),
        _text(pump_ids_value[1], "asset.component_ids[1]"),
    )
    values = _parameter_values(member)
    inspection_lower_threshold, inspection_upper_threshold = _inspection_band_edges(member)

    def decimal_parameter(identity: str) -> Decimal:
        try:
            value = values[identity]
        except KeyError:
            _fail("reference-package-data", f"missing parameter {identity}")
        return _decimal(value, identity)

    def integer_parameter(identity: str) -> int:
        try:
            value = values[identity]
        except KeyError:
            _fail("reference-package-data", f"missing parameter {identity}")
        return _integer(value, identity)

    def boolean_parameter(identity: str) -> bool:
        try:
            value = values[identity]
        except KeyError:
            _fail("reference-package-data", f"missing parameter {identity}")
        return _boolean(value, identity)

    asset_transfer_limit = _integer(
        asset.get("maximum_duty_transfers"),
        "asset.maximum_duty_transfers",
    )
    parameter_transfer_limit = integer_parameter("topology.transfer_limit")
    if asset_transfer_limit != parameter_transfer_limit:
        _fail(
            "reference-package-data",
            "asset and topology transfer limits differ",
        )

    return PumpStationModel(
        asset_id=_text(asset.get("asset_id"), "asset.asset_id"),
        pump_ids=pump_ids,
        initial_duty_pump_id=_text(
            asset.get("initial_duty_component_id"),
            "asset.initial_duty_component_id",
        ),
        initial_standby_pump_id=_text(
            asset.get("initial_standby_component_id"),
            "asset.initial_standby_component_id",
        ),
        maximum_running_pumps=integer_parameter("topology.max_running_pumps"),
        maximum_duty_transfers=asset_transfer_limit,
        fluid=FluidProperties(
            density_kg_m3=decimal_parameter("fluid.rho"),
            dynamic_viscosity_pa_s=decimal_parameter("fluid.mu"),
            gravity_m_s2=decimal_parameter("fluid.g"),
        ),
        wet_well=WetWellGeometry(
            diameter_m=decimal_parameter("well.D_w"),
            stop_level_m=decimal_parameter("well.h_stop"),
            start_level_m=decimal_parameter("well.h_start"),
            high_level_m=decimal_parameter("well.h_high"),
            overflow_level_m=decimal_parameter("well.h_overflow"),
        ),
        force_main=ForceMainParameters(
            discharge_level_m=decimal_parameter("system.z_d"),
            length_m=decimal_parameter("system.L"),
            diameter_m=decimal_parameter("system.D"),
            roughness_m=decimal_parameter("system.epsilon"),
            minor_loss_coefficient=decimal_parameter("system.K_minor"),
            minimum_reynolds_number=decimal_parameter("system.Re_min"),
        ),
        pump_curve=PumpCurveParameters(
            shutoff_head_m=decimal_parameter("pump.H_0"),
            zero_head_flow_m3_s=decimal_parameter("pump.Q_0"),
            obstruction_head_loss_factor=decimal_parameter("mechanism.a_o"),
            obstruction_curve_factor=decimal_parameter("mechanism.b_o"),
            clearance_head_loss_factor=decimal_parameter("mechanism.a_c"),
            clearance_curve_factor=decimal_parameter("mechanism.b_c"),
        ),
        inflow=InflowParameters(
            low_m3_s=decimal_parameter("inflow.Q_low"),
            nominal_m3_s=decimal_parameter("inflow.Q_nominal"),
            assessment_m3_s=decimal_parameter("inflow.Q_assess"),
            diagnostic_period_seconds=integer_parameter("inflow.T_diagnostic"),
        ),
        degradation=DegradationParameters(
            obstruction_runtime_rate=decimal_parameter("mechanism.r_o_runtime"),
            obstruction_start_rate=decimal_parameter("mechanism.r_o_start"),
            clearance_runtime_rate=decimal_parameter("mechanism.r_c_runtime"),
        ),
        exposure_limits=ExposureLimits(
            calendar_seconds=integer_parameter("exposure.calendar_max"),
            pump_runtime_seconds=integer_parameter("exposure.runtime_max"),
            pump_completed_starts=integer_parameter("exposure.starts_max"),
        ),
        capability_drawdown_limit_seconds=decimal_parameter("capability.t_draw_limit"),
        observations=ObservationParameters(
            level_resolution_m=decimal_parameter("observation.level_resolution"),
            level_bias_m=decimal_parameter("observation.level_bias"),
            flow_resolution_m3_s=decimal_parameter("observation.flow_resolution"),
            flow_bias_fraction=decimal_parameter("observation.flow_bias"),
            runtime_resolution_seconds=integer_parameter("observation.runtime_resolution"),
            inspection_lower_threshold=inspection_lower_threshold,
            inspection_upper_threshold=inspection_upper_threshold,
        ),
        interventions=InterventionParameters(
            obstruction_clearance_effectiveness=decimal_parameter("intervention.e_clear"),
            obstruction_residual=decimal_parameter("intervention.o_residual"),
            clearance_repair_effectiveness=decimal_parameter("intervention.e_repair"),
            clearance_residual=decimal_parameter("intervention.c_residual"),
        ),
        resources=PumpStationResourceRequirements(
            repair_kit_initially_available=boolean_parameter("resource.kit_initial"),
            repair_kit_lead_seconds=integer_parameter("resource.kit_lead"),
            access_duration_seconds=integer_parameter("resource.access_duration"),
            concurrent_intervention_limit=integer_parameter("resource.concurrent_limit"),
        ),
    )


def initial_pump_station_state(model: PumpStationModel) -> PumpStationState:
    """Create the clean initial physical state for a pump-station model."""
    pumps = tuple(
        PumpState(
            pump_id=pump_id,
            condition=PumpCondition.clean(),
            exposure=PumpExposure.zero(),
        )
        for pump_id in model.pump_ids
    )
    return PumpStationState(
        calendar_seconds=0,
        duty_pump_id=model.initial_duty_pump_id,
        standby_pump_id=model.initial_standby_pump_id,
        duty_transfer_count=0,
        pumps=cast(tuple[PumpState, PumpState], pumps),
    )


def _validate_state(model: PumpStationModel, state: PumpStationState) -> None:
    if tuple(pump.pump_id for pump in state.pumps) != model.pump_ids:
        _fail("pump-station-state", "pump identities or order differ from model")
    if state.calendar_seconds > model.exposure_limits.calendar_seconds:
        _fail("exposure-limit", "calendar time exceeds the certified envelope")
    if state.duty_transfer_count > model.maximum_duty_transfers:
        _fail("duty-transfer-limit", "state exceeds the permitted transfer count")
    for pump in state.pumps:
        if pump.exposure.runtime_seconds > model.exposure_limits.pump_runtime_seconds:
            _fail("exposure-limit", f"{pump.pump_id} runtime exceeds the certified envelope")
        if pump.exposure.completed_starts > model.exposure_limits.pump_completed_starts:
            _fail("exposure-limit", f"{pump.pump_id} starts exceed the certified envelope")


def _validate_environment(
    model: PumpStationModel,
    environment: PumpStationEnvironment,
) -> None:
    if environment.wet_well_level_m > model.wet_well.overflow_level_m:
        _fail(
            "pump-station-environment",
            "wet-well level exceeds the certified overflow level",
        )


def _pump_support_factors(
    model: PumpStationModel,
    condition: PumpCondition,
) -> tuple[float, float]:
    curve = model.pump_curve
    obstruction = float(condition.obstruction)
    clearance = float(condition.clearance_loss)
    head_factor = (
        1.0
        - float(curve.obstruction_head_loss_factor) * obstruction
        - float(curve.clearance_head_loss_factor) * clearance
    )
    curve_factor = (
        1.0 + float(curve.obstruction_curve_factor) * obstruction + float(curve.clearance_curve_factor) * clearance
    )
    if head_factor <= 0.0 or curve_factor <= 0.0:
        _fail("operating-point", "pump support factors must be positive")
    return head_factor, curve_factor


def _pump_head_m(
    model: PumpStationModel,
    flow_m3_s: float,
    condition: PumpCondition,
) -> float:
    head_factor, curve_factor = _pump_support_factors(model, condition)
    flow_ratio = flow_m3_s / float(model.pump_curve.zero_head_flow_m3_s)
    return max(
        0.0,
        float(model.pump_curve.shutoff_head_m) * (head_factor - curve_factor * flow_ratio * flow_ratio),
    )


def _support_flow_m3_s(
    model: PumpStationModel,
    condition: PumpCondition,
) -> float:
    head_factor, curve_factor = _pump_support_factors(model, condition)
    support = float(model.pump_curve.zero_head_flow_m3_s) * math.sqrt(head_factor / curve_factor)
    if not 0.0 < support <= float(model.pump_curve.zero_head_flow_m3_s):
        _fail("operating-point", "pump support flow leaves the physical envelope")
    return support


def _system_loss_head_m(model: PumpStationModel, flow_m3_s: float) -> float:
    if flow_m3_s == 0.0:
        return 0.0
    force_main = model.force_main
    diameter = float(force_main.diameter_m)
    velocity = 4.0 * flow_m3_s / (math.pi * diameter * diameter)
    reynolds = float(model.fluid.density_kg_m3) * velocity * diameter / float(model.fluid.dynamic_viscosity_pa_s)
    if reynolds < float(force_main.minimum_reynolds_number):
        _fail("operating-point", "positive flow leaves the turbulent envelope")
    friction = 0.25 / (math.log10(float(force_main.roughness_m) / (3.7 * diameter) + 5.74 / reynolds**0.9) ** 2)
    velocity_head = velocity * velocity / (2.0 * float(model.fluid.gravity_m_s2))
    return (friction * float(force_main.length_m) / diameter + float(force_main.minor_loss_coefficient)) * velocity_head


def _system_head_m(
    model: PumpStationModel,
    flow_m3_s: float,
    wet_well_level_m: Decimal,
) -> float:
    return float(model.force_main.discharge_level_m) - float(wet_well_level_m) + _system_loss_head_m(model, flow_m3_s)


def _operating_flow_m3_s(
    model: PumpStationModel,
    condition: PumpCondition,
    wet_well_level_m: Decimal,
) -> float:
    lower = 0.0
    upper = _support_flow_m3_s(model, condition)

    def residual(flow_m3_s: float) -> float:
        return _pump_head_m(model, flow_m3_s, condition) - _system_head_m(
            model,
            flow_m3_s,
            wet_well_level_m,
        )

    if residual(lower) <= 0.0 or residual(upper) >= 0.0:
        _fail("operating-point", "operating-flow root is not strictly internal")
    for _ in range(128):
        midpoint = (lower + upper) / 2.0
        if residual(midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _capability(
    model: PumpStationModel,
    condition: PumpCondition,
) -> PumpCapability:
    operating_flow = _operating_flow_m3_s(
        model,
        condition,
        model.wet_well.start_level_m,
    )
    net_flow = operating_flow - float(model.inflow.assessment_m3_s)
    wet_well_area = math.pi * float(model.wet_well.diameter_m) ** 2 / 4.0
    working_volume = wet_well_area * float(model.wet_well.start_level_m - model.wet_well.stop_level_m)
    drawdown_seconds = math.inf if net_flow <= 0.0 else working_volume / net_flow
    return PumpCapability(
        operating_flow_m3_s=operating_flow,
        drawdown_seconds=drawdown_seconds,
        review_required=(net_flow <= 0.0 or drawdown_seconds > float(model.capability_drawdown_limit_seconds)),
    )


def _quantize_half_up(value: Decimal, resolution: Decimal) -> Decimal:
    return resolution * (value / resolution).quantize(
        Decimal(1),
        rounding=ROUND_HALF_UP,
    )


def _observation(
    model: PumpStationModel,
    state: PumpStationState,
    environment: PumpStationEnvironment,
    hydraulic_balance: PumpStationHydraulicBalance,
) -> PumpStationObservation:
    duty_pump = state.pump(state.duty_pump_id)
    flow = Decimal(str(hydraulic_balance.pump_flow_m3_s)) * (Decimal(1) + model.observations.flow_bias_fraction)
    level = environment.wet_well_level_m + model.observations.level_bias_m
    runtime_resolution = Decimal(model.observations.runtime_resolution_seconds)
    runtime_meter = _quantize_half_up(
        Decimal(duty_pump.exposure.runtime_seconds),
        runtime_resolution,
    )
    return PumpStationObservation(
        sample_time_seconds=state.calendar_seconds,
        duty_pump_id=state.duty_pump_id,
        standby_pump_id=state.standby_pump_id,
        wet_well_level_m=_quantize_half_up(
            level,
            model.observations.level_resolution_m,
        ),
        active_pump_flow_m3_s=_quantize_half_up(
            flow,
            model.observations.flow_resolution_m3_s,
        ),
        runtime_meter_seconds=int(runtime_meter),
        completed_starts=duty_pump.exposure.completed_starts,
        isolated=environment.isolated,
    )


def _hydraulic_balance(
    model: PumpStationModel,
    state: PumpStationState,
    environment: PumpStationEnvironment,
) -> PumpStationHydraulicBalance:
    duty_pump = state.pump(state.duty_pump_id)
    pump_flow = (
        0.0
        if environment.isolated
        else _operating_flow_m3_s(
            model,
            duty_pump.condition,
            environment.wet_well_level_m,
        )
    )
    inflow = float(environment.inflow_m3_s)
    return PumpStationHydraulicBalance(
        inflow_m3_s=inflow,
        pump_flow_m3_s=pump_flow,
        net_wet_well_inflow_m3_s=inflow - pump_flow,
    )


def _pump_station_result(
    model: PumpStationModel,
    previous_state: PumpStationState,
    state: PumpStationState,
    environment: PumpStationEnvironment,
    change_kind: PumpStationChangeKind,
) -> PumpStationResult:
    _validate_state(model, state)
    _validate_environment(model, environment)
    duty_pump = state.pump(state.duty_pump_id)
    hydraulic_balance = _hydraulic_balance(model, state, environment)
    return PumpStationResult(
        previous_state=previous_state,
        state=state,
        change_kind=change_kind,
        capability=_capability(model, duty_pump.condition),
        hydraulic_balance=hydraulic_balance,
        observation=_observation(
            model,
            state,
            environment,
            hydraulic_balance,
        ),
    )


def assess_pump_station(
    model: PumpStationModel,
    state: PumpStationState,
    environment: PumpStationEnvironment,
) -> PumpStationResult:
    """Return current physical capability and quantized readings without mutation."""
    return _pump_station_result(
        model,
        state,
        state,
        environment,
        PumpStationChangeKind.ASSESSMENT,
    )


def inspect_pump(
    model: PumpStationModel,
    state: PumpStationState,
    pump_id: str,
) -> PumpInspectionObservation:
    """Generate deterministic inspection bands without changing physical state."""
    _validate_state(model, state)
    condition = state.pump(pump_id).condition
    lower = model.observations.inspection_lower_threshold
    upper = model.observations.inspection_upper_threshold
    if condition.obstruction < lower:
        obstruction_finding = ObstructionFinding.NO_MATERIAL_CONFIRMED
    elif condition.obstruction < upper:
        obstruction_finding = ObstructionFinding.MATERIAL_PRESENT
    else:
        obstruction_finding = ObstructionFinding.SUBSTANTIAL_MATERIAL_PRESENT
    if condition.clearance_loss < lower:
        clearance_finding = ClearanceFinding.CLEARANCE_LOSS_LOW
    elif condition.clearance_loss < upper:
        clearance_finding = ClearanceFinding.CLEARANCE_LOSS_MODERATE
    else:
        clearance_finding = ClearanceFinding.CLEARANCE_LOSS_HIGH
    return PumpInspectionObservation(
        sample_time_seconds=state.calendar_seconds,
        pump_id=pump_id,
        obstruction_finding=obstruction_finding,
        clearance_finding=clearance_finding,
    )


def _progress_condition(
    model: PumpStationModel,
    condition: PumpCondition,
    runtime_seconds: int,
    completed_starts: int,
) -> PumpCondition:
    degradation = model.degradation
    obstruction = min(
        Decimal(1),
        condition.obstruction
        + degradation.obstruction_runtime_rate * runtime_seconds
        + degradation.obstruction_start_rate * completed_starts,
    )
    clearance_loss = min(
        Decimal(1),
        condition.clearance_loss + degradation.clearance_runtime_rate * runtime_seconds,
    )
    return PumpCondition(
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )


def advance_pump_station(
    model: PumpStationModel,
    state: PumpStationState,
    interval: OperatingInterval,
) -> PumpStationResult:
    """Advance calendar, duty exposure, latent condition, and end observations."""
    _validate_state(model, state)
    _validate_environment(model, interval.environment)
    duty_pump = state.pump(state.duty_pump_id)
    updated_pump = replace(
        duty_pump,
        condition=_progress_condition(
            model,
            duty_pump.condition,
            interval.duty_runtime_seconds,
            interval.duty_completed_starts,
        ),
        exposure=PumpExposure(
            runtime_seconds=(duty_pump.exposure.runtime_seconds + interval.duty_runtime_seconds),
            completed_starts=(duty_pump.exposure.completed_starts + interval.duty_completed_starts),
        ),
    )
    updated_state = replace(
        state.with_pump(updated_pump),
        calendar_seconds=state.calendar_seconds + interval.elapsed_seconds,
    )
    _validate_state(model, updated_state)
    return _pump_station_result(
        model,
        state,
        updated_state,
        interval.environment,
        PumpStationChangeKind.OPERATING_INTERVAL,
    )


def transfer_duty_to_standby(
    model: PumpStationModel,
    state: PumpStationState,
    environment: PumpStationEnvironment,
) -> PumpStationResult:
    """Apply the one permitted physical duty-to-standby transfer."""
    _validate_state(model, state)
    if state.duty_transfer_count >= model.maximum_duty_transfers:
        _fail("duty-transfer-limit", "no further duty transfer is permitted")
    updated_state = replace(
        state,
        duty_pump_id=state.standby_pump_id,
        standby_pump_id=state.duty_pump_id,
        duty_transfer_count=state.duty_transfer_count + 1,
    )
    return _pump_station_result(
        model,
        state,
        updated_state,
        environment,
        PumpStationChangeKind.DUTY_TRANSFER,
    )


def _validate_intervention_resources(
    model: PumpStationModel,
    intervention: PumpIntervention,
    resources: PumpStationResources,
) -> None:
    requirements = model.resources
    if (
        resources.access_window_seconds < requirements.access_duration_seconds
        or resources.available_intervention_slots < 1
        or (intervention.kind is PumpInterventionKind.REPAIR_CLEARANCE and not resources.repair_kit_available)
    ):
        _fail(
            "intervention-resources",
            "access, repair kit, or intervention capacity is insufficient",
        )


def apply_pump_intervention(
    model: PumpStationModel,
    state: PumpStationState,
    intervention: PumpIntervention,
    resources: PumpStationResources,
    environment: PumpStationEnvironment,
) -> PumpStationResult:
    """Apply one completed physical intervention without authority semantics."""
    _validate_state(model, state)
    _validate_environment(model, environment)
    _validate_intervention_resources(model, intervention, resources)
    pump = state.pump(intervention.pump_id)
    condition = pump.condition
    parameters = model.interventions
    if intervention.kind is PumpInterventionKind.CLEAR_OBSTRUCTION:
        updated_condition = PumpCondition(
            obstruction=max(
                parameters.obstruction_residual,
                (Decimal(1) - parameters.obstruction_clearance_effectiveness) * condition.obstruction,
            ),
            clearance_loss=condition.clearance_loss,
        )
    else:
        updated_condition = PumpCondition(
            obstruction=condition.obstruction,
            clearance_loss=max(
                parameters.clearance_residual,
                (Decimal(1) - parameters.clearance_repair_effectiveness) * condition.clearance_loss,
            ),
        )
    updated_state = state.with_pump(
        replace(
            pump,
            condition=updated_condition,
        )
    )
    change_kind = (
        PumpStationChangeKind.CLEAR_OBSTRUCTION
        if intervention.kind is PumpInterventionKind.CLEAR_OBSTRUCTION
        else PumpStationChangeKind.REPAIR_CLEARANCE
    )
    return _pump_station_result(
        model,
        state,
        updated_state,
        environment,
        change_kind,
    )


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
