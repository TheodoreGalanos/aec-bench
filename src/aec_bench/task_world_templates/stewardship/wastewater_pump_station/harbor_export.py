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

from aec_bench.contracts.continual_world import ContinualWorldProfileRef
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_control import (
    PUMP_STATION_REVIEW_TASK_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    bundled_reference_package_root,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PumpStationReferenceSystem,
    bundled_reference_system_root,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    PUMP_STATION_RICH_WORK_TOOL_NAMES,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES,
    PUMP_STATION_TOOL_NAMES,
)

PUMP_STATION_HARBOR_EXECUTION_KIND: Final[Literal["stewardship_world_session"]] = "stewardship_world_session"
PUMP_STATION_HARBOR_BRIDGE_MODE = "wastewater_pump_station_reference"
PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND: Final[Literal["stewardship_review_session"]] = "stewardship_review_session"
PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE = "wastewater_pump_station_closeout_review"
PUMP_STATION_HARBOR_OUTPUT_PATH = "/workspace/world-session"
PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION = "aecbench.pump-station-harbor-export.v1"
PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION = "aecbench.pump-station-harbor-export.v2"
PUMP_STATION_CONTROLLER_MODES = (
    "deterministic_reference",
    "model_tool_loop",
)
PUMP_STATION_REVIEW_CONTROLLER_MODES = ("deterministic_reference",)

_MANIFEST_NAME = "world-session-export.json"
_PACKAGE_PATH = "tests/reference-package"
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
    maintenance_review: bool
    execution_kind: str
    task_world_id: str
    bridge_mode: str
    profile_ref: ContinualWorldProfileRef | None
    reference_system_root: Path | None


def _export_authority(
    profile_ref: ContinualWorldProfileRef | None,
) -> tuple[ReferencePackage, PumpStationReferenceSystem | None]:
    if profile_ref is None:
        return load_reference_package(), None
    definition = pump_station_continual_world_definition()
    if profile_ref not in definition.spec.profiles:
        raise ValueError("pump-station Harbor profile is not registered")
    loaded = definition.load_profile(profile_ref).value
    if not isinstance(loaded, PumpStationContinualProfile):
        raise TypeError("registered pump-station profile has the wrong value type")
    return loaded.station_package, loaded.reference_system


def export_pump_station_harbor_task(
    task_dir: Path,
    *,
    project_root: Path,
    rich_work_processes: bool = False,
    evidence_health: bool = False,
    temporal_evidence: bool = False,
    maintenance_review: bool = False,
    profile_ref: ContinualWorldProfileRef | None = None,
) -> ExportedPumpStationHarborTask:
    """Materialize one immutable task package for provider-free Harbor execution."""

    destination = Path(task_dir)
    if destination.exists():
        raise FileExistsError(f"Harbor task output already exists: {destination}")
    root = _validated_project_root(project_root)
    package, reference_system = _export_authority(profile_ref)
    registered_profile = profile_ref is not None
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
            rich_work_processes=(
                registered_profile or rich_work_processes or evidence_health or temporal_evidence or maintenance_review
            ),
            evidence_health=(registered_profile or evidence_health or temporal_evidence or maintenance_review),
            temporal_evidence=(registered_profile or temporal_evidence),
            maintenance_review=maintenance_review,
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
        "schema_version",
        "task_world_id",
        "verifier",
    }
    schema_version = manifest.get("schema_version")
    registered_profile = schema_version == PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION
    if schema_version not in {
        PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
        PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION,
    }:
        raise ValueError("unsupported pump-station Harbor export version")
    _require_exact_keys(
        manifest,
        base_fields | ({"continual_profile", "reference_system"} if registered_profile else set()),
        label="pump-station Harbor export manifest",
    )
    profile_ref: ContinualWorldProfileRef | None = None
    reference_system_root: Path | None = None
    if registered_profile:
        profile_ref = ContinualWorldProfileRef.model_validate(manifest["continual_profile"])
        if profile_ref not in pump_station_continual_world_definition().spec.profiles:
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
    bridge_payload = _mapping(manifest["bridge"], "bridge")
    maintenance_review = bool(bridge_payload.get("maintenance_review", False))
    if registered_profile and maintenance_review:
        raise ValueError("registered pump-station Harbor profile cannot be a review task")
    expected_execution_kind = (
        PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND if maintenance_review else PUMP_STATION_HARBOR_EXECUTION_KIND
    )
    expected_task_world_id = PUMP_STATION_REVIEW_TASK_ID if maintenance_review else PUMP_STATION_TASK_WORLD_ID
    expected_bridge_mode = (
        PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE if maintenance_review else PUMP_STATION_HARBOR_BRIDGE_MODE
    )
    expected_controller_modes = (
        PUMP_STATION_REVIEW_CONTROLLER_MODES if maintenance_review else PUMP_STATION_CONTROLLER_MODES
    )
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
    if allowed_tools not in {
        PUMP_STATION_TOOL_NAMES,
        PUMP_STATION_RICH_WORK_TOOL_NAMES,
        PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
        PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES,
        PUMP_STATION_REVIEW_TOOL_NAMES,
        PUMP_STATION_ACTOR_ACTION_NAMES_V2,
    }:
        raise ValueError("pump-station Harbor tool catalogue differs")
    rich_work_processes = bool(bridge_payload.get("rich_work_processes", False))
    evidence_health = bool(bridge_payload.get("evidence_health", False))
    temporal_evidence = bool(bridge_payload.get("temporal_evidence", False))
    if maintenance_review and not (rich_work_processes and evidence_health):
        raise ValueError("pump-station review requires version 3 rich work")
    if evidence_health and not rich_work_processes:
        raise ValueError("pump-station evidence health requires rich work")
    if temporal_evidence and not evidence_health:
        raise ValueError("pump-station temporal evidence requires evidence health")
    expected_tools = (
        PUMP_STATION_ACTOR_ACTION_NAMES_V2
        if registered_profile
        else PUMP_STATION_REVIEW_TOOL_NAMES
        if maintenance_review
        else PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES
        if temporal_evidence
        else PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
        if evidence_health
        else PUMP_STATION_RICH_WORK_TOOL_NAMES
        if rich_work_processes
        else PUMP_STATION_TOOL_NAMES
    )
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
        maintenance_review=maintenance_review,
        execution_kind=expected_execution_kind,
        task_world_id=expected_task_world_id,
        bridge_mode=expected_bridge_mode,
        profile_ref=profile_ref,
        reference_system_root=reference_system_root,
    )


