# ABOUTME: Exercises ASW-6A sensor evidence and physical-inspection separation.
# ABOUTME: Proves version 3 projections expose health facts without private treatment state.

from __future__ import annotations

from dataclasses import replace

import pytest
from rich_work_support import apply_bound

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PUMP_STATION_RECEIPT_VERSION_V3,
    PUMP_STATION_STATE_VERSION_V3,
    PumpStationActorView,
    PumpStationAuthorityOutcome,
    PumpStationEvidenceKind,
    PumpStationEvidenceQuality,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationEvidenceTreatmentStatus,
    PumpStationEvidenceView,
    PumpStationExecutionOutcome,
    PumpStationModel,
    PumpStationObservationSourceView,
    PumpStationProjectionContext,
    PumpStationSchedule,
    PumpStationStewardshipState,
    PumpStationTransition,
    ReferencePackage,
    RequestConditionCheck,
    RequestObstructionClearance,
    advance_to_next_decision_point,
    apply_evidence_treatment_schedule,
    create_evidence_health_reference_state,
    load_reference_package,
    project_actor_view,
    pump_station_artifact_bytes,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id,
)


def _reference_state() -> tuple[
    ReferencePackage,
    PumpStationModel,
    PumpStationStewardshipState,
]:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_evidence_health_reference_state(
        model,
        schedule=PumpStationSchedule(
            access_available_after_seconds=86_400,
            repair_kit_available_after_seconds=86_400,
            decision_point_after_seconds=(3_600, 32_401),
        ),
    )
    return package, model, state


def _view(
    package: ReferencePackage,
    model: PumpStationModel,
    state: PumpStationStewardshipState,
) -> PumpStationActorView:
    return project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-evidence-health",
            world_branch_id="branch-evidence-health",
            actor_id="station-steward",
            agent_tenure_id="tenure-evidence-health",
            episode_started_at_seconds=state.physical.calendar_seconds,
            tenure_started_at_seconds=state.physical.calendar_seconds,
            projection_policy_id="pump-station-current-state.v3",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
            ),
        ),
    )


def _schedule_treatment(
    state: PumpStationStewardshipState,
    treatment_class: PumpStationEvidenceTreatmentClass,
) -> PumpStationTransition:
    next_decision_point = min(
        event.scheduled_seconds for event in state.scheduled_events if event.event_type.value == "decision_point"
    )
    request = PumpStationEvidenceTreatmentRequest(
        request_id=f"request-{treatment_class.value}",
        run_id="run-evidence-health",
        episode_id="episode-evidence-health",
        world_branch_id="branch-evidence-health",
        base_state_id=stewardship_state_id(state),
        base_commit_id="commit-before-treatment",
        based_on_sequence=state.sequence,
        treatment_class=treatment_class,
        treatment_version=PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        target_source_id="station-condition-sensor",
        effective_decision_point_seconds=next_decision_point,
        visibility_policy=PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    )
    return apply_evidence_treatment_schedule(state, request)


def test_version_three_projection_exposes_source_and_evidence_health_only() -> None:
    package, model, state = _reference_state()

    view = _view(package, model, state)
    source = view.current_state.observation_source
    evidence = view.current_state.evidence[0]
    public_bytes = pump_station_artifact_bytes(view)

    assert state.state_version == PUMP_STATION_STATE_VERSION_V3
    assert isinstance(source, PumpStationObservationSourceView)
    assert source.age_seconds == 0
    assert source.quality is PumpStationEvidenceQuality.CURRENT
    assert source.observation == view.current_state.observation
    assert source.component_scope == ("pump-a", "pump-b")
    assert isinstance(evidence, PumpStationEvidenceView)
    assert evidence.age_seconds == 0
    assert evidence.source_id == "maintenance-functional-checks"
    assert evidence.accepted is True
    assert b"evidence_treatments" not in public_bytes
    assert b"treatment_class" not in public_bytes
    assert b"refresh_enabled" not in public_bytes
    assert b"reading_available" not in public_bytes


def test_condition_check_creates_sensor_evidence_but_cannot_authorize_clearance() -> None:
    _, model, state = _reference_state()

    checked = apply_bound(
        model,
        state,
        RequestConditionCheck,
        "proposal-condition-check",
        pump_id="pump-a",
    )
    condition_evidence = checked.state.evidence[-1]
    clearance = apply_bound(
        model,
        checked.state,
        RequestObstructionClearance,
        "proposal-clearance-from-sensor",
        pump_id="pump-a",
        inspection_evidence_id=condition_evidence.evidence_id,
    )

    assert checked.receipt.receipt_version == PUMP_STATION_RECEIPT_VERSION_V3
    assert condition_evidence.kind is PumpStationEvidenceKind.CONDITION_CHECK
    assert condition_evidence.condition_observation is not None
    assert condition_evidence.health is not None
    assert condition_evidence.health.source_id == "station-condition-sensor"
    assert condition_evidence.health.component_scope == ("pump-a",)
    assert clearance.receipt.authority is not None
    assert clearance.receipt.authority.outcome is PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES
    assert clearance.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert clearance.state.physical == checked.state.physical


def test_repeated_condition_check_supersedes_the_prior_sensor_record() -> None:
    _, model, state = _reference_state()
    first = apply_bound(
        model,
        state,
        RequestConditionCheck,
        "proposal-condition-first",
        pump_id="pump-a",
    )
    second = apply_bound(
        model,
        first.state,
        RequestConditionCheck,
        "proposal-condition-second",
        pump_id="pump-a",
    )

    first_evidence = first.state.evidence[-1]
    second_evidence = second.state.evidence[-1]
    assert second_evidence.health is not None
    assert second_evidence.health.supersedes_evidence_id == first_evidence.evidence_id


def test_version_three_view_age_is_computed_without_mutating_state() -> None:
    package, model, state = _reference_state()
    source = state.evidence_sources[0]
    later = replace(
        state,
        physical=replace(
            state.physical,
            calendar_seconds=source.observed_at_seconds + 28_801,
        ),
    )

    view = _view(package, model, later)

    assert view.current_state.observation_source is not None
    assert view.current_state.observation_source.age_seconds == 28_801
    assert view.current_state.observation_source.quality is PumpStationEvidenceQuality.SUSPECT
    assert state.evidence_sources[0].quality is PumpStationEvidenceQuality.CURRENT


@pytest.mark.parametrize(
    ("treatment_class", "expected_quality", "observation_available"),
    (
        (
            PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
            PumpStationEvidenceQuality.SUSPECT,
            True,
        ),
        (
            PumpStationEvidenceTreatmentClass.OBSERVATION_LOSS,
            PumpStationEvidenceQuality.UNAVAILABLE,
            False,
        ),
    ),
)
def test_source_treatments_activate_at_the_next_decision_point(
    treatment_class: PumpStationEvidenceTreatmentClass,
    expected_quality: PumpStationEvidenceQuality,
    observation_available: bool,
) -> None:
    package, model, state = _reference_state()

    scheduled = _schedule_treatment(state, treatment_class)
    activated = advance_to_next_decision_point(model, scheduled.state)
    view = _view(package, model, activated.state)
    source = view.current_state.observation_source

    assert scheduled.receipt.clock_delta_seconds == 0
    assert scheduled.state.physical == state.physical
    assert scheduled.state.evidence_treatments[0].status is PumpStationEvidenceTreatmentStatus.SCHEDULED
    assert activated.state.evidence_treatments[0].status is PumpStationEvidenceTreatmentStatus.ACTIVE
    assert source is not None
    assert source.quality is expected_quality
    assert (source.observation is not None) is observation_available
    assert b"treatment_class" not in pump_station_artifact_bytes(view)
    assert b"effective_decision_point_seconds" not in pump_station_artifact_bytes(view)


