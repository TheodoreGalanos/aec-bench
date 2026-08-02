# ABOUTME: Freezes the complete durable artifact inventory for supported pump record versions.
# ABOUTME: Detects any path, size, or byte-hash drift before shared storage mechanics change.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from rich_work_support import rich_work_schedule
from world_run_support import bind_proposal, create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    ContinueOperation,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationSchedule,
    PumpStationWorldRun,
    PumpStationWorldRunRepository,
    RequestConditionalDeferral,
    create_evidence_health_reference_state,
    create_rich_work_reference_state,
    load_reference_package,
    pump_station_model_from_package,
)

type _RunBuilder = Callable[[Path], PumpStationWorldRun]


def _durable_inventory(root: Path) -> dict[str, list[int | str]]:
    result: dict[str, list[int | str]] = {}
    for path in sorted(root.rglob("*.json")):
        payload = path.read_bytes()
        result[path.relative_to(root).as_posix()] = [
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        ]
    return result


def _build_v1_run(root: Path) -> PumpStationWorldRun:
    run = create_world_run(root)
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-resource-effect",
        pump_id="pump-a",
    )
    run.apply(proposal, information_set=information_set)
    return run


def _build_v2_run(root: Path) -> PumpStationWorldRun:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    run = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=model,
        initial_state=create_rich_work_reference_state(
            model,
            schedule=rich_work_schedule(model),
        ),
        run_id="run-v2",
        episode_id="episode-v2",
        world_branch_id="branch-v2",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V2,
    )
    proposal, information_set = bind_proposal(
        run,
        ContinueOperation,
        "proposal-resource-arrival",
    )
    run.apply(proposal, information_set=information_set)
    return run


def _build_v3_run(root: Path) -> PumpStationWorldRun:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    run = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=model,
        initial_state=create_evidence_health_reference_state(
            model,
            schedule=PumpStationSchedule(
                access_available_after_seconds=86_400,
                repair_kit_available_after_seconds=86_400,
                decision_point_after_seconds=(3_600,),
            ),
        ),
        run_id="run-evidence-health",
        episode_id="episode-evidence-health",
        world_branch_id="branch-evidence-health",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
    )
    snapshot = run.snapshot()
    decision_point = min(
        event.scheduled_seconds for event in run.state.scheduled_events if event.event_type.value == "decision_point"
    )
    run.schedule_evidence_treatment(
        PumpStationEvidenceTreatmentRequest(
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
    )
    return run


def _baselines() -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "world_run_byte_inventories.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))["baselines"]


@pytest.mark.parametrize(
    ("version", "builder"),
    (
        ("v1", _build_v1_run),
        ("v2", _build_v2_run),
        ("v3", _build_v3_run),
    ),
)
def test_supported_record_versions_retain_exact_durable_artifact_inventory(
    tmp_path: Path,
    version: str,
    builder: _RunBuilder,
) -> None:
    run = builder(tmp_path / version)

    assert _durable_inventory(run.repository.root) == _baselines()[version]["artifacts"]
