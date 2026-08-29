# ABOUTME: Exports compiled lifecycle worlds as least-privilege Harbor task packages.
# ABOUTME: Keeps Harbor packaging in the concrete integration owner and outside task semantics.

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.harness.harbor_task_exporting.bridge import (
    allowed_tools as _allowed_tools,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    load_bridge as _load_bridge,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validate_bridge_attestation as _validate_bridge_attestation,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validate_compiled_world as _validate_compiled_world,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validate_harbor_lifecycle_semantics as validate_harbor_lifecycle_semantics,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validate_operation_surface as _validate_operation_surface,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validate_source_identity as _validate_source_identity,
)
from aec_bench.harness.harbor_task_exporting.bridge import (
    validated_manifest_shape as _validated_manifest_shape,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    ATTESTATION_FILENAME as _ATTESTATION_FILENAME,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    BASE_IMAGE as _BASE_IMAGE,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    HARBOR_LIFECYCLE_BRIDGE_MODE as HARBOR_LIFECYCLE_BRIDGE_MODE,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    HARBOR_SECURITY as _HARBOR_SECURITY,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    OUTPUT_PATH as _OUTPUT_PATH,
)
from aec_bench.harness.harbor_task_exporting.constants import (
    RUNTIME_DEPENDENCIES as _RUNTIME_DEPENDENCIES,
)
from aec_bench.harness.harbor_task_exporting.runtime_wheel import (
    build_verifier_runtime_wheel as _build_verifier_runtime_wheel,
)
from aec_bench.harness.harbor_task_exporting.stable_io import (
    canonical_sha256 as _canonical_sha256,
)
from aec_bench.harness.harbor_task_exporting.stable_io import (
    directory_sha256 as _directory_sha256,
)
from aec_bench.harness.harbor_task_exporting.stable_io import (
    file_sha256 as _file_sha256,
)
from aec_bench.harness.harbor_task_exporting.surfaces import (
    dockerfile_text as _dockerfile,
)
from aec_bench.harness.harbor_task_exporting.surfaces import (
    instruction_text as _instruction,
)
from aec_bench.harness.harbor_task_exporting.surfaces import (
    stage_initial_context as _stage_initial_context,
)
from aec_bench.harness.harbor_task_exporting.surfaces import (
    task_toml_text as _task_toml,
)
from aec_bench.harness.harbor_task_exporting.surfaces import (
    test_script_text as _test_script,
)
from aec_bench.lifecycles.catalogue import verify_lifecycle
from aec_bench.lifecycles.compiled import (
    CompiledLifecycle,
    CompiledLifecycleEnvelope,
    load_compiled_lifecycle,
)


@dataclass(frozen=True)
class ExportedHarborTask:
    task_dir: Path
    manifest_path: Path
    verifier_runtime_wheel_path: Path


@dataclass(frozen=True)
class HarborLifecycleBridge:
    """Validated host-only authority for one exported Harbor lifecycle task."""

    task_root: Path
    package_dir: Path
    envelope: CompiledLifecycleEnvelope
    manifest_sha256: str
    allowed_tools: tuple[str, ...]
    output_path: str


