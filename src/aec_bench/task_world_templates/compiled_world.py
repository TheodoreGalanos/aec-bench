# ABOUTME: Defines canonical compiled-world identity and typed lifecycle runtime adapters.
# ABOUTME: Binds package bytes to task-owned materializer, resolver, verifier, and smoke entrypoints.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_lifecycle_package_identity,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeEnvironment
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationResolver,
    lifecycle_operation_protocol_identity,
)
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceLifecycleSpec


@dataclass(frozen=True, slots=True)
class LifecycleWorldAdapterIdentity:
    template_id: str
    entry_point: str
    artifact_sha256: str
    capabilities: tuple[Literal["operations", "variants"], ...] = ()

    def __post_init__(self) -> None:
        if not self.template_id.strip() or not self.entry_point.strip():
            raise ValueError("lifecycle adapter identity values must be non-empty")
        ArtifactReference.validate_sha256(self.artifact_sha256)


class CompiledWorldEnvelope(StrictModel):
    visibility: Literal["public", "holdout"]
    template_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_id: NonEmptyStr
    variant_id: NonEmptyStr | None = None
    variant_metadata_sha256: NonEmptyStr | None = None
    template_sha256: NonEmptyStr
    world_sha256: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    adapter: LifecycleWorldAdapterIdentity
    operation_protocol_sha256: NonEmptyStr | None = None

    @field_validator(
        "variant_metadata_sha256",
        "template_sha256",
        "world_sha256",
        "lifecycle_spec_sha256",
        "package_sha256",
        "operation_protocol_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_identity_alignment(self) -> CompiledWorldEnvelope:
        if (self.variant_id is None) != (self.variant_metadata_sha256 is None):
            raise ValueError("compiled variant id and metadata hash must be declared together")
        if self.adapter.template_id != self.template_id:
            raise ValueError("compiled adapter template identity does not match the envelope")
        return self


@dataclass(frozen=True)
class CompiledLifecycleWorld:
    package_dir: Path
    envelope: CompiledWorldEnvelope


@dataclass(frozen=True)
class VariantLifecycleFunctions:
    """Callables present only for lifecycle templates with named variants."""

    package_validator: Callable[[Path], dict[str, Any]]
    variant_ids: Callable[[], tuple[str, ...]]
    variant_metadata: Callable[[str], Any]


@dataclass(frozen=True)
class OperationLifecycleFunctions:
    """Callables present only for lifecycle templates with interactive operations."""

    resolver: Callable[[Path, Path], LifecycleOperationResolver]
    smoke_environment: Callable[[Path], LifecycleEpisodeEnvironment]


@dataclass(frozen=True)
class LifecycleWorldAdapter:
    """Concrete task-owned lifecycle composition with only supported capabilities."""

    template_id: str
    entry_point: str
    artifact_sha256: str
    materializer_entrypoint: Callable[..., Path]
    verifier_entrypoint: Callable[[Path, Path], dict[str, Any]]
    capabilities: tuple[VariantLifecycleFunctions | OperationLifecycleFunctions, ...] = ()

    def identity(self) -> LifecycleWorldAdapterIdentity:
        names = tuple(
            sorted(
                "variants" if isinstance(capability, VariantLifecycleFunctions) else "operations"
                for capability in self.capabilities
            )
        )
        return LifecycleWorldAdapterIdentity(
            template_id=self.template_id,
            entry_point=self.entry_point,
            artifact_sha256=self.artifact_sha256,
            capabilities=cast(tuple[Literal["operations", "variants"], ...], names),
        )

    def variant_ids(self) -> tuple[str, ...]:
        variants = self._capability(VariantLifecycleFunctions)
        return () if variants is None else tuple(variants.variant_ids())

    def variant_metadata(self, variant_id: str) -> dict[str, Any]:
        variants = self._capability(VariantLifecycleFunctions)
        if variants is None:
            raise KeyError(f"lifecycle template {self.template_id!r} does not declare variant metadata")
        return _mapping_payload(variants.variant_metadata(variant_id), label="variant metadata")

    def materialize(
        self,
        output_dir: Path,
        *,
        template: CompositeTaskWorldTemplate,
        variant_id: str | None,
    ) -> Path:
        if template.template_id != self.template_id:
            raise ValueError("lifecycle adapter template identity does not match the declarative template")
        variants = self._capability(VariantLifecycleFunctions)
        if variants is None:
            if variant_id is not None:
                raise ValueError(f"lifecycle template {self.template_id!r} does not support variants")
            return Path(self.materializer_entrypoint(Path(output_dir), template=template))
        if variant_id is not None and variant_id not in self.variant_ids():
            known = ", ".join(self.variant_ids())
            raise ValueError(f"unknown lifecycle variant for {self.template_id}: {variant_id}. Known: {known}")
        return Path(self.materializer_entrypoint(Path(output_dir), template=template, variant_id=variant_id))

    def validate_package(self, package_dir: Path) -> dict[str, Any] | None:
        variants = self._capability(VariantLifecycleFunctions)
        return (
            None
            if variants is None
            else _mapping_payload(variants.package_validator(Path(package_dir)), label="package variant metadata")
        )

    def build_operation_resolver(
        self,
        package_dir: Path,
        run_dir: Path,
    ) -> LifecycleOperationResolver | None:
        operations = self._capability(OperationLifecycleFunctions)
        return None if operations is None else operations.resolver(Path(package_dir), Path(run_dir))

    def verify(self, package_dir: Path, run_dir: Path) -> dict[str, Any]:
        return validate_lifecycle_verification(self.verifier_entrypoint(Path(package_dir), Path(run_dir)))

    def build_smoke_environment(self, package_dir: Path) -> LifecycleEpisodeEnvironment | None:
        operations = self._capability(OperationLifecycleFunctions)
        return None if operations is None else operations.smoke_environment(Path(package_dir))

    def _capability[CapabilityT: (VariantLifecycleFunctions, OperationLifecycleFunctions)](
        self,
        capability_type: type[CapabilityT],
    ) -> CapabilityT | None:
        matching = tuple(item for item in self.capabilities if isinstance(item, capability_type))
        if len(matching) > 1:
            raise ValueError(f"lifecycle adapter has repeated {capability_type.__name__}")
        return matching[0] if matching else None


def validate_lifecycle_world_adapter(
    template: CompositeTaskWorldTemplate,
    adapter: LifecycleWorldAdapter,
) -> None:
    """Require one task adapter to satisfy its exact declarative lifecycle contract."""
    template = CompositeTaskWorldTemplate.model_validate(template.model_dump(mode="json"))
    lifecycle = template.evidence_lifecycle
    if lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    if adapter.template_id != template.template_id or adapter.identity().template_id != template.template_id:
        raise ValueError("lifecycle adapter template identity does not match the declarative template")
    variant_ids = adapter.variant_ids()
    if variant_ids != tuple(sorted(set(variant_ids))):
        raise ValueError("lifecycle adapter variant ids must be sorted and unique")
    supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in lifecycle.checkpoints)
    identity = adapter.identity()
    if supports_operations != ("operations" in identity.capabilities):
        raise ValueError("lifecycle operation capability differs from the declarative lifecycle")


