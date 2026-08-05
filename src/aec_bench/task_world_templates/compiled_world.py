# ABOUTME: Binds current lifecycle package bytes to task code and runtime protocol identity.
# ABOUTME: Keeps compiled identity separate from the agent-visible lifecycle package.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import field_validator

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import evidence_lifecycle_package_identity
from aec_bench.meta_harness.lifecycle_operation_protocol import lifecycle_operation_protocol_identity


class CompiledWorldEnvelope(StrictModel):
    visibility: Literal["public", "holdout"]
    template_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_id: NonEmptyStr
    variant_id: NonEmptyStr | None = None
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    executable_artifact_sha256: NonEmptyStr
    operation_protocol_sha256: NonEmptyStr | None = None

    @field_validator(
        "lifecycle_spec_sha256",
        "package_sha256",
        "executable_artifact_sha256",
        "operation_protocol_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else ArtifactReference.validate_sha256(value)


@dataclass(frozen=True, slots=True)
class CompiledLifecycleWorld:
    package_dir: Path
    envelope: CompiledWorldEnvelope


def compile_lifecycle(
    template_id: str,
    output_dir: Path,
    *,
    variant_id: str | None = None,
) -> CompiledLifecycleWorld:
    from aec_bench.task_world_templates.lifecycles import materialize_lifecycle

    package_dir = materialize_lifecycle(template_id, Path(output_dir), variant_id=variant_id)
    envelope = build_compiled_world_envelope(
        template_id=template_id,
        package_dir=package_dir,
        requested_variant_id=variant_id,
    )
    return CompiledLifecycleWorld(package_dir=package_dir, envelope=envelope)


def build_compiled_world_envelope(
    *,
    template_id: str,
    package_dir: Path,
    requested_variant_id: str | None,
    visibility: Literal["public", "holdout"] = "public",
) -> CompiledWorldEnvelope:
    from aec_bench.task_world_templates.lifecycles import (
        lifecycle_definition,
        lifecycle_executable_artifact_sha256,
        lifecycle_package_variant,
        lifecycle_variant_ids,
    )

    definition = lifecycle_definition(template_id)
    package = Path(package_dir)
    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
    if metadata != definition.metadata or lifecycle != definition.lifecycle:
        raise ValueError("materialized lifecycle contracts do not match the current task definition")

    variant_ids = lifecycle_variant_ids(template_id)
    if variant_ids != tuple(sorted(set(variant_ids))):
        raise ValueError("lifecycle variant ids must be sorted and unique")
    variant_metadata = lifecycle_package_variant(package)
    materialized_variant_id: str | None = None
    if variant_metadata is not None:
        raw_variant_id = variant_metadata.get("variant_id")
        if not isinstance(raw_variant_id, str) or not raw_variant_id.strip():
            raise ValueError("materialized lifecycle variant identity is invalid")
        materialized_variant_id = raw_variant_id
    if requested_variant_id is not None and materialized_variant_id != requested_variant_id:
        raise ValueError("materialized lifecycle variant does not match the requested variant")
    if variant_ids and materialized_variant_id is None:
        raise ValueError("materialized lifecycle package is missing variant identity")

    supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in lifecycle.checkpoints)
    if supports_operations != (definition.operation_resolver is not None):
        raise ValueError("task operation resolver differs from the lifecycle contract")
    protocol_sha256 = cast(str, lifecycle_operation_protocol_identity()["sha256"]) if supports_operations else None
    package_identity = evidence_lifecycle_package_identity(package)
    return CompiledWorldEnvelope(
        visibility=visibility,
        template_id=metadata.template_id,
        world_id=package_identity["world_id"],
        lifecycle_id=package_identity["lifecycle_id"],
        variant_id=materialized_variant_id,
        lifecycle_spec_sha256=package_identity["spec_sha256"],
        package_sha256=package_identity["package_sha256"],
        executable_artifact_sha256=lifecycle_executable_artifact_sha256(template_id),
        operation_protocol_sha256=protocol_sha256,
    )


def source_tree_artifact_sha256(paths: tuple[Path, ...]) -> str:
    """Hash a stable manifest of exact Python source-file bytes."""
    source_root = Path(__file__).resolve().parents[1]
    manifest: dict[str, str] = {}
    for selected in paths:
        path = Path(selected).resolve(strict=True)
        candidates = (path,) if path.is_file() else tuple(sorted(path.rglob("*.py")))
        for candidate in candidates:
            relative = candidate.relative_to(source_root).as_posix()
            manifest[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if not manifest:
        raise ValueError("lifecycle executable artifact requires source files")
    return _canonical_sha256(manifest)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload
