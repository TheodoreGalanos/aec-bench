# ABOUTME: Direct composition for the three current evidence-lifecycle tasks.
# ABOUTME: Resolves task-owned callables without string entrypoints or capability adapters.

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.meta_harness.evidence_lifecycle import validate_lifecycle_verification
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeEnvironment
from aec_bench.meta_harness.lifecycle_operation_protocol import LifecycleOperationResolver
from aec_bench.task_world_templates.compiled_world import source_tree_artifact_sha256
from aec_bench.task_world_templates.lifecycles import (
    ssc03_drainage_model,
    ssc03_drainage_variants,
    ssc03_hydraulic_interaction,
    ssc03_hydraulic_interaction_smoke,
    ssc03_hydraulic_interaction_variants,
    ssc03_hydraulic_intervention,
    ssc03_hydraulic_intervention_smoke,
)
from aec_bench.task_world_templates.lifecycles.provider import (
    SealedLifecycleMount,
    SealedLifecycleProvider,
    SealedLifecycleProviderError,
    _bind_sealed_lifecycle,
    _materialize_sealed_lifecycle,
    active_sealed_lifecycle_mount,
    is_sealed_lifecycle_package,
)


@dataclass(frozen=True, slots=True)
class _LifecycleDefinition:
    metadata: LifecycleTaskMetadata
    lifecycle: EvidenceLifecycleSpec
    materializer: Callable[..., Path]
    verifier: Callable[[Path, Path], dict[str, Any]]
    source_paths: tuple[Path, ...]
    package_validator: Callable[[Path], dict[str, Any]] | None = None
    variant_ids: Callable[[], tuple[str, ...]] | None = None
    variant_metadata: Callable[[str], Any] | None = None
    operation_resolver: Callable[[Path, Path], LifecycleOperationResolver] | None = None
    smoke_environment: Callable[[Path], LifecycleEpisodeEnvironment] | None = None


_DEFINITIONS = {
    definition.metadata.template_id: definition
    for definition in (
        _LifecycleDefinition(
            metadata=ssc03_drainage_model.METADATA,
            lifecycle=ssc03_drainage_model.LIFECYCLE,
            materializer=ssc03_drainage_model.materialize_ssc03_evidence_lifecycle,
            verifier=ssc03_drainage_model.verify_ssc03_evidence_lifecycle,
            source_paths=(
                Path(ssc03_drainage_model.__file__),
                Path(ssc03_drainage_variants.__file__),
            ),
            package_validator=ssc03_drainage_model.validated_ssc03_package_variant,
            variant_ids=ssc03_drainage_variants.list_ssc03_lifecycle_variant_ids,
            variant_metadata=ssc03_drainage_variants.get_ssc03_lifecycle_variant,
        ),
        _LifecycleDefinition(
            metadata=ssc03_hydraulic_interaction.METADATA,
            lifecycle=ssc03_hydraulic_interaction.LIFECYCLE,
            materializer=ssc03_hydraulic_interaction.materialize_ssc03_hydraulic_interaction_lifecycle,
            verifier=ssc03_hydraulic_interaction.verify_ssc03_hydraulic_interaction_lifecycle,
            source_paths=(
                Path(ssc03_hydraulic_interaction.__file__),
                Path(ssc03_hydraulic_interaction_variants.__file__),
                Path(ssc03_hydraulic_interaction_smoke.__file__),
            ),
            package_validator=ssc03_hydraulic_interaction.validated_ssc03_hydraulic_interaction_variant,
            variant_ids=ssc03_hydraulic_interaction_variants.list_ssc03_hydraulic_interaction_variant_ids,
            variant_metadata=ssc03_hydraulic_interaction_variants.get_ssc03_hydraulic_interaction_variant,
            operation_resolver=ssc03_hydraulic_interaction.build_ssc03_hydraulic_operation_resolver,
            smoke_environment=ssc03_hydraulic_interaction_smoke.build_ssc03_hydraulic_smoke_environment,
        ),
        _LifecycleDefinition(
            metadata=ssc03_hydraulic_intervention.METADATA,
            lifecycle=ssc03_hydraulic_intervention.LIFECYCLE,
            materializer=ssc03_hydraulic_intervention.materialize_ssc03_hydraulic_intervention_lifecycle,
            verifier=ssc03_hydraulic_intervention.verify_ssc03_hydraulic_intervention_lifecycle,
            source_paths=(
                Path(ssc03_hydraulic_intervention.__file__),
                Path(ssc03_hydraulic_intervention_smoke.__file__),
            ),
            operation_resolver=ssc03_hydraulic_intervention.build_ssc03_hydraulic_intervention_resolver,
            smoke_environment=ssc03_hydraulic_intervention_smoke.build_ssc03_hydraulic_intervention_smoke_environment,
        ),
    )
}