def build_compiled_world_envelope(
    *,
    template: CompositeTaskWorldTemplate,
    adapter: LifecycleWorldAdapter,
    package_dir: Path,
    requested_variant_id: str | None,
    visibility: Literal["public", "holdout"] = "public",
) -> CompiledWorldEnvelope:
    """Validate one materialized package and return identity without changing package bytes."""
    template = CompositeTaskWorldTemplate.model_validate(template.model_dump(mode="json"))
    validate_lifecycle_world_adapter(template, adapter)
    assert template.evidence_lifecycle is not None
    package = Path(package_dir)
    packaged_template = CompositeTaskWorldTemplate.model_validate(_read_json(package / "template.json"))
    if packaged_template != template:
        raise ValueError("materialized template contract does not match the compiled template")
    packaged_lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
    if packaged_lifecycle != template.evidence_lifecycle:
        raise ValueError("materialized lifecycle contract does not match the compiled template")

    variant_metadata = adapter.validate_package(package)
    materialized_variant_id: str | None = None
    variant_metadata_sha256: str | None = None
    if variant_metadata is not None:
        raw_variant_id = variant_metadata.get("variant_id")
        if not isinstance(raw_variant_id, str) or not raw_variant_id.strip():
            raise ValueError("materialized lifecycle variant identity is invalid")
        materialized_variant_id = raw_variant_id
        variant_metadata_sha256 = _canonical_sha256(variant_metadata)
    if requested_variant_id is not None and materialized_variant_id != requested_variant_id:
        raise ValueError("materialized lifecycle variant does not match the requested variant")
    if adapter.variant_ids() and materialized_variant_id is None:
        raise ValueError("materialized lifecycle package is missing registered variant identity")

    package_identity = evidence_lifecycle_package_identity(package)
    supports_operations = any(
        checkpoint.conditional_operations is not None for checkpoint in template.evidence_lifecycle.checkpoints
    )
    protocol_sha256 = cast(str, lifecycle_operation_protocol_identity()["sha256"]) if supports_operations else None
    return CompiledWorldEnvelope(
        visibility=visibility,
        template_id=template.template_id,
        world_id=package_identity["world_id"],
        lifecycle_id=package_identity["lifecycle_id"],
        variant_id=materialized_variant_id,
        variant_metadata_sha256=variant_metadata_sha256,
        template_sha256=_file_sha256(package / "template.json"),
        world_sha256=_file_sha256(package / "world.json"),
        lifecycle_spec_sha256=package_identity["spec_sha256"],
        package_sha256=package_identity["package_sha256"],
        adapter=adapter.identity(),
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


def _mapping_payload(value: Any, *, label: str) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping")
    return cast(dict[str, Any], value)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload
