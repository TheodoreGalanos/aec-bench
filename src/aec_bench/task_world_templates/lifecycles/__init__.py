# ABOUTME: Registry namespace for runnable evidence-lifecycle companion packages.
# ABOUTME: Keeps task-specific packet builders separate from the generic lifecycle runtime.

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from aec_bench.meta_harness.evidence_lifecycle import validate_lifecycle_verification
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleEpisodeEnvironment
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceLifecycleSpec
from aec_bench.task_world_templates.lifecycles.provider import (
    SEALED_LIFECYCLE_RECEIPT_FILENAME,
    SealedLifecycleMount,
    SealedLifecycleProvider,
    SealedLifecycleProviderError,
    _bind_sealed_lifecycle,
    _materialize_sealed_lifecycle,
    active_sealed_lifecycle_mount,
    is_sealed_lifecycle_package,
    sealed_lifecycle_mount_active,
    sealed_lifecycle_provider_protocol_identity,
)

__all__ = [
    "SEALED_LIFECYCLE_RECEIPT_FILENAME",
    "LifecycleTemplateRegistration",
    "SealedLifecycleMount",
    "SealedLifecycleProvider",
    "SealedLifecycleProviderError",
    "bind_sealed_lifecycle",
    "is_sealed_lifecycle_package",
    "lifecycle_operation_resolver",
    "lifecycle_package_variant",
    "lifecycle_variant_ids",
    "lifecycle_variant_metadata",
    "materialize_lifecycle_template",
    "materialize_sealed_lifecycle",
    "registered_lifecycle_operation_resolver",
    "registered_lifecycle_smoke_environment",
    "registered_lifecycle_template_ids",
    "registered_lifecycle_verifier",
    "sealed_lifecycle_mount_active",
    "sealed_lifecycle_provider_protocol_identity",
    "verify_lifecycle_template",
]


@dataclass(frozen=True)
class LifecycleTemplateRegistration:
    template_id: str
    module_name: str
    materializer_name: str
    verifier_name: str
    variant_module_name: str | None = None
    variant_ids_name: str | None = None
    variant_get_name: str | None = None
    variant_metadata_name: str | None = None
    operation_resolver_name: str | None = None
    smoke_module_name: str | None = None
    smoke_environment_name: str | None = None


_LIFECYCLES = {
    registration.template_id: registration
    for registration in [
        LifecycleTemplateRegistration(
            template_id="drainage-model-evidence-lifecycle-review",
            module_name="aec_bench.task_world_templates.lifecycles.ssc03_drainage_model",
            materializer_name="materialize_ssc03_evidence_lifecycle",
            verifier_name="verify_ssc03_evidence_lifecycle",
            variant_module_name="aec_bench.task_world_templates.lifecycles.ssc03_drainage_variants",
            variant_ids_name="list_ssc03_lifecycle_variant_ids",
            variant_get_name="get_ssc03_lifecycle_variant",
            variant_metadata_name="validated_ssc03_package_variant",
        ),
        LifecycleTemplateRegistration(
            template_id="hydraulic-interaction-lifecycle-review",
            module_name="aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction",
            materializer_name="materialize_ssc03_hydraulic_interaction_lifecycle",
            verifier_name="verify_ssc03_hydraulic_interaction_lifecycle",
            variant_module_name=("aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_variants"),
            variant_ids_name="list_ssc03_hydraulic_interaction_variant_ids",
            variant_get_name="get_ssc03_hydraulic_interaction_variant",
            variant_metadata_name="validated_ssc03_hydraulic_interaction_variant",
            operation_resolver_name="build_ssc03_hydraulic_operation_resolver",
            smoke_module_name=("aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_smoke"),
            smoke_environment_name="build_ssc03_hydraulic_smoke_environment",
        ),
    ]
}


def registered_lifecycle_template_ids() -> set[str]:
    """Return the template IDs with executable lifecycle registrations."""
    return set(_LIFECYCLES)


def materialize_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    output_dir: Path,
) -> SealedLifecycleMount:
    """Materialize one external holdout without adding it to any public registry."""
    return _materialize_sealed_lifecycle(
        provider,
        output_dir,
        public_template_ids=frozenset(_LIFECYCLES),
    )


def bind_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    package_dir: Path,
) -> SealedLifecycleMount:
    """Rebind one existing sealed package for an explicit recovery call context."""
    return _bind_sealed_lifecycle(
        provider,
        package_dir,
        public_template_ids=frozenset(_LIFECYCLES),
    )


def lifecycle_variant_ids(template_id: str) -> tuple[str, ...]:
    """Return declared materialization variants without exposing hidden task answers."""
    registration = _entry(template_id)
    if registration.variant_ids_name is None:
        return ()
    module = import_module(registration.variant_module_name or registration.module_name)
    return tuple(getattr(module, registration.variant_ids_name)())


def lifecycle_variant_metadata(template_id: str, variant_id: str) -> dict[str, Any]:
    """Return validated host-side metadata for one registered public variant."""
    registration = _entry(template_id)
    if registration.variant_get_name is None:
        raise KeyError(f"lifecycle template {template_id!r} does not declare variant metadata")
    module = import_module(registration.variant_module_name or registration.module_name)
    variant = getattr(module, registration.variant_get_name)(variant_id)
    return cast(dict[str, Any], variant.model_dump(mode="json"))