def export_compiled_lifecycle_harbor_task(
    compiled: CompiledLifecycle,
    task_dir: Path,
    *,
    project_root: Path,
) -> ExportedHarborTask:
    """Export one immutable compiled world without exposing hidden authority to the agent."""
    source = _validate_compiled_world(compiled)
    validate_harbor_lifecycle_semantics(source.lifecycle)
    _validate_operation_surface(compiled.envelope)
    root = _validate_project_root(project_root)

    destination = Path(task_dir)
    if destination.exists():
        raise FileExistsError(f"Harbor task output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as raw_staging:
        staging = Path(raw_staging) / destination.name
        staging.mkdir()
        exported = _write_export(
            compiled=compiled,
            metadata=source.metadata,
            lifecycle=source.lifecycle,
            task_dir=staging,
            project_root=root,
        )
        staging.rename(destination)

    return ExportedHarborTask(
        task_dir=destination,
        manifest_path=destination / exported.manifest_path.relative_to(exported.task_dir),
        verifier_runtime_wheel_path=(destination / exported.verifier_runtime_wheel_path.relative_to(exported.task_dir)),
    )


def load_harbor_lifecycle_bridge(environment_dir: Path) -> HarborLifecycleBridge:
    """Resolve and validate a task-owned bridge before any provider is constructed."""
    loaded = _load_bridge(environment_dir)
    return HarborLifecycleBridge(
        task_root=loaded.task_root,
        package_dir=loaded.package_dir,
        envelope=loaded.envelope,
        manifest_sha256=loaded.manifest_sha256,
        allowed_tools=loaded.allowed_tools,
        output_path=_OUTPUT_PATH,
    )


def write_harbor_lifecycle_attestation(
    run_dir: Path,
    bridge: HarborLifecycleBridge,
) -> Path:
    """Bind the uploaded agent run to the host-validated task authority."""
    destination_dir = Path(run_dir)
    if not destination_dir.is_dir() or destination_dir.is_symlink():
        raise ValueError("Harbor lifecycle attestation requires a safe materialized run directory")
    attestation_path = destination_dir / _ATTESTATION_FILENAME
    if attestation_path.exists() or attestation_path.is_symlink():
        raise ValueError("Harbor lifecycle run already contains a bridge attestation")
    _write_json(
        attestation_path,
        {
            "bridge_mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
            "manifest_sha256": bridge.manifest_sha256,
            "output_path": bridge.output_path,
            "reward_owner": "harbor_verifier",
            "source_package_sha256": bridge.envelope.package_sha256,
        },
    )
    return attestation_path


def _write_export(
    *,
    compiled: CompiledLifecycle,
    metadata: LifecycleTaskMetadata,
    lifecycle: EvidenceLifecycleSpec,
    task_dir: Path,
    project_root: Path,
) -> ExportedHarborTask:
    tests_dir = task_dir / "tests"
    initial_context = task_dir / "environment" / "context" / "initial"
    verifier_package = tests_dir / "compiled-world"
    runtime_dir = tests_dir / "runtime"
    tests_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)

    shutil.copytree(compiled.package_dir, verifier_package)
    copied = load_compiled_lifecycle(verifier_package)
    if copied.envelope != compiled.envelope:
        raise ValueError("copied lifecycle package does not match the compiled source")
    _validate_compiled_world(copied)
    _stage_initial_context(compiled.package_dir, initial_context)

    envelope_payload = compiled.envelope.model_dump(mode="json")
    _write_json(tests_dir / "compiled-world-envelope.json", envelope_payload)
    runtime = _build_verifier_runtime_wheel(project_root=project_root, output_dir=runtime_dir)

    instruction_path = task_dir / "instruction.md"
    instruction_path.write_text(_instruction(metadata=metadata, lifecycle=lifecycle), encoding="utf-8")
    dockerfile = task_dir / "environment" / "Dockerfile"
    dockerfile.parent.mkdir(parents=True, exist_ok=True)
    dockerfile.write_text(_dockerfile(), encoding="utf-8")
    task_toml = task_dir / "task.toml"
    task_toml.write_text(
        _task_toml(metadata=metadata, envelope=compiled.envelope),
        encoding="utf-8",
    )
    test_script = tests_dir / "test.sh"
    test_script.write_text(_test_script(runtime.path.name), encoding="utf-8")
    test_script.chmod(0o755)

    manifest = {
        "source": {
            "envelope": envelope_payload,
            "envelope_sha256": _canonical_sha256(envelope_payload),
            "package": "tests/compiled-world",
            "package_sha256": compiled.envelope.package_sha256,
        },
        "agent_surface": {
            "base_image": _BASE_IMAGE,
            "dependencies": list(_RUNTIME_DEPENDENCIES),
            "dockerfile_sha256": _file_sha256(dockerfile),
            "initial_context": "environment/context/initial",
            "initial_context_sha256": _directory_sha256(initial_context),
            "task_instruction_sha256": _file_sha256(instruction_path),
        },
        "bridge": {
            "allowed_tools": list(_allowed_tools(lifecycle)),
            "mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
            "output_path": _OUTPUT_PATH,
            "reward_owner": "harbor_verifier",
            "visibility_policy": "persistent_context",
        },
        "harbor": {
            "output_path": _OUTPUT_PATH,
            "reward_owner": "harbor_verifier",
            "security": dict(_HARBOR_SECURITY),
            "task_toml": "task.toml",
            "task_toml_sha256": _file_sha256(task_toml),
            "test_script": "tests/test.sh",
            "test_script_sha256": _file_sha256(test_script),
        },
        "verifier": {
            "runtime_wheel": f"tests/runtime/{runtime.path.name}",
            "runtime_wheel_sha256": runtime.sha256,
            "source_tree_sha256": runtime.source_tree_sha256,
        },
    }
    manifest_path = task_dir / "compiled-world-export.json"
    _write_json(manifest_path, manifest)
    _write_json(tests_dir / "compiled-world-export.json", manifest)
    return ExportedHarborTask(
        task_dir=task_dir,
        manifest_path=manifest_path,
        verifier_runtime_wheel_path=runtime.path,
    )


def _validate_project_root(project_root: Path) -> Path:
    root = Path(project_root).resolve()
    pyproject_path = root / "pyproject.toml"
    source_package = root / "src" / "aec_bench"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid canonical project root: {root}") from exc
    if pyproject.get("project", {}).get("name") != "aec-bench" or not source_package.is_dir():
        raise ValueError(f"project root does not contain the canonical aec-bench package: {root}")
    return root


