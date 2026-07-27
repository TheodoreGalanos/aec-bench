# ABOUTME: Tests canonical compiled-world identity and typed lifecycle adapter wiring.
# ABOUTME: Pins SSC-03 package bytes while exercising the real operation-driven smoke fixture.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.compiled_world import (
    CallableLifecycleWorldAdapter,
    CompiledWorldEnvelope,
    LifecycleWorldAdapter,
    validate_lifecycle_world_adapter,
)
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_adapter
from aec_bench.task_world_templates.materializer import compile_template_lifecycle

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "ssc03_hydraulic_compiled_world.v1.json"


def _golden_identity() -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _package_stats(package_dir: Path) -> tuple[int, int]:
    files = [path for path in package_dir.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def test_ssc03_registration_resolves_runtime_checkable_adapter() -> None:
    template = get_template(TEMPLATE_ID)

    adapter = registered_lifecycle_adapter(TEMPLATE_ID)

    assert isinstance(adapter, LifecycleWorldAdapter)
    validate_lifecycle_world_adapter(template, adapter)
    assert adapter.template_id == TEMPLATE_ID
    assert adapter.variant_ids() == tuple(_golden_identity()["variants"])
    identity = adapter.identity()
    assert identity.schema_version == adapter.schema_version
    assert identity.template_id == TEMPLATE_ID
    assert identity.operation_resolver_factory is not None
    assert identity.smoke_environment_factory is not None


def test_operation_lifecycle_adapter_requires_resolver_and_smoke() -> None:
    template = get_template(TEMPLATE_ID)
    adapter = cast(CallableLifecycleWorldAdapter, registered_lifecycle_adapter(TEMPLATE_ID))

    with pytest.raises(ValueError, match="operation resolver"):
        validate_lifecycle_world_adapter(template, replace(adapter, operation_resolver_factory=None))
    with pytest.raises(ValueError, match="smoke environment"):
        validate_lifecycle_world_adapter(template, replace(adapter, smoke_environment_factory=None))


def test_adapter_rejects_mismatched_declarative_template() -> None:
    adapter = registered_lifecycle_adapter(TEMPLATE_ID)
    other_template = get_template("drainage-model-evidence-lifecycle-review")

    with pytest.raises(ValueError, match="template identity"):
        validate_lifecycle_world_adapter(other_template, adapter)


@pytest.mark.parametrize(
    "variant_id",
    (
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    ),
)
def test_compiled_ssc03_package_matches_golden_bytes(tmp_path: Path, variant_id: str) -> None:
    golden = _golden_identity()

    compiled = compile_template_lifecycle(
        get_template(TEMPLATE_ID),
        tmp_path / variant_id,
        variant_id=variant_id,
    )

    expected = golden["variants"][variant_id]
    assert compiled.envelope.template_id == golden["template_id"]
    assert compiled.envelope.world_id == golden["world_id"]
    assert compiled.envelope.lifecycle_id == golden["lifecycle_id"]
    assert compiled.envelope.lifecycle_spec_sha256 == golden["lifecycle_spec_sha256"]
    assert compiled.envelope.variant_id == variant_id
    assert compiled.envelope.package_sha256 == expected["package_sha256"]
    assert _package_stats(compiled.package_dir) == (expected["file_count"], expected["total_bytes"])
    assert not (compiled.package_dir / "compiled-world.json").exists()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompiledWorldEnvelope.model_validate(compiled.envelope.model_dump(mode="json") | {"unexpected": True})


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
