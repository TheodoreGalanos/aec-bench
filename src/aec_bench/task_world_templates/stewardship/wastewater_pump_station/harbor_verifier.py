# ABOUTME: Independently reloads and verifies exported pump-station Harbor evidence.
# ABOUTME: Reconciles package, session, inventory, and durable transition identities.

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.task_world_templates.harbor_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION,
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSessionFactory,
)


def verify_pump_station_harbor_run(
    *,
    run_dir: Path,
    export_manifest_path: Path,
    package_dir: Path,
    verifier_runtime_path: Path | None = None,
) -> dict[str, Any]:
    """Verify one completed Harbor world session without trusting agent claims."""

    root = Path(run_dir)
    manifest = _read_json(export_manifest_path)
    if (
        manifest.get("schema_version") != PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION
        or manifest.get("execution_kind") != PUMP_STATION_HARBOR_EXECUTION_KIND
        or manifest.get("task_world_id") != PUMP_STATION_TASK_WORLD_ID
    ):
        raise ValueError("pump-station Harbor export identity differs")
    package_payload = _mapping(manifest.get("package"), "package")
    package = load_reference_package(package_dir)
    if (
        package.package_content_id != package_payload.get("package_content_id")
        or package.manifest_content_id != package_payload.get("manifest_content_id")
        or directory_sha256(package_dir) != package_payload.get("directory_sha256")
        or file_sha256(package_dir / "promotion-manifest.json") != package_payload.get("manifest_sha256")
    ):
        raise ValueError("pump-station Harbor package evidence differs")
    verifier_payload = _mapping(manifest.get("verifier"), "verifier")
    if verifier_runtime_path is not None and (
        file_sha256(verifier_runtime_path) != verifier_payload.get("runtime_wheel_sha256")
    ):
        raise ValueError("pump-station Harbor verifier runtime differs")
    request = WorldSessionRequest.model_validate(_read_json(root / "world-session-request.json"))
    result = WorldSessionResult.model_validate(_read_json(root / "world-session-result.json"))
    inventory = _read_json(root / "artifact-inventory.json")
    if (
        inventory.get("schema_version") != PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION
        or inventory.get("execution_kind") != PUMP_STATION_HARBOR_EXECUTION_KIND
        or inventory.get("task_world_id") != PUMP_STATION_TASK_WORLD_ID
        or inventory.get("export_manifest_sha256") != file_sha256(export_manifest_path)
        or inventory.get("verifier_runtime_sha256") != verifier_payload.get("runtime_wheel_sha256")
        or inventory.get("package_content_id") != package.package_content_id
        or inventory.get("package_manifest_content_id") != package.manifest_content_id
        or tuple(inventory.get("tool_names", ())) != PUMP_STATION_TOOL_NAMES
    ):
        raise ValueError("pump-station Harbor artifact inventory identity differs")
    _verify_inventory(root, inventory)
    start_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("start_snapshot"))
    end_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("end_snapshot"))
    if (
        result.snapshot != end_snapshot
        or int(inventory.get("transition_count", -1)) != end_snapshot.sequence - start_snapshot.sequence
        or request.execution_kind is not WorldSessionExecutionKind.STEWARDSHIP
        or request.open_mode is not WorldSessionOpenMode.START
        or (
            request.session_id,
            request.task_world_id,
            request.agent_tenure_id,
        )
        != (
            result.session_id,
            result.task_world_id,
            result.agent_tenure_id,
        )
    ):
        raise ValueError("pump-station Harbor session request and result differ")
    resumed = PumpStationWorldSessionFactory(
        root / "world-run",
        package_root=Path(package_dir),
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="harbor-verification",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="harbor-verification",
            run_id=end_snapshot.run_id,
            episode_id=end_snapshot.episode_id,
            world_branch_id=end_snapshot.world_branch_id,
            start_snapshot=end_snapshot,
        )
    )
    report = resumed.verify()
    stored_report = _read_json(root / "verification-report.json")
    expected_report = _verification_payload(report)
    if not report.valid or stored_report != expected_report:
        raise ValueError("pump-station Harbor verification evidence differs")
    transition_count = end_snapshot.sequence - start_snapshot.sequence
    _verify_controller_completion(root, inventory)
    _verify_stewardship_objective(
        actor_view=_read_actor_view(resumed),
        report=report,
        transition_count=transition_count,
    )
    return {
        "valid": True,
        "objective_complete": True,
        "reward_owner": "harbor_verifier",
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "start_snapshot": start_snapshot.model_dump(mode="json"),
        "end_snapshot": end_snapshot.model_dump(mode="json"),
        "transition_count": transition_count,
        "replayed_transition_ids": list(report.replayed_transition_ids),
        "final_state_id": report.final_state_id,
    }