def verify_exported_lifecycle_run(
    *,
    package_dir: Path,
    run_dir: Path,
    envelope_path: Path,
    export_manifest_path: Path,
    verifier_runtime_wheel_path: Path,
    reward_path: Path,
    details_path: Path,
    initial_context_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the task verifier as the sole reward authority after agent completion."""
    envelope = CompiledLifecycleEnvelope.model_validate(_read_json(envelope_path))
    compiled = load_compiled_lifecycle(Path(package_dir))
    if compiled.envelope != envelope:
        raise ValueError("exported lifecycle package does not match its compiled envelope")
    source = _validate_compiled_world(compiled)
    validate_harbor_lifecycle_semantics(source.lifecycle)
    _validate_operation_surface(envelope)
    manifest = _validated_manifest_shape(_read_json(export_manifest_path))
    manifest_source = cast(dict[str, Any], manifest["source"])
    bridge_payload = cast(dict[str, Any], manifest["bridge"])
    harbor_payload = cast(dict[str, Any], manifest["harbor"])
    verifier_payload = cast(dict[str, Any], manifest["verifier"])
    agent_surface = cast(dict[str, Any], manifest["agent_surface"])
    _validate_source_identity(source=manifest_source, envelope=envelope)
    if bridge_payload["reward_owner"] != "harbor_verifier":
        raise ValueError("export manifest assigns reward outside Harbor verifier")
    if harbor_payload["reward_owner"] != "harbor_verifier" or harbor_payload["output_path"] != _OUTPUT_PATH:
        raise ValueError("Harbor authority does not preserve verifier-owned reward")
    if harbor_payload["security"] != _HARBOR_SECURITY:
        raise ValueError("Harbor task security contract is not supported")
    if harbor_payload["test_script"] != "tests/test.sh":
        raise ValueError("Harbor verifier script path is not canonical")
    test_script = Path(export_manifest_path).parent / "test.sh"
    if _file_sha256(test_script) != harbor_payload["test_script_sha256"]:
        raise ValueError("Harbor verifier script does not match the export manifest")
    if test_script.read_text(encoding="utf-8") != _test_script(Path(verifier_runtime_wheel_path).name):
        raise ValueError("Harbor verifier script does not match the canonical lifecycle export")
    if _file_sha256(verifier_runtime_wheel_path) != verifier_payload["runtime_wheel_sha256"]:
        raise ValueError("verifier runtime does not match the export manifest")
    context = initial_context_dir
    if context is None:
        context = Path(export_manifest_path).parent.parent / cast(str, agent_surface["initial_context"])
    if _directory_sha256(Path(context)) != agent_surface["initial_context_sha256"]:
        raise ValueError("initial context does not match the export manifest")
    manifest_sha256 = _file_sha256(export_manifest_path)
    _validate_bridge_attestation(
        run_dir=Path(run_dir),
        envelope=envelope,
        manifest_sha256=manifest_sha256,
    )

    verification = verify_lifecycle(Path(package_dir), Path(run_dir))
    reward = float(verification["reward"])
    passed = bool(verification["passed"])
    details = {
        "passed": passed,
        "bridge_manifest_sha256": manifest_sha256,
        "reward_owner": "harbor_verifier",
        "source_package_sha256": envelope.package_sha256,
        "verifier_runtime_sha256": verifier_payload["runtime_wheel_sha256"],
        "verification": verification,
    }
    _write_json(Path(reward_path), {"reward": reward})
    _write_json(Path(details_path), details)
    return details


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one exported compiled lifecycle Harbor task")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--package-dir", type=Path, required=True)
    verify.add_argument("--run-dir", type=Path, required=True)
    verify.add_argument("--envelope", type=Path, required=True)
    verify.add_argument("--export-manifest", type=Path, required=True)
    verify.add_argument("--initial-context", type=Path, required=True)
    verify.add_argument("--verifier-runtime", type=Path, required=True)
    verify.add_argument("--reward-path", type=Path, required=True)
    verify.add_argument("--details-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verify_exported_lifecycle_run(
            package_dir=args.package_dir,
            run_dir=args.run_dir,
            envelope_path=args.envelope,
            export_manifest_path=args.export_manifest,
            initial_context_dir=args.initial_context,
            verifier_runtime_wheel_path=args.verifier_runtime,
            reward_path=args.reward_path,
            details_path=args.details_path,
        )
    except Exception as exc:
        _write_json(args.reward_path, {"reward": 0.0})
        _write_json(args.details_path, {"passed": False, "reward_owner": "harbor_verifier", "error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(_main())
