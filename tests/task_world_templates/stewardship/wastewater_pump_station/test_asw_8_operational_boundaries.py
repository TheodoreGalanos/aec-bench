# ABOUTME: Tests ASW-8 generation, interruption, failure, and common-boundary rules.
# ABOUTME: Covers the negative paths that the successful Day 0 to Day 2 journey does not enter.

from __future__ import annotations

from dataclasses import replace

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    create_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldError,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationAvailabilityInterval,
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationCoupledProcessStatus,
    PumpStationDeclaredWorkTrigger,
    PumpStationPriority,
    PumpStationReusablePool,
    PumpStationWorkGenerationRecord,
    apply_declared_work_generation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PUMP_STATION_PROCESS_OUTCOME_VERSION,
    PumpStationCommonBoundaryRequest,
    PumpStationProcessOutcomeRequest,
)


def _actor(
    run: PumpStationCoupledRun,
    request_id: str,
    action_name: str,
    **arguments: object,
) -> PumpStationCoupledRun:
    return run.apply_actor(
        request_id=request_id,
        action_name=action_name,
        arguments={"reason": f"Apply {request_id} under the visible rules.", **arguments},
    )


def test_all_declared_generation_rules_create_or_retain_exact_work() -> None:
    records: tuple[PumpStationWorkGenerationRecord, ...] = ()
    backlog: tuple[PumpStationBacklogItem, ...] = ()
    for ordinal, rule_id in enumerate(
        ("WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06", "WG-07"),
        start=1,
    ):
        result = apply_declared_work_generation(
            records,
            backlog,
            PumpStationDeclaredWorkTrigger(
                rule_id=rule_id,
                source_transition_id=f"source-{rule_id}",
                target_kind="resource_pool" if rule_id == "WG-06" else "asset",
                target_id="obstruction-clearance-kit" if rule_id == "WG-06" else "pump-c",
                generation_ordinal=ordinal,
                generated_at_calendar_seconds=100_000,
                current_runtime_seconds=20_000,
                next_capacity_critical_calendar_seconds=120_000,
                linked_clearance_due_calendar_seconds=130_000,
                target_is_serving=rule_id == "WG-05",
                blocks_urgent_work=rule_id == "WG-06",
            ),
        )
        records, backlog = result.records, result.backlog
    assert tuple(record.rule_id for record in records) == (
        "WG-01",
        "WG-02",
        "WG-03",
        "WG-04",
        "WG-05",
        "WG-06",
        "WG-07",
    )
    assert next(item for item in backlog if item.generation_rule_id == "WG-05").base_priority is PumpStationPriority.P0
    assert next(item for item in backlog if item.generation_rule_id == "WG-06").base_priority is PumpStationPriority.P1
    selected = backlog[2]
    suspended = apply_declared_work_generation(
        records,
        backlog,
        PumpStationDeclaredWorkTrigger(
            rule_id="WG-08",
            source_transition_id="suspend-source",
            target_kind=selected.target_kind,
            target_id=selected.target_id,
            generation_ordinal=1,
            generated_at_calendar_seconds=110_000,
            existing_item_id=selected.item_id,
        ),
    )
    blocked = next(item for item in suspended.backlog if item.item_id == selected.item_id)
    assert blocked.status is PumpStationBacklogStatus.BLOCKED
    cancelled = apply_declared_work_generation(
        suspended.records,
        suspended.backlog,
        PumpStationDeclaredWorkTrigger(
            rule_id="WG-09",
            source_transition_id="cancel-source",
            target_kind=selected.target_kind,
            target_id=selected.target_id,
            generation_ordinal=1,
            generated_at_calendar_seconds=120_000,
            existing_item_id=selected.item_id,
        ),
    )
    replanned = next(item for item in cancelled.backlog if item.item_id == selected.item_id)
    assert replanned.status is PumpStationBacklogStatus.PLANNED
    assert cancelled.records == records
    assert len(cancelled.backlog) == 7


