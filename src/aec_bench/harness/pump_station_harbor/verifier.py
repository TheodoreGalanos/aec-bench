# ABOUTME: Independently reloads and verifies registered pump-station Harbor evidence.
# ABOUTME: Keeps artifact reconciliation outside the pump functional core and evaluator.

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from pydantic import TypeAdapter

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRunRef,
    ContinualWorldProfileRef,
    WorldBuildRef,
)
from aec_bench.contracts.world_session import StewardshipStateSnapshotRef, WorldSessionRequest, WorldSessionResult
from aec_bench.evaluation.stewardship import evaluate_pump_station_reference_run
from aec_bench.harness.harbor_task_exporting.stable_io import directory_sha256, file_sha256
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    is_pump_station_harbor_inventory_artifact,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    validate_pump_station_rollout_child_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceRepository,
    verify_temporal_evidence_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)


def verify_pump_station_harbor_run(
    *,
    run_dir: Path,
    export_manifest_path: Path,
    package_dir: Path,
    reference_system_dir: Path | None = None,
    initial_run_dir: Path | None = None,
    verifier_runtime_path: Path | None = None,
) -> dict[str, Any]:
    """Verify one completed registered episode without trusting agent claims."""
    root = Path(run_dir)
    manifest = _read_json(export_manifest_path)
    if (
        manifest.get("execution_kind") != PUMP_STATION_HARBOR_EXECUTION_KIND
        or manifest.get("task_world_id") != PUMP_STATION_TASK_WORLD_ID
    ):
        raise ValueError("pump-station Harbor export identity differs")
    definition = pump_station_continual_world_definition()
    world_build = TypeAdapter(WorldBuildRef).validate_python(manifest.get("world_build"))
    profile_ref = TypeAdapter(ContinualWorldProfileRef).validate_python(manifest.get("continual_profile"))
    if world_build != definition.ref or profile_ref not in definition.profiles:
        raise ValueError("pump-station Harbor profile is not registered")
    _verify_export_authority(
        manifest=manifest,
        package_dir=package_dir,
        reference_system_dir=reference_system_dir,
        profile_ref=profile_ref,
        verifier_runtime_path=verifier_runtime_path,
    )
    child_ref = _verify_initial_run(
        manifest=manifest,
        initial_run_dir=initial_run_dir,
        world_build=world_build,
        profile_ref=profile_ref,
    )

    request = WorldSessionRequest.model_validate(_read_json(root / "world-session-request.json"))
    result = WorldSessionResult.model_validate(_read_json(root / "world-session-result.json"))
    inventory = _read_json(root / "artifact-inventory.json")
    verifier_payload = _mapping(manifest.get("verifier"), "verifier")
    package_payload = _mapping(manifest.get("package"), "package")
    package = load_reference_package(Path(package_dir), profile_id=str(package_payload["profile_id"]))
    if (
        inventory.get("execution_kind") != PUMP_STATION_HARBOR_EXECUTION_KIND
        or inventory.get("task_world_id") != PUMP_STATION_TASK_WORLD_ID
        or inventory.get("export_manifest_sha256") != file_sha256(export_manifest_path)
        or inventory.get("verifier_runtime_sha256") != verifier_payload.get("runtime_wheel_sha256")
        or inventory.get("package_content_id") != package.package_content_id
        or inventory.get("package_manifest_content_id") != package.manifest_content_id
        or tuple(inventory.get("tool_names", ())) != PUMP_STATION_ACTOR_ACTION_NAMES
    ):
        raise ValueError("pump-station Harbor artifact inventory identity differs")
    _verify_inventory(root, inventory)
    start = StewardshipStateSnapshotRef.model_validate(inventory.get("start_snapshot"))
    end = StewardshipStateSnapshotRef.model_validate(inventory.get("end_snapshot"))
    if (
        request.start_snapshot != start
        or result.snapshot != end
        or request.run_id != end.run_id
        or request.episode_id != end.episode_id
        or request.world_branch_id != end.world_branch_id
        or request.session_id != result.session_id
        or request.agent_tenure_id != result.agent_tenure_id
        or int(inventory.get("transition_count", -1)) != end.sequence - start.sequence
    ):
        raise ValueError("pump-station Harbor episode request and result differ")

    repository = PumpStationWorldRunRepository(root / "world-run")
    current = repository.current_snapshot()
    if _snapshot_identity(current) != _snapshot_identity(end):
        raise ValueError("pump-station Harbor terminal snapshot differs from the durable run")
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=current)
    report = run.verify()
    if not report.valid or _read_json(root / "verification-report.json") != _verification_payload(report):
        raise ValueError("pump-station Harbor verification evidence differs")

    actor_bindings = {
        step.command.request_id: (
            step.command.information_set_id or "",
            step.command.actor_view_id or "",
        )
        for step in repository.command_steps()
        if step.command.kind == "actor"
    }
    temporal = verify_temporal_evidence_repository(
        TemporalEvidenceRepository(repository.root / "temporal-evidence"),
        package=run.package,
        actor_bindings=actor_bindings,
    )
    if not temporal.valid or _read_json(root / "temporal-verification-report.json") != temporal.model_dump(mode="json"):
        raise ValueError("pump-station temporal verification evidence differs")
    temporal_inventory = _mapping(inventory.get("temporal_evidence"), "temporal evidence inventory")
    if (
        temporal_inventory.get("verification_report_id") != temporal.content_sha256
        or temporal_inventory.get("access_count") != temporal.access_count
        or temporal_inventory.get("reliance_count") != temporal.reliance_count
        or temporal_inventory.get("carrier_count") != temporal.carrier_count
    ):
        raise ValueError("pump-station temporal inventory differs")

    _verify_controller_completion(root, inventory)
    evaluation = None
    if child_ref is None:
        evaluation = evaluate_pump_station_reference_run(run)
        if not evaluation.valid:
            raise ValueError("registered pump-station Harbor evaluation failed")
    else:
        _verify_rollout_child_execution(
            repository=repository,
            request=request,
            result=result,
            child_ref=child_ref,
            controller_id=inventory.get("controller_id"),
        )
    details: dict[str, Any] = {
        "valid": True,
        "objective_complete": True,
        "reward_owner": "harbor_verifier",
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "start_snapshot": start.model_dump(mode="json"),
        "end_snapshot": end.model_dump(mode="json"),
        "transition_count": end.sequence - start.sequence,
        "replayed_transition_ids": list(report.replayed_transition_ids),
        "final_state_id": report.final_state_id,
        "temporal_evidence": temporal.model_dump(mode="json"),
    }
    if evaluation is not None:
        details["evaluation"] = evaluation.model_dump(mode="json")
    return details


