# ABOUTME: Exports, runs, and independently verifies the ASW-8 reference system through Harbor v2.
# ABOUTME: Copies exact descriptor and station-data bytes while credentials remain outside the task.

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.task_world_templates.harbor_exporting.constants import (
    BASE_IMAGE,
    RUNTIME_DEPENDENCIES,
)
from aec_bench.task_world_templates.harbor_exporting.runtime_wheel import (
    build_verifier_runtime_wheel,
)
from aec_bench.task_world_templates.harbor_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_agent import (
    PumpStationCoupledAgentSession,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    PumpStationCoupledEvaluationResult,
    PumpStationCoupledVerificationReport,
    PumpStationSemanticOutcome,
    evaluate_coupled_run,
    semantic_outcome,
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_execution import (
    PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
    PumpStationReferenceControllerResult,
    execute_asw_8_reference_controller_through_interface,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    verify_coupled_temporal_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    bundled_reference_package_root,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    bundled_reference_system_root,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.verification import (
    verify_temporal_evidence_repository,
)
from aec_bench.trajectory.writer import TrajectoryWriter

PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION = "aecbench.pump-station-harbor-export.v2"
PUMP_STATION_ASW_8_HARBOR_RUN_VERSION = "aecbench.pump-station-harbor-run.v2"
PUMP_STATION_ASW_8_HARBOR_VERIFICATION_VERSION = "aecbench.pump-station-harbor-verification.v2"
PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE = "wastewater_pump_station_asw_8_reference"
PUMP_STATION_ASW_8_HARBOR_OUTPUT_PATH = "/workspace/world-session"
PUMP_STATION_ASW_8_HARBOR_EXECUTION_KIND: Final[Literal["stewardship_world_session"]] = "stewardship_world_session"
_MANIFEST_NAME = "world-session-export.json"


@dataclass(frozen=True, slots=True)
class ExportedPumpStationAsw8HarborTask:
    """Paths and identity for one exact ASW-8 Harbor task."""

    task_dir: Path
    manifest_path: Path
    package_dir: Path
    reference_system_dir: Path
    verifier_runtime_wheel_path: Path


@dataclass(frozen=True, slots=True)
class PumpStationAsw8HarborBridge:
    """Validated host-side authority for one exported ASW-8 task."""

    task_root: Path
    package_root: Path
    reference_system_root: Path
    export_manifest_path: Path
    export_manifest_sha256: str
    verifier_runtime_path: Path
    verifier_runtime_sha256: str
    allowed_tools: tuple[str, ...]
    output_path: str
    execution_kind: str
    task_world_id: str
    bridge_mode: str
    maintenance_review: bool = False
    rich_work_processes: bool = True
    evidence_health: bool = True
    temporal_evidence: bool = True


@dataclass(frozen=True, slots=True)
class CompletedPumpStationAsw8ModelSession:
    """Bounded model execution evidence over the closed ASW-8 actor surface."""

    session_id: str
    run: PumpStationCoupledRun
    verification: PumpStationCoupledVerificationReport
    adapter_result: AdapterResult
    output_dir: Path


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else canonical_stewardship_value(value, record_profile="v4")
    )
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def export_asw_8_harbor_task(
    task_dir: Path,
    *,
    project_root: Path,
) -> ExportedPumpStationAsw8HarborTask:
    """Materialize one provider-free Harbor task with exact ASW-8 artifacts."""
    destination = Path(task_dir)
    if destination.exists():
        raise FileExistsError(f"Harbor task output already exists: {destination}")
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    system = load_reference_system()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as raw:
        staging = Path(raw) / destination.name
        environment_dir = staging / "environment"
        tests_dir = staging / "tests"
        package_dir = tests_dir / "reference-package"
        reference_system_dir = tests_dir / "reference-system"
        runtime_dir = tests_dir / "runtime"
        environment_dir.mkdir(parents=True)
        runtime_dir.mkdir(parents=True)
        shutil.copytree(
            bundled_reference_package_root(profile_id=REFERENCE_PROFILE_V2),
            package_dir,
        )
        shutil.copytree(bundled_reference_system_root(), reference_system_dir)
        if load_reference_package(package_dir, profile_id=REFERENCE_PROFILE_V2) != package:
            raise ValueError("staged v2 station data differs")
        if load_reference_system(root=reference_system_dir) != system:
            raise ValueError("staged ASW-8 reference system differs")
        runtime = build_verifier_runtime_wheel(project_root=project_root, output_dir=runtime_dir)
        instruction = staging / "instruction.md"
        dockerfile = environment_dir / "Dockerfile"
        task_toml = staging / "task.toml"
        test_script = tests_dir / "test.sh"
        instruction.write_text(
            "# ASW-8 pump-station stewardship\n\n"
            "Execute the closed three-pump reference journey and preserve all evidence.\n",
            encoding="utf-8",
        )
        dockerfile.write_text(
            "# ABOUTME: Provides the public ASW-8 Harbor execution environment.\n"
            "# ABOUTME: Contains no credentials or private verifier authority.\n"
            f"FROM --platform=linux/amd64 {BASE_IMAGE}\n\n"
            f"RUN python -m pip install --no-cache-dir {' '.join(RUNTIME_DEPENDENCIES)}\n"
            "WORKDIR /workspace\n",
            encoding="utf-8",
        )
        task_toml.write_text(
            "# ABOUTME: Declares one provider-free ASW-8 Harbor task.\n"
            "# ABOUTME: Keeps independent reward ownership in the Harbor verifier.\n"
            'version = "1.0"\n\n'
            "[metadata]\n"
            'difficulty = "hard"\n'
            'category = "asset-stewardship"\n'
            'domain = "mechanical"\n'
            'visibility = "public"\n'
            'tags = ["asset-stewardship", "pump-station", "asw-8"]\n\n'
            "[agent]\n"
            "timeout_sec = 900.0\n\n"
            "[verifier]\n"
            "timeout_sec = 600.0\n\n"
            "[environment]\n"
            "build_timeout_sec = 1800.0\n"
            "cpus = 2\n"
            "memory_mb = 4096\n"
            "storage_mb = 10240\n"
            "allow_internet = false\n",
            encoding="utf-8",
        )
        test_script.write_text(
            "#!/bin/sh\n"
            "# ABOUTME: Runs the independent ASW-8 verifier after the Harbor agent phase.\n"
            "# ABOUTME: Replays v4 and recomputes all four conservation sections.\n"
            "set -eu\n"
            f'RUN_DIR="${{AEC_BENCH_WORLD_SESSION_DIR:-{PUMP_STATION_ASW_8_HARBOR_OUTPUT_PATH}}}"\n'
            f'EXPORT_MANIFEST="${{AEC_BENCH_EXPORT_MANIFEST:-/tests/{_MANIFEST_NAME}}}"\n'
            'PACKAGE_DIR="${AEC_BENCH_REFERENCE_PACKAGE_DIR:-/tests/reference-package}"\n'
            'REFERENCE_SYSTEM_DIR="${AEC_BENCH_REFERENCE_SYSTEM_DIR:-/tests/reference-system}"\n'
            f'VERIFIER_RUNTIME="${{AEC_BENCH_VERIFIER_RUNTIME:-/tests/runtime/{runtime.path.name}}}"\n'
            'REWARD_PATH="${AEC_BENCH_REWARD_PATH:-/logs/verifier/reward.json}"\n'
            'DETAILS_PATH="${AEC_BENCH_DETAILS_PATH:-/logs/verifier/details.json}"\n'
            'PYTHON_BIN="${AEC_BENCH_PYTHON:-python3}"\n'
            'RUNTIME_DIR="$(mktemp -d)"\n'
            '"$PYTHON_BIN" -m zipfile -e "$VERIFIER_RUNTIME" "$RUNTIME_DIR"\n'
            'PYTHONPATH="$RUNTIME_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" '
            "-m aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_harbor "
            '--verify --run-dir "$RUN_DIR" --export-manifest "$EXPORT_MANIFEST" '
            '--package-dir "$PACKAGE_DIR" --reference-system-dir "$REFERENCE_SYSTEM_DIR" '
            '--reward-path "$REWARD_PATH" --details-path "$DETAILS_PATH"\n',
            encoding="utf-8",
        )
        test_script.chmod(0o755)
        manifest = {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION,
            "execution_kind": PUMP_STATION_ASW_8_HARBOR_EXECUTION_KIND,
            "task_world_id": "wastewater-pump-station-stewardship.v1",
            "package": {
                "path": "tests/reference-package",
                "profile_id": package.profile_id,
                "package_content_id": package.package_content_id,
                "manifest_content_id": package.manifest_content_id,
                "directory_sha256": directory_sha256(package_dir),
            },
            "reference_system": {
                "path": "tests/reference-system",
                "descriptor_id": system.descriptor_id,
                "descriptor_content_id": system.descriptor_content_id,
                "directory_sha256": directory_sha256(reference_system_dir),
            },
            "agent_surface": {
                "instruction_sha256": file_sha256(instruction),
                "dockerfile_sha256": file_sha256(dockerfile),
                "allow_internet": False,
            },
            "bridge": {
                "mode": PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE,
                "allowed_tools": list(PUMP_STATION_ACTOR_ACTION_NAMES_V2),
                "output_path": PUMP_STATION_ASW_8_HARBOR_OUTPUT_PATH,
                "controller_modes": ["deterministic_reference", "model_tool_loop"],
            },
            "harbor": {
                "reward_owner": "harbor_verifier",
                "task_toml_sha256": file_sha256(task_toml),
                "test_script_sha256": file_sha256(test_script),
            },
            "verifier": {
                "runtime_wheel": f"tests/runtime/{runtime.path.name}",
                "runtime_wheel_sha256": runtime.sha256,
                "source_tree_sha256": runtime.source_tree_sha256,
            },
        }
        _write_json(staging / _MANIFEST_NAME, manifest)
        _write_json(tests_dir / _MANIFEST_NAME, manifest)
        staging.rename(destination)
    return ExportedPumpStationAsw8HarborTask(
        task_dir=destination,
        manifest_path=destination / _MANIFEST_NAME,
        package_dir=destination / "tests" / "reference-package",
        reference_system_dir=destination / "tests" / "reference-system",
        verifier_runtime_wheel_path=destination / "tests" / "runtime" / runtime.path.name,
    )


def load_asw_8_harbor_bridge(environment_dir: Path) -> PumpStationAsw8HarborBridge:
    """Load and verify an exact ASW-8 export before execution."""
    task_root = Path(environment_dir).parent.resolve(strict=True)
    manifest_path = task_root / _MANIFEST_NAME
    manifest = cast(dict[str, Any], _read_json(manifest_path))
    if manifest.get("schema_version") != PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION:
        raise ValueError("ASW-8 Harbor export version differs")
    package_value = cast(dict[str, Any], manifest["package"])
    system_value = cast(dict[str, Any], manifest["reference_system"])
    bridge_value = cast(dict[str, Any], manifest["bridge"])
    verifier_value = cast(dict[str, Any], manifest["verifier"])
    package_root = task_root / str(package_value["path"])
    system_root = task_root / str(system_value["path"])
    package = load_reference_package(package_root, profile_id=REFERENCE_PROFILE_V2)
    system = load_reference_system(root=system_root)
    if (
        package.package_content_id != package_value.get("package_content_id")
        or directory_sha256(package_root) != package_value.get("directory_sha256")
        or system.descriptor_content_id != system_value.get("descriptor_content_id")
        or directory_sha256(system_root) != system_value.get("directory_sha256")
    ):
        raise ValueError("ASW-8 Harbor authority artifacts differ")
    runtime = task_root / str(verifier_value["runtime_wheel"])
    if file_sha256(runtime) != verifier_value.get("runtime_wheel_sha256"):
        raise ValueError("ASW-8 verifier runtime differs")
    if bridge_value.get("mode") != PUMP_STATION_ASW_8_HARBOR_BRIDGE_MODE:
        raise ValueError("ASW-8 Harbor bridge mode differs")
    return PumpStationAsw8HarborBridge(
        task_root=task_root,
        package_root=package_root,
        reference_system_root=system_root,
        export_manifest_path=manifest_path,
        export_manifest_sha256=file_sha256(manifest_path),
        verifier_runtime_path=runtime,
        verifier_runtime_sha256=file_sha256(runtime),
        allowed_tools=tuple(bridge_value["allowed_tools"]),
        output_path=str(bridge_value["output_path"]),
        execution_kind=str(manifest["execution_kind"]),
        task_world_id=str(manifest["task_world_id"]),
        bridge_mode=str(bridge_value["mode"]),
    )


def run_asw_8_harbor_reference_session(
    *,
    bridge: PumpStationAsw8HarborBridge,
    output_dir: Path,
    session_identity: str,
) -> PumpStationReferenceControllerResult:
    """Run the fixed controller and publish the complete Harbor v2 evidence set."""
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"ASW-8 session output exists: {destination}")
    destination.mkdir(parents=True)
    world_run_root = destination / "world-run"
    result = execute_asw_8_reference_controller_through_interface(
        run_root=world_run_root,
        run_id=f"asw-8-{session_identity}",
        world_branch_id=f"branch-{session_identity}",
    )
    report = verify_coupled_run(result.run)
    evaluation = evaluate_coupled_run(result.run)
    package = load_reference_package(bridge.package_root, profile_id=REFERENCE_PROFILE_V2)
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        package,
        world_branch_id=result.run.manifest.world_branch_id,
    )
    temporal_dir = destination / "temporal-evidence"
    for name, value in (
        ("capability.json", bundle.capability),
        ("corpus-manifest.json", bundle.corpus_manifest),
        ("lineage.json", bundle.lineage),
        ("availability.json", bundle.availability),
        ("retrieval-policy.json", bundle.retrieval_policy),
        ("access-policy.json", bundle.access_policy),
        ("branch-policy.json", bundle.branch_policy),
        ("cost-policy.json", bundle.cost_policy),
        ("access-ledger.json", result.temporal_access),
    ):
        _write_json(temporal_dir / name, value)
    start = create_start_snapshot(result)
    end = create_end_snapshot(result)
    _write_json(
        destination / "world-session-request.json",
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_RUN_VERSION,
            "session_id": session_identity,
            "controller_id": PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
            "start_snapshot": start,
        },
    )
    _write_json(
        destination / "world-session-result.json",
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_RUN_VERSION,
            "session_id": session_identity,
            "controller_id": PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
            "end_snapshot": end,
            "transition_count": len(result.run.receipts),
            "tool_names": PUMP_STATION_ACTOR_ACTION_NAMES_V2,
        },
    )
    _write_json(destination / "verification-report.json", report)
    _write_json(destination / "evaluation.json", evaluation)
    _write_json(destination / "semantic-outcome.json", result.semantic_outcome)
    _write_json(
        destination / "temporal-verification-report.json",
        {
            "valid": True,
            "access_count": len(result.temporal_access),
            "bundle_content_id": bundle.content_sha256,
        },
    )
    _write_artifact_inventory(destination, bridge, result)
    return result


