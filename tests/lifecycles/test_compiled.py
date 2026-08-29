# ABOUTME: Tests current compiled lifecycle identity and deterministic task composition.
# ABOUTME: Proves package, executable, and operation identities without adapter contracts.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.lifecycles.catalogue import (
    lifecycle_definition,
    lifecycle_executable_artifact_sha256,
    lifecycle_operation_resolver,
    lifecycle_smoke_environment,
    lifecycle_template_ids,
    lifecycle_variant_ids,
    verify_lifecycle,
)
from aec_bench.lifecycles.compiled import (
    CompiledLifecycle,
    CompiledLifecycleEnvelope,
    compile_lifecycle,
    load_compiled_lifecycle,
)
from aec_bench.lifecycles.runtime.lifecycle import run_lifecycle
from tests.support.kernel_source_closure import internal_source_closure

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
VARIANT_IDS = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_SHARED_EXECUTABLE_PATHS = {
    "aec_bench/contracts/evidence_lifecycle.py",
    "aec_bench/contracts/lifecycle_evaluation.py",
    "aec_bench/contracts/trial_record.py",
    "aec_bench/contracts/validators.py",
    "aec_bench/evaluation/lifecycle.py",
    "aec_bench/ledger/durability.py",
    "aec_bench/ledger/immutable_byte_store.py",
    "aec_bench/ledger/local_lock.py",
    "aec_bench/ledger/process_log.py",
}


def _package_stats(package_dir: Path) -> tuple[int, int]:
    files = [path for path in package_dir.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def _executable_inventory(template_id: str) -> set[str]:
    inventory: set[str] = set()
    for selected in lifecycle_definition(template_id).executable_source_roots:
        path = selected.resolve(strict=True)
        candidates = (path,) if path.is_file() else tuple(sorted(path.rglob("*.py")))
        inventory.update(candidate.relative_to(_SOURCE_ROOT).as_posix() for candidate in candidates)
    return inventory


def test_current_lifecycle_definitions_expose_only_real_task_functions() -> None:
    drainage = lifecycle_definition("drainage-model-evidence-lifecycle-review")
    facade = lifecycle_definition("facade-submittal-review-lifecycle")
    hydraulic = lifecycle_definition(TEMPLATE_ID)

    assert lifecycle_variant_ids(TEMPLATE_ID) == VARIANT_IDS
    assert drainage.operation_resolver is None
    assert drainage.smoke_environment is None
    assert facade.operation_resolver is None
    assert facade.smoke_environment is None
    assert hydraulic.operation_resolver is not None
    assert hydraulic.smoke_environment is not None


@pytest.mark.parametrize(
    ("template_id", "task_source"),
    (
        (
            "facade-submittal-review-lifecycle",
            "aec_bench/lifecycles/structural_review/facade_submittal.py",
        ),
        (
            "drainage-model-evidence-lifecycle-review",
            "aec_bench/lifecycles/stormwater_design/drainage_model.py",
        ),
        (
            TEMPLATE_ID,
            "aec_bench/lifecycles/stormwater_design/hydraulic_review.py",
        ),
        (
            "hydraulic-design-response-lifecycle-review",
            "aec_bench/lifecycles/stormwater_design/design_response.py",
        ),
    ),
)
def test_lifecycle_executable_inventory_covers_shared_and_task_owned_imports(
    template_id: str,
    task_source: str,
) -> None:
    inventory = _executable_inventory(template_id)
    imported = internal_source_closure(project_root=_PROJECT_ROOT, seed_paths=(task_source,))
    owned_imports = {
        path for path in imported if path.startswith("aec_bench/lifecycles/") or path in _SHARED_EXECUTABLE_PATHS
    }

    assert _SHARED_EXECUTABLE_PATHS.issubset(inventory)
    assert owned_imports.issubset(inventory)
    if template_id == "facade-submittal-review-lifecycle":
        assert {
            "aec_bench/templates/builtin/structural/facade_submittal_source_policy_package/engine.py",
            "aec_bench/templates/builtin/structural/facade_submittal_source_policy_package/params.toml",
        }.issubset(inventory)


def test_current_lifecycle_executable_identities_are_task_specific() -> None:
    identities = {lifecycle_executable_artifact_sha256(template_id) for template_id in lifecycle_template_ids()}

    assert len(identities) == len(lifecycle_template_ids())


@pytest.mark.parametrize("variant_id", VARIANT_IDS)
def test_compiled_hydraulic_review_package_uses_current_identity(tmp_path: Path, variant_id: str) -> None:
    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / variant_id, variant_id=variant_id)

    assert compiled.envelope.template_id == TEMPLATE_ID
    assert compiled.envelope.lifecycle_id == "hydraulic-interaction-review"
    assert compiled.envelope.variant_id == variant_id
    assert len(compiled.envelope.lifecycle_spec_sha256) == 64
    assert len(compiled.envelope.package_sha256) == 64
    assert len(compiled.envelope.executable_artifact_sha256) == 64
    assert len(compiled.envelope.operation_protocol_sha256 or "") == 64
    assert set(compiled.envelope.model_fields_set) == {
        "visibility",
        "template_id",
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
        CompiledLifecycleEnvelope.model_validate(compiled.envelope.model_dump(mode="json") | {"unexpected": True})


def test_compiled_hydraulic_review_package_is_deterministic(tmp_path: Path) -> None:
    first = compile_lifecycle(TEMPLATE_ID, tmp_path / "first", variant_id="major_idf_revision")
    second = compile_lifecycle(TEMPLATE_ID, tmp_path / "second", variant_id="major_idf_revision")

    assert first.envelope.package_sha256 == second.envelope.package_sha256
    assert _package_stats(first.package_dir) == _package_stats(second.package_dir)


def test_compiled_lifecycle_requires_validated_package_construction(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match=r"use compile_lifecycle\(\) or load_compiled_lifecycle\(\)"):
        CompiledLifecycle()

    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / "package", variant_id="major_idf_revision")

    assert load_compiled_lifecycle(compiled.package_dir) == compiled


def test_compiled_lifecycle_accepts_catalogue_default_variant(tmp_path: Path) -> None:
    compiled = compile_lifecycle("drainage-model-evidence-lifecycle-review", tmp_path / "package")

    assert compiled.envelope.variant_id == "staged_full_correction"


def test_compiled_hydraulic_review_fixture_executes_and_verifies(tmp_path: Path) -> None:
    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / "package", variant_id="administrative_no_op")
    environment = lifecycle_smoke_environment(TEMPLATE_ID, compiled.package_dir)
    assert environment is not None
    operation_resolver = lifecycle_operation_resolver(compiled.package_dir, tmp_path / "run")
    assert operation_resolver is not None

    run_lifecycle(
        compiled.package_dir,
        tmp_path / "run",
        operation_resolver=operation_resolver,
        episode_environment=environment,
    )
    verification = verify_lifecycle(compiled.package_dir, tmp_path / "run")

    assert verification["passed"] is True
    assert verification["reward"] == 1.0
    assert len(verification["gates"]) == 11
    assert all(gate["passed"] for gate in verification["gates"].values())