def _verify_export_authority(
    *,
    manifest: dict[str, Any],
    package_dir: Path,
    reference_system_dir: Path | None,
    profile_ref: ContinualWorldProfileRef,
    verifier_runtime_path: Path | None,
) -> None:
    if reference_system_dir is None or verifier_runtime_path is None:
        raise ValueError("registered pump-station Harbor verifier lacks exported authority")
    package_payload = _mapping(manifest.get("package"), "package")
    package = load_reference_package(Path(package_dir), profile_id=str(package_payload["profile_id"]))
    if (
        package.package_content_id != package_payload.get("package_content_id")
        or package.manifest_content_id != package_payload.get("manifest_content_id")
        or directory_sha256(package_dir) != package_payload.get("directory_sha256")
    ):
        raise ValueError("pump-station Harbor package evidence differs")
    reference_payload = _mapping(manifest.get("reference_system"), "reference system")
    reference = load_reference_system(root=reference_system_dir)
    if (
        reference.descriptor_id != reference_payload.get("descriptor_id")
        or reference.descriptor_content_id != reference_payload.get("descriptor_content_id")
        or directory_sha256(reference_system_dir) != reference_payload.get("directory_sha256")
        or reference.descriptor_content_id != profile_ref.profile_content_sha256
    ):
        raise ValueError("pump-station Harbor reference-system evidence differs")
    verifier_payload = _mapping(manifest.get("verifier"), "verifier")
    if file_sha256(verifier_runtime_path) != verifier_payload.get("runtime_wheel_sha256"):
        raise ValueError("pump-station Harbor verifier runtime differs")


