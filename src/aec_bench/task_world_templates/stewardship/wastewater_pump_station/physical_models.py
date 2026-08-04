# ABOUTME: Defines immutable physical models for the synthetic wastewater pump station.
# ABOUTME: Keeps clocks, latent condition, environment, resources, and observations task-local.

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn, Self, cast


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
class DegradationParameters:
    """Exposure rates for obstruction and clearance loss."""

    obstruction_runtime_rate: Decimal
    obstruction_start_rate: Decimal
    clearance_runtime_rate: Decimal


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


class PumpStationPumpMode(StrEnum):
    """Closed ASW-8 operating boundary for one pump."""

    ISOLATED_FOR_WORK = "isolated_for_work"
    TEST_ONLY = "test_only"
    RUN_IN_SERVICE = "run_in_service"
    SERVICE_AVAILABLE = "service_available"


@dataclass(frozen=True, slots=True)
class PumpStationCoupledModel:
    """Certified three-pump topology with discrete service accounting."""

    profile_id: str
    asset_id: str
    pump_ids: tuple[str, str, str]
    maximum_running_pumps: int
    service_capacity_units_per_running_pump: int
    test_running_service_capacity_units: int
    degradation: DegradationParameters

    def __post_init__(self) -> None:
        if len(set(self.pump_ids)) != 3:
            _fail("coupled-model", "the model must contain three distinct pumps")
        if self.maximum_running_pumps != 2:
            _fail("coupled-model", "the model must permit two physically running pumps")
        if self.service_capacity_units_per_running_pump != 1:
            _fail("coupled-model", "each service-running pump must supply one SCU")
        if self.test_running_service_capacity_units != 0:
            _fail("coupled-model", "test-running pumps must supply zero SCU")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledEnvironment:
    """Current shared physical conditions without station-wide isolation."""

    inflow_m3_s: Decimal
    wet_well_level_m: Decimal

    def __post_init__(self) -> None:
        _require_non_negative(self.inflow_m3_s, "coupled-environment", "inflow_m3_s")
        _require_non_negative(self.wet_well_level_m, "coupled-environment", "wet_well_level_m")


@dataclass(frozen=True, slots=True)
class PumpStationBoundaryAvailability:
    """Common power and discharge availability for the station."""

    power_available: bool
    discharge_available: bool
    source_transition_id: str

    @property
    def available(self) -> bool:
        """Return whether both common operating boundaries are available."""
        return self.power_available and self.discharge_available


@dataclass(frozen=True, slots=True)
class PumpStationPumpBoundary:
    """Durable operating mode and source evidence for one pump."""

    pump_id: str
    mode: PumpStationPumpMode
    source_permit_or_evidence_id: str
    effective_transition_id: str


@dataclass(frozen=True, slots=True)
class PumpStationPumpAvailability:
    """Three separate actor-visible operating predicates for one pump."""

    pump_id: str
    run_eligible: bool
    test_eligible: bool
    assured_for_outage_planning: bool
    source_evidence_ids: tuple[str, ...]
    source_restriction_ids: tuple[str, ...]
    decision_role: str
    effective_calendar_seconds: int
    closure_rule: str


def pump_availability_for_boundary(
    boundary: PumpStationPumpBoundary,
    common_boundary: PumpStationBoundaryAvailability,
    calendar_seconds: int,
) -> PumpStationPumpAvailability:
    """Derive the three policy predicates from explicit durable boundaries."""
    common_available = common_boundary.available
    return PumpStationPumpAvailability(
        pump_id=boundary.pump_id,
        run_eligible=common_available
        and boundary.mode in {PumpStationPumpMode.RUN_IN_SERVICE, PumpStationPumpMode.SERVICE_AVAILABLE},
        test_eligible=common_available and boundary.mode is PumpStationPumpMode.TEST_ONLY,
        assured_for_outage_planning=common_available and boundary.mode is PumpStationPumpMode.SERVICE_AVAILABLE,
        source_evidence_ids=(boundary.source_permit_or_evidence_id,),
        source_restriction_ids=(
            (boundary.source_permit_or_evidence_id,)
            if boundary.mode is not PumpStationPumpMode.SERVICE_AVAILABLE
            else ()
        ),
        decision_role="operations-controller",
        effective_calendar_seconds=calendar_seconds,
        closure_rule="accepted evidence and Operations boundary review",
    )


