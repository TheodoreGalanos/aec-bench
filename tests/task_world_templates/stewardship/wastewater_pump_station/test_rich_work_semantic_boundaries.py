# ABOUTME: Attacks rich-work view, evidence, event-order, and reservation boundaries.
# ABOUTME: Proves invalid rich-work actions fail closed without hidden-state leakage.

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace

from rich_work_support import apply_bound, bind_proposal, latest_process, rich_work_schedule

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationAuthorityOutcome,
    PumpStationDependencyKind,
    PumpStationEventType,
    PumpStationExecutionOutcome,
    PumpStationModel,
    PumpStationProcessKind,
    PumpStationProjectionContext,
    PumpStationStewardshipState,
    ReferencePackage,
    RequestDependencyWaiver,
    RequestInspection,
    ResumeProcess,
    TransferDuty,
    advance_to_next_decision_point,
    apply_stewardship_proposal,
    create_rich_work_reference_state,
    load_reference_package,
    project_actor_view,
    pump_station_model_from_package,
)


def _world() -> tuple[ReferencePackage, PumpStationModel, PumpStationStewardshipState]:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )
    return package, model, state


def test_stale_resume_and_forged_waiver_evidence_fail_closed() -> None:
    _, model, state = _world()
    state = advance_to_next_decision_point(model, state).state
    state = apply_bound(model, state, TransferDuty, "proposal-transfer").state
    state = apply_bound(
        model,
        state,
        RequestInspection,
        "proposal-inspection",
        pump_id="pump-b",
    ).state
    suspended = advance_to_next_decision_point(model, state).state
    process = latest_process(suspended, PumpStationProcessKind.INSPECTION, "pump-b")
    stale_proposal, stale_information = bind_proposal(
        model,
        suspended,
        ResumeProcess,
        "proposal-stale-resume",
        process_id=process.process_id,
    )
    advanced = advance_to_next_decision_point(model, suspended).state

    stale = apply_stewardship_proposal(
        model,
        advanced,
        stale_proposal,
        information_set=stale_information,
    )

    assert stale.receipt.authority is not None
    assert stale.receipt.authority.outcome is PumpStationAuthorityOutcome.INVALID
    assert stale.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert replace(stale.state, sequence=advanced.sequence) == advanced

    verification = apply_bound(
        model,
        advanced,
        RequestInspection,
        "proposal-second-inspection",
        pump_id="pump-a",
    ).state
    blocked = latest_process(verification, PumpStationProcessKind.INSPECTION, "pump-a")
    dependency = next(
        item
        for item in verification.dependencies
        if item.process_id == blocked.process_id and item.kind is PumpStationDependencyKind.RESOURCE
    )
    forged = apply_bound(
        model,
        verification,
        RequestDependencyWaiver,
        "proposal-forged-waiver",
        process_id=blocked.process_id,
        dependency_id=dependency.dependency_id,
        evidence_id="evidence-forged",
    )
    assert forged.receipt.authority is not None
    assert forged.receipt.authority.outcome is (PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES)
    assert forged.state.dependency_waivers == verification.dependency_waivers


def test_simultaneous_resource_events_have_one_canonical_order() -> None:
    _, model, state = _world()

    transition = advance_to_next_decision_point(model, state)

    assert transition.receipt.applied_event_types == (
        PumpStationEventType.ACCESS_AVAILABLE,
        PumpStationEventType.REPAIR_KIT_AVAILABLE,
    )
    assert len({item.reservation_id for item in transition.state.resource_reservations}) == len(
        transition.state.resource_reservations
    )


def test_actor_view_has_process_controls_but_no_latent_or_future_state() -> None:
    package, model, state = _world()
    view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-view",
            world_branch_id="branch-view",
            actor_id="station-steward",
            agent_tenure_id="tenure-view",
            episode_started_at_seconds=state.physical.calendar_seconds,
            tenure_started_at_seconds=state.physical.calendar_seconds,
            projection_policy_id="pump-station-current-state.v2",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
            ),
        ),
    )

    def field_names(value: object) -> set[str]:
        if is_dataclass(value) and not isinstance(value, type):
            names = {field.name for field in fields(value)}
            return names | {child for field in fields(value) for child in field_names(getattr(value, field.name))}
        if isinstance(value, tuple):
            return {child for item in value for child in field_names(item)}
        return set()

    names = field_names(view)
    assert "dependencies" in names
    assert "resource_reservations" in names
    assert "condition" not in names
    assert "scheduled_events" not in names
