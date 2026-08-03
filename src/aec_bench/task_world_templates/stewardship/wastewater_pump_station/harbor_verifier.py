# ABOUTME: Independently reloads and verifies exported pump-station Harbor evidence.
# ABOUTME: Reconciles package, session, inventory, and durable transition identities.

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRunRef,
    ContinualWorldDefinitionRef,
    ContinualWorldProfileRef,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.evaluation.stewardship import evaluate_pump_station_reference_run
from aec_bench.task_world_templates.harbor_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    validate_pump_station_rollout_child_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
    PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION,
    is_pump_station_harbor_inventory_artifact,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION,
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    PumpStationVerificationReportV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceRepository,
    verify_temporal_evidence_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    PUMP_STATION_RICH_WORK_TOOL_NAMES,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSessionFactory,
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
    """Verify one completed Harbor world session without trusting agent claims."""

    root = Path(run_dir)
    manifest = _read_json(export_manifest_path)
    bridge_payload = _mapping(manifest.get("bridge"), "bridge")
    if bridge_payload.get("maintenance_review") is True:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_harbor import (
            verify_pump_station_harbor_review_run,
        )

        return verify_pump_station_harbor_review_run(
            run_dir=root,
            export_manifest_path=export_manifest_path,
            package_dir=package_dir,
            verifier_runtime_path=verifier_runtime_path,
        )
    schema_version = manifest.get("schema_version")
    registered_profile = schema_version == PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION
    if (
        schema_version
        not in {
            PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
            PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION,
        }
        or manifest.get("execution_kind") != PUMP_STATION_HARBOR_EXECUTION_KIND
        or manifest.get("task_world_id") != PUMP_STATION_TASK_WORLD_ID
    ):
        raise ValueError("pump-station Harbor export identity differs")
    profile_ref: ContinualWorldProfileRef | None = None
    rollout_child_ref: ContinualRolloutChildRunRef | None = None
    if registered_profile:
        definition = pump_station_continual_world_definition()
        definition_ref = ContinualWorldDefinitionRef.model_validate(manifest.get("continual_definition"))
        if definition_ref != definition.ref:
            raise ValueError("pump-station Harbor definition is not registered")
        profile_ref = ContinualWorldProfileRef.model_validate(manifest.get("continual_profile"))
        if profile_ref not in definition.spec.profiles:
            raise ValueError("pump-station Harbor profile is not registered")
        if reference_system_dir is None:
            raise ValueError("registered pump-station Harbor verifier lacks its reference system")
        reference_payload = _mapping(manifest.get("reference_system"), "reference_system")
        reference_system = load_reference_system(root=reference_system_dir)
        if (
            reference_system.descriptor_id != reference_payload.get("descriptor_id")
            or reference_system.descriptor_content_id != reference_payload.get("descriptor_content_id")
            or directory_sha256(reference_system_dir) != reference_payload.get("directory_sha256")
            or reference_system.descriptor_content_id != profile_ref.profile_content_sha256
        ):
            raise ValueError("pump-station Harbor reference system evidence differs")
        if "initial_run" in manifest:
            initial_run_payload = _mapping(manifest.get("initial_run"), "initial run")
            if (
                set(initial_run_payload)
                != {
                    "directory_sha256",
                    "path",
                    "rollout_child_ref",
                }
                or initial_run_payload.get("path") != "tests/initial-world-run"
            ):
                raise ValueError("pump-station Harbor initial run fields differ")
            if initial_run_dir is None:
                raise ValueError("pump-station Harbor verifier lacks its initial run")
            if directory_sha256(initial_run_dir) != initial_run_payload.get("directory_sha256"):
                raise ValueError("pump-station Harbor initial run evidence differs")
            rollout_child_ref = ContinualRolloutChildRunRef.model_validate(
                initial_run_payload.get("rollout_child_ref"),
            )
            validate_pump_station_rollout_child_run(
                initial_run_dir,
                rollout_child_ref,
                definition_ref=definition_ref,
                profile_ref=profile_ref,
            )
    package_payload = _mapping(manifest.get("package"), "package")
    rich_work_processes = bool(bridge_payload.get("rich_work_processes", False))
    evidence_health = bool(bridge_payload.get("evidence_health", False))
    temporal_evidence = bool(bridge_payload.get("temporal_evidence", False))
    expected_tools = (
        PUMP_STATION_ACTOR_ACTION_NAMES_V2
        if registered_profile
        else PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES
        if temporal_evidence
        else PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
        if evidence_health
        else PUMP_STATION_RICH_WORK_TOOL_NAMES
        if rich_work_processes
        else PUMP_STATION_TOOL_NAMES
    )
    if tuple(bridge_payload.get("allowed_tools", ())) != expected_tools:
        raise ValueError("pump-station Harbor bridge tools differ")
    package = load_reference_package(package_dir, profile_id=str(package_payload.get("profile_id")))
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
        or tuple(inventory.get("tool_names", ())) != expected_tools
    ):
        raise ValueError("pump-station Harbor artifact inventory identity differs")
    _verify_inventory(root, inventory)
    start_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("start_snapshot"))
    end_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("end_snapshot"))
    if (
        result.snapshot != end_snapshot
        or int(inventory.get("transition_count", -1)) != end_snapshot.sequence - start_snapshot.sequence
        or request.execution_kind is not WorldSessionExecutionKind.STEWARDSHIP
        or request.open_mode is not (WorldSessionOpenMode.RESUME if rich_work_processes else WorldSessionOpenMode.START)
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
    resumed: Any | None = None
    registered_evaluation = None
    report: PumpStationVerificationReport | PumpStationVerificationReportV4
    if registered_profile:
        repository = PumpStationWorldRunRepository(root / "world-run")
        current_snapshot = repository.current_snapshot()
        if (
            current_snapshot.run_id,
            current_snapshot.episode_id,
            current_snapshot.world_branch_id,
            current_snapshot.sequence,
            current_snapshot.state_id,
            current_snapshot.commit_id,
        ) != (
            end_snapshot.run_id,
            end_snapshot.episode_id,
            end_snapshot.world_branch_id,
            end_snapshot.sequence,
            end_snapshot.state_id,
            end_snapshot.commit_id,
        ):
            raise ValueError("pump-station Harbor terminal snapshot differs from the durable run")
        registered_run = PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=current_snapshot,
        )
        report = registered_run.verify_v4()
        if rollout_child_ref is not None:
            _verify_rollout_child_execution(
                repository=repository,
                request=request,
                result=result,
                child_ref=rollout_child_ref,
                controller_id=inventory.get("controller_id"),
                inventory_start=start_snapshot,
            )
        else:
            registered_evaluation = evaluate_pump_station_reference_run(registered_run)
            if not registered_evaluation.valid:
                raise ValueError("registered pump-station Harbor evaluation failed")
    else:
        resumed = PumpStationWorldSessionFactory(
            root / "world-run",
            package_root=Path(package_dir),
            rich_work_processes=rich_work_processes,
            evidence_health=evidence_health,
            temporal_evidence=temporal_evidence,
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
    temporal_report: dict[str, Any] | None = None
    if temporal_evidence:
        if registered_profile:
            proposal_bindings = {
                step.proposal.context.proposal_id: (
                    step.proposal.context.information_set_id,
                    step.proposal.context.base_view_id,
                )
                for step in registered_run.repository.v4_steps()
                if step.proposal is not None
            }
            recomputed_temporal = verify_temporal_evidence_repository(
                TemporalEvidenceRepository(root / "world-run" / "temporal-evidence"),
                package=registered_run.package,
                proposal_bindings=proposal_bindings,
            )
        else:
            assert resumed is not None
            recomputed_temporal = resumed.verify_temporal_evidence()
        temporal_report = recomputed_temporal.model_dump(mode="json")
        if not recomputed_temporal.valid or _read_json(root / "temporal-verification-report.json") != temporal_report:
            raise ValueError("pump-station temporal verification evidence differs")
        temporal_inventory = _mapping(
            inventory.get("temporal_evidence"),
            "temporal evidence inventory",
        )
        if (
            temporal_inventory.get("verification_report_id") != recomputed_temporal.content_sha256
            or temporal_inventory.get("access_count") != recomputed_temporal.access_count
            or temporal_inventory.get("reliance_count") != recomputed_temporal.reliance_count
            or temporal_inventory.get("carrier_count") != recomputed_temporal.carrier_count
        ):
            raise ValueError("pump-station temporal inventory differs")
    transition_count = end_snapshot.sequence - start_snapshot.sequence
    _verify_controller_completion(root, inventory)
    if not registered_profile:
        assert resumed is not None
        assert isinstance(report, PumpStationVerificationReport)
        _verify_stewardship_objective(
            actor_view=_read_actor_view(resumed),
            report=report,
            transition_count=transition_count,
            rich_work_processes=rich_work_processes,
            evidence_health=evidence_health,
        )
    details = {
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
    if temporal_report is not None:
        details["temporal_evidence"] = temporal_report
    if registered_evaluation is not None:
        details["evaluation"] = registered_evaluation.model_dump(mode="json")
    return details


def _verify_rollout_child_execution(
    *,
    repository: PumpStationWorldRunRepository,
    request: WorldSessionRequest,
    result: WorldSessionResult,
    child_ref: ContinualRolloutChildRunRef,
    controller_id: object,
    inventory_start: StewardshipStateSnapshotRef,
) -> None:
    """Prove one completed session is a one-action continuation of the bound child."""

    start_snapshot = request.start_snapshot
    if start_snapshot is None:
        raise ValueError("pump-station Harbor rollout child has no start snapshot")
    expected_identity = (
        child_ref.run_id,
        child_ref.episode_id,
        child_ref.world_branch_id,
        child_ref.initial_snapshot.sequence,
        child_ref.initial_snapshot.state_id,
        child_ref.initial_snapshot.commit_id,
    )
    request_identity = (
        request.run_id,
        request.episode_id,
        request.world_branch_id,
        start_snapshot.sequence,
        start_snapshot.state_id,
        start_snapshot.commit_id,
    )
    inventory_identity = (
        inventory_start.run_id,
        inventory_start.episode_id,
        inventory_start.world_branch_id,
        inventory_start.sequence,
        inventory_start.state_id,
        inventory_start.commit_id,
    )
    result_identity = (
        result.snapshot.run_id,
        result.snapshot.episode_id,
        result.snapshot.world_branch_id,
    )
    manifest = repository.load_manifest()
    manifest_identity = (
        manifest.run_id,
        manifest.episode_id,
        manifest.world_branch_id,
    )
    steps = repository.v4_steps()
    command = steps[0].command if len(steps) == 1 else None
    action_name = getattr(command, "action_name", None)
    command_base = (
        getattr(command, "run_id", None),
        getattr(command, "episode_id", None),
        getattr(command, "world_branch_id", None),
        getattr(command, "based_on_sequence", None),
        getattr(command, "base_state_id", None),
        getattr(command, "base_commit_id", None),
    )
    expected_action = (
        "request_condition_check" if controller_id == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID else None
    )
    if (
        request.open_mode is not WorldSessionOpenMode.RESUME
        or request_identity != expected_identity
        or inventory_identity != expected_identity
        or result_identity != expected_identity[:3]
        or manifest_identity != expected_identity[:3]
        or pump_station_artifact_id(manifest, record_profile="manifest-v2") != child_ref.child_manifest_content_sha256
        or result.snapshot.sequence != child_ref.initial_snapshot.sequence + 1
        or len(steps) != 1
        or getattr(command, "kind", None) != "actor"
        or getattr(command, "session_id", None) != request.session_id
        or getattr(command, "agent_tenure_id", None) != request.agent_tenure_id
        or command_base != expected_identity
        or action_name not in PUMP_STATION_ACTOR_ACTION_NAMES_V2
        or (expected_action is not None and action_name != expected_action)
    ):
        raise ValueError("pump-station Harbor rollout child execution differs")


def _verify_controller_completion(
    root: Path,
    inventory: dict[str, Any],
) -> None:
    controller_id = inventory.get("controller_id")
    if controller_id in {
        PUMP_STATION_REFERENCE_CONTROLLER_ID,
        PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    }:
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
    rich_work_processes: bool,
    evidence_health: bool,
) -> None:
    state = _mapping(actor_view.get("current_state"), "final actor state")
    evidence = state.get("evidence")
    work_orders = state.get("work_orders")
    verification_passed = isinstance(evidence, list) and any(
        isinstance(item, dict) and item.get("kind") == "post_maintenance_verification" and item.get("passed") is True
        for item in evidence
    )
    closure_recorded = isinstance(work_orders, list) and any(
        isinstance(item, dict) and item.get("status") == "provisionally_closed" for item in work_orders
    )
    if evidence_health:
        source = state.get("observation_source")
        processes = state.get("processes")
        condition_recorded = isinstance(evidence, list) and any(
            isinstance(item, dict) and item.get("kind") == "condition_check" and item.get("quality") == "suspect"
            for item in evidence
        )
        physical_inspection_requested = isinstance(processes, list) and any(
            isinstance(item, dict) and item.get("kind") == "inspection" for item in processes
        )
        source_suspect = isinstance(source, dict) and source.get("quality") == "suspect"
        if transition_count < 4 or not condition_recorded or not physical_inspection_requested or not source_suspect:
            raise ValueError("pump-station evidence-health objective is incomplete")
        return
    rich_completion = (
        isinstance(evidence, list)
        and any(
            isinstance(item, dict)
            and item.get("kind") == "functional_checks"
            and item.get("pump_id") == "pump-b"
            and item.get("passed") is True
            for item in evidence
        )
        and not state.get("resources", {}).get("repair_kit_available", True)
        and not any(
            isinstance(item, dict) and item.get("status") in {"active", "suspended"}
            for item in cast(list[object], state.get("processes", []))
        )
    )
    administrative_completion = rich_completion if rich_work_processes else closure_recorded
    if transition_count < 1 or report.open_obligation_ids or not verification_passed or not administrative_completion:
        raise ValueError("pump-station stewardship objective is incomplete")


def _verify_inventory(root: Path, inventory: dict[str, Any]) -> None:
    raw_entries = inventory.get("artifacts")
    if not isinstance(raw_entries, list):
        raise ValueError("pump-station Harbor artifact inventory is not a list")
    expected: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(
            root,
            path,
        ):
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
    report: PumpStationVerificationReport | PumpStationVerificationReportV4,
) -> dict[str, Any]:
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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one exported pump-station Harbor session")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--reference-system-dir", type=Path)
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