def lifecycle_template_ids() -> set[str]:
    return set(_DEFINITIONS)


def lifecycle_definition(template_id: str) -> _LifecycleDefinition:
    try:
        return _DEFINITIONS[template_id]
    except KeyError as exc:
        known = ", ".join(sorted(_DEFINITIONS))
        raise KeyError(f"No lifecycle task for {template_id!r}. Known: {known}") from exc


@cache
def lifecycle_executable_artifact_sha256(template_id: str) -> str:
    return source_tree_artifact_sha256(lifecycle_definition(template_id).source_paths)


def lifecycle_variant_ids(template_id: str) -> tuple[str, ...]:
    variants = lifecycle_definition(template_id).variant_ids
    return () if variants is None else tuple(variants())


def lifecycle_variant_metadata(template_id: str, variant_id: str) -> dict[str, Any]:
    resolver = lifecycle_definition(template_id).variant_metadata
    if resolver is None:
        raise KeyError(f"lifecycle task {template_id!r} does not declare variant metadata")
    value = resolver(variant_id)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        raise TypeError("lifecycle variant metadata must be a mapping")
    return value


def lifecycle_verifier(template_id: str) -> Callable[[Path, Path], dict[str, Any]]:
    return lifecycle_definition(template_id).verifier


def lifecycle_smoke_environment(template_id: str, package_dir: Path) -> LifecycleEpisodeEnvironment | None:
    factory = lifecycle_definition(template_id).smoke_environment
    return None if factory is None else factory(Path(package_dir))


def lifecycle_package_variant(package_dir: Path) -> dict[str, Any] | None:
    package = Path(package_dir)
    if is_sealed_lifecycle_package(package):
        return None
    metadata_path = package / "template.json"
    if not metadata_path.is_file():
        return None
    metadata = LifecycleTaskMetadata.model_validate(_read_json(metadata_path))
    try:
        validator = lifecycle_definition(metadata.template_id).package_validator
    except KeyError:
        return None
    return None if validator is None else validator(package)


def materialize_lifecycle(
    template_id: str,
    output_dir: Path,
    *,
    variant_id: str | None = None,
) -> Path:
    definition = lifecycle_definition(template_id)
    variants = lifecycle_variant_ids(template_id)
    if definition.variant_ids is None:
        if variant_id is not None:
            raise ValueError(f"lifecycle task {template_id!r} does not support variants")
        return Path(definition.materializer(Path(output_dir)))
    if variant_id is not None and variant_id not in variants:
        known = ", ".join(variants)
        raise ValueError(f"unknown lifecycle variant for {template_id}: {variant_id}. Known: {known}")
    return Path(definition.materializer(Path(output_dir), variant_id=variant_id))


def lifecycle_operation_resolver(package_dir: Path, run_dir: Path) -> LifecycleOperationResolver | None:
    package = Path(package_dir)
    if is_sealed_lifecycle_package(package):
        return active_sealed_lifecycle_mount(package).build_operation_resolver(Path(run_dir))
    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    factory = lifecycle_definition(metadata.template_id).operation_resolver
    return None if factory is None else factory(package, Path(run_dir))


def verify_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    package = Path(package_dir)
    if is_sealed_lifecycle_package(package):
        result = active_sealed_lifecycle_mount(package).verify(Path(run_dir))
        validated: dict[str, Any] | None = None
        valid = False
        try:
            validated = validate_lifecycle_verification(result)
            metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
            lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
            if validated["lifecycle_id"] != lifecycle.lifecycle_id or validated.get("template_id") not in {
                None,
                metadata.template_id,
            }:
                raise ValueError("sealed verifier identity mismatch")
            valid = True
        except Exception:
            pass
        if not valid or validated is None:
            raise SealedLifecycleProviderError("sealed_provider_verifier_result_invalid")
        return validated

    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
    definition = lifecycle_definition(metadata.template_id)
    if metadata != definition.metadata or lifecycle != definition.lifecycle:
        raise ValueError("materialized lifecycle contracts do not match the current task definition")
    return validate_lifecycle_verification(definition.verifier(package, Path(run_dir)))


def materialize_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    output_dir: Path,
) -> SealedLifecycleMount:
    return _materialize_sealed_lifecycle(provider, output_dir, public_template_ids=frozenset(_DEFINITIONS))


def bind_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    package_dir: Path,
) -> SealedLifecycleMount:
    return _bind_sealed_lifecycle(provider, package_dir, public_template_ids=frozenset(_DEFINITIONS))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload
