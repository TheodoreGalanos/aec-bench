# ABOUTME: Admits task-owned Harbor lifecycle bridges against frozen export contracts.
# ABOUTME: Separates manifest, agent, verifier, and Harbor authority validation stages.

from __future__ import annotations

import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.task_world_templates.compiled_world import (
    CompiledLifecycleWorld,
    CompiledWorldEnvelope,
    build_compiled_world_envelope,
)
from aec_bench.task_world_templates.contracts import (
    CompositeTaskWorldTemplate,
    EvidenceLifecycleSpec,
)
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_adapter

from .constants import (
    ATTESTATION_FILENAME,
    ATTESTATION_SCHEMA_VERSION,
    BASE_IMAGE,
    BASE_TOOLS,
    EXPORT_SCHEMA_VERSION,
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    HARBOR_SECURITY,
    MAX_EXPORT_MANIFEST_BYTES,
    MAX_RUNTIME_WHEEL_BYTES,
    MAX_TASK_CONTROL_FILE_BYTES,
    OUTPUT_PATH,
    RUNTIME_DEPENDENCIES,
)
from .runtime_wheel import validate_verifier_runtime_wheel as validate_verifier_runtime_wheel
from .stable_io import (
    RegularFileSnapshot,
    assert_snapshot_current,
    canonical_sha256,
    directory_sha256,
    read_stable_regular_file,
    snapshot_json_object,
    snapshot_text,
)
from .surfaces import (
    task_toml_text,
    test_script_text,
    validate_canonical_agent_surface,
)


@dataclass(frozen=True)
class ValidatedCompiledWorld:
    template: CompositeTaskWorldTemplate
    lifecycle: EvidenceLifecycleSpec


@dataclass(frozen=True)
class BridgeLoadResult:
    task_root: Path
    package_dir: Path
    envelope: CompiledWorldEnvelope
    manifest_sha256: str
    allowed_tools: tuple[str, ...]


@dataclass(frozen=True)
class _BridgeManifest:
    public: RegularFileSnapshot
    hidden: RegularFileSnapshot
    payload: dict[str, Any]


@dataclass(frozen=True)
class _BridgeSource:
    envelope: CompiledWorldEnvelope
    package_dir: Path
    compiled: ValidatedCompiledWorld


def validate_harbor_lifecycle_semantics(lifecycle: EvidenceLifecycleSpec) -> None:
    """Reject lifecycle behavior that the explicit Harbor bridge cannot preserve."""
    lifecycle = EvidenceLifecycleSpec.model_validate(lifecycle.model_dump(mode="json"))
    if any(checkpoint.conditional_evidence is not None for checkpoint in lifecycle.checkpoints):
        raise ValueError("Harbor lifecycle export does not support conditional evidence requests")
    previous_checkpoint_id: str | None = None
    for checkpoint in lifecycle.checkpoints:
        if checkpoint.allow_additional_submission_fields:
            raise ValueError("Harbor lifecycle export requires exact JSON submission fields")
        expected_dependencies = [] if previous_checkpoint_id is None else [previous_checkpoint_id]
        if checkpoint.depends_on != expected_dependencies:
            raise ValueError("Harbor lifecycle export requires a linear checkpoint graph")
        previous_checkpoint_id = checkpoint.checkpoint_id


def load_bridge(environment_dir: Path) -> BridgeLoadResult:
    """Resolve and validate one task-owned bridge before provider construction."""
    resolved_environment, task_root = _resolve_bridge_location(environment_dir)
    manifest = _load_bridge_manifest(task_root)
    source = _load_bridge_source(task_root=task_root, manifest=manifest.payload)
    bridge_payload = cast(dict[str, Any], manifest.payload["bridge"])
    agent_surface = cast(dict[str, Any], manifest.payload["agent_surface"])
    harbor_payload = cast(dict[str, Any], manifest.payload["harbor"])
    verifier_payload = cast(dict[str, Any], manifest.payload["verifier"])
    expected_tools = _validate_bridge_contract(
        bridge=bridge_payload,
        lifecycle=source.compiled.lifecycle,
    )
    agent_snapshots = _validate_bridge_agent_surface(
        resolved_environment=resolved_environment,
        task_root=task_root,
        source=source,
        agent_surface=agent_surface,
    )
    runtime_snapshot = _validate_bridge_runtime(
        task_root=task_root,
        verifier=verifier_payload,
    )
    authority_snapshots = _validate_harbor_authority(
        task_root=task_root,
        template=source.compiled.template,
        envelope=source.envelope,
        harbor=harbor_payload,
        runtime_wheel=runtime_snapshot.path,
    )
    for snapshot in (
        manifest.public,
        manifest.hidden,
        *agent_snapshots,
        runtime_snapshot,
        *authority_snapshots,
    ):
        assert_snapshot_current(snapshot)
    return BridgeLoadResult(
        task_root=task_root,
        package_dir=source.package_dir,
        envelope=source.envelope,
        manifest_sha256=manifest.public.sha256,
        allowed_tools=expected_tools,
    )


