# ABOUTME: Attacks durable pump-station replay, continuity, and certified claim binding.
# ABOUTME: Proves equal runs are byte-stable and drift fails during independent reload.

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from world_run_support import bind_proposal, create_world_run

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    PumpStationWorldRunError,
    ReferencePackageError,
    RequestConditionalDeferral,
    RequestInspection,
    TransferDuty,
    bundled_reference_package_root,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def _durable_json(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*.json"))}


def _apply_durable_prefix(run) -> None:
    proposals = (
        (RequestConditionalDeferral, "proposal-01-deferral", {"pump_id": "pump-a"}),
        (TransferDuty, "proposal-02-transfer", {}),
        (RequestInspection, "proposal-03-inspection", {"pump_id": "pump-a"}),
        (ContinueOperation, "proposal-04-complete-inspection", {}),
    )
    for proposal_type, proposal_id, parameters in proposals:
        proposal, information_set = bind_proposal(
            run,
            proposal_type,
            proposal_id,
            **parameters,
        )
        run.apply(
            proposal,
            information_set=information_set,
        )


def _start_request() -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="session-asw-3a-1",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-1",
        run_id="run-asw-3a",
        episode_id="episode-asw-3a",
        world_branch_id="branch-asw-3a",
    )


def _run_to_verification_process(session) -> dict[str, object]:
    reason = "Exercise durable world-run continuity."
    session.request_conditional_deferral("proposal-01", reason, "pump-a")
    session.transfer_duty("proposal-02", reason)
    session.request_inspection("proposal-03", reason, "pump-a")
    inspection_completed = json.loads(session.continue_operation("proposal-04", reason))
    inspection_id = next(
        item["evidence_id"]
        for item in inspection_completed["view"]["current_state"]["evidence"]
        if item["kind"] == "inspection"
    )
    session.continue_operation("proposal-05", reason)
    session.request_obstruction_clearance(
        "proposal-06",
        reason,
        "pump-a",
        inspection_id,
    )
    session.continue_operation("proposal-07", reason)
    checks_completed = json.loads(session.continue_operation("proposal-08", reason))
    functional_check_id = next(
        item["evidence_id"]
        for item in checks_completed["view"]["current_state"]["evidence"]
        if item["kind"] == "functional_checks"
    )
    returned = json.loads(
        session.request_provisional_return(
            "proposal-09",
            reason,
            "pump-a",
            functional_check_id,
        )
    )
    work_order_id = returned["view"]["current_state"]["work_orders"][0]["work_order_id"]
    session.request_provisional_closure("proposal-10", reason, work_order_id)
    return json.loads(
        session.request_post_maintenance_verification(
            "proposal-11",
            reason,
            "pump-a",
        )
    )


def _write_canonical_json(path: Path, value: object) -> None:
    path.write_bytes(
        (
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )


def _drift_reference_package(package_root: Path, drift: str) -> None:
    if drift in {
        "profile",
        "generation",
        "version",
        "prohibited-claim",
    }:
        path = package_root / "public-profile.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        if drift == "profile":
            document["profile_id"] = "AU-NSW-LH-SYN-SPS-hostile"
        elif drift == "generation":
            document["generation_id"] = "0" * 64
        elif drift == "version":
            document["schema_id"] = "asw-0b5.public-profile.v2"
        else:
            document["prohibited_claim_ids"] = []
    else:
        path = package_root / "promotion-manifest.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        if drift == "certified-envelope":
            document["claims"]["certified_envelope"] = "all real pump stations"
        else:
            document["authority"]["w3_sha256"] = "0" * 64
    _write_canonical_json(path, document)


def test_equal_durable_replays_publish_byte_equivalent_artifacts(tmp_path: Path) -> None:
    first = create_world_run(tmp_path / "first")
    second = create_world_run(tmp_path / "second")

    _apply_durable_prefix(first)
    _apply_durable_prefix(second)

    assert first.state == second.state
    assert first.steps() == second.steps()
    assert _durable_json(first.repository.root) == _durable_json(second.repository.root)


def test_closure_snapshot_and_fresh_tenure_conserve_active_duties(
    tmp_path: Path,
) -> None:
    factory = PumpStationWorldSessionFactory(tmp_path / "world")
    first = factory.open(_start_request())
    scheduled = _run_to_verification_process(first)
    before = scheduled["view"]["current_state"]
    snapshot = first.result.snapshot

    resumed = factory.open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="session-asw-3a-2",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure-2",
            run_id="run-asw-3a",
            episode_id="episode-asw-3a",
            world_branch_id="branch-asw-3a",
            start_snapshot=snapshot,
        )
    )
    after = json.loads(resumed.observe_pump_station())["current_state"]

    assert after == before
    assert after["work_orders"][0]["status"] == "provisionally_closed"
    assert after["processes"][0]["status"] == "in_progress"
    assert after["processes"][0]["kind"] == "post_maintenance_verification"
    assert after["obligations"][0]["status"] == "active"
    assert after["obligations"][0]["kind"] == "post_maintenance_verification"
    assert after["restrictions"][0]["status"] == "active"
    assert after["restrictions"][0]["kind"] == "post_maintenance_run_in"
    assert {item["kind"] for item in after["evidence"]} == {
        "inspection",
        "functional_checks",
    }

    completed = json.loads(
        resumed.continue_operation(
            "proposal-12",
            "Complete the carried verification process.",
        )
    )
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=tmp_path / "world",
    )

    assert completed["status"] == "completed"
    assert resumed.verify().valid is True
    assert evaluation.valid is True
    assert evaluation.metrics.handover_count == 1
    assert evaluation.metrics.handover_omission_count == 0


def test_evaluation_report_binds_exact_world_run_manifest(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")

    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=run.repository.root,
    )

    assert evaluation.valid is True
    assert evaluation.evidence.world_run_manifest_content_id == pump_station_artifact_id(run.manifest)
    assert evaluation.evidence.initial_state_id == run.manifest.initial_state_id
    assert evaluation.evidence.terminal_state_id == run.snapshot().state_id


@pytest.mark.parametrize(
    "drift",
    (
        "profile",
        "generation",
        "version",
        "certified-envelope",
        "prohibited-claim",
        "certifier-lineage",
    ),
)
def test_evaluation_rejects_certified_package_claim_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    run = create_world_run(tmp_path / "run")
    package_root = tmp_path / "hostile-package"
    shutil.copytree(
        bundled_reference_package_root(),
        package_root,
    )
    _drift_reference_package(package_root, drift)

    with pytest.raises(ReferencePackageError):
        evaluate_pump_station_stewardship_run(
            run_dir=run.repository.root,
            package_root=package_root,
        )


def test_evaluation_rejects_world_run_identity_drift(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    manifest_path = run.repository.root / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["profile_id"] = "AU-NSW-LH-SYN-SPS-hostile"
    _write_canonical_json(manifest_path, document)

    with pytest.raises(PumpStationWorldRunError, match="world-run-identity"):
        evaluate_pump_station_stewardship_run(
            run_dir=run.repository.root,
        )