def _verify_controller_completion(
    root: Path,
    inventory: dict[str, Any],
) -> None:
    controller_id = inventory.get("controller_id")
    if controller_id == PUMP_STATION_REFERENCE_CONTROLLER_ID:
        return
    if not isinstance(controller_id, str) or not controller_id.strip():
        raise ValueError("pump-station controller identity is missing")
    agent_result = _read_json(root / "agent-result.json")
    if (
        agent_result.get("status") != "completed"
        or agent_result.get("failure_kind") is not None
        or agent_result.get("resolved_model") != controller_id
    ):
        raise ValueError("pump-station model controller did not complete")


def _read_actor_view(session: Any) -> dict[str, Any]:
    payload = json.loads(session.observe_pump_station())
    if not isinstance(payload, dict):
        raise ValueError("pump-station final actor view is not an object")
    return cast(dict[str, Any], payload)


def _verify_stewardship_objective(
    *,
    actor_view: dict[str, Any],
    report: PumpStationVerificationReport,
    transition_count: int,
) -> None:
    state = _mapping(actor_view.get("current_state"), "final actor state")
    evidence = state.get("evidence")
    work_orders = state.get("work_orders")
    verification_passed = isinstance(evidence, list) and any(
        isinstance(item, dict)
        and item.get("kind") == "post_maintenance_verification"
        and item.get("passed") is True
        for item in evidence
    )
    closure_recorded = isinstance(work_orders, list) and any(
        isinstance(item, dict)
        and item.get("status") == "provisionally_closed"
        for item in work_orders
    )
    if (
        transition_count < 1
        or report.open_obligation_ids
        or not verification_passed
        or not closure_recorded
    ):
        raise ValueError("pump-station stewardship objective is incomplete")


def _verify_inventory(root: Path, inventory: dict[str, Any]) -> None:
    raw_entries = inventory.get("artifacts")
    if not isinstance(raw_entries, list):
        raise ValueError("pump-station Harbor artifact inventory is not a list")
    expected: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {
            ".world-run.lock",
            "artifact-inventory.json",
            "current.json",
        }:
            continue
        payload = path.read_bytes()
        expected.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    if raw_entries != expected:
        raise ValueError("pump-station Harbor artifact inventory differs from files")


def _verification_payload(
    report: PumpStationVerificationReport,
) -> dict[str, Any]:
    return {
        "valid": report.valid,
        "issues": list(report.issues),
        "replayed_transition_ids": list(report.replayed_transition_ids),
        "final_state_id": report.final_state_id,
        "active_restriction_ids": list(report.active_restriction_ids),
        "open_obligation_ids": list(report.open_obligation_ids),
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"pump-station Harbor {label} must be an object")
    return cast(dict[str, Any], value)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one exported pump-station Harbor session")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--verifier-runtime", type=Path, required=True)
    parser.add_argument("--reward-path", type=Path, required=True)
    parser.add_argument("--details-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        details = verify_pump_station_harbor_run(
            run_dir=args.run_dir,
            export_manifest_path=args.export_manifest,
            package_dir=args.package_dir,
            verifier_runtime_path=args.verifier_runtime,
        )
    except Exception as error:
        _write_json(args.reward_path, {"reward": 0.0})
        _write_json(
            args.details_path,
            {
                "valid": False,
                "reward_owner": "harbor_verifier",
                "error": str(error),
            },
        )
        print(str(error), file=sys.stderr)
        return 1
    _write_json(args.reward_path, {"reward": 1.0})
    _write_json(args.details_path, details)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ("verify_pump_station_harbor_run",)