def validate_compiled_world(compiled: CompiledLifecycleWorld) -> ValidatedCompiledWorld:
    package = Path(compiled.package_dir)
    template = CompositeTaskWorldTemplate.model_validate(_read_json_object(package / "template.json"))
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json_object(package / "lifecycle.json"))
    if template.evidence_lifecycle != lifecycle:
        raise ValueError("compiled world template and lifecycle contracts do not match")
    adapter = registered_lifecycle_adapter(compiled.envelope.template_id)
    rebuilt = build_compiled_world_envelope(
        template=template,
        adapter=adapter,
        package_dir=package,
        requested_variant_id=compiled.envelope.variant_id,
        visibility=compiled.envelope.visibility,
    )
    if rebuilt != compiled.envelope:
        raise ValueError("compiled world envelope does not match the materialized package bytes")
    return ValidatedCompiledWorld(template=template, lifecycle=lifecycle)


def validate_adapter_surface(envelope: CompiledWorldEnvelope) -> None:
    if envelope.visibility != "public":
        raise ValueError("Harbor lifecycle export refuses non-public compiled worlds")
    if "operations" not in envelope.adapter.capabilities or envelope.operation_protocol_sha256 is None:
        raise ValueError("Harbor lifecycle export requires a content-pinned operation resolver")


def validated_manifest_shape(manifest: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(
        manifest,
        {"schema_version", "source", "agent_surface", "bridge", "harbor", "verifier"},
        label="export manifest",
    )
    if manifest["schema_version"] != EXPORT_SCHEMA_VERSION:
        raise ValueError("unsupported Harbor lifecycle export schema")
    source = _require_mapping(manifest["source"], label="source manifest")
    _require_exact_keys(source, {"envelope", "envelope_sha256", "package", "package_sha256"}, label="source")
    agent_surface = _require_mapping(manifest["agent_surface"], label="agent surface manifest")
    _require_exact_keys(
        agent_surface,
        {
            "base_image",
            "dependencies",
            "dockerfile_sha256",
            "initial_context",
            "initial_context_sha256",
            "task_instruction_sha256",
        },
        label="agent_surface",
    )
    if not isinstance(agent_surface["dependencies"], list) or not all(
        isinstance(item, str) for item in agent_surface["dependencies"]
    ):
        raise ValueError("agent surface dependencies must be a string list")
    bridge = _require_mapping(manifest["bridge"], label="bridge manifest")
    _require_exact_keys(
        bridge,
        {"allowed_tools", "mode", "output_path", "reward_owner", "visibility_policy"},
        label="bridge",
    )
    if not isinstance(bridge["allowed_tools"], list) or not all(
        isinstance(item, str) for item in bridge["allowed_tools"]
    ):
        raise ValueError("bridge allowed_tools must be a string list")
    harbor = _require_mapping(manifest["harbor"], label="Harbor authority manifest")
    _require_exact_keys(
        harbor,
        {
            "output_path",
            "reward_owner",
            "security",
            "task_toml",
            "task_toml_sha256",
            "test_script",
            "test_script_sha256",
        },
        label="harbor",
    )
    security = _require_mapping(harbor["security"], label="Harbor security manifest")
    _require_exact_keys(security, set(HARBOR_SECURITY), label="harbor.security")
    verifier = _require_mapping(manifest["verifier"], label="verifier manifest")
    _require_exact_keys(
        verifier,
        {"runtime_wheel", "runtime_wheel_sha256", "source_tree_sha256"},
        label="verifier",
    )
    return manifest


def validate_source_identity(*, source: dict[str, Any], envelope: CompiledWorldEnvelope) -> None:
    envelope_payload = envelope.model_dump(mode="json")
    if source["envelope"] != envelope_payload or source["envelope_sha256"] != canonical_sha256(envelope_payload):
        raise ValueError("export manifest does not match the compiled world envelope")
    if source["package_sha256"] != envelope.package_sha256:
        raise ValueError("export manifest does not match the compiled world package")


def validate_bridge_attestation(
    *,
    run_dir: Path,
    envelope: CompiledWorldEnvelope,
    manifest_sha256: str,
) -> None:
    attestation_path = Path(run_dir) / ATTESTATION_FILENAME
    try:
        attestation = _read_json_object(attestation_path)
    except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Harbor bridge attestation is missing or invalid") from exc
    expected = {
        "bridge_mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
        "manifest_sha256": manifest_sha256,
        "output_path": OUTPUT_PATH,
        "reward_owner": "harbor_verifier",
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "source_package_sha256": envelope.package_sha256,
    }
    if attestation != expected:
        raise ValueError("Harbor bridge attestation does not match the verifier authority")


def _resolve_bridge_location(environment_dir: Path) -> tuple[Path, Path]:
    raw_environment = Path(environment_dir)
    try:
        resolved_environment = raw_environment.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"Harbor lifecycle environment directory is missing: {raw_environment}") from exc
    if resolved_environment.name != "environment" or not resolved_environment.is_dir():
        raise ValueError("Harbor lifecycle bridge requires the canonical task environment directory")
    task_root = resolved_environment.parent
    if (task_root / "environment").resolve(strict=True) != resolved_environment:
        raise ValueError("Harbor lifecycle task-root provenance is ambiguous")
    return resolved_environment, task_root


