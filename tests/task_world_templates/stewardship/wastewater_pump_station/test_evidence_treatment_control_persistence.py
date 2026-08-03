# ABOUTME: Tests durable evidence-treatment scheduling, restart retry, and replay.
# ABOUTME: Covers exact binding, immutable recovery, staged crash recovery, and conflicts.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import (
    WorldControlRequest,
    WorldControlResult,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PUMP_STATION_SNAPSHOT_VERSION_V3,
    PumpStationEvidenceControlRequest,
    PumpStationEvidenceControlResult,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationSchedule,
    PumpStationStateSnapshotRef,
    PumpStationWorldControl,
    PumpStationWorldRun,
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
    create_evidence_health_reference_state,
    load_reference_package,
    pump_station_model_from_package,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def _create_run(root: Path) -> PumpStationWorldRun:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_evidence_health_reference_state(
        model,
        schedule=PumpStationSchedule(
            access_available_after_seconds=86_400,
            repair_kit_available_after_seconds=86_400,
            decision_point_after_seconds=(3_600,),
        ),
    )
    return PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=model,
        initial_state=state,
        run_id="run-evidence-health",
        episode_id="episode-evidence-health",
        world_branch_id="branch-evidence-health",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
    )


def _request(run: PumpStationWorldRun) -> PumpStationEvidenceTreatmentRequest:
    snapshot = run.snapshot()
    decision_point = min(
        event.scheduled_seconds for event in run.state.scheduled_events if event.event_type.value == "decision_point"
    )
    return PumpStationEvidenceTreatmentRequest(
        request_id="treatment-control-001",
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        treatment_class=PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
        treatment_version=PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        target_source_id="station-condition-sensor",
        effective_decision_point_seconds=decision_point,
        visibility_policy=PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    )


def test_exact_retry_survives_process_restart_without_another_transition(
    tmp_path: Path,
) -> None:
    run = _create_run(tmp_path / "run")
    request = _request(run)

    first = run.schedule_evidence_treatment(request)
    selected = run.snapshot()
    resumed = PumpStationWorldRun.resume(
        repository=run.repository,
        package=run.package,
        model=run.model,
        snapshot=selected,
    )
    repeated = resumed.schedule_evidence_treatment(request)
    recovered_request, recovered_transition = resumed.recover_evidence_treatment(request.request_id)
    steps = resumed.steps()
    verification = verify_stewardship_run(
        run.model,
        run.repository.load_state(run.manifest.initial_state_id),
        steps,
        record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
    )

    assert repeated == first
    assert resumed.snapshot() == selected
    assert len(resumed.repository.commits()) == 2
    assert len(tuple((run.repository.root / "control-requests").glob("*.json"))) == 1
    assert recovered_request == request
    assert recovered_transition == first
    assert steps[0].proposal is None
    assert steps[0].information_set is None
    assert steps[0].control_request == request
    assert verification.valid is True


def test_conflict_and_wrong_scope_fail_before_state_change(tmp_path: Path) -> None:
    run = _create_run(tmp_path / "run")
    request = _request(run)
    run.schedule_evidence_treatment(request)
    selected = run.snapshot()

    with pytest.raises(PumpStationWorldRunError, match="control-request-id-conflict"):
        run.schedule_evidence_treatment(
            replace(
                request,
                treatment_class=PumpStationEvidenceTreatmentClass.OBSERVATION_LOSS,
            )
        )
    with pytest.raises(PumpStationWorldRunError, match="control-request-scope"):
        run.schedule_evidence_treatment(
            replace(
                request,
                request_id="treatment-control-wrong-branch",
                world_branch_id="branch-other",
            )
        )
    with pytest.raises(PumpStationWorldRunError, match="control-request-scope"):
        run.schedule_evidence_treatment(
            replace(
                request,
                request_id="treatment-control-stale-state",
            )
        )
    with pytest.raises(PumpStationWorldRunError, match="control-request-not-found"):
        run.recover_evidence_treatment("treatment-control-unknown")

    assert run.snapshot() == selected


