# ABOUTME: Exports the wastewater pump-station world as a provider-neutral Harbor task.
# ABOUTME: Keeps public agent material separate from package and verifier authority.

from __future__ import annotations

import json
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from aec_bench.task_world_templates.harbor_exporting.constants import (
    BASE_IMAGE,
    RUNTIME_DEPENDENCIES,
)
from aec_bench.task_world_templates.harbor_exporting.runtime_wheel import (
    RuntimeWheel,
    build_verifier_runtime_wheel,
)
from aec_bench.task_world_templates.harbor_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    bundled_reference_package_root,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    PUMP_STATION_RICH_WORK_TOOL_NAMES,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TOOL_NAMES,
)

PUMP_STATION_HARBOR_EXECUTION_KIND: Final[Literal["stewardship_world_session"]] = "stewardship_world_session"
PUMP_STATION_HARBOR_BRIDGE_MODE = "wastewater_pump_station_reference"
PUMP_STATION_HARBOR_OUTPUT_PATH = "/workspace/world-session"
PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION = "aecbench.pump-station-harbor-export.v1"
PUMP_STATION_CONTROLLER_MODES = (
    "deterministic_reference",
    "model_tool_loop",
)

_MANIFEST_NAME = "world-session-export.json"
_PACKAGE_PATH = "tests/reference-package"
_MAX_MANIFEST_BYTES = 1024 * 1024
_NON_AUTHORITY_ARTIFACT_NAMES = frozenset(
    {
        ".world-run.lock",
        "artifact-inventory.json",
        "current.json",
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


def export_pump_station_harbor_task(
    task_dir: Path,
    *,
    project_root: Path,
    rich_work_processes: bool = False,
    evidence_health: bool = False,
) -> ExportedPumpStationHarborTask:
    """Materialize one immutable task package for provider-free Harbor execution."""

    destination = Path(task_dir)
    if destination.exists():
        raise FileExistsError(f"Harbor task output already exists: {destination}")
    root = _validated_project_root(project_root)
    package = load_reference_package()
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
            rich_work_processes=(rich_work_processes or evidence_health),
            evidence_health=evidence_health,
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
    _require_exact_keys(
        manifest,
        {
            "agent_surface",
            "bridge",
            "execution_kind",
            "harbor",
            "package",
            "schema_version",
            "task_world_id",
            "verifier",
        },
        label="pump-station Harbor export manifest",
    )
    if manifest["schema_version"] != PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION:
        raise ValueError("unsupported pump-station Harbor export version")
    if manifest["execution_kind"] != PUMP_STATION_HARBOR_EXECUTION_KIND:
        raise ValueError("pump-station Harbor execution kind differs")
    if manifest["task_world_id"] != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError("pump-station Harbor task-world identity differs")
    agent_surface = _mapping(manifest["agent_surface"], "agent_surface")
    if agent_surface.get("allow_internet") is not False or agent_surface.get("dependencies") != list(
        RUNTIME_DEPENDENCIES
    ):
        raise ValueError("pump-station Harbor agent runtime differs")
    package_payload = _mapping(manifest["package"], "package")
    bridge_payload = _mapping(manifest["bridge"], "bridge")
    harbor_payload = _mapping(manifest["harbor"], "harbor")
    verifier_payload = _mapping(manifest["verifier"], "verifier")
    package_root = task_root / str(package_payload["path"])
    package = load_reference_package(package_root)
    if (
        package.package_content_id != package_payload["package_content_id"]
        or package.manifest_content_id != package_payload["manifest_content_id"]
        or directory_sha256(package_root) != package_payload["directory_sha256"]
    ):
        raise ValueError("pump-station Harbor package differs from the export")
    allowed_tools = tuple(cast(list[str], bridge_payload["allowed_tools"]))
    if allowed_tools not in {
        PUMP_STATION_TOOL_NAMES,
        PUMP_STATION_RICH_WORK_TOOL_NAMES,
        PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    }:
        raise ValueError("pump-station Harbor tool catalogue differs")
    rich_work_processes = bool(bridge_payload.get("rich_work_processes", False))
    evidence_health = bool(bridge_payload.get("evidence_health", False))
    if evidence_health and not rich_work_processes:
        raise ValueError("pump-station evidence health requires rich work")
    expected_tools = (
        PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
        if evidence_health
        else PUMP_STATION_RICH_WORK_TOOL_NAMES
        if rich_work_processes
        else PUMP_STATION_TOOL_NAMES
    )
    if allowed_tools != expected_tools:
        raise ValueError("pump-station Harbor work profile and tools differ")
    if (
        bridge_payload["mode"] != PUMP_STATION_HARBOR_BRIDGE_MODE
        or bridge_payload["output_path"] != PUMP_STATION_HARBOR_OUTPUT_PATH
        or tuple(bridge_payload.get("controller_modes", ())) != PUMP_STATION_CONTROLLER_MODES
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
    )


def _write_export(
    *,
    task_dir: Path,
    project_root: Path,
    package: ReferencePackage,
    rich_work_processes: bool,
    evidence_health: bool,
) -> ExportedPumpStationHarborTask:
    task_dir.mkdir()
    tests_dir = task_dir / "tests"
    runtime_dir = tests_dir / "runtime"
    environment_dir = task_dir / "environment"
    package_dir = task_dir / _PACKAGE_PATH
    runtime_dir.mkdir(parents=True)
    environment_dir.mkdir()
    shutil.copytree(bundled_reference_package_root(), package_dir)
    loaded = load_reference_package(package_dir)
    if loaded != package:
        raise ValueError("staged pump-station package differs from the bundled package")
    runtime = build_verifier_runtime_wheel(
        project_root=project_root,
        output_dir=runtime_dir,
    )
    instruction_path = task_dir / "instruction.md"
    dockerfile_path = environment_dir / "Dockerfile"
    task_toml_path = task_dir / "task.toml"
    test_script_path = tests_dir / "test.sh"
    instruction_path.write_text(_instruction_text(), encoding="utf-8")
    dockerfile_path.write_text(_dockerfile_text(), encoding="utf-8")
    task_toml_path.write_text(_task_toml_text(package), encoding="utf-8")
    test_script_path.write_text(
        _test_script_text(runtime.path.name),
        encoding="utf-8",
    )
    test_script_path.chmod(0o755)
    manifest = _export_manifest(
        task_dir=task_dir,
        package=package,
        package_dir=package_dir,
        runtime=runtime,
        rich_work_processes=rich_work_processes,
        evidence_health=evidence_health,
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
    runtime: RuntimeWheel,
    rich_work_processes: bool,
    evidence_health: bool,
) -> dict[str, Any]:
    instruction = task_dir / "instruction.md"
    dockerfile = task_dir / "environment" / "Dockerfile"
    task_toml = task_dir / "task.toml"
    test_script = task_dir / "tests" / "test.sh"
    return {
        "schema_version": PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
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
        "bridge": {
            "mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
            "allowed_tools": list(
                PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
                if evidence_health
                else PUMP_STATION_RICH_WORK_TOOL_NAMES
                if rich_work_processes
                else PUMP_STATION_TOOL_NAMES
            ),
            "rich_work_processes": rich_work_processes,
            "evidence_health": evidence_health,
            "output_path": PUMP_STATION_HARBOR_OUTPUT_PATH,
            "controller_modes": list(PUMP_STATION_CONTROLLER_MODES),
        },
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


def _task_toml_text(package: ReferencePackage) -> str:
    return (
        "# ABOUTME: Declares one provider-neutral wastewater pump-station Harbor task.\n"
        "# ABOUTME: Binds task metadata while Harbor retains independent reward ownership.\n"
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "hard"\n'
        'category = "asset-stewardship"\n'
        'domain = "mechanical"\n'
        'visibility = "public"\n'
        'tags = ["asset-stewardship", "pump-station", "world-session"]\n'
        f"task_world_id = {json.dumps(PUMP_STATION_TASK_WORLD_ID)}\n"
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


def _test_script_text(wheel_name: str) -> str:
    return f"""#!/bin/sh
# ABOUTME: Runs the hidden pump-station verifier after Harbor ends the agent phase.
# ABOUTME: Reloads the exact exported package and immutable world-session evidence.
set -eu

RUN_DIR="${{AEC_BENCH_WORLD_SESSION_DIR:-{PUMP_STATION_HARBOR_OUTPUT_PATH}}}"
EXPORT_MANIFEST="${{AEC_BENCH_EXPORT_MANIFEST:-/tests/{_MANIFEST_NAME}}}"
PACKAGE_DIR="${{AEC_BENCH_REFERENCE_PACKAGE_DIR:-/tests/reference-package}}"
VERIFIER_RUNTIME="${{AEC_BENCH_VERIFIER_RUNTIME:-/tests/runtime/{wheel_name}}}"
REWARD_PATH="${{AEC_BENCH_REWARD_PATH:-/logs/verifier/reward.json}}"
DETAILS_PATH="${{AEC_BENCH_DETAILS_PATH:-/logs/verifier/details.json}}"
PYTHON_BIN="${{AEC_BENCH_PYTHON:-python3}}"
RUNTIME_DIR="$(mktemp -d)"
"$PYTHON_BIN" -m zipfile -e "$VERIFIER_RUNTIME" "$RUNTIME_DIR"

PYTHONPATH="$RUNTIME_DIR${{PYTHONPATH:+:$PYTHONPATH}}" "$PYTHON_BIN" \\
  -m aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier \\
  --run-dir "$RUN_DIR" \\
  --export-manifest "$EXPORT_MANIFEST" \\
  --package-dir "$PACKAGE_DIR" \\
  --verifier-runtime "$VERIFIER_RUNTIME" \\
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
