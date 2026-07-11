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
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceLifecycleSpec


@dataclass(frozen=True)
class LifecycleTemplateRegistration:
    template_id: str
    module_name: str
    materializer_name: str
    verifier_name: str
    variant_module_name: str | None = None
    variant_ids_name: str | None = None
    variant_metadata_name: str | None = None


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
            variant_metadata_name="validated_ssc03_package_variant",
        )
    ]
}


def registered_lifecycle_template_ids() -> set[str]:
    """Return the template IDs with executable lifecycle registrations."""
    return set(_LIFECYCLES)


def lifecycle_variant_ids(template_id: str) -> tuple[str, ...]:
    """Return declared materialization variants without exposing hidden task answers."""
    registration = _entry(template_id)
    if registration.variant_ids_name is None:
        return ()
    module = import_module(registration.variant_module_name or registration.module_name)
    return tuple(getattr(module, registration.variant_ids_name)())


def lifecycle_package_variant(package_dir: Path) -> dict[str, Any] | None:
    """Validate and return task-owned variant metadata when a package declares it."""
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


def verify_lifecycle_template(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Validate package identity, then dispatch through the registered task verifier."""
    template_path = Path(package_dir) / "template.json"
    template = CompositeTaskWorldTemplate.model_validate(_read_json(template_path))
    if template.evidence_lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(Path(package_dir) / "lifecycle.json"))
    if lifecycle != template.evidence_lifecycle:
        raise ValueError("materialized lifecycle contract does not match template.json")
    registration = _entry(template.template_id)
    verifier = getattr(import_module(registration.module_name), registration.verifier_name)
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
