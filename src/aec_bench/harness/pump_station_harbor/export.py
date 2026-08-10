# ABOUTME: Exports the wastewater pump-station world as a provider-neutral Harbor task.
# ABOUTME: Keeps transport packaging outside the task-owned pump functional core.

from __future__ import annotations

import json
import shutil
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import TypeAdapter

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRunRef,
)
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.harness.harbor_task_exporting.constants import (
    BASE_IMAGE,
    RUNTIME_DEPENDENCIES,
)
from aec_bench.harness.harbor_task_exporting.runtime_wheel import (
    RuntimeWheel,
    build_verifier_runtime_wheel,
)
from aec_bench.harness.harbor_task_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    validate_pump_station_rollout_child_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    bundled_reference_package_root,
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PumpStationReferenceSystem,
    bundled_reference_system_root,
    load_reference_system,
)

PUMP_STATION_HARBOR_EXECUTION_KIND: Final[Literal["stewardship_world_session"]] = "stewardship_world_session"
PUMP_STATION_HARBOR_BRIDGE_MODE = "wastewater_pump_station_reference"
PUMP_STATION_HARBOR_OUTPUT_PATH = "/workspace/world-session"
PUMP_STATION_CONTROLLER_MODES = (
    "deterministic_reference",
    "model_tool_loop",
)

_MANIFEST_NAME = "world-session-export.json"
_PACKAGE_PATH = "tests/reference-package"
_INITIAL_RUN_PATH = "tests/initial-world-run"
_MAX_MANIFEST_BYTES = 1024 * 1024
_NON_AUTHORITY_ARTIFACT_NAMES = frozenset(
    {
        ".review-case.lock",
        ".world-run.lock",
        "artifact-inventory.json",
        "current.json",
        "current-information-set.json",
    }
)


def is_pump_station_harbor_inventory_artifact(
    root: Path,
    path: Path,
) -> bool:
    """Return whether one session file is eligible for the Harbor inventory."""
    relative = path.relative_to(root)
    if path.name in _NON_AUTHORITY_ARTIFACT_NAMES:
        return False
    return not (relative.parts and relative.parts[0] == "world-run" and path.name.startswith("."))


@dataclass(frozen=True)
class ExportedPumpStationHarborTask:
    """Paths and identity for one materialized pump-station Harbor task."""

    task_dir: Path
    manifest_path: Path
    package_dir: Path
    verifier_runtime_wheel_path: Path


@dataclass(frozen=True)
class PumpStationHarborBridge:
    """Host-only validated authority for one exported pump-station task."""

    task_root: Path
    package_root: Path
    package: ReferencePackage
    export_manifest_path: Path
    export_manifest_sha256: str
    verifier_runtime_path: Path
    verifier_runtime_sha256: str
    allowed_tools: tuple[str, ...]
    output_path: str
    rich_work_processes: bool
    evidence_health: bool
    temporal_evidence: bool
    execution_kind: str
    task_world_id: str
    bridge_mode: str
    world_build: WorldBuildRef
    profile_ref: InteractiveWorldProfileRef
    reference_system_root: Path
    initial_run_root: Path | None
    rollout_child_ref: ContinualRolloutChildRunRef | None


def _export_authority(
    profile_ref: InteractiveWorldProfileRef | None,
) -> tuple[ReferencePackage, PumpStationReferenceSystem | None]:
    definition = pump_station_continual_world_definition()
    if profile_ref is None:
        raise ValueError("pump-station Harbor export requires the registered profile")
    if profile_ref not in definition.profiles:
        raise ValueError("pump-station Harbor profile is not registered")
    loaded = definition.load_profile(profile_ref).value
    if not isinstance(loaded, PumpStationContinualProfile):
        raise TypeError("registered pump-station profile has the wrong value type")
    return loaded.station_package, loaded.reference_system


