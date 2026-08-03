# ABOUTME: Runs evidence-treatment control and condition checks through installed JSON.
# ABOUTME: Proves restart retry, public privacy, activation, actor use, and replay verification.

from __future__ import annotations

import json
from pathlib import Path

from test_actor_interface_transport_e2e import (
    _invoke_installed_action,
    _resume_request,
    _run_interface,
    _write_request,
)

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)


def test_installed_json_runs_complete_evidence_health_control_path(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "world"
    start = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-installed-evidence",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-installed-evidence",
        run_id="run-installed-evidence",
        episode_id="episode-installed-evidence",
        world_branch_id="branch-installed-evidence",
    )
    created = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "create-evidence.json",
            {
                "surface": "control",
                "operation": "execute",
                "evidence_health": True,
                "control_request": {
                    "request_id": "create-installed-evidence",
                    "operation": "create_session",
                    "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                    "authority_id": "host-installed-evidence",
                    "session_request": start.model_dump(mode="json"),
                },
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-evidence",
    )
    snapshot = StewardshipStateSnapshotRef.model_validate(created["session_result"]["snapshot"])
    observed = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "observe-evidence.json",
            {
                "surface": "actor",
                "operation": "observe",
                "session_request": _resume_request(start, snapshot).model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    current = observed["view"]["current_state"]
    treatment_request = {
        "request_id": "treatment-installed-calibration",
        "run_id": snapshot.run_id,
        "episode_id": snapshot.episode_id,
        "world_branch_id": snapshot.world_branch_id,
        "base_state_id": snapshot.state_id,
        "base_commit_id": snapshot.commit_id,
        "based_on_sequence": snapshot.sequence,
        "treatment_class": "calibration_lapse",
        "treatment_version": PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        "target_source_id": "station-condition-sensor",
        "effective_decision_point_seconds": current["calendar_seconds"] + 28_800,
        "visibility_policy": PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    }
    schedule_payload = {
        "surface": "control",
        "operation": "execute",
        "evidence_health": True,
        "control_request": {
            "request_id": treatment_request["request_id"],
            "operation": "schedule_evidence_treatment",
            "task_world_id": PUMP_STATION_TASK_WORLD_ID,
            "authority_id": "host-installed-evidence",
            "treatment_request": treatment_request,
        },
    }
    scheduled = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "schedule-evidence.json",
            schedule_payload,
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-evidence",
    )
    scheduled_snapshot = StewardshipStateSnapshotRef.model_validate(scheduled["receipt"]["result_snapshot"])
    before_activation = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "observe-before-activation.json",
            {
                "surface": "actor",
                "operation": "observe",
                "session_request": _resume_request(
                    start,
                    scheduled_snapshot,
                ).model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    public_text = json.dumps(before_activation["view"], sort_keys=True)

    activated, activated_snapshot = _invoke_installed_action(
        run_dir=run_dir,
        tmp_path=tmp_path,
        start=start,
        snapshot=scheduled_snapshot,
        request_id="proposal-activate-treatment",
        action_name="continue_operation",
        arguments={"reason": "Continue to the next declared decision point."},
    )
    checked, checked_snapshot = _invoke_installed_action(
        run_dir=run_dir,
        tmp_path=tmp_path,
        start=start,
        snapshot=activated_snapshot,
        request_id="proposal-condition-after-calibration",
        action_name="request_condition_check",
        arguments={
            "reason": "Record the current sensor-based condition check.",
            "pump_id": "pump-a",
        },
    )
    physical_inspection, physical_inspection_snapshot = _invoke_installed_action(
        run_dir=run_dir,
        tmp_path=tmp_path,
        start=start,
        snapshot=checked_snapshot,
        request_id="proposal-physical-inspection-after-condition",
        action_name="request_inspection",
        arguments={
            "reason": "Request the separate physical inspection.",
            "pump_id": "pump-b",
        },
    )
    inspected = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "inspect-treatment.json",
            {
                "surface": "control",
                "operation": "execute",
                "evidence_health": True,
                "control_request": {
                    "request_id": "inspect-installed-treatment",
                    "operation": "inspect_evidence_treatment",
                    "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                    "authority_id": "host-installed-evidence",
                    "treatment_request_id": treatment_request["request_id"],
                },
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-evidence",
    )
    retried = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "retry-schedule-evidence.json",
            schedule_payload,
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-evidence",
    )
    verified = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "verify-evidence.json",
            {
                "surface": "control",
                "operation": "execute",
                "evidence_health": True,
                "control_request": {
                    "request_id": "verify-installed-evidence",
                    "operation": "verify",
                    "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                    "authority_id": "host-installed-evidence",
                },
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-evidence",
    )

    assert "treatment_class" not in public_text
    assert "effective_decision_point_seconds" not in public_text
    assert activated["next_observation"]["view"]["current_state"]["observation_source"]["quality"] == "suspect"
    evidence = checked["next_observation"]["view"]["current_state"]["evidence"]
    assert evidence[-1]["kind"] == "condition_check"
    assert evidence[-1]["quality"] == "suspect"
    assert any(
        item["kind"] == "inspection" and item["pump_id"] == "pump-b"
        for item in physical_inspection["next_observation"]["view"]["current_state"]["processes"]
    )
    assert inspected["treatment"]["status"] == "active"
    assert retried == scheduled
    assert physical_inspection_snapshot.sequence == scheduled_snapshot.sequence + 3
    assert verified["verification"]["valid"] is True