def _write_export(
    *,
    task_dir: Path,
    project_root: Path,
    package: ReferencePackage,
    profile_ref: ContinualWorldProfileRef | None,
    reference_system: PumpStationReferenceSystem | None,
    rich_work_processes: bool,
    evidence_health: bool,
    temporal_evidence: bool,
    maintenance_review: bool,
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
    runtime = build_verifier_runtime_wheel(
        project_root=project_root,
        output_dir=runtime_dir,
    )
    instruction_path = task_dir / "instruction.md"
    dockerfile_path = environment_dir / "Dockerfile"
    task_toml_path = task_dir / "task.toml"
    test_script_path = tests_dir / "test.sh"
    instruction_path.write_text(
        _instruction_text(maintenance_review=maintenance_review),
        encoding="utf-8",
    )
    dockerfile_path.write_text(_dockerfile_text(), encoding="utf-8")
    task_toml_path.write_text(
        _task_toml_text(
            package,
            maintenance_review=maintenance_review,
        ),
        encoding="utf-8",
    )
    test_script_path.write_text(
        _test_script_text(
            runtime.path.name,
            registered_profile=profile_ref is not None,
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
        runtime=runtime,
        rich_work_processes=rich_work_processes,
        evidence_health=evidence_health,
        temporal_evidence=temporal_evidence,
        maintenance_review=maintenance_review,
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
    profile_ref: ContinualWorldProfileRef | None,
    reference_system: PumpStationReferenceSystem | None,
    reference_system_dir: Path | None,
    runtime: RuntimeWheel,
    rich_work_processes: bool,
    evidence_health: bool,
    temporal_evidence: bool,
    maintenance_review: bool,
) -> dict[str, Any]:
    instruction = task_dir / "instruction.md"
    dockerfile = task_dir / "environment" / "Dockerfile"
    task_toml = task_dir / "task.toml"
    test_script = task_dir / "tests" / "test.sh"
    registered_profile = profile_ref is not None
    if registered_profile != (reference_system is not None and reference_system_dir is not None):
        raise ValueError("registered Harbor profile authority is incomplete")
    bridge = {
        "mode": (PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE if maintenance_review else PUMP_STATION_HARBOR_BRIDGE_MODE),
        "allowed_tools": list(
            PUMP_STATION_ACTOR_ACTION_NAMES_V2
            if registered_profile
            else PUMP_STATION_REVIEW_TOOL_NAMES
            if maintenance_review
            else PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES
            if temporal_evidence
            else PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
            if evidence_health
            else PUMP_STATION_RICH_WORK_TOOL_NAMES
            if rich_work_processes
            else PUMP_STATION_TOOL_NAMES
        ),
        "rich_work_processes": rich_work_processes,
        "evidence_health": evidence_health,
        "temporal_evidence": temporal_evidence,
        "output_path": PUMP_STATION_HARBOR_OUTPUT_PATH,
        "controller_modes": list(
            PUMP_STATION_REVIEW_CONTROLLER_MODES if maintenance_review else PUMP_STATION_CONTROLLER_MODES
        ),
    }
    if maintenance_review:
        bridge["maintenance_review"] = True
    manifest: dict[str, Any] = {
        "schema_version": (
            PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION
            if registered_profile
            else PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION
        ),
        "execution_kind": (
            PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND if maintenance_review else PUMP_STATION_HARBOR_EXECUTION_KIND
        ),
        "task_world_id": (PUMP_STATION_REVIEW_TASK_ID if maintenance_review else PUMP_STATION_TASK_WORLD_ID),
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
        manifest["continual_profile"] = profile_ref.model_dump(mode="json")
        manifest["reference_system"] = {
            "path": "tests/reference-system",
            "descriptor_id": reference_system.descriptor_id,
            "descriptor_content_id": reference_system.descriptor_content_id,
            "directory_sha256": directory_sha256(reference_system_dir),
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


def _validated_project_root(project_root: Path) -> Path:
    root = Path(project_root).resolve()
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"invalid canonical project root: {root}") from error
    if config.get("project", {}).get("name") != "aec-bench":
        raise ValueError(f"invalid canonical project root: {root}")
    return root


def _instruction_text(*, maintenance_review: bool = False) -> str:
    if maintenance_review:
        return (
            "# Wastewater pump-station maintenance closeout review\n\n"
            "Review the named Pump A closeout pack through the declared "
            "reviewer tools. Identify any source-bound evidence issue and submit "
            "every required review field. The selected controller must preserve "
            "the complete review evidence at "
            f"`{PUMP_STATION_HARBOR_OUTPUT_PATH}`. Harbor owns reward and runs "
            "the independent verifier after the agent phase.\n"
        )
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
    *,
    maintenance_review: bool = False,
) -> str:
    task_world_id = PUMP_STATION_REVIEW_TASK_ID if maintenance_review else PUMP_STATION_TASK_WORLD_ID
    tags = (
        '["asset-stewardship", "pump-station", "maintenance-review"]'
        if maintenance_review
        else '["asset-stewardship", "pump-station", "world-session"]'
    )
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
) -> str:
    reference_system_variable = (
        'REFERENCE_SYSTEM_DIR="${AEC_BENCH_REFERENCE_SYSTEM_DIR:-/tests/reference-system}"\n'
        if registered_profile
        else ""
    )
    reference_system_argument = '  --reference-system-dir "$REFERENCE_SYSTEM_DIR" \\\n' if registered_profile else ""
    return f"""#!/bin/sh
# ABOUTME: Runs the hidden pump-station verifier after Harbor ends the agent phase.
# ABOUTME: Reloads the exact exported package and immutable world-session evidence.
set -eu

RUN_DIR="${{AEC_BENCH_WORLD_SESSION_DIR:-{PUMP_STATION_HARBOR_OUTPUT_PATH}}}"
EXPORT_MANIFEST="${{AEC_BENCH_EXPORT_MANIFEST:-/tests/{_MANIFEST_NAME}}}"
PACKAGE_DIR="${{AEC_BENCH_REFERENCE_PACKAGE_DIR:-/tests/reference-package}}"
{reference_system_variable}VERIFIER_RUNTIME="${{AEC_BENCH_VERIFIER_RUNTIME:-/tests/runtime/{wheel_name}}}"
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
{reference_system_argument}  --verifier-runtime "$VERIFIER_RUNTIME" \\
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
    "PUMP_STATION_REGISTERED_HARBOR_EXPORT_SCHEMA_VERSION",
    "PumpStationHarborBridge",
    "export_pump_station_harbor_task",
    "is_pump_station_harbor_inventory_artifact",
    "load_pump_station_harbor_bridge",
)