def export_pump_station_harbor_task(
    task_dir: Path,
    *,
    project_root: Path,
    profile_ref: InteractiveWorldProfileRef | None = None,
    initial_run_root: Path | None = None,
    rollout_child_ref: ContinualRolloutChildRunRef | None = None,
) -> ExportedPumpStationHarborTask:
    """Materialize one immutable registered-world task for Harbor execution."""

    if profile_ref is None:
        raise ValueError("pump-station Harbor export requires the registered current profile")
    if (initial_run_root is None) != (rollout_child_ref is None):
        raise ValueError("pump-station Harbor initial run binding is incomplete")
    if initial_run_root is not None and profile_ref is None:
        raise ValueError("pump-station Harbor initial run requires a registered profile")
    destination = Path(task_dir)
    if destination.exists():
        raise FileExistsError(f"Harbor task output already exists: {destination}")
    root = _validated_project_root(project_root)
    package, reference_system = _export_authority(profile_ref)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-",
        dir=destination.parent,
    ) as raw_staging:
        staging = Path(raw_staging) / destination.name
        exported = _write_export(
            task_dir=staging,
            project_root=root,
            package=package,
            profile_ref=profile_ref,
            reference_system=reference_system,
            initial_run_root=initial_run_root,
            rollout_child_ref=rollout_child_ref,
            rich_work_processes=True,
            evidence_health=True,
            temporal_evidence=True,
        )
        staging.rename(destination)
    return ExportedPumpStationHarborTask(
        task_dir=destination,
        manifest_path=destination / exported.manifest_path.relative_to(exported.task_dir),
        package_dir=destination / exported.package_dir.relative_to(exported.task_dir),
        verifier_runtime_wheel_path=(destination / exported.verifier_runtime_wheel_path.relative_to(exported.task_dir)),
    )