def _load_bridge_manifest(task_root: Path) -> _BridgeManifest:
    manifest_path = task_root / "compiled-world-export.json"
    public = read_stable_regular_file(
        manifest_path,
        label="task-owned bridge manifest",
        max_bytes=MAX_EXPORT_MANIFEST_BYTES,
    )
    manifest = validated_manifest_shape(snapshot_json_object(public))
    hidden_manifest_path = task_root / "tests" / "compiled-world-export.json"
    hidden = read_stable_regular_file(
        hidden_manifest_path,
        label="hidden export manifest",
        max_bytes=MAX_EXPORT_MANIFEST_BYTES,
    )
    if hidden.sha256 != public.sha256:
        raise ValueError("hidden export manifest does not match the task-owned bridge manifest")
    return _BridgeManifest(public=public, hidden=hidden, payload=manifest)


def _load_bridge_source(*, task_root: Path, manifest: dict[str, Any]) -> _BridgeSource:
    source = cast(dict[str, Any], manifest["source"])
    envelope = CompiledWorldEnvelope.model_validate(source["envelope"])
    package_dir = _task_relative_path(task_root, source["package"], expected_root="tests")
    compiled = CompiledLifecycleWorld(package_dir=package_dir, envelope=envelope)
    validated = validate_compiled_world(compiled)
    validate_harbor_lifecycle_semantics(validated.lifecycle)
    validate_adapter_surface(envelope)
    validate_source_identity(source=source, envelope=envelope)
    return _BridgeSource(
        envelope=envelope,
        package_dir=package_dir,
        compiled=validated,
    )


def _validate_bridge_contract(
    *,
    bridge: dict[str, Any],
    lifecycle: EvidenceLifecycleSpec,
) -> tuple[str, ...]:
    expected_tools = allowed_tools(lifecycle)
    if tuple(bridge["allowed_tools"]) != expected_tools:
        raise ValueError("Harbor lifecycle bridge tool allowlist does not match the lifecycle contract")
    if bridge["mode"] != HARBOR_LIFECYCLE_BRIDGE_MODE:
        raise ValueError("Harbor lifecycle bridge mode is not supported")
    if bridge["output_path"] != OUTPUT_PATH:
        raise ValueError("Harbor lifecycle bridge output path is not supported")
    if bridge["reward_owner"] != "harbor_verifier":
        raise ValueError("Harbor lifecycle bridge cannot own reward")
    if bridge["visibility_policy"] != "persistent_context":
        raise ValueError("Harbor lifecycle bridge visibility policy is not supported")
    return expected_tools


def _validate_bridge_agent_surface(
    *,
    resolved_environment: Path,
    task_root: Path,
    source: _BridgeSource,
    agent_surface: dict[str, Any],
) -> tuple[RegularFileSnapshot, RegularFileSnapshot]:
    initial_context = _task_relative_path(task_root, agent_surface["initial_context"], expected_root="environment")
    if directory_sha256(initial_context) != agent_surface["initial_context_sha256"]:
        raise ValueError("initial context does not match the export manifest")
    instruction = read_stable_regular_file(
        task_root / "instruction.md",
        label="task instruction",
        max_bytes=MAX_TASK_CONTROL_FILE_BYTES,
    )
    if instruction.sha256 != agent_surface["task_instruction_sha256"]:
        raise ValueError("task instruction does not match the export manifest")
    dockerfile = read_stable_regular_file(
        resolved_environment / "Dockerfile",
        label="agent environment",
        max_bytes=MAX_TASK_CONTROL_FILE_BYTES,
    )
    if dockerfile.sha256 != agent_surface["dockerfile_sha256"]:
        raise ValueError("agent environment does not match the export manifest")
    if agent_surface["base_image"] != BASE_IMAGE or tuple(agent_surface["dependencies"]) != RUNTIME_DEPENDENCIES:
        raise ValueError("agent environment identity is not supported")
    if (resolved_environment / "runtime").exists():
        raise ValueError("agent environment must not contain an AEC-Bench runtime")
    validate_canonical_agent_surface(
        package_dir=source.package_dir,
        initial_context=initial_context,
        instruction=instruction,
        dockerfile=dockerfile,
        template=source.compiled.template,
        lifecycle=source.compiled.lifecycle,
    )
    return instruction, dockerfile


