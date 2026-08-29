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
from aec_bench.lifecycles.runtime.lifecycle import evidence_lifecycle_package_identity
from aec_bench.lifecycles.runtime.operation_protocol import lifecycle_operation_protocol_identity


class CompiledLifecycleEnvelope(StrictModel):
    visibility: Literal["public", "holdout"]
    template_id: NonEmptyStr
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


@dataclass(frozen=True, slots=True, init=False)
class CompiledLifecycle:
    """A lifecycle package whose bytes have been validated against its envelope."""

    package_dir: Path
    envelope: CompiledLifecycleEnvelope

    def __init__(self) -> None:
        raise TypeError("use compile_lifecycle() or load_compiled_lifecycle()")


def compile_lifecycle(
    template_id: str,
    output_dir: Path,
    *,
    variant_id: str | None = None,
) -> CompiledLifecycle:
    from aec_bench.lifecycles.catalogue import materialize_lifecycle

    package_dir = materialize_lifecycle(template_id, Path(output_dir), variant_id=variant_id)
    compiled = load_compiled_lifecycle(package_dir)
    if compiled.envelope.template_id != template_id or (
        variant_id is not None and compiled.envelope.variant_id != variant_id
    ):
        raise ValueError("compiled lifecycle does not match the requested template and variant")
    return compiled


def load_compiled_lifecycle(package_dir: Path) -> CompiledLifecycle:
    """Validate an existing materialized package and bind its compiled identity."""
    from aec_bench.lifecycles.catalogue import lifecycle_package_variant

    package = Path(package_dir)
    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    variant = lifecycle_package_variant(package)
    variant_id: str | None = None
    visibility: Literal["public", "holdout"] = "public"
    if variant is not None:
        raw_variant_id = variant.get("variant_id")
        if not isinstance(raw_variant_id, str) or not raw_variant_id.strip():
            raise ValueError("materialized lifecycle variant identity is invalid")
        variant_id = raw_variant_id
        raw_visibility = variant.get("visibility")
        if raw_visibility not in {"public", "holdout"}:
            raise ValueError("materialized lifecycle visibility is invalid")
        visibility = cast(Literal["public", "holdout"], raw_visibility)
    envelope = build_compiled_lifecycle_envelope(
        template_id=metadata.template_id,
        package_dir=package,
        requested_variant_id=variant_id,
        visibility=visibility,
    )
    return _bind_compiled_lifecycle(package, envelope)


def _bind_compiled_lifecycle(package_dir: Path, envelope: CompiledLifecycleEnvelope) -> CompiledLifecycle:
    compiled = object.__new__(CompiledLifecycle)
    object.__setattr__(compiled, "package_dir", Path(package_dir))
    object.__setattr__(compiled, "envelope", envelope)
    return compiled


def build_compiled_lifecycle_envelope(
    *,
    template_id: str,
    package_dir: Path,
    requested_variant_id: str | None,
    visibility: Literal["public", "holdout"] = "public",
) -> CompiledLifecycleEnvelope:
    from aec_bench.lifecycles.catalogue import (
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
    return CompiledLifecycleEnvelope(
        visibility=visibility,
        template_id=metadata.template_id,
        lifecycle_id=package_identity["lifecycle_id"],
        variant_id=materialized_variant_id,
        lifecycle_spec_sha256=package_identity["spec_sha256"],
        package_sha256=package_identity["package_sha256"],
        executable_artifact_sha256=lifecycle_executable_artifact_sha256(template_id),
        operation_protocol_sha256=protocol_sha256,
    )


def source_tree_artifact_sha256(paths: tuple[Path, ...]) -> str:
    """Hash a stable manifest of exact task and runtime source bytes."""
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
