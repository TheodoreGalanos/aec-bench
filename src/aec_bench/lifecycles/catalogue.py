# ABOUTME: Direct composition for the current evidence-lifecycle tasks.
# ABOUTME: Resolves task-owned callables without string entrypoints or capability adapters.

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.lifecycles.compiled import source_tree_artifact_sha256
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.lifecycle import validate_lifecycle_verification
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design import (
    design_response,
    design_response_smoke,
    drainage_model,
    drainage_variants,
    hydraulic_review,
    hydraulic_review_smoke,
    hydraulic_review_variants,
)
from aec_bench.lifecycles.structural_review import facade_submittal


@dataclass(frozen=True, slots=True)
class _LifecycleDefinition:
    metadata: LifecycleTaskMetadata
    lifecycle: EvidenceLifecycleSpec
    materializer: Callable[..., Path]
    verifier: Callable[[Path, Path], dict[str, Any]]
    executable_source_roots: tuple[Path, ...]
    variant_validator: Callable[[Path], dict[str, Any]] | None = None
    variant_ids: Callable[[], tuple[str, ...]] | None = None
    variant_metadata: Callable[[str], Any] | None = None
    operation_resolver: Callable[[Path, Path], LifecycleOperationResolver] | None = None
    smoke_environment: Callable[[Path], LifecycleEpisodeEnvironment] | None = None


_AEC_BENCH_ROOT = Path(__file__).resolve().parents[1]
_STORMWATER_ROOT = Path(drainage_model.__file__).resolve().parent
_STRUCTURAL_REVIEW_ROOT = Path(facade_submittal.__file__).resolve().parent
_FACADE_TEMPLATE_ROOT = (
    _AEC_BENCH_ROOT / "templates" / "builtin" / "structural" / "facade_submittal_source_policy_package"
)
_SHARED_EXECUTABLE_SOURCE_ROOTS = (
    Path(__file__).resolve(),
    _AEC_BENCH_ROOT / "contracts" / "evidence_lifecycle.py",
    _AEC_BENCH_ROOT / "contracts" / "lifecycle_evaluation.py",
    _AEC_BENCH_ROOT / "contracts" / "trial_record.py",
    _AEC_BENCH_ROOT / "contracts" / "validators.py",
    _AEC_BENCH_ROOT / "evaluation" / "lifecycle.py",
    _AEC_BENCH_ROOT / "ledger" / "durability.py",
    _AEC_BENCH_ROOT / "ledger" / "immutable_byte_store.py",
    _AEC_BENCH_ROOT / "ledger" / "local_lock.py",
    _AEC_BENCH_ROOT / "ledger" / "process_log.py",
    _AEC_BENCH_ROOT / "lifecycles" / "__init__.py",
    _AEC_BENCH_ROOT / "lifecycles" / "runtime",
)


_DEFINITIONS = {
    definition.metadata.template_id: definition
    for definition in (
        _LifecycleDefinition(
            metadata=facade_submittal.METADATA,
            lifecycle=facade_submittal.LIFECYCLE,
            materializer=facade_submittal.materialize_facade_submittal_lifecycle,
            verifier=facade_submittal.verify_facade_submittal_lifecycle,
            executable_source_roots=(
                *_SHARED_EXECUTABLE_SOURCE_ROOTS,
                _STRUCTURAL_REVIEW_ROOT / "__init__.py",
                Path(facade_submittal.__file__),
                _FACADE_TEMPLATE_ROOT / "engine.py",
                _FACADE_TEMPLATE_ROOT / "params.toml",
            ),
        ),
        _LifecycleDefinition(
            metadata=drainage_model.METADATA,
            lifecycle=drainage_model.LIFECYCLE,
            materializer=drainage_model.materialize_drainage_model_lifecycle,
            verifier=drainage_model.verify_drainage_model_lifecycle,
            executable_source_roots=(
                *_SHARED_EXECUTABLE_SOURCE_ROOTS,
                _STORMWATER_ROOT / "__init__.py",
                Path(drainage_model.__file__),
                Path(drainage_variants.__file__),
            ),
            variant_validator=drainage_model.validated_drainage_model_variant,
            variant_ids=drainage_variants.list_drainage_model_variant_ids,
            variant_metadata=drainage_variants.get_drainage_model_variant,
        ),
        _LifecycleDefinition(
            metadata=hydraulic_review.METADATA,
            lifecycle=hydraulic_review.LIFECYCLE,
            materializer=hydraulic_review.materialize_hydraulic_review_lifecycle,
            verifier=hydraulic_review.verify_hydraulic_review_lifecycle,
            executable_source_roots=(
                *_SHARED_EXECUTABLE_SOURCE_ROOTS,
                _STORMWATER_ROOT / "__init__.py",
                Path(hydraulic_review.__file__),
                Path(hydraulic_review_variants.__file__),
                _STORMWATER_ROOT / "hydraulic_evidence.py",
                _STORMWATER_ROOT / "hydraulic_operations.py",
                _STORMWATER_ROOT / "hydraulic_review_verifier.py",
                _STORMWATER_ROOT / "hydraulics",
            ),
            variant_validator=hydraulic_review.validated_hydraulic_review_variant,
            variant_ids=hydraulic_review_variants.list_hydraulic_review_variant_ids,
            variant_metadata=hydraulic_review_variants.get_hydraulic_review_variant,
            operation_resolver=hydraulic_review.build_hydraulic_operation_resolver,
            smoke_environment=hydraulic_review_smoke.build_hydraulic_review_smoke_environment,
        ),
        _LifecycleDefinition(
            metadata=design_response.METADATA,
            lifecycle=design_response.LIFECYCLE,
            materializer=design_response.materialize_hydraulic_design_response_lifecycle,
            verifier=design_response.verify_hydraulic_design_response_lifecycle,
            executable_source_roots=(
                *_SHARED_EXECUTABLE_SOURCE_ROOTS,
                _STORMWATER_ROOT / "__init__.py",
                Path(design_response.__file__),
                _STORMWATER_ROOT / "design_response_operations.py",
                _STORMWATER_ROOT / "design_response_verifier.py",
                _STORMWATER_ROOT / "hydraulic_evidence.py",
                _STORMWATER_ROOT / "hydraulic_operations.py",
                _STORMWATER_ROOT / "hydraulics",
            ),
            operation_resolver=design_response.build_hydraulic_design_response_resolver,
            smoke_environment=design_response_smoke.build_hydraulic_design_response_smoke_environment,
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
    return source_tree_artifact_sha256(lifecycle_definition(template_id).executable_source_roots)


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
    metadata_path = package / "template.json"
    if not metadata_path.is_file():
        return None
    metadata = LifecycleTaskMetadata.model_validate(_read_json(metadata_path))
    try:
        validator = lifecycle_definition(metadata.template_id).variant_validator
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
