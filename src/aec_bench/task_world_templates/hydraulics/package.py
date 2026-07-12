# ABOUTME: Materializes immutable hydraulic source packages and deterministic run directories.
# ABOUTME: Binds source, engine, request, report, and verifier artifacts with strong hashes.

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts import validators as validators_module
from aec_bench.ledger.durability import fsync_directory, fsync_tree
from aec_bench.task_world_templates.hydraulics import contracts as contracts_module
from aec_bench.task_world_templates.hydraulics import identity as identity_module
from aec_bench.task_world_templates.hydraulics import kernel
from aec_bench.task_world_templates.hydraulics import report as report_module
from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicEngineIdentity,
    HydraulicPackageManifest,
    HydraulicRunManifest,
    HydraulicRunRequest,
    HydraulicSourceState,
    hydraulic_run_id,
)
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256
from aec_bench.task_world_templates.hydraulics.registry import get_hydraulic_source_state
from aec_bench.task_world_templates.hydraulics.report import render_hydraulic_report

_PACKAGE_MANIFEST = "package-manifest.json"
_RUN_MANIFEST = "run-manifest.json"
_RUN_ARTIFACTS = ("request.json", "results.json", "timeseries.json", "report.md")


class HydraulicWorldIntegrityError(ValueError):
    """Raised when immutable hydraulic package or run evidence does not reconcile."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _engine_identity() -> HydraulicEngineIdentity:
    source_inventory = {
        "contracts.py": _sha256(Path(contracts_module.__file__)),
        "identity.py": _sha256(Path(identity_module.__file__)),
        "kernel.py": _sha256(Path(kernel.__file__)),
        "package.py": _sha256(Path(__file__)),
        "report.py": _sha256(Path(report_module.__file__)),
        "validators.py": _sha256(Path(validators_module.__file__)),
    }
    runtime_dependencies = {
        "pydantic": importlib.metadata.version("pydantic"),
        "python_cache_tag": sys.implementation.cache_tag or "unknown",
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }
    return HydraulicEngineIdentity(
        engine_id="aec-bench.deterministic-hydraulic-screening-kernel",
        engine_version="1",
        source_inventory_sha256=source_inventory,
        implementation_sha256=canonical_json_sha256(source_inventory),
        runtime_dependencies=runtime_dependencies,
        runtime_dependency_sha256=canonical_json_sha256(runtime_dependencies),
    )


def _walk_files(root: Path) -> dict[str, Path]:
    if root.is_symlink():
        raise HydraulicWorldIntegrityError(f"symlink is not allowed: {root}")
    files: dict[str, Path] = {}
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in directory_names:
            path = directory_path / name
            if path.is_symlink():
                raise HydraulicWorldIntegrityError(f"symlink is not allowed: {path.relative_to(root)}")
        for name in file_names:
            path = directory_path / name
            if path.is_symlink():
                raise HydraulicWorldIntegrityError(f"symlink is not allowed: {path.relative_to(root)}")
            files[path.relative_to(root).as_posix()] = path
    return files


def _artifact_hashes(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    files = _walk_files(root)
    missing = [name for name in names if name not in files]
    if missing:
        raise HydraulicWorldIntegrityError(f"missing artifact: {missing[0]}")
    return {name: _sha256(files[name]) for name in names}


def _validate_file_set(root: Path, expected: set[str]) -> dict[str, Path]:
    files = _walk_files(root)
    missing = sorted(expected - set(files))
    if missing:
        raise HydraulicWorldIntegrityError(f"missing artifact: {missing[0]}")
    unexpected = sorted(set(files) - expected)
    if unexpected:
        raise HydraulicWorldIntegrityError(f"unexpected artifact: {unexpected[0]}")
    return files


def _preflight_destination(destination: Path) -> None:
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f"output directory must be empty: {destination}")


def _publish_staged_directory(destination: Path, staging: Path) -> Path:
    fsync_tree(staging)
    if destination.exists():
        destination.rmdir()
    os.replace(staging, destination)
    fsync_directory(destination.parent)
    return destination


def _staging_directory(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))


def materialize_hydraulic_world(
    world_id: str,
    output_dir: Path,
    *,
    source_state: HydraulicSourceState | None = None,
) -> Path:
    """Materialize one immutable public hydraulic source package."""
    destination = Path(output_dir)
    _preflight_destination(destination)
    source = source_state or get_hydraulic_source_state(world_id)
    if source.world_id != world_id:
        raise ValueError(f"source state world_id {source.world_id!r} does not match {world_id!r}")
    staging = _staging_directory(destination)
    try:
        _write_json(staging / "source" / "source-state.json", source.model_dump(mode="json"))
        _write_json(staging / "engine" / "identity.json", _engine_identity().model_dump(mode="json"))
        (staging / "README.md").write_text(_package_readme(source), encoding="utf-8")
        artifact_names = ("README.md", "engine/identity.json", "source/source-state.json")
        artifact_sha256 = _artifact_hashes(staging, artifact_names)
        package_sha256 = canonical_json_sha256(
            {"world_id": world_id, "artifact_sha256": dict(sorted(artifact_sha256.items()))}
        )
        manifest = HydraulicPackageManifest(
            world_id=world_id,
            artifact_sha256=artifact_sha256,
            package_sha256=package_sha256,
        )
        _write_json(staging / _PACKAGE_MANIFEST, manifest.model_dump(mode="json"))
        return _publish_staged_directory(destination, staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _package_readme(source: HydraulicSourceState) -> str:
    return (
        f"# {source.title}\n\n"
        f"{source.description}\n\n"
        f"{source.claim_boundary}\n\n"
        "This immutable package contains the exact public source state and selected "
        "benchmark-owned engine identity. Run outputs must be written outside this directory.\n"
    )


def _load_validated_package(
    package_dir: Path,
) -> tuple[HydraulicSourceState, HydraulicPackageManifest, HydraulicEngineIdentity]:
    package = Path(package_dir)
    files = _validate_file_set(
        package,
        {"README.md", "engine/identity.json", "source/source-state.json", _PACKAGE_MANIFEST},
    )
    try:
        manifest = HydraulicPackageManifest.model_validate(_read_json(files[_PACKAGE_MANIFEST]))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HydraulicWorldIntegrityError("invalid package manifest") from exc
    for name, expected_hash in manifest.artifact_sha256.items():
        if _sha256(files[name]) != expected_hash:
            raise HydraulicWorldIntegrityError(f"artifact hash mismatch: {name}")
    source = HydraulicSourceState.model_validate(_read_json(files["source/source-state.json"]))
    engine = HydraulicEngineIdentity.model_validate(_read_json(files["engine/identity.json"]))
    if source.world_id != manifest.world_id:
        raise HydraulicWorldIntegrityError("package world identity mismatch")
    if engine != _engine_identity():
        raise HydraulicWorldIntegrityError("package engine identity does not match this checkout")
    return source, manifest, engine


def build_hydraulic_run_request(package_dir: Path, *, scenario_id: str) -> HydraulicRunRequest:
    """Build a request that binds one scenario to exact package, source, and engine bytes."""
    package = Path(package_dir)
    source, manifest, engine = _load_validated_package(package)
    if scenario_id not in {scenario.scenario_id for scenario in source.payload.scenarios}:
        known = ", ".join(scenario.scenario_id for scenario in source.payload.scenarios)
        raise ValueError(f"unknown hydraulic scenario {scenario_id!r}; expected one of: {known}")
    source_state_sha256 = _sha256(package / "source" / "source-state.json")
    calculation_input_sha256 = canonical_json_sha256(source.payload.model_dump(mode="json"))
    run_id = hydraulic_run_id(
        world_id=source.world_id,
        scenario_id=scenario_id,
        package_sha256=manifest.package_sha256,
        source_state_sha256=source_state_sha256,
        calculation_input_sha256=calculation_input_sha256,
        engine=engine,
    )
    return HydraulicRunRequest(
        run_id=run_id,
        world_id=source.world_id,
        scenario_id=scenario_id,
        package_sha256=manifest.package_sha256,
        source_state_sha256=source_state_sha256,
        calculation_input_sha256=calculation_input_sha256,
        engine=engine,
    )


def _assert_disjoint(package: Path, run: Path) -> None:
    package_resolved = package.resolve()
    run_resolved = run.resolve()
    if (
        package_resolved == run_resolved
        or run_resolved.is_relative_to(package_resolved)
        or package_resolved.is_relative_to(run_resolved)
    ):
        raise ValueError("hydraulic package and run output must not overlap")


def execute_hydraulic_world(
    package_dir: Path,
    run_dir: Path,
    request: HydraulicRunRequest,
) -> Path:
    """Execute one source-bound scenario and atomically publish immutable run evidence."""
    package = Path(package_dir)
    destination = Path(run_dir)
    _assert_disjoint(package, destination)
    _preflight_destination(destination)
    source, manifest, engine = _load_validated_package(package)
    expected_request = build_hydraulic_run_request(package, scenario_id=request.scenario_id)
    if request != expected_request:
        raise HydraulicWorldIntegrityError("run request does not match current package identity")
    result, time_series = kernel.simulate_hydraulic_world(
        source=source,
        scenario_id=request.scenario_id,
        run_id=request.run_id,
        engine=engine,
        source_state_sha256=request.source_state_sha256,
        calculation_input_sha256=request.calculation_input_sha256,
    )
    staging = _staging_directory(destination)
    try:
        _write_json(staging / "request.json", request.model_dump(mode="json"))
        _write_json(staging / "results.json", result.model_dump(mode="json"))
        _write_json(staging / "timeseries.json", time_series.model_dump(mode="json"))
        (staging / "report.md").write_text(render_hydraulic_report(source, request, result), encoding="utf-8")
        artifact_sha256 = _artifact_hashes(staging, _RUN_ARTIFACTS)
        run_manifest = HydraulicRunManifest(
            run_id=request.run_id,
            world_id=request.world_id,
            scenario_id=request.scenario_id,
            package_sha256=manifest.package_sha256,
            source_state_sha256=request.source_state_sha256,
            calculation_input_sha256=request.calculation_input_sha256,
            engine=engine,
            artifact_sha256=artifact_sha256,
        )
        _write_json(staging / _RUN_MANIFEST, run_manifest.model_dump(mode="json"))
        return _publish_staged_directory(destination, staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