def registered_lifecycle_verifier(template_id: str) -> Callable[[Path, Path], dict[str, Any]]:
    """Resolve the task-specific verifier that performs lifecycle scoring."""
    registration = _entry(template_id)
    return cast(
        Callable[[Path, Path], dict[str, Any]],
        getattr(import_module(registration.module_name), registration.verifier_name),
    )


def registered_lifecycle_operation_resolver(template_id: str) -> Callable[[Path, Path], Any] | None:
    """Resolve an optional task-owned lifecycle operation resolver factory."""
    registration = _entry(template_id)
    if registration.operation_resolver_name is None:
        return None
    return cast(
        Callable[[Path, Path], Any],
        getattr(import_module(registration.module_name), registration.operation_resolver_name),
    )


def registered_lifecycle_smoke_environment(
    template_id: str,
    package_dir: Path,
) -> LifecycleEpisodeEnvironment | None:
    """Build an optional task-owned deterministic environment for campaign preflight."""
    registration = _entry(template_id)
    if registration.smoke_environment_name is None:
        return None
    module = import_module(registration.smoke_module_name or registration.module_name)
    factory = cast(
        Callable[[Path], LifecycleEpisodeEnvironment],
        getattr(module, registration.smoke_environment_name),
    )
    return factory(Path(package_dir))


def lifecycle_package_variant(package_dir: Path) -> dict[str, Any] | None:
    """Validate and return task-owned variant metadata when a package declares it."""
    if is_sealed_lifecycle_package(package_dir):
        return None
    template_path = Path(package_dir) / "template.json"
    if not template_path.is_file():
        return None
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("template_id"), str):
        raise ValueError(f"invalid lifecycle package template identity: {template_path}")
    try:
        registration = _entry(payload["template_id"])
    except KeyError:
        return None
    if registration.variant_metadata_name is None:
        return None
    validator = getattr(import_module(registration.module_name), registration.variant_metadata_name)
    return cast(dict[str, Any], validator(Path(package_dir)))


def materialize_lifecycle_template(
    template: CompositeTaskWorldTemplate,
    output_dir: Path,
    *,
    variant_id: str | None = None,
) -> Path:
    """Dispatch lifecycle materialisation from the exact validated template contract."""
    if template.evidence_lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    registration = _entry(template.template_id)
    materializer = cast(
        Callable[..., Path], getattr(import_module(registration.module_name), registration.materializer_name)
    )
    if registration.variant_ids_name is None:
        if variant_id is not None:
            raise ValueError(f"lifecycle template {template.template_id!r} does not support variants")
        return materializer(Path(output_dir), template=template)
    return materializer(Path(output_dir), template=template, variant_id=variant_id)


def lifecycle_operation_resolver(package_dir: Path, run_dir: Path) -> Any | None:
    """Resolve operations from an exact sealed mount or the public registry."""
    package = Path(package_dir)
    if is_sealed_lifecycle_package(package):
        return active_sealed_lifecycle_mount(package).build_operation_resolver(Path(run_dir))
    template = _read_json(package / "template.json")
    template_id = template.get("template_id")
    if not isinstance(template_id, str):
        raise ValueError("lifecycle package template identity is invalid")
    factory = registered_lifecycle_operation_resolver(template_id)
    return None if factory is None else factory(package, Path(run_dir))


def verify_lifecycle_template(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Validate package identity, then dispatch through the registered task verifier."""
    if is_sealed_lifecycle_package(package_dir):
        result = active_sealed_lifecycle_mount(package_dir).verify(Path(run_dir))
        invalid_result = False
        validated: dict[str, Any] | None = None
        try:
            validated = validate_lifecycle_verification(result)
            template_payload = _read_json(Path(package_dir) / "template.json")
            lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(Path(package_dir) / "lifecycle.json"))
            if validated["lifecycle_id"] != lifecycle.lifecycle_id or validated.get("template_id") not in {
                None,
                template_payload.get("template_id"),
            }:
                raise ValueError("sealed verifier identity mismatch")
        except Exception:
            invalid_result = True
        if invalid_result or validated is None:
            raise SealedLifecycleProviderError("sealed_provider_verifier_result_invalid")
        return validated
    template_path = Path(package_dir) / "template.json"
    template = CompositeTaskWorldTemplate.model_validate(_read_json(template_path))
    if template.evidence_lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(Path(package_dir) / "lifecycle.json"))
    if lifecycle != template.evidence_lifecycle:
        raise ValueError("materialized lifecycle contract does not match template.json")
    verifier = registered_lifecycle_verifier(template.template_id)
    return validate_lifecycle_verification(verifier(Path(package_dir), Path(run_dir)))


def _entry(template_id: str) -> LifecycleTemplateRegistration:
    try:
        return _LIFECYCLES[template_id]
    except KeyError as exc:
        known = ", ".join(sorted(_LIFECYCLES))
        raise KeyError(f"No lifecycle package builder for {template_id!r}. Known: {known}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload
