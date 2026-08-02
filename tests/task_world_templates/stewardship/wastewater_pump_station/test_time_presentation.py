# ABOUTME: Tests human-readable pump-station dates, durations, and clock deadlines.
# ABOUTME: Proves actor time is clear while replay clocks remain exact and backward compatible.

from __future__ import annotations

import json
from dataclasses import replace

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_TIME_PROJECTION_POLICY_ID,
    ContinueOperation,
    ProposalContext,
    PumpStationActorView,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEventType,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationRunStep,
    PumpStationWorldSessionFactory,
    advance_to_next_decision_point,
    apply_stewardship_proposal,
    bind_information_set,
    create_evidence_health_reference_state,
    load_pump_station_artifact,
    load_reference_package,
    project_actor_view,
    pump_station_artifact_bytes,
    pump_station_model_from_package,
    verify_stewardship_run,
)


def _reference():
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_evidence_health_reference_state(model)
    return package, model, state


def _context(package, state, projection_policy_id: str) -> PumpStationProjectionContext:
    return PumpStationProjectionContext(
        episode_id="episode-time",
        world_branch_id="branch-time",
        actor_id="station-steward",
        agent_tenure_id="tenure-time",
        episode_started_at_seconds=state.physical.calendar_seconds,
        tenure_started_at_seconds=state.physical.calendar_seconds,
        projection_policy_id=projection_policy_id,
        source_artifact_ids=(
            package.package_content_id,
            package.manifest_content_id,
        ),
    )


def test_actor_time_context_uses_dates_and_domain_durations() -> None:
    package, model, state = _reference()

    view = project_actor_view(
        model,
        state,
        _context(package, state, PUMP_STATION_TIME_PROJECTION_POLICY_ID),
    )

    time = view.time_context
    assert time is not None
    assert time.time_zone == "Australia/Sydney"
    assert time.calendar_origin_datetime == "2026-01-01T00:00:00+11:00"
    assert time.current_datetime == "2026-03-25T08:00:00+11:00"
    assert time.calendar_elapsed == "83 days 8 hours"
    assert time.episode_elapsed == "0 seconds"
    assert time.tenure_elapsed == "0 seconds"
    assert {item.pump_id: item.runtime for item in time.pump_runtimes} == {
        "pump-a": "0 operating hours",
        "pump-b": "2,000 operating hours",
    }

    obligation = time.obligations[0]
    assert obligation.calendar_deadline == "2026-03-28T16:00:00+11:00"
    assert obligation.calendar_remaining == "3 days 8 hours"
    assert obligation.runtime_limit == "80 operating hours"
    assert obligation.runtime_remaining == "80 operating hours"
    assert obligation.due_rule == "calendar deadline or pump runtime limit, whichever occurs first"
    assert obligation.status is PumpStationObligationStatus.ACTIVE

    process = next(item for item in time.processes if item.process_id == "process-0000-access-preparation")
    assert process.completion_time == "2026-04-08T07:00:00+10:00"
    assert process.time_remaining == "14 days"

    payload = pump_station_artifact_bytes(view)
    restored = load_pump_station_artifact(payload, PumpStationActorView)
    assert restored == view
    assert json.loads(payload)["time_context"]["current_datetime"] == time.current_datetime


def test_version_three_actor_view_remains_byte_compatible() -> None:
    package, model, state = _reference()

    view = project_actor_view(
        model,
        state,
        _context(package, state, "pump-station-current-state.v3"),
    )
    payload = pump_station_artifact_bytes(view)

    assert view.time_context is None
    assert "time_context" not in json.loads(payload)
    assert load_pump_station_artifact(payload, PumpStationActorView) == view


