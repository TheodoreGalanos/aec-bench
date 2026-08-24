# ABOUTME: Implements the causal dam seepage monitoring task and actor-visible projection.
# ABOUTME: Uses site-specific synthetic limits without granting emergency or dam-safety authority.

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition, TransitionResult

DAM_SEEPAGE_TASK_WORLD_ID = "dam-seepage-monitoring"


class DownstreamCondition(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    SEDIMENT_OBSERVED = "sediment-observed"
    NEW_SEEP = "new-seep"


class InstrumentCondition(StrEnum):
    SERVICEABLE = "serviceable"
    UNRELIABLE = "unreliable"


class FlowStatus(StrEnum):
    EXPECTED = "expected"
    ABOVE_EXPECTED = "above-expected"
    ABOVE_ALERT = "above-alert"


class SeepageResponse(StrEnum):
    ENGINEERING_REVIEW = "engineering-review"
    ROUTINE_SURVEILLANCE = "routine-surveillance"


class SeepageAction(StrEnum):
    RECORD_CONFIRMATION_READING = "record-confirmation-reading"
    CHECK_MEASUREMENT_SYSTEM = "check-measurement-system"
    INSPECT_DOWNSTREAM_AREA = "inspect-downstream-area"
    ESCALATE_FOR_ENGINEERING_REVIEW = "escalate-for-engineering-review"
    CONTINUE_ROUTINE_SURVEILLANCE = "continue-routine-surveillance"


class SeepageReading(FrozenStrictModel):
    elapsed_hours: int = Field(ge=0)
    reservoir_level_m: float
    recent_rainfall_mm: float = Field(ge=0.0)
    expected_flow_l_min: float = Field(gt=0.0)
    alert_flow_l_min: float = Field(gt=0.0)
    measured_flow_l_min: float = Field(ge=0.0)
    downstream_condition: DownstreamCondition

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.alert_flow_l_min < self.expected_flow_l_min:
            raise ValueError("seepage alert flow must not be below expected flow")
        return self


class SeepageScenario(FrozenStrictModel):
    task_world_id: Literal["dam-seepage-monitoring"]
    profile_id: NonEmptyStr
    monitoring_point_id: NonEmptyStr
    objective: NonEmptyStr
    baseline_note: NonEmptyStr
    required_consecutive_alert_readings: int = Field(ge=1)
    visual_alert_conditions: tuple[DownstreamCondition, ...]
    instrument_condition: InstrumentCondition
    readings: tuple[SeepageReading, ...]

    @model_validator(mode="after")
    def validate_scenario(self) -> Self:
        if len(self.readings) < 2:
            raise ValueError("seepage scenario requires at least two readings")
        if self.required_consecutive_alert_readings > len(self.readings):
            raise ValueError("required consecutive alerts exceed the reading count")
        elapsed_hours = tuple(reading.elapsed_hours for reading in self.readings)
        if any(later <= earlier for earlier, later in pairwise(elapsed_hours)):
            raise ValueError("seepage reading times must increase")
        if not self.visual_alert_conditions:
            raise ValueError("seepage scenario requires at least one visual alert condition")
        if len(self.visual_alert_conditions) != len(set(self.visual_alert_conditions)):
            raise ValueError("seepage visual alert conditions must be distinct")
        return self


@dataclass(frozen=True, slots=True)
class SeepageState:
    scenario: SeepageScenario
    reading_index: int = 0
    measurement_system_checked: bool = False
    inspected_reading_indexes: tuple[int, ...] = ()
    response: SeepageResponse | None = None


@dataclass(frozen=True, slots=True)
class PublicSeepageReading:
    sequence: int
    elapsed_hours: int
    reservoir_level_m: float
    recent_rainfall_mm: float
    expected_flow_l_min: float
    alert_flow_l_min: float
    measured_flow_l_min: float
    flow_status: FlowStatus
    downstream_condition: DownstreamCondition | None


@dataclass(frozen=True, slots=True)
class SeepageObservation:
    profile_id: str
    monitoring_point_id: str
    objective: str
    baseline_note: str
    required_consecutive_alert_readings: int
    visual_alert_conditions: tuple[DownstreamCondition, ...]
    readings: tuple[PublicSeepageReading, ...]
    scheduled_readings_remaining: int
    instrument_condition: InstrumentCondition | None
    response: SeepageResponse | None


@dataclass(frozen=True, slots=True)
class SeepageActionResult:
    action: SeepageAction
    detail: str


@dataclass(frozen=True, slots=True)
class SeepageEvaluation:
    assessment_submitted: bool
    selected_response: SeepageResponse | None
    required_response: SeepageResponse
    response_correct: bool
    all_scheduled_readings_reviewed: bool
    measurement_system_checked: bool
    latest_downstream_area_inspected: bool
    evidence_complete: bool
    successful: bool


def initial_state(scenario: SeepageScenario) -> SeepageState:
    """Create the exact opening state for one task-owned monitoring scenario."""
    return SeepageState(scenario=scenario)


def _flow_status(reading: SeepageReading) -> FlowStatus:
    if reading.measured_flow_l_min >= reading.alert_flow_l_min:
        return FlowStatus.ABOVE_ALERT
    if reading.measured_flow_l_min > reading.expected_flow_l_min:
        return FlowStatus.ABOVE_EXPECTED
    return FlowStatus.EXPECTED


def observe(state: SeepageState) -> SeepageObservation:
    """Project only released readings and requested field checks to the actor."""
    readings = tuple(
        PublicSeepageReading(
            sequence=index + 1,
            elapsed_hours=reading.elapsed_hours,
            reservoir_level_m=reading.reservoir_level_m,
            recent_rainfall_mm=reading.recent_rainfall_mm,
            expected_flow_l_min=reading.expected_flow_l_min,
            alert_flow_l_min=reading.alert_flow_l_min,
            measured_flow_l_min=reading.measured_flow_l_min,
            flow_status=_flow_status(reading),
            downstream_condition=(reading.downstream_condition if index in state.inspected_reading_indexes else None),
        )
        for index, reading in enumerate(state.scenario.readings[: state.reading_index + 1])
    )
    return SeepageObservation(
        profile_id=state.scenario.profile_id,
        monitoring_point_id=state.scenario.monitoring_point_id,
        objective=state.scenario.objective,
        baseline_note=state.scenario.baseline_note,
        required_consecutive_alert_readings=state.scenario.required_consecutive_alert_readings,
        visual_alert_conditions=state.scenario.visual_alert_conditions,
        readings=readings,
        scheduled_readings_remaining=len(state.scenario.readings) - state.reading_index - 1,
        instrument_condition=(state.scenario.instrument_condition if state.measurement_system_checked else None),
        response=state.response,
    )


def available_actions(state: SeepageState) -> tuple[SeepageAction, ...]:
    """Return the task actions that are available from the current state."""
    if state.response is not None:
        return ()
    actions: list[SeepageAction] = []
    if state.reading_index + 1 < len(state.scenario.readings):
        actions.append(SeepageAction.RECORD_CONFIRMATION_READING)
    if not state.measurement_system_checked:
        actions.append(SeepageAction.CHECK_MEASUREMENT_SYSTEM)
    if state.reading_index not in state.inspected_reading_indexes:
        actions.append(SeepageAction.INSPECT_DOWNSTREAM_AREA)
    actions.extend(
        (
            SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW,
            SeepageAction.CONTINUE_ROUTINE_SURVEILLANCE,
        )
    )
    return tuple(actions)


def _accepted(
    state: SeepageState,
    action: SeepageAction,
    detail: str,
    *,
    termination_reason: str | None = None,
) -> Transition[SeepageState, SeepageActionResult]:
    return Transition(
        state=state,
        output=SeepageActionResult(action=action, detail=detail),
        termination_reason=termination_reason,
    )


def transition(
    state: SeepageState,
    action: SeepageAction,
) -> TransitionResult[SeepageState, SeepageActionResult]:
    """Apply one task action without persistence, episode advancement, or scoring."""
    if state.response is not None:
        return ActionRejected("world-terminated", "the seepage assessment is already submitted")
    if not isinstance(action, SeepageAction):
        return ActionRejected("action-unknown", "the seepage action is not supported")

    if action is SeepageAction.RECORD_CONFIRMATION_READING:
        if state.reading_index + 1 >= len(state.scenario.readings):
            return ActionRejected("action-unavailable", "no scheduled confirmation reading remains")
        next_index = state.reading_index + 1
        return _accepted(
            replace(state, reading_index=next_index),
            action,
            f"released scheduled seepage reading {next_index + 1}",
        )

    if action is SeepageAction.CHECK_MEASUREMENT_SYSTEM:
        if state.measurement_system_checked:
            return ActionRejected("action-unavailable", "the measurement system was already checked")
        return _accepted(
            replace(state, measurement_system_checked=True),
            action,
            "released the task-owned measurement-system check",
        )

    if action is SeepageAction.INSPECT_DOWNSTREAM_AREA:
        if state.reading_index in state.inspected_reading_indexes:
            return ActionRejected("action-unavailable", "the current downstream condition was already inspected")
        return _accepted(
            replace(
                state,
                inspected_reading_indexes=(*state.inspected_reading_indexes, state.reading_index),
            ),
            action,
            f"released the downstream condition for reading {state.reading_index + 1}",
        )

    response = (
        SeepageResponse.ENGINEERING_REVIEW
        if action is SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW
        else SeepageResponse.ROUTINE_SURVEILLANCE
    )
    return _accepted(
        replace(state, response=response),
        action,
        f"submitted {response.value} as the monitoring response",
        termination_reason="assessment-submitted",
    )


def requires_engineering_review(scenario: SeepageScenario) -> bool:
    if scenario.instrument_condition is InstrumentCondition.UNRELIABLE:
        return True

    consecutive_alerts = 0
    for reading in scenario.readings:
        if reading.downstream_condition in scenario.visual_alert_conditions:
            return True
        if reading.measured_flow_l_min >= reading.alert_flow_l_min:
            consecutive_alerts += 1
            if consecutive_alerts >= scenario.required_consecutive_alert_readings:
                return True
        else:
            consecutive_alerts = 0
    return False


def _released_evidence_requires_engineering_review(state: SeepageState) -> bool:
    if state.measurement_system_checked and state.scenario.instrument_condition is InstrumentCondition.UNRELIABLE:
        return True

    consecutive_alerts = 0
    for index, reading in enumerate(state.scenario.readings[: state.reading_index + 1]):
        if (
            index in state.inspected_reading_indexes
            and reading.downstream_condition in state.scenario.visual_alert_conditions
        ):
            return True
        if reading.measured_flow_l_min >= reading.alert_flow_l_min:
            consecutive_alerts += 1
            if consecutive_alerts >= state.scenario.required_consecutive_alert_readings:
                return True
        else:
            consecutive_alerts = 0
    return False


def evaluate(state: SeepageState) -> SeepageEvaluation:
    """Evaluate the submitted response from canonical task state outside transition."""
    required_response = (
        SeepageResponse.ENGINEERING_REVIEW
        if requires_engineering_review(state.scenario)
        else SeepageResponse.ROUTINE_SURVEILLANCE
    )
    all_readings_reviewed = state.reading_index == len(state.scenario.readings) - 1
    latest_inspected = state.reading_index in state.inspected_reading_indexes
    evidence_complete = (
        _released_evidence_requires_engineering_review(state)
        if state.response is SeepageResponse.ENGINEERING_REVIEW
        else all_readings_reviewed and state.measurement_system_checked and latest_inspected
    )
    response_correct = state.response is not None and state.response is required_response
    return SeepageEvaluation(
        assessment_submitted=state.response is not None,
        selected_response=state.response,
        required_response=required_response,
        response_correct=response_correct,
        all_scheduled_readings_reviewed=all_readings_reviewed,
        measurement_system_checked=state.measurement_system_checked,
        latest_downstream_area_inspected=latest_inspected,
        evidence_complete=evidence_complete,
        successful=response_correct and evidence_complete,
    )