def test_stale_sample_holds_the_original_reading_until_age_exceeds_threshold() -> None:
    package, model, state = _reference_state()
    original_source = state.evidence_sources[0]

    scheduled = _schedule_treatment(
        state,
        PumpStationEvidenceTreatmentClass.STALE_SAMPLE,
    )
    activated = advance_to_next_decision_point(model, scheduled.state)
    first_view = _view(package, model, activated.state)
    aged = advance_to_next_decision_point(model, activated.state)
    aged_view = _view(package, model, aged.state)

    assert first_view.current_state.observation_source is not None
    assert first_view.current_state.observation_source.observed_at_seconds == (original_source.observed_at_seconds)
    assert first_view.current_state.observation_source.quality is PumpStationEvidenceQuality.CURRENT
    assert aged_view.current_state.observation_source is not None
    assert aged_view.current_state.observation_source.age_seconds == 32_401
    assert aged_view.current_state.observation_source.quality is PumpStationEvidenceQuality.SUSPECT


def test_baseline_change_marks_old_sensor_evidence_not_applicable() -> None:
    package, model, state = _reference_state()
    checked = apply_bound(
        model,
        state,
        RequestConditionCheck,
        "proposal-before-baseline",
        pump_id="pump-a",
    )

    scheduled = _schedule_treatment(
        checked.state,
        PumpStationEvidenceTreatmentClass.BASELINE_CHANGE,
    )
    activated = advance_to_next_decision_point(model, scheduled.state)
    view = _view(package, model, activated.state)
    earlier = next(
        item for item in view.current_state.evidence if item.evidence_id == checked.state.evidence[-1].evidence_id
    )

    assert isinstance(earlier, PumpStationEvidenceView)
    assert view.current_state.observation_source is not None
    assert view.current_state.observation_source.baseline_id == "station-condition-baseline.v2"
    assert earlier.baseline_id == "station-condition-baseline.v1"
    assert earlier.applicable is False
    assert earlier.quality is PumpStationEvidenceQuality.SUSPECT


def test_evidence_delay_hides_one_record_for_exactly_28800_seconds() -> None:
    package, model, state = _reference_state()
    scheduled = _schedule_treatment(
        state,
        PumpStationEvidenceTreatmentClass.EVIDENCE_DELAY,
    )
    activated = advance_to_next_decision_point(model, scheduled.state)
    checked = apply_bound(
        model,
        activated.state,
        RequestConditionCheck,
        "proposal-delayed-condition",
        pump_id="pump-a",
    )
    hidden_id = checked.state.pending_evidence[0].evidence.evidence_id

    assert all(item.evidence_id != hidden_id for item in _view(package, model, checked.state).current_state.evidence)
    released = advance_to_next_decision_point(model, checked.state)
    released_item = next(
        item for item in _view(package, model, released.state).current_state.evidence if item.evidence_id == hidden_id
    )

    assert released.receipt.clock_delta_seconds == 28_800
    assert isinstance(released_item, PumpStationEvidenceView)
    assert released_item.available_at_seconds - released_item.produced_at_seconds == 28_800
    assert released_item.age_seconds == 28_800
    assert released_item.quality is PumpStationEvidenceQuality.CURRENT
    assert released.state.pending_evidence == ()


def test_contradictory_report_keeps_both_claims_and_their_relation() -> None:
    _, model, state = _reference_state()
    scheduled = _schedule_treatment(
        state,
        PumpStationEvidenceTreatmentClass.CONTRADICTORY_REPORT,
    )
    activated = advance_to_next_decision_point(model, scheduled.state)
    checked = apply_bound(
        model,
        activated.state,
        RequestConditionCheck,
        "proposal-contradictory-condition",
        pump_id="pump-a",
    )
    original, contradiction = checked.state.evidence[-2:]

    assert original.passed is not None
    assert contradiction.passed is (not original.passed)
    assert original.health is not None
    assert original.health.accepted is True
    assert contradiction.health is not None
    assert contradiction.health.accepted is False
    assert contradiction.health.quality is PumpStationEvidenceQuality.SUSPECT
    assert contradiction.health.contradicts_evidence_id == original.evidence_id
    assert checked.state.evidence_treatments[0].status is PumpStationEvidenceTreatmentStatus.APPLIED