def run_asw_8_harbor_model_session(
    *,
    bridge: PumpStationAsw8HarborBridge,
    output_dir: Path,
    session_identity: str,
    model: str,
    max_turns: int,
    registry: Any | None = None,
) -> CompletedPumpStationAsw8ModelSession:
    """Run one bounded real model against projection v5 and the closed v2 tools."""
    identity = session_identity.strip()
    model_name = model.strip()
    if not identity or not model_name:
        raise ValueError("ASW-8 model session requires identity and model")
    if max_turns < 1:
        raise ValueError("ASW-8 model session max turns must be positive")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"ASW-8 session output exists: {destination}")
    destination.mkdir(parents=True)
    session_id = f"session-{identity}"
    session = PumpStationCoupledAgentSession.start(
        run_root=destination / "world-run",
        run_id=f"asw-8-{identity}",
        world_branch_id=f"branch-{identity}",
        agent_tenure_id=f"tenure-{identity}",
        session_id=session_id,
    )
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    try:
        if registry is None:
            from aec_bench.adapters.local_registry import LocalAdapterRegistry

            resolved_registry: Any = LocalAdapterRegistry()
        else:
            resolved_registry = registry
        adapter = resolved_registry.build(
            adapter_kind="tool_loop",
            model_name=model_name,
            workspace=str(destination),
            trajectory_writer=trajectory,
            native_tools=session.native_tools,
            enable_bash=False,
        )
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=(
                    "Observe the three-pump station and its visible dates, service plan, shared "
                    "resources, and work. Use documentary search only if it helps. Take no more "
                    "than one supported stewardship action. Give the reason in clear natural "
                    "language. Supply an exact backlog, pump, process, or evidence identifier only "
                    "when the selected tool requires it. Then stop with a short factual summary."
                ),
                system_prompt=(
                    "You are the accountable wastewater pump-station steward. Use only projection "
                    "v5 and the declared closed tools. Do not infer latent pump health, hidden "
                    "events, another branch, verifier expectations, or a prescribed gold sequence."
                ),
                tools=list(session.tool_specs),
                configuration={"max_turns": max_turns},
                output_path=str(destination / "output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()
    run = PumpStationCoupledRunRepository(destination / "world-run").open()
    verification = verify_coupled_run(run)
    evaluation = evaluate_coupled_run(run)
    temporal_repository, _ = verify_coupled_temporal_repository(
        destination / "world-run",
        run,
    )
    package = load_reference_package(bridge.package_root, profile_id=REFERENCE_PROFILE_V2)
    temporal_verification = verify_temporal_evidence_repository(
        temporal_repository,
        package=package,
    )
    access = _temporal_access_summary(temporal_repository)
    outcome = semantic_outcome(run, temporal_access=access)
    controller_result = PumpStationReferenceControllerResult(
        controller_id=model_name,
        run=run,
        temporal_access=access,
        semantic_outcome=outcome,
    )
    _write_asw_8_model_evidence(
        destination=destination,
        adapter_result=adapter_result,
        model=model_name,
        max_turns=max_turns,
    )
    _write_json(
        destination / "world-session-request.json",
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_RUN_VERSION,
            "session_id": session_id,
            "controller_id": model_name,
            "start_snapshot": create_start_snapshot(controller_result),
        },
    )
    _write_json(
        destination / "world-session-result.json",
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_RUN_VERSION,
            "session_id": session_id,
            "controller_id": model_name,
            "end_snapshot": create_end_snapshot(controller_result),
            "transition_count": len(run.receipts),
            "tool_names": PUMP_STATION_ACTOR_ACTION_NAMES_V2,
        },
    )
    _write_json(destination / "verification-report.json", verification)
    _write_json(destination / "evaluation.json", evaluation)
    _write_json(destination / "semantic-outcome.json", outcome)
    _write_json(destination / "temporal-evidence" / "access-ledger.json", access)
    _write_json(
        destination / "temporal-verification-report.json",
        temporal_verification,
    )
    _write_artifact_inventory(
        destination,
        bridge,
        controller_result,
        controller_id=model_name,
    )
    return CompletedPumpStationAsw8ModelSession(
        session_id=session_id,
        run=run,
        verification=verification,
        adapter_result=adapter_result,
        output_dir=destination,
    )