@dataclass(frozen=True, slots=True)
class PumpStationCoupledPhysicalState:
    """Three-pump physical state with separate service and test running sets."""

    calendar_seconds: int
    pumps: tuple[PumpState, PumpState, PumpState]
    pump_boundaries: tuple[PumpStationPumpBoundary, PumpStationPumpBoundary, PumpStationPumpBoundary]
    common_boundary: PumpStationBoundaryAvailability
    service_running_pump_ids: tuple[str, ...]
    test_running_pump_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        pump_ids = tuple(pump.pump_id for pump in self.pumps)
        boundary_ids = tuple(boundary.pump_id for boundary in self.pump_boundaries)
        if len(set(pump_ids)) != 3 or set(boundary_ids) != set(pump_ids):
            _fail("coupled-state", "physical and boundary pump identities differ")
        service = set(self.service_running_pump_ids)
        test = set(self.test_running_pump_ids)
        if len(service) != len(self.service_running_pump_ids) or len(test) != len(self.test_running_pump_ids):
            _fail("coupled-state", "running sets contain duplicate pumps")
        if service & test or not service | test <= set(pump_ids) or len(service | test) > 2:
            _fail("coupled-state", "running sets are invalid")
        for pump_id in service:
            if not self.availability(pump_id).run_eligible:
                _fail("coupled-state", f"{pump_id} is not service-run eligible")
        for pump_id in test:
            if not self.availability(pump_id).test_eligible:
                _fail("coupled-state", f"{pump_id} is not test eligible")

    def pump(self, pump_id: str) -> PumpState:
        """Return one physical pump by identity."""
        for pump in self.pumps:
            if pump.pump_id == pump_id:
                return pump
        _fail("unknown-pump", pump_id)

    def boundary(self, pump_id: str) -> PumpStationPumpBoundary:
        """Return one pump boundary by identity."""
        for boundary in self.pump_boundaries:
            if boundary.pump_id == pump_id:
                return boundary
        _fail("unknown-pump", pump_id)

    def availability(self, pump_id: str) -> PumpStationPumpAvailability:
        """Return current derived operating predicates for one pump."""
        return pump_availability_for_boundary(
            self.boundary(pump_id),
            self.common_boundary,
            self.calendar_seconds,
        )

    def with_boundary_mode(
        self,
        pump_id: str,
        mode: PumpStationPumpMode,
        source_id: str,
    ) -> Self:
        """Return state after one explicit pump-boundary transition."""
        self.boundary(pump_id)
        boundaries = tuple(
            PumpStationPumpBoundary(
                pump_id=pump_id,
                mode=mode,
                source_permit_or_evidence_id=source_id,
                effective_transition_id=source_id,
            )
            if boundary.pump_id == pump_id
            else boundary
            for boundary in self.pump_boundaries
        )
        service = tuple(
            item
            for item in self.service_running_pump_ids
            if item != pump_id or mode in {PumpStationPumpMode.RUN_IN_SERVICE, PumpStationPumpMode.SERVICE_AVAILABLE}
        )
        test = tuple(
            item for item in self.test_running_pump_ids if item != pump_id or mode is PumpStationPumpMode.TEST_ONLY
        )
        return replace(
            self,
            pump_boundaries=cast(
                tuple[PumpStationPumpBoundary, PumpStationPumpBoundary, PumpStationPumpBoundary],
                boundaries,
            ),
            service_running_pump_ids=service,
            test_running_pump_ids=test,
        )


@dataclass(frozen=True, slots=True)
class PumpStationServiceRequirement:
    """One exact half-open declared service interval."""

    start_calendar_seconds: int
    end_calendar_seconds: int
    required_service_scu: int

    def __post_init__(self) -> None:
        if self.start_calendar_seconds < 0 or self.end_calendar_seconds <= self.start_calendar_seconds:
            _fail("service-requirement", "service interval is invalid")
        if self.required_service_scu not in {1, 2}:
            _fail("service-requirement", "required service must be one or two SCU")


@dataclass(frozen=True, slots=True)
class PumpStationBaselineAssignment:
    """Scenario-owned expected assignment for one service interval."""

    start_calendar_seconds: int
    end_calendar_seconds: int
    ordered_pump_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationDutyAssignment:
    """One ordered accepted assignment separate from physical running sets."""

    assignment_id: str
    ordered_pump_ids: tuple[str, ...]
    active: bool
    source_need_id: str
    effective_transition_id: str
    required_service_scu: int
    assigned_service_scu: int
    unserved_service_scu: int
    decision_detail: str
    suspension_source_id: str | None = None
    supersession_transition_id: str | None = None

    def __post_init__(self) -> None:
        if not self.ordered_pump_ids or len(set(self.ordered_pump_ids)) != len(self.ordered_pump_ids):
            _fail("duty-assignment", "assignment must contain distinct pumps")
        if (
            min(
                self.required_service_scu,
                self.assigned_service_scu,
                self.unserved_service_scu,
            )
            < 0
            or self.required_service_scu != self.assigned_service_scu + self.unserved_service_scu
        ):
            _fail("duty-assignment", "assignment service accounting is invalid")
        if not self.decision_detail.strip():
            _fail("duty-assignment", "assignment decision detail is required")


@dataclass(frozen=True, slots=True)
class PumpStationOutageEpisode:
    """Durable source for collateral exposure attribution."""

    episode_id: str
    unavailable_baseline_pump_id: str
    source_record_id: str
    opening_transition_id: str
    closing_transition_id: str | None
    status: str


@dataclass(frozen=True, slots=True)
class PumpStationOperatingDelta:
    """Per-pump exposure and attribution for one coupled interval."""

    pump_id: str
    service_runtime_seconds: int
    test_runtime_seconds: int
    attributed_outage_episode_id: str | None
    start_added: int = 0
    opening_exposure: PumpExposure | None = None
    closing_exposure: PumpExposure | None = None
    opening_condition: PumpCondition | None = None
    closing_condition: PumpCondition | None = None

    def __post_init__(self) -> None:
        _require_non_negative(self.service_runtime_seconds, "operating-delta", "service runtime")
        _require_non_negative(self.test_runtime_seconds, "operating-delta", "test runtime")
        if self.service_runtime_seconds and self.test_runtime_seconds:
            _fail("operating-delta", "one pump cannot serve and test in the same interval")
        if self.start_added not in {0, 1}:
            _fail("operating-delta", "start delta must be zero or one")

    @property
    def total_runtime_seconds(self) -> int:
        """Return combined physical runtime."""
        return self.service_runtime_seconds + self.test_runtime_seconds

    @property
    def collateral_runtime_seconds(self) -> int:
        """Return only service runtime attributed to a named outage."""
        return self.service_runtime_seconds if self.attributed_outage_episode_id is not None else 0


@dataclass(frozen=True, slots=True)
class PumpStationCoupledOperatingInterval:
    """Authoritative coupled interval with service and per-pump physical deltas."""

    start_calendar_seconds: int
    end_calendar_seconds: int
    required_service_scu: int
    baseline_assignment_pump_ids: tuple[str, ...]
    actual_assignment_pump_ids: tuple[str, ...]
    service_running_pump_ids: tuple[str, ...]
    test_running_pump_ids: tuple[str, ...]
    pump_deltas: tuple[PumpStationOperatingDelta, PumpStationOperatingDelta, PumpStationOperatingDelta]

    def __post_init__(self) -> None:
        elapsed = self.end_calendar_seconds - self.start_calendar_seconds
        service = set(self.service_running_pump_ids)
        test = set(self.test_running_pump_ids)
        if elapsed <= 0 or self.required_service_scu not in {1, 2}:
            _fail("coupled-operating-interval", "time or service requirement is invalid")
        if service & test or len(service | test) > 2:
            _fail("coupled-operating-interval", "physical running sets are invalid")
        if len({delta.pump_id for delta in self.pump_deltas}) != 3:
            _fail("coupled-operating-interval", "one delta per distinct pump is required")
        for delta in self.pump_deltas:
            expected_service = elapsed if delta.pump_id in service else 0
            expected_test = elapsed if delta.pump_id in test else 0
            if delta.service_runtime_seconds != expected_service or delta.test_runtime_seconds != expected_test:
                _fail("coupled-operating-interval", f"{delta.pump_id} runtime differs from its running set")

    @property
    def elapsed_seconds(self) -> int:
        """Return interval duration."""
        return self.end_calendar_seconds - self.start_calendar_seconds

    def pump_delta(self, pump_id: str) -> PumpStationOperatingDelta:
        """Return one pump delta by identity."""
        for delta in self.pump_deltas:
            if delta.pump_id == pump_id:
                return delta
        _fail("unknown-pump", pump_id)