def _verify_initial_run(
    *,
    manifest: dict[str, Any],
    initial_run_dir: Path | None,
    world_build: WorldBuildRef,
    profile_ref: ContinualWorldProfileRef,
) -> ContinualRolloutChildRunRef | None:
    payload = manifest.get("initial_run")
    if payload is None:
        if initial_run_dir is not None:
            raise ValueError("pump-station Harbor verifier received an unexpected initial run")
        return None
    if initial_run_dir is None:
        raise ValueError("pump-station Harbor verifier lacks its initial run")
    initial = _mapping(payload, "initial run")
    if directory_sha256(initial_run_dir) != initial.get("directory_sha256"):
        raise ValueError("pump-station Harbor initial run evidence differs")
    child_ref = ContinualRolloutChildRunRef.model_validate(initial.get("rollout_child_ref"))
    validate_pump_station_rollout_child_run(
        initial_run_dir,
        child_ref,
        world_build=world_build,
        profile_ref=profile_ref,
    )
    return child_ref


def _verify_rollout_child_execution(
    *,
    repository: PumpStationWorldRunRepository,
    request: WorldSessionRequest,
    result: WorldSessionResult,
    child_ref: ContinualRolloutChildRunRef,
    controller_id: object,
) -> None:
    start = request.start_snapshot
    steps = repository.command_steps()
    command = steps[0].command if len(steps) == 1 else None
    manifest = repository.load_manifest()
    expected_action = (
        "request_condition_check" if controller_id == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID else None
    )
    if (
        start is None
        or _snapshot_identity(start) != _snapshot_identity(child_ref.initial_snapshot)
        or result.snapshot.sequence != child_ref.initial_snapshot.sequence + 1
        or len(steps) != 1
        or getattr(command, "kind", None) != "actor"
        or getattr(command, "action_name", None) not in PUMP_STATION_ACTOR_ACTION_NAMES
        or (expected_action is not None and getattr(command, "action_name", None) != expected_action)
        or pump_station_artifact_id(manifest) != child_ref.child_manifest_content_sha256
    ):
        raise ValueError("pump-station Harbor rollout child execution differs")


def _verify_controller_completion(root: Path, inventory: dict[str, Any]) -> None:
    controller_id = inventory.get("controller_id")
    if controller_id == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID:
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


def _verify_inventory(root: Path, inventory: dict[str, Any]) -> None:
    expected: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(root, path):
            continue
        payload = path.read_bytes()
        expected.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    if inventory.get("artifacts") != expected:
        raise ValueError("pump-station Harbor artifact inventory differs from files")


def _snapshot_identity(snapshot: Any) -> tuple[Any, ...]:
    return (
        snapshot.run_id,
        snapshot.episode_id,
        snapshot.world_branch_id,
        snapshot.sequence,
        snapshot.state_id,
        snapshot.commit_id,
    )


def _verification_payload(report: Any) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(asdict(report))))


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one exported pump-station Harbor episode")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--reference-system-dir", type=Path, required=True)
    parser.add_argument("--initial-run-dir", type=Path)
    parser.add_argument("--verifier-runtime", type=Path, required=True)
    parser.add_argument("--reward-path", type=Path, required=True)
    parser.add_argument("--details-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        details = verify_pump_station_harbor_run(
            run_dir=args.run_dir,
            export_manifest_path=args.export_manifest,
            package_dir=args.package_dir,
            reference_system_dir=args.reference_system_dir,
            initial_run_dir=args.initial_run_dir,
            verifier_runtime_path=args.verifier_runtime,
        )
    except Exception as error:
        _write_json(args.reward_path, {"reward": 0.0})
        _write_json(
            args.details_path,
            {"valid": False, "reward_owner": "harbor_verifier", "error": str(error)},
        )
        print(str(error), file=sys.stderr)
        return 1
    _write_json(args.reward_path, {"reward": 1.0})
    _write_json(args.details_path, details)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ("verify_pump_station_harbor_run",)