def load_pump_station_harbor_bridge(
    environment_dir: Path,
) -> PumpStationHarborBridge:
    """Load and validate an exported task before a world session is started."""

    environment = Path(environment_dir)
    if environment.is_symlink() or not environment.is_dir():
        raise ValueError("pump-station Harbor environment must be a plain directory")
    task_root = environment.parent.resolve(strict=True)
    manifest_path = task_root / _MANIFEST_NAME
    manifest = _read_json(manifest_path)
    base_fields = {
        "agent_surface",
        "bridge",
        "execution_kind",
        "harbor",
        "package",
        "task_world_id",
        "verifier",
    }
    initial_run_present = "initial_run" in manifest
    _require_exact_keys(
        manifest,
        base_fields
        | {"world_build", "continual_profile", "reference_system"}
        | ({"initial_run"} if initial_run_present else set()),
        label="pump-station Harbor export manifest",
    )
    definition = pump_station_continual_world_definition()
    world_build = TypeAdapter(WorldBuildRef).validate_python(manifest["world_build"])
    if world_build != definition.ref:
        raise ValueError("pump-station Harbor build is not registered")
    profile_ref = TypeAdapter(InteractiveWorldProfileRef).validate_python(manifest["continual_profile"])
    if profile_ref not in definition.profiles:
        raise ValueError("pump-station Harbor profile is not registered")
    reference_payload = _mapping(manifest["reference_system"], "reference_system")
    _require_exact_keys(
        reference_payload,
        {"descriptor_content_id", "descriptor_id", "directory_sha256", "path"},
        label="pump-station Harbor reference system",
    )
    reference_system_root = task_root / str(reference_payload["path"])
    reference_system = load_reference_system(root=reference_system_root)
    if (
        reference_system.descriptor_id != reference_payload["descriptor_id"]
        or reference_system.descriptor_content_id != reference_payload["descriptor_content_id"]
        or directory_sha256(reference_system_root) != reference_payload["directory_sha256"]
        or reference_system.descriptor_content_id != profile_ref.profile_content_sha256
    ):
        raise ValueError("pump-station Harbor reference system differs from the export")
    initial_run_root: Path | None = None
    rollout_child_ref: ContinualRolloutChildRunRef | None = None
    if initial_run_present:
        initial_run_payload = _mapping(manifest["initial_run"], "initial run")
        _require_exact_keys(
            initial_run_payload,
            {"directory_sha256", "path", "rollout_child_ref"},
            label="pump-station Harbor initial run",
        )
        if initial_run_payload["path"] != _INITIAL_RUN_PATH:
            raise ValueError("pump-station Harbor initial run path differs")
        initial_run_root = task_root / _INITIAL_RUN_PATH
        if directory_sha256(initial_run_root) != initial_run_payload["directory_sha256"]:
            raise ValueError("pump-station Harbor initial run differs from the export")
        rollout_child_ref = ContinualRolloutChildRunRef.model_validate(initial_run_payload["rollout_child_ref"])
        try:
            validate_pump_station_rollout_child_run(
                initial_run_root,
                rollout_child_ref,
                world_build=world_build,
                profile_ref=profile_ref,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("pump-station Harbor initial run identity differs") from exc
    bridge_payload = _mapping(manifest["bridge"], "bridge")
    expected_execution_kind = PUMP_STATION_HARBOR_EXECUTION_KIND
    expected_task_world_id = PUMP_STATION_TASK_WORLD_ID
    expected_bridge_mode = PUMP_STATION_HARBOR_BRIDGE_MODE
    expected_controller_modes = PUMP_STATION_CONTROLLER_MODES
    if manifest["execution_kind"] != expected_execution_kind:
        raise ValueError("pump-station Harbor execution kind differs")
    if manifest["task_world_id"] != expected_task_world_id:
        raise ValueError("pump-station Harbor task-world identity differs")
    agent_surface = _mapping(manifest["agent_surface"], "agent_surface")
    if agent_surface.get("allow_internet") is not False or agent_surface.get("dependencies") != list(
        RUNTIME_DEPENDENCIES
    ):
        raise ValueError("pump-station Harbor agent runtime differs")
    package_payload = _mapping(manifest["package"], "package")
    harbor_payload = _mapping(manifest["harbor"], "harbor")
    verifier_payload = _mapping(manifest["verifier"], "verifier")
    package_root = task_root / str(package_payload["path"])
    package = load_reference_package(package_root, profile_id=str(package_payload["profile_id"]))
    if (
        package.package_content_id != package_payload["package_content_id"]
        or package.manifest_content_id != package_payload["manifest_content_id"]
        or directory_sha256(package_root) != package_payload["directory_sha256"]
    ):
        raise ValueError("pump-station Harbor package differs from the export")
    allowed_tools = tuple(cast(list[str], bridge_payload["allowed_tools"]))
    if allowed_tools != PUMP_STATION_ACTOR_ACTION_NAMES:
        raise ValueError("pump-station Harbor tool catalogue differs")
    rich_work_processes = bool(bridge_payload.get("rich_work_processes", False))
    evidence_health = bool(bridge_payload.get("evidence_health", False))
    temporal_evidence = bool(bridge_payload.get("temporal_evidence", False))
    if evidence_health and not rich_work_processes:
        raise ValueError("pump-station evidence health requires rich work")
    if temporal_evidence and not evidence_health:
        raise ValueError("pump-station temporal evidence requires evidence health")
    expected_tools = PUMP_STATION_ACTOR_ACTION_NAMES
    if allowed_tools != expected_tools:
        raise ValueError("pump-station Harbor work profile and tools differ")
    if (
        bridge_payload["mode"] != expected_bridge_mode
        or bridge_payload["output_path"] != PUMP_STATION_HARBOR_OUTPUT_PATH
        or tuple(bridge_payload.get("controller_modes", ())) != expected_controller_modes
    ):
        raise ValueError("pump-station Harbor bridge contract differs")
    if harbor_payload["reward_owner"] != "harbor_verifier":
        raise ValueError("pump-station reward authority is not Harbor")
    runtime_path = task_root / str(verifier_payload["runtime_wheel"])
    runtime_sha256 = file_sha256(runtime_path)
    if runtime_sha256 != verifier_payload["runtime_wheel_sha256"]:
        raise ValueError("pump-station verifier runtime differs from the export")
    _validate_surface(task_root=task_root, manifest=manifest)
    return PumpStationHarborBridge(
        task_root=task_root,
        package_root=package_root,
        package=package,
        export_manifest_path=manifest_path,
        export_manifest_sha256=file_sha256(manifest_path),
        verifier_runtime_path=runtime_path,
        verifier_runtime_sha256=runtime_sha256,
        allowed_tools=allowed_tools,
        output_path=PUMP_STATION_HARBOR_OUTPUT_PATH,
        rich_work_processes=rich_work_processes,
        evidence_health=evidence_health,
        temporal_evidence=temporal_evidence,
        execution_kind=expected_execution_kind,
        task_world_id=expected_task_world_id,
        bridge_mode=expected_bridge_mode,
        world_build=world_build,
        profile_ref=profile_ref,
        reference_system_root=reference_system_root,
        initial_run_root=initial_run_root,
        rollout_child_ref=rollout_child_ref,
    )


def _write_export(
    *,
    task_dir: Path,
    project_root: Path,
    package: ReferencePackage,
    profile_ref: InteractiveWorldProfileRef | None,
    reference_system: PumpStationReferenceSystem | None,
    initial_run_root: Path | None,
    rollout_child_ref: ContinualRolloutChildRunRef | None,
    rich_work_processes: bool,
    evidence_health: bool,
    temporal_evidence: bool,
) -> ExportedPumpStationHarborTask:
    task_dir.mkdir()
    tests_dir = task_dir / "tests"
    runtime_dir = tests_dir / "runtime"
    environment_dir = task_dir / "environment"
    package_dir = task_dir / _PACKAGE_PATH
    runtime_dir.mkdir(parents=True)
    environment_dir.mkdir()
    shutil.copytree(
        bundled_reference_package_root(profile_id=package.profile_id),
        package_dir,
    )
    loaded = load_reference_package(package_dir, profile_id=package.profile_id)
    if loaded != package:
        raise ValueError("staged pump-station package differs from the bundled package")
    reference_system_dir: Path | None = None
    if reference_system is not None:
        reference_system_dir = tests_dir / "reference-system"
        shutil.copytree(bundled_reference_system_root(), reference_system_dir)
        if load_reference_system(root=reference_system_dir) != reference_system:
            raise ValueError("staged pump-station reference system differs from the registered profile")
    initial_run_dir: Path | None = None
    initial_run_sha256: str | None = None
    if initial_run_root is not None and rollout_child_ref is not None:
        if profile_ref is None:
            raise ValueError("pump-station Harbor rollout child requires one exact profile")
        world_build = pump_station_continual_world_definition().ref
        validate_pump_station_rollout_child_run(
            initial_run_root,
            rollout_child_ref,
            world_build=world_build,
            profile_ref=profile_ref,
        )
        initial_run_dir = task_dir / _INITIAL_RUN_PATH
        initial_run_sha256 = _copy_content_addressed_directory(
            initial_run_root,
            initial_run_dir,
        )
        validate_pump_station_rollout_child_run(
            initial_run_dir,
            rollout_child_ref,
            world_build=world_build,
            profile_ref=profile_ref,
        )
    runtime = build_verifier_runtime_wheel(
        project_root=project_root,
        output_dir=runtime_dir,
    )
    instruction_path = task_dir / "instruction.md"
    dockerfile_path = environment_dir / "Dockerfile"
    task_toml_path = task_dir / "task.toml"
    test_script_path = tests_dir / "test.sh"
    instruction_path.write_text(
        _instruction_text(),
        encoding="utf-8",
    )
    dockerfile_path.write_text(_dockerfile_text(), encoding="utf-8")
    task_toml_path.write_text(
        _task_toml_text(package),
        encoding="utf-8",
    )
    test_script_path.write_text(
        _test_script_text(
            runtime.path.name,
            registered_profile=profile_ref is not None,
            initial_run=initial_run_dir is not None,
        ),
        encoding="utf-8",
    )
    test_script_path.chmod(0o755)
    manifest = _export_manifest(
        task_dir=task_dir,
        package=package,
        package_dir=package_dir,
        profile_ref=profile_ref,
        reference_system=reference_system,
        reference_system_dir=reference_system_dir,
        initial_run_dir=initial_run_dir,
        initial_run_sha256=initial_run_sha256,
        rollout_child_ref=rollout_child_ref,
        runtime=runtime,
        rich_work_processes=rich_work_processes,
        evidence_health=evidence_health,
        temporal_evidence=temporal_evidence,
    )
    manifest_path = task_dir / _MANIFEST_NAME
    _write_json(manifest_path, manifest)
    _write_json(tests_dir / _MANIFEST_NAME, manifest)
    return ExportedPumpStationHarborTask(
        task_dir=task_dir,
        manifest_path=manifest_path,
        package_dir=package_dir,
        verifier_runtime_wheel_path=runtime.path,
    )


def _export_manifest(
    *,
    task_dir: Path,
    package: ReferencePackage,
    package_dir: Path,
    profile_ref: InteractiveWorldProfileRef | None,
    reference_system: PumpStationReferenceSystem | None,
    reference_system_dir: Path | None,
    initial_run_dir: Path | None,
    initial_run_sha256: str | None,
    rollout_child_ref: ContinualRolloutChildRunRef | None,
    runtime: RuntimeWheel,
    rich_work_processes: bool,
    evidence_health: bool,
    temporal_evidence: bool,
) -> dict[str, Any]:
    instruction = task_dir / "instruction.md"
    dockerfile = task_dir / "environment" / "Dockerfile"
    task_toml = task_dir / "task.toml"
    test_script = task_dir / "tests" / "test.sh"
    registered_profile = profile_ref is not None
    if registered_profile != (reference_system is not None and reference_system_dir is not None):
        raise ValueError("registered Harbor profile authority is incomplete")
    if (initial_run_dir is None) != (initial_run_sha256 is None) or (initial_run_dir is None) != (
        rollout_child_ref is None
    ):
        raise ValueError("registered Harbor initial run authority is incomplete")
    if not registered_profile or not (rich_work_processes and evidence_health and temporal_evidence):
        raise ValueError("Harbor export requires the registered current world profile")
    bridge = {
        "mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
        "allowed_tools": list(PUMP_STATION_ACTOR_ACTION_NAMES),
        "rich_work_processes": rich_work_processes,
        "evidence_health": evidence_health,
        "temporal_evidence": temporal_evidence,
        "output_path": PUMP_STATION_HARBOR_OUTPUT_PATH,
        "controller_modes": list(PUMP_STATION_CONTROLLER_MODES),
    }
    manifest: dict[str, Any] = {
        "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "package": {
            "path": _PACKAGE_PATH,
            "profile_id": package.profile_id,
            "generation_id": package.generation_id,
            "package_content_id": package.package_content_id,
            "manifest_content_id": package.manifest_content_id,
            "directory_sha256": directory_sha256(package_dir),
            "manifest": f"{_PACKAGE_PATH}/promotion-manifest.json",
            "manifest_sha256": file_sha256(package_dir / "promotion-manifest.json"),
        },
        "agent_surface": {
            "instruction_sha256": file_sha256(instruction),
            "dockerfile_sha256": file_sha256(dockerfile),
            "allow_internet": False,
            "dependencies": list(RUNTIME_DEPENDENCIES),
        },
        "bridge": bridge,
        "harbor": {
            "reward_owner": "harbor_verifier",
            "task_toml": "task.toml",
            "task_toml_sha256": file_sha256(task_toml),
            "test_script": "tests/test.sh",
            "test_script_sha256": file_sha256(test_script),
        },
        "verifier": {
            "runtime_wheel": f"tests/runtime/{runtime.path.name}",
            "runtime_wheel_sha256": runtime.sha256,
            "source_tree_sha256": runtime.source_tree_sha256,
        },
    }
    if profile_ref is not None and reference_system is not None and reference_system_dir is not None:
        manifest["world_build"] = asdict(pump_station_continual_world_definition().ref)
        manifest["continual_profile"] = asdict(profile_ref)
        manifest["reference_system"] = {
            "path": "tests/reference-system",
            "descriptor_id": reference_system.descriptor_id,
            "descriptor_content_id": reference_system.descriptor_content_id,
            "directory_sha256": directory_sha256(reference_system_dir),
        }
    if initial_run_dir is not None and initial_run_sha256 is not None and rollout_child_ref is not None:
        manifest["initial_run"] = {
            "path": _INITIAL_RUN_PATH,
            "directory_sha256": initial_run_sha256,
            "rollout_child_ref": rollout_child_ref.model_dump(mode="json"),
        }
    return manifest


