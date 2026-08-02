# ABOUTME: Tests governed physical treatments, delayed activation, replay, and isolation.
# ABOUTME: Covers recurrence, continuation, restoration quality, and common-cause effects.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_rollout_control_e2e import _continue, _group_request, _start_parent

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
    PumpStationTreatmentSeverity,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
    PumpStationRolloutError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)


def _control(tmp_path: Path) -> tuple[PumpStationRolloutControl, object]:
    parent = _start_parent(tmp_path / "parent")
    control = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )
    return control, control.create_group(_group_request(parent))


def _request(
    control: PumpStationRolloutControl,
    *,
    treatment_class: PumpStationPhysicalTreatmentClass,
    affected_pump_ids: tuple[str, ...],
    activation_offset_seconds: int = 0,
) -> PumpStationPhysicalTreatmentRequest:
    child = control.open_actor_session(
        group_id="rollout-group-01",
        child_id="candidate",
        session_id="session.treatment-base",
        agent_tenure_id="tenure.treatment-base",
    )
    snapshot = child.run.snapshot()
    return PumpStationPhysicalTreatmentRequest(
        request_id=f"treatment-{treatment_class.value}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        group_id="rollout-group-01",
        child_id="candidate",
        child_run_id=snapshot.run_id,
        child_episode_id=snapshot.episode_id,
        child_world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        parent_state_id=control.inspect_group("rollout-group-01").parent_snapshot.state_id,
        treatment_class=treatment_class,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=affected_pump_ids,
        activation_calendar_seconds=(child.run.state.physical.calendar_seconds + activation_offset_seconds),
        severity=PumpStationTreatmentSeverity.MODERATE,
        random_stream_id="common-random-stream-01",
        random_seed=73,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id="task-owned-physical-treatment-control",
    )


@pytest.mark.parametrize(
    ("treatment_class", "affected_pump_ids"),
    (
        (PumpStationPhysicalTreatmentClass.CONTINUED_OBSTRUCTION, ("pump-a",)),
        (PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION, ("pump-a",)),
        (PumpStationPhysicalTreatmentClass.RESTORATION_SHORTFALL, ("pump-a",)),
        (PumpStationPhysicalTreatmentClass.MAINTENANCE_INDUCED_CLEARANCE_LOSS, ("pump-a",)),
        (PumpStationPhysicalTreatmentClass.CLEARANCE_REPAIR_ALTERNATIVE, ("pump-b",)),
        (PumpStationPhysicalTreatmentClass.COMMON_CAUSE_OBSTRUCTION, ("pump-a", "pump-b")),
    ),
)
def test_closed_treatment_classes_activate_once_and_replay(
    tmp_path: Path,
    treatment_class: PumpStationPhysicalTreatmentClass,
    affected_pump_ids: tuple[str, ...],
) -> None:
    control, lineage = _control(tmp_path)
    request = _request(
        control,
        treatment_class=treatment_class,
        affected_pump_ids=affected_pump_ids,
    )
    parent_before = lineage.parent_snapshot
    sibling_before = lineage.children[0].initial_snapshot

    scheduled = control.schedule_treatment(request)
    actor_before = control.open_actor_session(
        group_id=request.group_id,
        child_id=request.child_id,
        session_id="session.before-treatment",
        agent_tenure_id="tenure.before-treatment",
    )
    public_text = json.dumps(json.loads(actor_before.observe_pump_station()), sort_keys=True)
    assert request.request_id not in public_text
    assert treatment_class.value not in public_text
    assert scheduled.status.value == "scheduled"
    assert scheduled.affected_pump_ids == affected_pump_ids
    assert set(scheduled.affected_pump_ids).isdisjoint(scheduled.unaffected_pump_ids)

    activated = control.recover_treatment(
        group_id=request.group_id,
        child_id=request.child_id,
        treatment_request_id=request.request_id,
    )
    repeated = control.recover_treatment(
        group_id=request.group_id,
        child_id=request.child_id,
        treatment_request_id=request.request_id,
    )

    assert activated == repeated
    assert activated.status.value == "activated"
    assert activated.activation_snapshot.sequence == request.based_on_sequence + 1
    assert control.parent_snapshot() == parent_before
    sibling = control.open_actor_session(
        group_id=request.group_id,
        child_id="control",
        session_id="session.untreated-sibling",
        agent_tenure_id="tenure.untreated-sibling",
    )
    assert sibling.run.snapshot() == sibling_before
    treated = control.open_actor_session(
        group_id=request.group_id,
        child_id=request.child_id,
        session_id="session.treated-child",
        agent_tenure_id="tenure.treated-child",
    )
    assert treated.run.state.physical != sibling.run.state.physical
    treated_public_text = json.dumps(
        json.loads(treated.observe_pump_station()),
        sort_keys=True,
    )
    assert request.request_id not in treated_public_text
    assert treatment_class.value not in treated_public_text
    assert treated.verify().valid is True


def test_treatment_waits_for_clock_and_rejects_invalid_scope(tmp_path: Path) -> None:
    control, _ = _control(tmp_path)
    request = _request(
        control,
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        affected_pump_ids=("pump-a",),
        activation_offset_seconds=28_800,
    )
    control.schedule_treatment(request)

    with pytest.raises(PumpStationRolloutError, match="activation-clock"):
        control.recover_treatment(
            group_id=request.group_id,
            child_id=request.child_id,
            treatment_request_id=request.request_id,
        )

    actor = control.open_actor_session(
        group_id=request.group_id,
        child_id=request.child_id,
        session_id="session.advance-treatment",
        agent_tenure_id="tenure.advance-treatment",
    )
    _continue(actor, "proposal-reach-treatment-clock")
    sequence_before_activation = actor.run.snapshot().sequence
    receipt = control.recover_treatment(
        group_id=request.group_id,
        child_id=request.child_id,
        treatment_request_id=request.request_id,
    )
    assert receipt.activation_snapshot.sequence == sequence_before_activation + 1

    invalid = _request(
        control,
        treatment_class=PumpStationPhysicalTreatmentClass.COMMON_CAUSE_OBSTRUCTION,
        affected_pump_ids=("pump-a",),
    )
    with pytest.raises(PumpStationRolloutError, match="affected-entities"):
        control.schedule_treatment(invalid)