def test_safety_event_suspends_then_resume_uses_remaining_duration() -> None:
    run = create_coupled_run(
        run_id="suspend-resume",
        world_branch_id="branch-suspend-resume",
    )
    run = _actor(
        run,
        "late-b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = run.state.processes[-1].process_id
    run = run.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="suspending-power-stop",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=run.state.state_id,
        )
    )
    process = next(value for value in run.state.processes if value.process_id == process_id)
    assert process.status is PumpStationCoupledProcessStatus.SUSPENDED
    assert process.remaining_duration_seconds == 14_400
    run = run.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="suspending-power-restore",
            authority_id="operations-controller",
            boundary_kind="power",
            available=True,
            base_state_id=run.state.state_id,
        )
    )
    run = _actor(run, "resume-b-clearance", "resume_process", process_id=process_id)
    resumed = next(value for value in run.state.processes if value.process_id == process_id)
    assert resumed.due_at_calendar_seconds == 36_000
    run = _actor(run, "complete-resumed-clearance", "continue_operation")
    assert run.state.calendar_seconds == 36_000
    completed = next(value for value in run.state.processes if value.process_id == process_id)
    assert completed.status is PumpStationCoupledProcessStatus.COMPLETED
    assert verify_coupled_run(run).replay_valid is True


def test_resource_withdrawal_wins_over_same_time_process_completion() -> None:
    run = create_coupled_run(
        run_id="same-time-withdrawal",
        world_branch_id="branch-same-time-withdrawal",
    )
    run = replace(
        run,
        state=replace(
            run.state,
            physical=replace(run.state.physical, calendar_seconds=46_800),
        ),
    )
    opening_obstruction = run.state.physical.pump("pump-b").condition.obstruction
    run = _actor(
        run,
        "same-time-b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )

    run = _actor(
        run,
        "continue-to-withdrawal",
        "continue_operation",
    )

    process = run.state.processes[-1]
    assert run.state.calendar_seconds == 61_200
    assert process.status is PumpStationCoupledProcessStatus.SUSPENDED
    assert run.state.backlog_item("backlog-b-clearance-001").status is PumpStationBacklogStatus.BLOCKED
    assert run.state.physical.pump("pump-b").condition.obstruction == opening_obstruction


def test_field_process_start_and_resume_recheck_visible_assured_capacity() -> None:
    extended_window = (PumpStationAvailabilityInterval(21_600, 93_600),)

    def at_capacity_boundary(
        run: PumpStationCoupledRun,
    ) -> PumpStationCoupledRun:
        state = run.state
        resources = replace(
            state.resources,
            pools=tuple(
                replace(pool, availability_intervals=extended_window)
                if isinstance(pool, PumpStationReusablePool)
                else pool
                for pool in state.resources.pools
            ),
        )
        return replace(
            run,
            state=replace(
                state,
                physical=replace(state.physical, calendar_seconds=60_000),
                resources=resources,
            ),
        )

    start = at_capacity_boundary(
        create_coupled_run(
            run_id="capacity-start",
            world_branch_id="branch-capacity-start",
        )
    )
    with pytest.raises(PumpStationCoupledWorldError, match="planned-outage-capacity"):
        _actor(
            start,
            "capacity-blocked-start",
            "request_obstruction_clearance",
            pump_id="pump-b",
            backlog_item_id="backlog-b-clearance-001",
            inspection_evidence_id="initial-b-inspection-accepted",
        )

    resume = create_coupled_run(
        run_id="capacity-resume",
        world_branch_id="branch-capacity-resume",
    )
    resume = _actor(
        resume,
        "capacity-resume-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = resume.state.processes[-1].process_id
    resume = resume.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="capacity-resume-stop",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=resume.state.state_id,
        )
    )
    resume = at_capacity_boundary(resume)
    resume = replace(
        resume,
        state=replace(
            resume.state,
            physical=replace(
                resume.state.physical,
                common_boundary=replace(
                    resume.state.physical.common_boundary,
                    power_available=True,
                ),
            ),
        ),
    )
    with pytest.raises(PumpStationCoupledWorldError, match="planned-outage-capacity"):
        _actor(resume, "capacity-blocked-resume", "resume_process", process_id=process_id)


def test_cancel_after_suspension_replans_same_item_and_releases_kit() -> None:
    run = create_coupled_run(
        run_id="suspend-cancel",
        world_branch_id="branch-suspend-cancel",
    )
    run = _actor(
        run,
        "late-b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = run.state.processes[-1].process_id
    run = run.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="cancelling-power-stop",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=run.state.state_id,
        )
    )
    run = _actor(run, "cancel-b-clearance", "cancel_process", process_id=process_id)

    item = run.state.backlog_item("backlog-b-clearance-001")
    kit = run.state.resources.pool("obstruction-clearance-kit")
    assert item.status is PumpStationBacklogStatus.PLANNED
    assert item.linked_process_id is None
    assert kit.free == 1
    assert kit.reserved == 0
    assert verify_coupled_run(run).replay_valid is True