def _validate_surface(*, task_root: Path, manifest: dict[str, Any]) -> None:
    agent_surface = _mapping(manifest["agent_surface"], "agent_surface")
    harbor = _mapping(manifest["harbor"], "harbor")
    if file_sha256(task_root / "instruction.md") != agent_surface["instruction_sha256"]:
        raise ValueError("pump-station Harbor instruction differs from the export")
    if file_sha256(task_root / "environment" / "Dockerfile") != agent_surface["dockerfile_sha256"]:
        raise ValueError("pump-station Harbor environment differs from the export")
    if file_sha256(task_root / str(harbor["task_toml"])) != harbor["task_toml_sha256"]:
        raise ValueError("pump-station Harbor task metadata differs from the export")
    if file_sha256(task_root / str(harbor["test_script"])) != harbor["test_script_sha256"]:
        raise ValueError("pump-station Harbor verifier script differs from the export")


def _copy_content_addressed_directory(source: Path, destination: Path) -> str:
    """Copy one plain directory and prove that its bytes stayed unchanged."""

    expected_sha256 = directory_sha256(source)
    shutil.copytree(source, destination, symlinks=True)
    copied_sha256 = directory_sha256(destination)
    if directory_sha256(source) != expected_sha256 or copied_sha256 != expected_sha256:
        raise ValueError("pump-station Harbor initial run changed while it was copied")
    return copied_sha256


def _validated_project_root(project_root: Path) -> Path:
    root = Path(project_root).resolve()
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"invalid canonical project root: {root}") from error
    if config.get("project", {}).get("name") != "aec-bench":
        raise ValueError(f"invalid canonical project root: {root}")
    return root


def _instruction_text() -> str:
    return (
        "# Wastewater pump-station stewardship session\n\n"
        "Operate the host-owned pump-station world through its declared stewardship "
        "tools. The selected controller must preserve the complete world-session "
        f"evidence at `{PUMP_STATION_HARBOR_OUTPUT_PATH}`. Harbor owns reward and "
        "runs the independent verifier after the agent phase.\n"
    )


def _dockerfile_text() -> str:
    return (
        "# ABOUTME: Provides the public container for a host-owned pump-station world session.\n"
        "# ABOUTME: Contains no verifier package, private world package, or provider credentials.\n"
        f"FROM --platform=linux/amd64 {BASE_IMAGE}\n\n"
        f"RUN python -m pip install --no-cache-dir {' '.join(RUNTIME_DEPENDENCIES)}\n"
        "WORKDIR /workspace\n"
    )


def _task_toml_text(
    package: ReferencePackage,
) -> str:
    task_world_id = PUMP_STATION_TASK_WORLD_ID
    tags = '["asset-stewardship", "pump-station", "episode"]'
    return (
        "# ABOUTME: Declares one provider-neutral wastewater pump-station Harbor task.\n"
        "# ABOUTME: Binds task metadata while Harbor retains independent reward ownership.\n"
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "hard"\n'
        'category = "asset-stewardship"\n'
        'domain = "mechanical"\n'
        'visibility = "public"\n'
        f"tags = {tags}\n"
        f"task_world_id = {json.dumps(task_world_id)}\n"
        f"reference_profile_id = {json.dumps(package.profile_id)}\n"
        f"reference_generation_id = {json.dumps(package.generation_id)}\n\n"
        "[agent]\n"
        "timeout_sec = 900.0\n\n"
        "[verifier]\n"
        "timeout_sec = 600.0\n\n"
        "[environment]\n"
        "build_timeout_sec = 1800.0\n"
        "cpus = 2\n"
        "memory_mb = 4096\n"
        "storage_mb = 10240\n"
        "allow_internet = false\n"
    )