def _clock_limited_state(*, running: bool):
    _, model, state = _reference()
    obligation = state.obligations[0]
    pump = state.physical.pump(obligation.pump_id)
    now = state.physical.calendar_seconds
    obligation = replace(
        obligation,
        due_calendar_seconds=now + 100,
        due_runtime_seconds=pump.exposure.runtime_seconds + 10,
    )
    events = tuple(
        replace(
            event,
            scheduled_seconds=(
                now + 100
                if event.event_type is PumpStationEventType.OBLIGATION_DUE
                else now + 101
                if event.event_type is PumpStationEventType.OBLIGATION_OVERDUE
                else now + 100 + model.inflow.diagnostic_period_seconds
            ),
        )
        if event.obligation_id == obligation.obligation_id
        else event
        for event in state.scheduled_events
    )
    physical = state.physical
    if running:
        physical = replace(
            physical,
            duty_pump_id=obligation.pump_id,
            standby_pump_id=next(pump_id for pump_id in model.pump_ids if pump_id != obligation.pump_id),
        )
    return model, replace(
        state,
        physical=physical,
        obligations=(obligation,),
        scheduled_events=tuple(sorted(events, key=lambda item: (item.scheduled_seconds, item.event_id))),
    )


def test_running_pump_runtime_limit_triggers_due_and_overdue_events() -> None:
    model, state = _clock_limited_state(running=True)
    obligation = state.obligations[0]

    due = advance_to_next_decision_point(model, state)
    due_obligation = due.state.obligation(obligation.kind, obligation.pump_id)

    assert due.receipt.clock_delta_seconds == 10
    assert due.receipt.applied_event_types == (PumpStationEventType.OBLIGATION_DUE,)
    assert due_obligation.status is PumpStationObligationStatus.DUE
    assert due.state.physical.pump(obligation.pump_id).exposure.runtime_seconds == obligation.due_runtime_seconds

    overdue = advance_to_next_decision_point(model, due.state)
    overdue_obligation = overdue.state.obligation(obligation.kind, obligation.pump_id)
    assert overdue.receipt.clock_delta_seconds == 1
    assert overdue.receipt.applied_event_types == (PumpStationEventType.OBLIGATION_OVERDUE,)
    assert overdue_obligation.status is PumpStationObligationStatus.OVERDUE


def test_standby_pump_runtime_limit_waits_for_calendar_deadline() -> None:
    model, state = _clock_limited_state(running=False)
    obligation = state.obligations[0]
    before_runtime = state.physical.pump(obligation.pump_id).exposure.runtime_seconds

    due = advance_to_next_decision_point(model, state)
    due_obligation = due.state.obligation(obligation.kind, obligation.pump_id)

    assert due.receipt.clock_delta_seconds == 100
    assert due_obligation.status is PumpStationObligationStatus.DUE
    assert due.state.physical.pump(obligation.pump_id).exposure.runtime_seconds == before_runtime


def test_runtime_deadline_replays_from_the_bound_actor_action() -> None:
    package = load_reference_package()
    model, state = _clock_limited_state(running=True)
    projection = _context(
        package,
        state,
        PUMP_STATION_TIME_PROJECTION_POLICY_ID,
    )
    view = project_actor_view(model, state, projection)
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=projection.agent_tenure_id,
            view_ids=(view.view_id,),
        ),
        PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=("continue_operation",),
            visible_material_ids=(),
        ),
    )
    proposal = ContinueOperation(
        context=ProposalContext(
            proposal_id="proposal-runtime-deadline",
            agent_tenure_id=projection.agent_tenure_id,
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Continue to the first calendar or operating limit.",
        )
    )

    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )
    report = verify_stewardship_run(
        model,
        state,
        (
            PumpStationRunStep(
                proposal=proposal,
                information_set=information_set,
                transition=transition,
            ),
        ),
    )

    assert transition.receipt.clock_delta_seconds == 10
    assert report.valid is True
    assert report.issues == ()
    assert report.final_state_id == transition.receipt.post_state_id


def test_world_session_exposes_time_context_to_the_agent(tmp_path) -> None:
    session = PumpStationWorldSessionFactory(tmp_path / "run", evidence_health=True).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session-time",
            task_world_id="wastewater-pump-station-stewardship.v1",
            agent_tenure_id="tenure-time",
            run_id="run-time",
            episode_id="episode-time",
            world_branch_id="branch-time",
        )
    )

    document = json.loads(session.observe_pump_station())
    assert document["projection_policy_id"] == PUMP_STATION_TIME_PROJECTION_POLICY_ID
    assert document["time_context"]["current_datetime"] == "2026-03-25T08:00:00+11:00"
    assert document["time_context"]["obligations"][0]["calendar_remaining"] == "3 days 8 hours"
