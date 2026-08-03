# ABOUTME: Runs pump-station actor actions through the installed JSON interface and local Harbor controller.
# ABOUTME: Proves machine-readable calls and Harbor use the same task-owned actor contract.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_interface(
    *,
    run_dir: Path,
    request_path: Path,
    cwd: Path,
    host_authority_id: str | None = None,
) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    command = [
        str(executable),
        "--json",
        "task",
        "pump-station-world",
        "interface",
        "--run-dir",
        str(run_dir),
        "--request-path",
        str(request_path),
    ]
    if host_authority_id is not None:
        command.extend(("--host-authority-id", host_authority_id))
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _write_request(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _resume_request(
    start: WorldSessionRequest,
    snapshot: StewardshipStateSnapshotRef,
) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=start.session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=start.agent_tenure_id,
        run_id=start.run_id,
        episode_id=start.episode_id,
        world_branch_id=start.world_branch_id,
        start_snapshot=snapshot,
    )


def _invoke_installed_action(
    *,
    run_dir: Path,
    tmp_path: Path,
    start: WorldSessionRequest,
    snapshot: StewardshipStateSnapshotRef,
    request_id: str,
    action_name: str,
    arguments: dict[str, Any],
) -> tuple[dict[str, Any], StewardshipStateSnapshotRef]:
    resume = _resume_request(start, snapshot)
    observed = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / f"{request_id}-observe.json",
            {
                "surface": "actor",
                "operation": "observe",
                "session_request": resume.model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    action = WorldActorActionRequest(
        request_id=request_id,
        action_name=action_name,
        binding=observed["binding"],
        arguments=arguments,
    )
    invoked = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / f"{request_id}-invoke.json",
            {
                "surface": "actor",
                "operation": "invoke",
                "session_request": resume.model_dump(mode="json"),
                "action_request": action.model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    post = invoked["post_binding"]
    return invoked, StewardshipStateSnapshotRef(
        run_id=post["run_id"],
        episode_id=post["episode_id"],
        world_branch_id=post["world_branch_id"],
        sequence=post["sequence"],
        state_id=post["state_id"],
        commit_id=post["commit_id"],
    )


def test_installed_interface_creates_observes_invokes_and_verifies_real_run(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "world"
    start = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-cli",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-cli",
        run_id="run-cli",
        episode_id="episode-cli",
        world_branch_id="branch-cli",
    )
    created = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "create.json",
            {
                "surface": "control",
                "operation": "execute",
                "control_request": {
                    "request_id": "control-create",
                    "operation": "create_session",
                    "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                    "authority_id": "host-cli",
                    "session_request": start.model_dump(mode="json"),
                },
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-cli",
    )
    snapshot = StewardshipStateSnapshotRef.model_validate(created["session_result"]["snapshot"])
    resume = _resume_request(start, snapshot)
    capabilities = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "actor-capabilities.json",
            {
                "surface": "actor",
                "operation": "capabilities",
                "session_request": resume.model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    control_capabilities = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "control-capabilities.json",
            {
                "surface": "control",
                "operation": "capabilities",
                "authority_id": "host-cli",
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-cli",
    )
    reason = "Execute the deterministic reference stewardship journey."

    def invoke(
        request_id: str,
        action_name: str,
        **arguments: str,
    ) -> dict[str, Any]:
        nonlocal snapshot
        result, snapshot = _invoke_installed_action(
            run_dir=run_dir,
            tmp_path=tmp_path,
            start=start,
            snapshot=snapshot,
            request_id=request_id,
            action_name=action_name,
            arguments={"reason": reason, **arguments},
        )
        return result

    invoke("proposal-01", "request_conditional_deferral", pump_id="pump-a")
    invoke("proposal-02", "transfer_duty")
    invoke("proposal-03", "request_inspection", pump_id="pump-a")
    inspection_completed = invoke("proposal-04", "continue_operation")
    inspection_id = next(
        item["evidence_id"]
        for item in inspection_completed["next_observation"]["view"]["current_state"]["evidence"]
        if item["kind"] == "inspection"
    )
    invoke("proposal-05", "continue_operation")
    invoke(
        "proposal-06",
        "request_obstruction_clearance",
        pump_id="pump-a",
        inspection_evidence_id=inspection_id,
    )
    invoke("proposal-07", "continue_operation")
    checks_completed = invoke("proposal-08", "continue_operation")
    functional_check_id = next(
        item["evidence_id"]
        for item in checks_completed["next_observation"]["view"]["current_state"]["evidence"]
        if item["kind"] == "functional_checks"
    )
    returned = invoke(
        "proposal-09",
        "request_provisional_return",
        pump_id="pump-a",
        functional_check_evidence_id=functional_check_id,
    )
    work_order_id = returned["next_observation"]["view"]["current_state"]["work_orders"][0]["work_order_id"]
    invoke(
        "proposal-10",
        "request_provisional_closure",
        work_order_id=work_order_id,
    )
    invoke(
        "proposal-11",
        "request_post_maintenance_verification",
        pump_id="pump-a",
    )
    invoked = invoke("proposal-12", "continue_operation")
    verified = _run_interface(
        run_dir=run_dir,
        request_path=_write_request(
            tmp_path / "verify.json",
            {
                "surface": "control",
                "operation": "execute",
                "control_request": {
                    "request_id": "control-verify",
                    "operation": "verify",
                    "task_world_id": PUMP_STATION_TASK_WORLD_ID,
                    "authority_id": "host-cli",
                },
            },
        ),
        cwd=tmp_path,
        host_authority_id="host-cli",
    )

    actor_action_names = {item["name"] for item in capabilities["actions"]}
    control_operation_names = {item["operation"] for item in control_capabilities["operations"]}
    assert actor_action_names.isdisjoint(control_operation_names)
    assert "scheduled_events" not in invoked["next_observation"]["view"]
    assert invoked["post_binding"]["sequence"] == 12
    assert invoked["task_receipt"]["proposal_id"] == "proposal-12"
    assert verified["verification"]["valid"] is True

    task_dir = tmp_path / "parity-task"
    export_pump_station_harbor_task(task_dir, project_root=PROJECT_ROOT)
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    harbor = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "parity-harbor",
        session_identity="asw-5i-parity",
    )
    assert harbor.result.snapshot.sequence == snapshot.sequence
    assert harbor.result.snapshot.state_id == snapshot.state_id


def test_local_harbor_reference_controller_calls_the_actor_interface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[WorldActorActionRequest] = []
    original = PumpStationWorldSession.invoke_actor_action

    def record(
        session: PumpStationWorldSession,
        request: WorldActorActionRequest,
    ) -> Any:
        requests.append(request)
        return original(session, request)

    monkeypatch.setattr(PumpStationWorldSession, "invoke_actor_action", record)
    task_dir = tmp_path / "task"
    export_pump_station_harbor_task(task_dir, project_root=PROJECT_ROOT)
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "harbor",
        session_identity="asw-5i",
    )

    assert completed.verification.valid is True
    assert len(requests) == 12
    assert tuple(request.binding.sequence for request in requests) == tuple(range(12))
    assert all(request.binding.world_branch_id == "branch.asw-5i" for request in requests)
    assert all(request.action_name not in {"create_session", "verify"} for request in requests)