def _validate_bridge_runtime(
    *,
    task_root: Path,
    verifier: dict[str, Any],
) -> RegularFileSnapshot:
    runtime_wheel = _task_relative_path(task_root, verifier["runtime_wheel"], expected_root="tests")
    snapshot = read_stable_regular_file(
        runtime_wheel,
        label="verifier runtime",
        max_bytes=MAX_RUNTIME_WHEEL_BYTES,
    )
    if snapshot.sha256 != verifier["runtime_wheel_sha256"]:
        raise ValueError("verifier runtime does not match the export manifest")
    validate_verifier_runtime_wheel(snapshot, verifier)
    return snapshot


def _validate_harbor_authority(
    *,
    task_root: Path,
    template: CompositeTaskWorldTemplate,
    envelope: CompiledWorldEnvelope,
    harbor: dict[str, Any],
    runtime_wheel: Path,
) -> tuple[RegularFileSnapshot, RegularFileSnapshot]:
    if harbor["output_path"] != OUTPUT_PATH or harbor["reward_owner"] != "harbor_verifier":
        raise ValueError("Harbor output and reward authority do not match the bridge contract")
    if harbor["security"] != HARBOR_SECURITY:
        raise ValueError("Harbor task security contract is not supported")
    if harbor["task_toml"] != "task.toml":
        raise ValueError("Harbor task metadata path is not canonical")
    task_toml = read_stable_regular_file(
        task_root / "task.toml",
        label="Harbor task metadata",
        max_bytes=MAX_TASK_CONTROL_FILE_BYTES,
    )
    if task_toml.sha256 != harbor["task_toml_sha256"]:
        raise ValueError("Harbor task metadata does not match the export manifest")
    try:
        task_text = snapshot_text(task_toml)
        tomllib.loads(task_text)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Harbor task metadata is invalid") from exc
    if task_text != task_toml_text(template=template, envelope=envelope):
        raise ValueError("Harbor task security contract does not match the canonical lifecycle export")

    if harbor["test_script"] != "tests/test.sh":
        raise ValueError("Harbor verifier script path is not canonical")
    test_script = read_stable_regular_file(
        _task_relative_path(task_root, harbor["test_script"], expected_root="tests"),
        label="Harbor verifier script",
        max_bytes=MAX_TASK_CONTROL_FILE_BYTES,
    )
    if test_script.sha256 != harbor["test_script_sha256"]:
        raise ValueError("Harbor verifier script does not match the export manifest")
    if snapshot_text(test_script) != test_script_text(runtime_wheel.name):
        raise ValueError("Harbor verifier script does not match the canonical lifecycle export")
    return task_toml, test_script


def allowed_tools(lifecycle: EvidenceLifecycleSpec) -> tuple[str, ...]:
    tools = set(BASE_TOOLS)
    if any(checkpoint.conditional_operations is not None for checkpoint in lifecycle.checkpoints):
        tools.add("execute_operation")
    return tuple(sorted(tools))


def _task_relative_path(task_root: Path, value: Any, *, expected_root: str) -> Path:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ValueError("export manifest contains an invalid task-relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != expected_root:
        raise ValueError("export manifest path escapes its declared task surface")
    try:
        resolved = (task_root / relative).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"export manifest path is missing: {value}") from exc
    expected = (task_root / expected_root).resolve(strict=True)
    if resolved != expected and expected not in resolved.parents:
        raise ValueError("export manifest path escapes its declared task surface")
    return resolved


def _read_json_object(path: Path) -> dict[str, Any]:
    snapshot = read_stable_regular_file(
        Path(path),
        label=f"JSON document {path}",
        max_bytes=sys.maxsize,
    )
    return snapshot_json_object(snapshot)


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _require_exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} fields do not match the export schema")
