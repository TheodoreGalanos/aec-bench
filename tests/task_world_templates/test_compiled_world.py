# ABOUTME: Tests current compiled-world identity, deterministic materialization, and typed lifecycle wiring.
# ABOUTME: Exercises real package verification without freezing an obsolete serialized implementation.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.compiled_world import (
    CompiledWorldEnvelope,
    LifecycleWorldAdapter,
    validate_lifecycle_world_adapter,
)
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_adapter
from aec_bench.task_world_templates.materializer import compile_template_lifecycle

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
VARIANT_IDS = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)


def _package_stats(package_dir: Path) -> tuple[int, int]:
    files = [path for path in package_dir.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def test_ssc03_registration_resolves_concrete_adapter_with_exact_capabilities() -> None:
    template = get_template(TEMPLATE_ID)

    adapter = registered_lifecycle_adapter(TEMPLATE_ID)

    assert type(adapter) is LifecycleWorldAdapter
    validate_lifecycle_world_adapter(template, adapter)
    assert adapter.template_id == TEMPLATE_ID
    assert adapter.variant_ids() == VARIANT_IDS
    identity = adapter.identity()
    assert identity.template_id == TEMPLATE_ID
    assert identity.entry_point.endswith(":materialize_ssc03_hydraulic_interaction_lifecycle")
    assert len(identity.artifact_sha256) == 64
    assert identity.capabilities == ("operations", "variants")


def test_lifecycle_adapters_expose_only_their_real_capabilities() -> None:
    drainage = registered_lifecycle_adapter("drainage-model-evidence-lifecycle-review")
    hydraulic = registered_lifecycle_adapter(TEMPLATE_ID)

    assert drainage.identity().capabilities == ("variants",)
    assert drainage.build_operation_resolver(Path("unused"), Path("unused")) is None
    assert hydraulic.identity().capabilities == ("operations", "variants")


def test_adapter_rejects_mismatched_declarative_template() -> None:
    adapter = registered_lifecycle_adapter(TEMPLATE_ID)
    other_template = get_template("drainage-model-evidence-lifecycle-review")

    with pytest.raises(ValueError, match="template identity"):
        validate_lifecycle_world_adapter(other_template, adapter)


@pytest.mark.parametrize(
    "variant_id",
    VARIANT_IDS,
)
def test_compiled_ssc03_package_uses_current_registered_identity(tmp_path: Path, variant_id: str) -> None:
    compiled = compile_template_lifecycle(
        get_template(TEMPLATE_ID),
        tmp_path / variant_id,
        variant_id=variant_id,
    )

    assert compiled.envelope.template_id == TEMPLATE_ID
    assert compiled.envelope.world_id == "aec.task_world.composite.hydraulic-interaction-lifecycle-review"
    assert compiled.envelope.lifecycle_id == "ssc03.hydraulic-interaction-lifecycle"
    assert compiled.envelope.variant_id == variant_id
    assert len(compiled.envelope.lifecycle_spec_sha256) == 64
    assert len(compiled.envelope.package_sha256) == 64
    assert _package_stats(compiled.package_dir)[0] > 0
    assert not (compiled.package_dir / "compiled-world.json").exists()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompiledWorldEnvelope.model_validate(compiled.envelope.model_dump(mode="json") | {"unexpected": True})


def test_compiled_ssc03_package_is_deterministic(tmp_path: Path) -> None:
    template = get_template(TEMPLATE_ID)
    first = compile_template_lifecycle(template, tmp_path / "first", variant_id="major_idf_revision")
    second = compile_template_lifecycle(template, tmp_path / "second", variant_id="major_idf_revision")

    assert first.envelope.package_sha256 == second.envelope.package_sha256
    assert _package_stats(first.package_dir) == _package_stats(second.package_dir)


def test_compiled_ssc03_fixture_executes_and_verifies(tmp_path: Path) -> None:
    compiled = compile_template_lifecycle(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="administrative_no_op",
    )
    adapter = registered_lifecycle_adapter(TEMPLATE_ID)
    environment = adapter.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    assert adapter.build_operation_resolver(compiled.package_dir, tmp_path / "run") is not None

    run_evidence_lifecycle(
        compiled.package_dir,
        tmp_path / "run",
        episode_environment=environment,
    )
    verification = adapter.verify(compiled.package_dir, tmp_path / "run")

    assert verification["passed"] is True
    assert verification["reward"] == 1.0
    assert len(verification["gates"]) == 11
    assert all(gate["passed"] for gate in verification["gates"].values())
