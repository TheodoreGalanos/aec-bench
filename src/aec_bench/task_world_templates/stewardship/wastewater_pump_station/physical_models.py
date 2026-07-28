# ABOUTME: Defines immutable physical models for the synthetic wastewater pump station.
# ABOUTME: Keeps clocks, latent condition, environment, resources, and observations task-local.

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn, Self


class PumpStationInputError(ValueError):
    """Raised when a physical input leaves the pump-station contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationInputError(code, detail)


def _require_non_negative(value: int | Decimal, code: str, field_name: str) -> None:
    if value < 0:
        _fail(code, f"{field_name} must be non-negative")


@dataclass(frozen=True, slots=True)
class FluidProperties:
    """Fluid values used by the station hydraulic equations."""

    density_kg_m3: Decimal
    dynamic_viscosity_pa_s: Decimal
    gravity_m_s2: Decimal


@dataclass(frozen=True, slots=True)
class WetWellGeometry:
    """Wet-well geometry and ordered operating levels."""

    diameter_m: Decimal
    stop_level_m: Decimal
    start_level_m: Decimal
    high_level_m: Decimal
    overflow_level_m: Decimal


@dataclass(frozen=True, slots=True)
class ForceMainParameters:
    """Force-main values used to calculate the system head."""

    discharge_level_m: Decimal
    length_m: Decimal
    diameter_m: Decimal
    roughness_m: Decimal
    minor_loss_coefficient: Decimal
    minimum_reynolds_number: Decimal


@dataclass(frozen=True, slots=True)
class PumpCurveParameters:
    """Pump-curve values and deterministic condition response coefficients."""

    shutoff_head_m: Decimal
    zero_head_flow_m3_s: Decimal
    obstruction_head_loss_factor: Decimal
    obstruction_curve_factor: Decimal
    clearance_head_loss_factor: Decimal
    clearance_curve_factor: Decimal


@dataclass(frozen=True, slots=True)
class InflowParameters:
    """Declared inflow values used by the reference station."""

    low_m3_s: Decimal
    nominal_m3_s: Decimal
    assessment_m3_s: Decimal
    diagnostic_period_seconds: int


@dataclass(frozen=True, slots=True)
class DegradationParameters:
    """Exposure rates for obstruction and clearance loss."""

    obstruction_runtime_rate: Decimal
    obstruction_start_rate: Decimal
    clearance_runtime_rate: Decimal


@dataclass(frozen=True, slots=True)
class ExposureLimits:
    """Certified clock limits for one physical world run."""

    calendar_seconds: int
    pump_runtime_seconds: int
    pump_completed_starts: int


@dataclass(frozen=True, slots=True)
class ObservationParameters:
    """Resolution and fixed bias values for physical readings."""

    level_resolution_m: Decimal
    level_bias_m: Decimal
    flow_resolution_m3_s: Decimal
    flow_bias_fraction: Decimal
    runtime_resolution_seconds: int
    inspection_lower_threshold: Decimal
    inspection_upper_threshold: Decimal


@dataclass(frozen=True, slots=True)
class InterventionParameters:
    """Physical effectiveness and residual floors for pump interventions."""

    obstruction_clearance_effectiveness: Decimal
    obstruction_residual: Decimal
    clearance_repair_effectiveness: Decimal
    clearance_residual: Decimal


@dataclass(frozen=True, slots=True)
class PumpStationResourceRequirements:
    """Physical resource requirements supplied to intervention effects."""

    repair_kit_initially_available: bool
    repair_kit_lead_seconds: int
    access_duration_seconds: int
    concurrent_intervention_limit: int


@dataclass(frozen=True, slots=True)
class PumpStationModel:
    """Typed physical definition compiled from a validated reference package."""

    asset_id: str
    pump_ids: tuple[str, str]
    initial_duty_pump_id: str
    initial_standby_pump_id: str
    maximum_running_pumps: int
    maximum_duty_transfers: int
    fluid: FluidProperties
    wet_well: WetWellGeometry
    force_main: ForceMainParameters
    pump_curve: PumpCurveParameters
    inflow: InflowParameters
    degradation: DegradationParameters
    exposure_limits: ExposureLimits
    capability_drawdown_limit_seconds: Decimal
    observations: ObservationParameters
    interventions: InterventionParameters
    resources: PumpStationResourceRequirements

    def __post_init__(self) -> None:
        if len(set(self.pump_ids)) != 2:
            _fail("physical-model", "pump identities must be distinct")
        if (
            self.initial_duty_pump_id not in self.pump_ids
            or self.initial_standby_pump_id not in self.pump_ids
            or self.initial_duty_pump_id == self.initial_standby_pump_id
        ):
            _fail("physical-model", "initial duty and standby assignments differ")
        if self.maximum_duty_transfers < 0:
            _fail("physical-model", "maximum duty transfers must be non-negative")
        if self.maximum_running_pumps != 1:
            _fail("physical-model", "the reference station permits one running pump")


@dataclass(frozen=True, slots=True)
class PumpCondition:
    """Latent obstruction and clearance-loss severity for one pump."""

    obstruction: Decimal
    clearance_loss: Decimal

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.obstruction <= Decimal(1):
            _fail("pump-condition", "obstruction must remain inside [0, 1]")
        if not Decimal(0) <= self.clearance_loss <= Decimal(1):
            _fail("pump-condition", "clearance loss must remain inside [0, 1]")

    @classmethod
    def clean(cls) -> Self:
        """Return the clean latent condition."""
        return cls(obstruction=Decimal(0), clearance_loss=Decimal(0))


@dataclass(frozen=True, slots=True)
class PumpExposure:
    """Runtime and completed-start clocks for one pump."""

    runtime_seconds: int
    completed_starts: int

    def __post_init__(self) -> None:
        _require_non_negative(
            self.runtime_seconds,
            "pump-exposure",
            "runtime_seconds",
        )
        _require_non_negative(
            self.completed_starts,
            "pump-exposure",
            "completed_starts",
        )

    @classmethod
    def zero(cls) -> Self:
        """Return clocks with no operating exposure."""
        return cls(runtime_seconds=0, completed_starts=0)


@dataclass(frozen=True, slots=True)
class PumpState:
    """Latent condition and exposure for one physical pump."""

    pump_id: str
    condition: PumpCondition
    exposure: PumpExposure


@dataclass(frozen=True, slots=True)
class PumpStationState:
    """Immutable physical state for the two-pump station."""

    calendar_seconds: int
    duty_pump_id: str
    standby_pump_id: str
    duty_transfer_count: int
    pumps: tuple[PumpState, PumpState]

    def __post_init__(self) -> None:
        _require_non_negative(
            self.calendar_seconds,
            "pump-station-state",
            "calendar_seconds",
        )
        _require_non_negative(
            self.duty_transfer_count,
            "pump-station-state",
            "duty_transfer_count",
        )
        pump_ids = tuple(pump.pump_id for pump in self.pumps)
        if len(set(pump_ids)) != 2:
            _fail("pump-station-state", "state must contain two distinct pumps")
        if (
            self.duty_pump_id not in pump_ids
            or self.standby_pump_id not in pump_ids
            or self.duty_pump_id == self.standby_pump_id
        ):
            _fail("pump-station-state", "duty and standby assignments differ")

    def pump(self, pump_id: str) -> PumpState:
        """Return one pump by its stable component identity."""
        for pump in self.pumps:
            if pump.pump_id == pump_id:
                return pump
        _fail("unknown-pump", pump_id)

    def with_pump(self, updated_pump: PumpState) -> Self:
        """Return state with one pump replaced by matching identity."""
        if updated_pump.pump_id not in {pump.pump_id for pump in self.pumps}:
            _fail("unknown-pump", updated_pump.pump_id)
        first, second = self.pumps
        return replace(
            self,
            pumps=(
                updated_pump if first.pump_id == updated_pump.pump_id else first,
                updated_pump if second.pump_id == updated_pump.pump_id else second,
            ),
        )


@dataclass(frozen=True, slots=True)
class PumpStationEnvironment:
    """Current physical conditions supplied by the world controller."""

    inflow_m3_s: Decimal
    wet_well_level_m: Decimal
    isolated: bool

    def __post_init__(self) -> None:
        _require_non_negative(
            self.inflow_m3_s,
            "pump-station-environment",
            "inflow_m3_s",
        )
        _require_non_negative(
            self.wet_well_level_m,
            "pump-station-environment",
            "wet_well_level_m",
        )


@dataclass(frozen=True, slots=True)
class OperatingInterval:
    """One explicit interval of calendar and duty-pump exposure."""

    elapsed_seconds: int
    duty_runtime_seconds: int
    duty_completed_starts: int
    environment: PumpStationEnvironment

    def __post_init__(self) -> None:
        if self.elapsed_seconds <= 0:
            _fail("operating-interval", "elapsed_seconds must be positive")
        if not 0 <= self.duty_runtime_seconds <= self.elapsed_seconds:
            _fail(
                "operating-interval",
                "duty runtime must be inside the elapsed interval",
            )
        _require_non_negative(
            self.duty_completed_starts,
            "operating-interval",
            "duty_completed_starts",
        )
        if self.duty_completed_starts and self.duty_runtime_seconds == 0:
            _fail(
                "operating-interval",
                "completed starts require positive duty runtime",
            )
        if self.environment.isolated and (self.duty_runtime_seconds or self.duty_completed_starts):
            _fail(
                "operating-interval",
                "isolated intervals cannot add runtime or starts",
            )


@dataclass(frozen=True, slots=True)
class PumpStationResources:
    """Available physical resources for a completed intervention."""

    access_window_seconds: int
    repair_kit_available: bool
    available_intervention_slots: int

    def __post_init__(self) -> None:
        _require_non_negative(
            self.access_window_seconds,
            "pump-station-resources",
            "access_window_seconds",
        )
        _require_non_negative(
            self.available_intervention_slots,
            "pump-station-resources",
            "available_intervention_slots",
        )


class PumpInterventionKind(StrEnum):
    """Physical effect supported by the reference pump station."""

    CLEAR_OBSTRUCTION = "clear-obstruction"
    REPAIR_CLEARANCE = "repair-clearance"


class ObstructionFinding(StrEnum):
    """Deterministic obstruction inspection band."""

    NO_MATERIAL_CONFIRMED = "no_material_confirmed"
    MATERIAL_PRESENT = "material_present"
    SUBSTANTIAL_MATERIAL_PRESENT = "substantial_material_present"


class ClearanceFinding(StrEnum):
    """Deterministic clearance-loss inspection band."""

    CLEARANCE_LOSS_LOW = "clearance_loss_low"
    CLEARANCE_LOSS_MODERATE = "clearance_loss_moderate"
    CLEARANCE_LOSS_HIGH = "clearance_loss_high"


@dataclass(frozen=True, slots=True)
class PumpIntervention:
    """One completed physical intervention effect."""

    kind: PumpInterventionKind
    pump_id: str


@dataclass(frozen=True, slots=True)
class PumpCapability:
    """Physical duty capability at the declared assessment condition."""

    operating_flow_m3_s: float
    drawdown_seconds: float
    review_required: bool


@dataclass(frozen=True, slots=True)
class PumpStationHydraulicBalance:
    """Current inflow, pump flow, and net wet-well inflow."""

    inflow_m3_s: float
    pump_flow_m3_s: float
    net_wet_well_inflow_m3_s: float


@dataclass(frozen=True, slots=True)
class PumpStationObservation:
    """Quantized physical readings that exclude latent pump condition."""

    sample_time_seconds: int
    duty_pump_id: str
    standby_pump_id: str
    wet_well_level_m: Decimal
    active_pump_flow_m3_s: Decimal
    runtime_meter_seconds: int
    completed_starts: int
    isolated: bool


class PumpStationChangeKind(StrEnum):
    """Physical operation represented by one pump-station result."""

    ASSESSMENT = "assessment"
    OPERATING_INTERVAL = "operating-interval"
    DUTY_TRANSFER = "duty-transfer"
    CLEAR_OBSTRUCTION = "clear-obstruction"
    REPAIR_CLEARANCE = "repair-clearance"


@dataclass(frozen=True, slots=True)
class PumpInspectionObservation:
    """Inspection bands derived from latent condition without changing it."""

    sample_time_seconds: int
    pump_id: str
    obstruction_finding: ObstructionFinding
    clearance_finding: ClearanceFinding


@dataclass(frozen=True, slots=True)
class PumpStationResult:
    """Resulting state, physical capability, and end observation."""

    previous_state: PumpStationState
    state: PumpStationState
    change_kind: PumpStationChangeKind
    capability: PumpCapability
    hydraulic_balance: PumpStationHydraulicBalance
    observation: PumpStationObservation
