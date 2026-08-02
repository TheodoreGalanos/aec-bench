# ABOUTME: Tests installed JSON and local Harbor rollout paths against the direct contract.
# ABOUTME: Proves group lineage and governed treatment receipts survive transport boundaries.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from test_rollout_control_e2e import _group_request, _start_parent

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_rollout_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
    PumpStationTreatmentSeverity,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_interface import (
    PumpStationRolloutControlRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_installed(
    *,
    parent_root: Path,
    rollout_root: Path,
    request_path: Path,
    cwd: Path,
) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [
            str(executable),
            "--json",
            "task",
            "pump-station-world",
            "interface",
            "--run-dir",
            str(parent_root),
            "--rollout-dir",
            str(rollout_root),
            "--request-path",
            str(request_path),
            "--host-authority-id",
            "rollout-host",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _write(path: Path, request: PumpStationRolloutControlRequest) -> Path:
    path.write_text(
        json.dumps(
            {
                "surface": "control",
                "operation": "execute",
                "evidence_health": True,
                "control_request": request.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_installed_json_creates_group_and_activates_treatment(tmp_path: Path) -> None:
    parent = _start_parent(tmp_path / "parent")
    group = _group_request(parent)
    created = _run_installed(
        parent_root=tmp_path / "parent",
        rollout_root=tmp_path / "rollouts",
        request_path=_write(
            tmp_path / "create-rollout.json",
            PumpStationRolloutControlRequest(
                request_id=group.request_id,
                operation="create_rollout_group",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="rollout-host",
                group_request=group,
            ),
        ),
        cwd=tmp_path,
    )
    child = created["lineage"]["children"][1]["initial_snapshot"]
    treatment = PumpStationPhysicalTreatmentRequest(
        request_id="treatment-installed-recurrence",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        group_id=group.group_id,
        child_id="candidate",
        child_run_id=child["run_id"],
        child_episode_id=child["episode_id"],
        child_world_branch_id=child["world_branch_id"],
        base_state_id=child["state_id"],
        base_commit_id=child["commit_id"],
        based_on_sequence=child["sequence"],
        parent_state_id=created["lineage"]["parent_snapshot"]["state_id"],
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=parent.run.state.physical.calendar_seconds,
        severity=PumpStationTreatmentSeverity.MODERATE,
        random_stream_id="installed-common-random-stream",
        random_seed=17,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )
    scheduled = _run_installed(
        parent_root=tmp_path / "parent",
        rollout_root=tmp_path / "rollouts",
        request_path=_write(
            tmp_path / "schedule-treatment.json",
            PumpStationRolloutControlRequest(
                request_id=treatment.request_id,
                operation="schedule_physical_treatment",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="rollout-host",
                treatment_request=treatment,
            ),
        ),
        cwd=tmp_path,
    )
    activated = _run_installed(
        parent_root=tmp_path / "parent",
        rollout_root=tmp_path / "rollouts",
        request_path=_write(
            tmp_path / "recover-treatment.json",
            PumpStationRolloutControlRequest(
                request_id="recover-installed-treatment",
                operation="recover_physical_treatment",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="rollout-host",
                group_id=group.group_id,
                child_id="candidate",
                treatment_request_id=treatment.request_id,
            ),
        ),
        cwd=tmp_path,
    )

    assert scheduled["treatment_schedule"]["status"] == "scheduled"
    assert activated["treatment_activation"]["status"] == "activated"
    assert activated["treatment_activation"]["activation_snapshot"]["sequence"] == 1


def test_local_harbor_runs_isolated_control_and_treated_children(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        evidence_health=True,
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")

    completed = run_pump_station_rollout_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "harbor-output",
        session_identity="rollout-local-harbor",
    )

    assert completed.control_verification.valid is True
    assert completed.treated_verification.valid is True
    assert completed.lineage.children[0].initial_snapshot.state_id == (
        completed.lineage.children[1].initial_snapshot.state_id
    )
    assert completed.treatment_activation.status.value == "activated"
    assert (completed.output_dir / "rollout-lineage.json").is_file()