def create_start_snapshot(result: PumpStationReferenceControllerResult) -> dict[str, Any]:
    """Return the task-neutral opening snapshot reference."""
    return {
        "run_id": result.run.manifest.run_id,
        "episode_id": result.run.manifest.episode_id,
        "world_branch_id": result.run.manifest.world_branch_id,
        "sequence": 0,
        "state_id": result.run.manifest.initial_state_id,
        "commit_id": result.run.manifest.initial_state_id,
    }


def create_end_snapshot(result: PumpStationReferenceControllerResult) -> dict[str, Any]:
    """Return the task-neutral terminal snapshot reference."""
    return {
        "run_id": result.run.manifest.run_id,
        "episode_id": result.run.manifest.episode_id,
        "world_branch_id": result.run.manifest.world_branch_id,
        "sequence": len(result.run.receipts),
        "state_id": result.run.state.state_id,
        "commit_id": result.run.state.state_id,
    }


def _temporal_access_summary(
    repository: Any,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    rows: list[tuple[str, str, tuple[str, ...]]] = []
    for commit in repository.access_commits():
        result = repository.load_access_publication(commit).decision.result
        version_ids = tuple(item.version_id for item in result.references)
        if result.fetched_content is not None:
            version_ids = (result.fetched_content.version_id,)
        rows.append(
            (
                f"{result.operation.value.lower()}_evidence",
                result.public_status.value,
                version_ids,
            )
        )
    return tuple(rows)


def _write_asw_8_model_evidence(
    *,
    destination: Path,
    adapter_result: AdapterResult,
    model: str,
    max_turns: int,
) -> None:
    """Persist model output, token use, and the complete tool transcript."""
    (destination / "output.md").write_text(
        adapter_result.raw_output_text or "",
        encoding="utf-8",
    )
    _write_json(
        destination / "agent-result.json",
        {
            "status": adapter_result.agent_output.status.value,
            "model": model,
            "adapter": "tool_loop",
            "adapter_name": adapter_result.adapter_name,
            "resolved_model": adapter_result.resolved_model,
            "configuration_record": adapter_result.configuration_record,
            "max_turns": max_turns,
            "turns_used": adapter_result.turns_used,
            "input_tokens": adapter_result.usage_input_tokens or 0,
            "output_tokens": adapter_result.usage_output_tokens or 0,
            "cache_read_tokens": adapter_result.usage_cache_read_tokens or 0,
            "cache_write_tokens": adapter_result.usage_cache_write_tokens or 0,
            "failure_kind": (None if adapter_result.failure_kind is None else adapter_result.failure_kind.value),
            "provider_error": adapter_result.provider_error,
        },
    )
    with (destination / "conversation.jsonl").open("w", encoding="utf-8") as stream:
        for entry in adapter_result.transcript:
            stream.write(
                json.dumps(
                    {
                        "role": entry.role.value,
                        "event": entry.event.value,
                        "content": entry.content,
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def _write_artifact_inventory(
    destination: Path,
    bridge: PumpStationAsw8HarborBridge,
    result: PumpStationReferenceControllerResult,
    *,
    controller_id: str = PUMP_STATION_ASW_8_REFERENCE_CONTROLLER_ID,
) -> None:
    artifacts = []
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path.name != "artifact-inventory.json":
            raw = path.read_bytes()
            artifacts.append(
                {
                    "path": path.relative_to(destination).as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                }
            )
    _write_json(
        destination / "artifact-inventory.json",
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_RUN_VERSION,
            "execution_kind": PUMP_STATION_ASW_8_HARBOR_EXECUTION_KIND,
            "controller_id": controller_id,
            "export_manifest_sha256": bridge.export_manifest_sha256,
            "start_snapshot": create_start_snapshot(result),
            "end_snapshot": create_end_snapshot(result),
            "transition_count": len(result.run.receipts),
            "artifacts": artifacts,
        },
    )


def verify_asw_8_harbor_session(
    *,
    run_dir: Path,
    export_manifest: Path,
    package_dir: Path,
    reference_system_dir: Path,
) -> tuple[
    PumpStationCoupledVerificationReport,
    PumpStationCoupledEvaluationResult,
    PumpStationSemanticOutcome,
]:
    """Independently reload Harbor evidence and reject stored result drift."""
    export_value = cast(dict[str, Any], _read_json(export_manifest))
    if export_value.get("schema_version") != PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION:
        raise ValueError("ASW-8 export manifest version differs")
    load_reference_package(package_dir, profile_id=REFERENCE_PROFILE_V2)
    load_reference_system(root=reference_system_dir)
    run = PumpStationCoupledRunRepository(Path(run_dir) / "world-run").open()
    verify_coupled_temporal_repository(Path(run_dir) / "world-run", run)
    report = verify_coupled_run(run)
    evaluation = evaluate_coupled_run(run)
    temporal_access_value = _read_json(Path(run_dir) / "temporal-evidence" / "access-ledger.json")
    temporal_access = tuple(
        (str(row[0]), str(row[1]), tuple(str(value) for value in row[2])) for row in temporal_access_value
    )
    outcome = semantic_outcome(run, temporal_access=temporal_access)
    for name, recomputed in (
        ("verification-report.json", report),
        ("evaluation.json", evaluation),
        ("semantic-outcome.json", outcome),
    ):
        if _read_json(Path(run_dir) / name) != canonical_stewardship_value(
            recomputed,
            record_profile="v4",
        ):
            raise ValueError(f"stored {name} differs from independent recomputation")
    inventory = cast(dict[str, Any], _read_json(Path(run_dir) / "artifact-inventory.json"))
    for artifact in inventory.get("artifacts", []):
        path = Path(run_dir) / str(artifact["path"])
        if file_sha256(path) != artifact.get("sha256"):
            raise ValueError(f"Harbor artifact changed: {path.name}")
    if not report.valid or not evaluation.valid:
        raise ValueError("ASW-8 Harbor verification failed")
    return report, evaluation, outcome


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--reference-system-dir", type=Path, required=True)
    parser.add_argument("--reward-path", type=Path, required=True)
    parser.add_argument("--details-path", type=Path, required=True)
    args = parser.parse_args()
    if not args.verify:
        raise SystemExit("--verify is required")
    report, evaluation, _ = verify_asw_8_harbor_session(
        run_dir=args.run_dir,
        export_manifest=args.export_manifest,
        package_dir=args.package_dir,
        reference_system_dir=args.reference_system_dir,
    )
    _write_json(args.reward_path, {"reward": evaluation.reward})
    _write_json(
        args.details_path,
        {
            "schema_version": PUMP_STATION_ASW_8_HARBOR_VERIFICATION_VERSION,
            "valid": evaluation.valid,
            "verification_report_id": report.content_id,
            "conservation_report_id": report.conservation_content_id,
            "reward_owner": "harbor_verifier",
        },
    )


if __name__ == "__main__":
    _main()