def test_failed_functional_check_retains_wg03_and_failed_verification_creates_one_wg05() -> None:
    functional = create_coupled_run(
        run_id="failed-functional",
        world_branch_id="branch-failed-functional",
    )
    functional = _actor(
        functional,
        "b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    functional = _actor(functional, "complete-b-clearance", "continue_operation")
    wg03 = next(item for item in functional.state.backlog if item.generation_rule_id == "WG-03")
    functional = _actor(
        functional,
        "b-functional",
        "request_functional_check",
        pump_id="pump-b",
        backlog_item_id=wg03.item_id,
    )
    functional = functional.apply_process_outcome(
        PumpStationProcessOutcomeRequest(
            version=PUMP_STATION_PROCESS_OUTCOME_VERSION,
            request_id="fail-b-functional",
            authority_id="maintenance-controller",
            process_id=functional.state.processes[-1].process_id,
            outcome="failed",
            evidence_id="evidence-b-functional-failed-001",
            base_state_id=functional.state.state_id,
        )
    )
    retained = functional.state.backlog_item(wg03.item_id)
    assert functional.receipts[-1].required_authorities == ("maintenance",)
    assert retained.status is PumpStationBacklogStatus.PLANNED
    assert retained.closure_evidence_ids == ("evidence-b-functional-failed-001",)
    assert len([item for item in functional.state.backlog if item.generation_rule_id == "WG-03"]) == 1

    verification = create_coupled_run(
        run_id="failed-verification",
        world_branch_id="branch-failed-verification",
    )
    verification = _actor(
        verification,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    verification = verification.apply_process_outcome(
        PumpStationProcessOutcomeRequest(
            version=PUMP_STATION_PROCESS_OUTCOME_VERSION,
            request_id="fail-a-verification",
            authority_id="verification-engineer-01",
            process_id=verification.state.processes[-1].process_id,
            outcome="failed",
            evidence_id="evidence-a-verification-failed-001",
            base_state_id=verification.state.state_id,
        )
    )
    assert "restriction-a-run-in-001" in verification.state.active_restriction_ids
    rework = [item for item in verification.state.backlog if item.generation_rule_id == "WG-05"]
    assert len(rework) == 1
    assert verify_coupled_run(functional).replay_valid is True
    assert verify_coupled_run(verification).replay_valid is True


def test_common_hard_stop_clears_service_and_requires_fresh_assignment() -> None:
    run = create_coupled_run(run_id="hard-stop", world_branch_id="branch-hard-stop")
    stopped = run.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="power-stop",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=run.state.state_id,
        )
    )
    assert stopped.state.physical.service_running_pump_ids == ()
    assert stopped.state.assignment.active is False
    assert all(
        not stopped.state.physical.availability(pump.pump_id).assured_for_outage_planning
        for pump in stopped.state.physical.pumps
    )
    with pytest.raises(PumpStationCoupledWorldError, match="assignment"):
        _actor(
            stopped,
            "assignment-during-stop",
            "request_duty_assignment",
            ordered_pump_ids=("pump-c",),
        )
    restored = stopped.apply_common_boundary(
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="power-restore",
            authority_id="operations-controller",
            boundary_kind="power",
            available=True,
            base_state_id=stopped.state.state_id,
        )
    )
    assert restored.state.physical.service_running_pump_ids == ()
    assert restored.state.assignment.active is False
    reassigned = _actor(
        restored,
        "assignment-after-restore",
        "request_duty_assignment",
        ordered_pump_ids=("pump-c",),
    )
    assert reassigned.state.physical.service_running_pump_ids == ("pump-c",)
    assert verify_coupled_run(reassigned).replay_valid is True


