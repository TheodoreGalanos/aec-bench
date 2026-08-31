# ABOUTME: Resolves lifecycle definitions by stable template identity and current source.
# ABOUTME: Loads the committed generated owner composition without concrete registration here.

from __future__ import annotations

import json
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.contracts.identity import EntityIdentity, MemberIdentity
from aec_bench.lifecycles.compiled import source_tree_artifact_sha256
from aec_bench.lifecycles.generated_catalogue import load_lifecycle_definitions
from aec_bench.lifecycles.runtime.definition import LifecycleDefinition
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.lifecycle import validate_lifecycle_verification
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver

_DEFINITIONS = {definition.metadata.template_id: definition for definition in load_lifecycle_definitions()}
_DEFINITIONS_BY_KEY = {str(definition.identity.key): definition for definition in _DEFINITIONS.values()}
_DEFINITIONS_BY_ID = {definition.identity.id: definition for definition in _DEFINITIONS.values()}


def _validate_definition_identities() -> None:
    identities = [
        identity
        for definition in _DEFINITIONS.values()
        for identity in (definition.identity, *definition.variant_identities)
    ]
    if len(identities) != len({identity.id for identity in identities}):
        raise ValueError("lifecycle catalogue entity UUIDs must be unique")
    if len(identities) != len({identity.key for identity in identities}):
        raise ValueError("lifecycle catalogue entity keys must be unique")


_validate_definition_identities()


def lifecycle_template_ids() -> set[str]:
    return set(_DEFINITIONS)


def lifecycle_definition(template_id: str) -> LifecycleDefinition:
    try:
        return _DEFINITIONS[template_id]
    except KeyError as exc:
        known = ", ".join(sorted(_DEFINITIONS))
        raise KeyError(f"No lifecycle task for {template_id!r}. Known: {known}") from exc


def lifecycle_definition_by_key(lifecycle_key: str) -> LifecycleDefinition:
    """Resolve the current lifecycle definition by its canonical readable key."""

    try:
        return _DEFINITIONS_BY_KEY[lifecycle_key]
    except KeyError as exc:
        known = ", ".join(sorted(_DEFINITIONS_BY_KEY))
        raise KeyError(f"unknown lifecycle key: {lifecycle_key}. Known: {known}") from exc


def lifecycle_definition_by_identity(identity: UUID | str, *, version: int) -> LifecycleDefinition:
    """Resolve one current lifecycle by UUID or canonical key and exact version."""

    if version <= 0:
        raise ValueError("lifecycle version must be positive")
    definition = _DEFINITIONS_BY_ID.get(identity) if isinstance(identity, UUID) else _DEFINITIONS_BY_KEY.get(identity)
    if definition is None or definition.identity.version != version:
        raise KeyError(f"unknown lifecycle identity and version: {identity} version {version}")
    return definition


def lifecycle_identity(template_id: str) -> EntityIdentity:
    """Return the stable identity for one registered lifecycle template."""

    return lifecycle_definition(template_id).identity


@cache
def lifecycle_executable_artifact_sha256(template_id: str) -> str:
    return source_tree_artifact_sha256(lifecycle_definition(template_id).executable_source_roots)


def lifecycle_variant_ids(template_id: str) -> tuple[str, ...]:
    definition = lifecycle_definition(template_id)
    variants = definition.variant_ids
    if variants is None:
        return ()
    registered = tuple(variants())
    expected = tuple(identity.registration_id for identity in definition.variant_identities)
    if tuple(sorted(registered)) != expected:
        raise ValueError("lifecycle variant identities are out of sync with registered variants")
    return registered


def lifecycle_variant_identity(template_id: str, variant_id: str) -> MemberIdentity:
    """Return the stable identity for one registered lifecycle variant."""

    definition = lifecycle_definition(template_id)
    for identity in definition.variant_identities:
        if identity.registration_id == variant_id:
            return identity
    raise KeyError(f"unknown lifecycle variant identity: {template_id}/{variant_id}")


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
    metadata_path = package / "template.json"
    if not metadata_path.is_file():
        return None
    metadata = LifecycleTaskMetadata.model_validate(_read_json(metadata_path))
    try:
        validator = lifecycle_definition(metadata.template_id).variant_validator
    except KeyError:
        return None
    return None if validator is None else validator(package)


def materialize_lifecycle(template_id: str, output_dir: Path, *, variant_id: str | None = None) -> Path:
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
    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    factory = lifecycle_definition(metadata.template_id).operation_resolver
    return None if factory is None else factory(package, Path(run_dir))


def verify_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    package = Path(package_dir)
    metadata = LifecycleTaskMetadata.model_validate(_read_json(package / "template.json"))
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
    definition = lifecycle_definition(metadata.template_id)
    if metadata != definition.metadata or lifecycle != definition.lifecycle:
        raise ValueError("materialized lifecycle contracts do not match the current task definition")
    return validate_lifecycle_verification(definition.verifier(package, Path(run_dir)))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload
