# ABOUTME: Tests current compiled lifecycle identity and deterministic task composition.
# ABOUTME: Proves package, executable, and operation identities without adapter contracts.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle
from aec_bench.task_world_templates.compiled_world import CompiledWorldEnvelope, compile_lifecycle
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_definition,
    lifecycle_operation_resolver,
    lifecycle_smoke_environment,
    lifecycle_variant_ids,
    verify_lifecycle,
)

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


def test_current_lifecycle_definitions_expose_only_real_task_functions() -> None:
    drainage = lifecycle_definition("drainage-model-evidence-lifecycle-review")
    hydraulic = lifecycle_definition(TEMPLATE_ID)

    assert lifecycle_variant_ids(TEMPLATE_ID) == VARIANT_IDS
    assert drainage.operation_resolver is None
    assert drainage.smoke_environment is None
    assert hydraulic.operation_resolver is not None
    assert hydraulic.smoke_environment is not None


@pytest.mark.parametrize("variant_id", VARIANT_IDS)
def test_compiled_ssc03_package_uses_current_identity(tmp_path: Path, variant_id: str) -> None:
    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / variant_id, variant_id=variant_id)

    assert compiled.envelope.template_id == TEMPLATE_ID
    assert compiled.envelope.world_id == "aec.task_world.composite.hydraulic-interaction-lifecycle-review"
    assert compiled.envelope.lifecycle_id == "ssc03.hydraulic-interaction-lifecycle"
    assert compiled.envelope.variant_id == variant_id
    assert len(compiled.envelope.lifecycle_spec_sha256) == 64
    assert len(compiled.envelope.package_sha256) == 64
    assert len(compiled.envelope.executable_artifact_sha256) == 64
    assert len(compiled.envelope.operation_protocol_sha256 or "") == 64
    assert set(compiled.envelope.model_fields_set) == {
        "visibility",
        "template_id",
        "world_id",
        "lifecycle_id",
        "variant_id",
        "lifecycle_spec_sha256",
        "package_sha256",
        "executable_artifact_sha256",
        "operation_protocol_sha256",
    }
    assert _package_stats(compiled.package_dir)[0] > 0
    assert not (compiled.package_dir / "world.json").exists()
    assert set(json.loads((compiled.package_dir / "template.json").read_text())) == {
        "template_id",
        "name",
        "discipline",
    }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompiledWorldEnvelope.model_validate(compiled.envelope.model_dump(mode="json") | {"unexpected": True})


def test_compiled_ssc03_package_is_deterministic(tmp_path: Path) -> None:
    first = compile_lifecycle(TEMPLATE_ID, tmp_path / "first", variant_id="major_idf_revision")
    second = compile_lifecycle(TEMPLATE_ID, tmp_path / "second", variant_id="major_idf_revision")

    assert first.envelope.package_sha256 == second.envelope.package_sha256
    assert _package_stats(first.package_dir) == _package_stats(second.package_dir)


def test_compiled_ssc03_fixture_executes_and_verifies(tmp_path: Path) -> None:
    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / "package", variant_id="administrative_no_op")
    environment = lifecycle_smoke_environment(TEMPLATE_ID, compiled.package_dir)
    assert environment is not None
    assert lifecycle_operation_resolver(compiled.package_dir, tmp_path / "run") is not None

    run_evidence_lifecycle(compiled.package_dir, tmp_path / "run", episode_environment=environment)
    verification = verify_lifecycle(compiled.package_dir, tmp_path / "run")

    assert verification["passed"] is True
    assert verification["reward"] == 1.0
    assert len(verification["gates"]) == 11
    assert all(gate["passed"] for gate in verification["gates"].values())