def test_continue_operation_stops_at_earliest_named_pump_runtime_boundary() -> None:
    run = create_coupled_run(
        run_id="competing-runtime-clocks",
        world_branch_id="branch-competing-runtime-clocks",
    )
    state = replace(
        run.state,
        assignment=replace(
            run.state.assignment,
            ordered_pump_ids=("pump-a", "pump-c"),
        ),
        physical=replace(
            run.state.physical.with_boundary_mode(
                "pump-a",
                run.state.physical.boundary("pump-c").mode,
                "runtime-clock-test",
            ),
            calendar_seconds=64_800,
            service_running_pump_ids=("pump-a", "pump-c"),
        ),
        backlog=(
            PumpStationBacklogItem(
                item_id="pump-a-runtime-boundary",
                work_type="post_maintenance_verification",
                target_kind="asset",
                target_id="pump-a",
                generation_rule_id="WG-04",
                generation_ordinal=1,
                originating_record_id="runtime-a-source",
                linked_obligation_ids=(),
                linked_restriction_ids=(),
                linked_work_order_id=None,
                linked_process_id=None,
                generated_at_calendar_seconds=64_800,
                base_priority=PumpStationPriority.P3,
                effective_priority=PumpStationPriority.P3,
                due_calendar_seconds=None,
                due_runtime_clock_kind="pump_total",
                due_runtime_clock_id="pump-a",
                due_runtime_limit_seconds=5_400,
                status=PumpStationBacklogStatus.PLANNED,
                blocked_from_status=None,
                blocked_since_calendar_seconds=None,
                accumulated_blocked_seconds=0,
                closure_rule="accepted verification",
                closure_evidence_ids=(),
                supersedes_item_id=None,
                superseded_by_item_id=None,
            ),
            PumpStationBacklogItem(
                item_id="pump-c-runtime-boundary",
                work_type="collateral_duty_inspection",
                target_kind="asset",
                target_id="pump-c",
                generation_rule_id="WG-07",
                generation_ordinal=1,
                originating_record_id="runtime-c-source",
                linked_obligation_ids=(),
                linked_restriction_ids=(),
                linked_work_order_id=None,
                linked_process_id=None,
                generated_at_calendar_seconds=64_800,
                base_priority=PumpStationPriority.P3,
                effective_priority=PumpStationPriority.P3,
                due_calendar_seconds=None,
                due_runtime_clock_kind="pump_total",
                due_runtime_clock_id="pump-c",
                due_runtime_limit_seconds=3_600,
                status=PumpStationBacklogStatus.PLANNED,
                blocked_from_status=None,
                blocked_since_calendar_seconds=None,
                accumulated_blocked_seconds=0,
                closure_rule="accepted inspection",
                closure_evidence_ids=(),
                supersedes_item_id=None,
                superseded_by_item_id=None,
            ),
        ),
    )
    run = replace(run, state=state)

    advanced = _actor(run, "continue-to-first-runtime-boundary", "continue_operation")

    assert advanced.state.calendar_seconds == 66_600
    assert advanced.state.physical.pump("pump-a").exposure.runtime_seconds == 5_400
    assert advanced.state.physical.pump("pump-c").exposure.runtime_seconds == 1_800
    assert advanced.state.event_effect_ids[-1] == "backlog-runtime-boundary-pump-a-runtime-boundary-due"


def test_assignment_rejects_avoidable_deficit_and_records_unavoidable_unserved_scu() -> None:
    run = create_coupled_run(
        run_id="assignment-deficit",
        world_branch_id="branch-assignment-deficit",
    )
    peak = replace(
        run.state,
        physical=replace(run.state.physical, calendar_seconds=64_800),
    )
    unavoidable = _actor(
        replace(run, state=peak),
        "unavoidable-single-pump-peak",
        "request_duty_assignment",
        ordered_pump_ids=("pump-c",),
    )
    view = project_coupled_actor_view(unavoidable.state)

    assert unavoidable.state.assignment.required_service_scu == 2
    assert unavoidable.state.assignment.assigned_service_scu == 1
    assert unavoidable.state.assignment.unserved_service_scu == 1
    assert unavoidable.state.assignment.decision_detail == "accepted unavoidable degraded operation"
    assert view.required_service_scu == 2
    assert view.available_assured_scu == 1
    assert view.assigned_operating_scu == 1
    assert view.served_scu == 1
    assert view.unserved_scu == 1
    assert view.surplus_scu == 0

    avoidable_peak = replace(
        peak,
        physical=peak.physical.with_boundary_mode(
            "pump-a",
            peak.physical.boundary("pump-c").mode,
            "accepted-a-assurance",
        ),
    )
    with pytest.raises(PumpStationCoupledWorldError, match="avoidable-service-deficit"):
        _actor(
            replace(run, state=avoidable_peak),
            "avoidable-single-pump-peak",
            "request_duty_assignment",
            ordered_pump_ids=("pump-c",),
        )