def _test_script_text(
    wheel_name: str,
    *,
    registered_profile: bool = False,
    initial_run: bool = False,
) -> str:
    reference_system_variable = (
        'REFERENCE_SYSTEM_DIR="${AEC_BENCH_REFERENCE_SYSTEM_DIR:-/tests/reference-system}"\n'
        if registered_profile
        else ""
    )
    reference_system_argument = '  --reference-system-dir "$REFERENCE_SYSTEM_DIR" \\\n' if registered_profile else ""
    initial_run_variable = (
        'INITIAL_RUN_DIR="${AEC_BENCH_INITIAL_RUN_DIR:-${EXPORT_MANIFEST%/*}/initial-world-run}"\n'
        if initial_run
        else ""
    )
    initial_run_argument = '  --initial-run-dir "$INITIAL_RUN_DIR" \\\n' if initial_run else ""
    return f"""#!/bin/sh
# ABOUTME: Runs the hidden pump-station verifier after Harbor ends the agent phase.
# ABOUTME: Reloads the exact exported package and immutable world-session evidence.
set -eu

RUN_DIR="${{AEC_BENCH_WORLD_SESSION_DIR:-{PUMP_STATION_HARBOR_OUTPUT_PATH}}}"
EXPORT_MANIFEST="${{AEC_BENCH_EXPORT_MANIFEST:-/tests/{_MANIFEST_NAME}}}"
PACKAGE_DIR="${{AEC_BENCH_REFERENCE_PACKAGE_DIR:-/tests/reference-package}}"
{reference_system_variable}{initial_run_variable}VERIFIER_RUNTIME="${{AEC_BENCH_VERIFIER_RUNTIME:-/tests/runtime/{wheel_name}}}"
REWARD_PATH="${{AEC_BENCH_REWARD_PATH:-/logs/verifier/reward.json}}"
DETAILS_PATH="${{AEC_BENCH_DETAILS_PATH:-/logs/verifier/details.json}}"
PYTHON_BIN="${{AEC_BENCH_PYTHON:-python3}}"
RUNTIME_DIR="$(mktemp -d)"
"$PYTHON_BIN" -m zipfile -e "$VERIFIER_RUNTIME" "$RUNTIME_DIR"

PYTHONPATH="$RUNTIME_DIR${{PYTHONPATH:+:$PYTHONPATH}}" "$PYTHON_BIN" \\
  -m aec_bench.harness.pump_station_harbor.verifier \\
  --run-dir "$RUN_DIR" \\
  --export-manifest "$EXPORT_MANIFEST" \\
  --package-dir "$PACKAGE_DIR" \\
{reference_system_argument}{initial_run_argument}  --verifier-runtime "$VERIFIER_RUNTIME" \\
  --reward-path "$REWARD_PATH" \\
  --details-path "$DETAILS_PATH"
"""


def _read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise ValueError("pump-station Harbor export manifest is too large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"pump-station Harbor {label} must be an object")
    return cast(dict[str, Any], value)


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} fields differ")


__all__ = (
    "ExportedPumpStationHarborTask",
    "PUMP_STATION_HARBOR_BRIDGE_MODE",
    "PUMP_STATION_HARBOR_EXECUTION_KIND",
    "PUMP_STATION_HARBOR_OUTPUT_PATH",
    "PumpStationHarborBridge",
    "export_pump_station_harbor_task",
    "is_pump_station_harbor_inventory_artifact",
    "load_pump_station_harbor_bridge",
)