def test_staged_treatment_can_be_published_after_process_restart(tmp_path: Path) -> None:
    run = _create_run(tmp_path / "run")
    request = _request(run)

    staged = run.stage_evidence_treatment(request)
    assert run.snapshot() == staged.prior_snapshot
    resumed = PumpStationWorldRun.resume(
        repository=run.repository,
        package=run.package,
        model=run.model,
        snapshot=run.snapshot(),
    )
    published = resumed.repository.publish_staged_transition(staged)
    recovered_request, recovered = resumed.recover_evidence_treatment(request.request_id)

    assert published == staged.transition
    assert recovered_request == request
    assert recovered == published
    assert resumed.snapshot() == staged.snapshot


def test_host_control_schedules_inspects_and_recovers_without_actor_rights(
    tmp_path: Path,
) -> None:
    root = tmp_path / "controlled-run"
    schedule = PumpStationSchedule(
        access_available_after_seconds=86_400,
        repair_kit_available_after_seconds=86_400,
        decision_point_after_seconds=(3_600,),
    )
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("host-evidence",),
        schedule=schedule,
        evidence_health=True,
    )
    start = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-evidence-health",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-evidence-health",
        run_id="run-evidence-health",
        episode_id="episode-evidence-health",
        world_branch_id="branch-evidence-health",
    )
    created = control.execute(
        WorldControlRequest(
            request_id="create-evidence-health",
            operation="create_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-evidence",
            session_request=start,
        )
    )
    assert isinstance(created, WorldControlResult)
    assert created.session_result is not None
    snapshot = created.session_result.snapshot
    package = load_reference_package()
    run = PumpStationWorldRun.resume(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=pump_station_model_from_package(package),
        snapshot=PumpStationStateSnapshotRef(
            snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V3,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            sequence=snapshot.sequence,
            state_id=snapshot.state_id,
            commit_id=snapshot.commit_id,
        ),
    )
    treatment = _request(run)
    scheduled_request = PumpStationEvidenceControlRequest(
        request_id=treatment.request_id,
        operation="schedule_evidence_treatment",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="host-evidence",
        treatment_request=treatment,
    )

    scheduled = control.execute(scheduled_request)
    restarted = PumpStationWorldControl(
        root,
        authorised_principal_ids=("host-evidence",),
        schedule=schedule,
        evidence_health=True,
    ).execute(scheduled_request)
    inspected = control.execute(
        PumpStationEvidenceControlRequest(
            request_id="inspect-treatment-001",
            operation="inspect_evidence_treatment",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-evidence",
            treatment_request_id=treatment.request_id,
        )
    )
    recovered = control.execute(
        PumpStationEvidenceControlRequest(
            request_id="recover-treatment-001",
            operation="recover_evidence_treatment",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-evidence",
            treatment_request_id=treatment.request_id,
        )
    )
    assert isinstance(scheduled, PumpStationEvidenceControlResult)
    assert isinstance(restarted, PumpStationEvidenceControlResult)
    assert isinstance(inspected, PumpStationEvidenceControlResult)
    assert isinstance(recovered, PumpStationEvidenceControlResult)
    assert scheduled.receipt.result_snapshot is not None
    resume = WorldSessionRequest(
        execution_kind=start.execution_kind,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=start.session_id,
        task_world_id=start.task_world_id,
        agent_tenure_id=start.agent_tenure_id,
        run_id=start.run_id,
        episode_id=start.episode_id,
        world_branch_id=start.world_branch_id,
        start_snapshot=scheduled.receipt.result_snapshot,
    )
    actor_session = PumpStationWorldSessionFactory(
        root,
        schedule=schedule,
        evidence_health=True,
    ).open(resume)
    actor_actions = {item.name for item in actor_session.actor_capabilities.actions}
    control_operations = {item.operation for item in control.capabilities("host-evidence").operations}

    assert scheduled == restarted
    assert scheduled.receipt.state_changed is True
    assert inspected.treatment.status.value == "scheduled"
    assert recovered.treatment_request == treatment
    assert recovered.transition_receipt == scheduled.transition_receipt
    assert "request_condition_check" in actor_actions
    assert actor_actions.isdisjoint(control_operations)
    assert {
        "schedule_evidence_treatment",
        "inspect_evidence_treatment",
        "recover_evidence_treatment",
    }.issubset(control_operations)
    with pytest.raises(WorldInterfaceError, match="control-unauthorised"):
        control.execute(
            PumpStationEvidenceControlRequest(
                request_id="inspect-unauthorised",
                operation="inspect_evidence_treatment",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="actor-evidence",
                treatment_request_id=treatment.request_id,
            )
        )
