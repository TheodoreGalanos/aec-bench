# ABOUTME: Registry namespace for runnable evidence-lifecycle companion packages.
# ABOUTME: Keeps task-specific packet builders separate from the generic lifecycle runtime.

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle import validate_lifecycle_verification
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceLifecycleSpec


@dataclass(frozen=True)
class LifecycleTemplateRegistration:
    template_id: str
    module_name: str
    materializer_name: str
    verifier_name: str


_LIFECYCLES = {
    registration.template_id: registration
    for registration in [
        LifecycleTemplateRegistration(
            template_id="drainage-model-evidence-lifecycle-review",
            module_name="aec_bench.task_world_templates.lifecycles.ssc03_drainage_model",
            materializer_name="materialize_ssc03_evidence_lifecycle",
            verifier_name="verify_ssc03_evidence_lifecycle",
        )
    ]
}


def registered_lifecycle_template_ids() -> set[str]:
    """Return the template IDs with executable lifecycle registrations."""
    return set(_LIFECYCLES)


def materialize_lifecycle_template(
    template: CompositeTaskWorldTemplate,
    output_dir: Path,
) -> Path:
    """Dispatch lifecycle materialisation from the exact validated template contract."""
    if template.evidence_lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    registration = _entry(template.template_id)
    materializer = getattr(import_module(registration.module_name), registration.materializer_name)
    return materializer(Path(output_dir), template=template)


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
