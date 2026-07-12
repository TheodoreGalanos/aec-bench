# ABOUTME: Tests deterministic materialization of the public SSC-03 hydraulic interaction family.
# ABOUTME: Keeps revision packages immutable, hidden until activation, and free of gold invalidation answers.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.hydraulics import build_hydraulic_run_request
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_variant_ids,
    materialize_lifecycle_template,
    registered_lifecycle_template_ids,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction import (
    validated_ssc03_hydraulic_interaction_variant,
)

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
VARIANT_IDS = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_hydraulic_interaction_family_is_registered_with_exact_public_variants() -> None:
    template = get_template(TEMPLATE_ID)

    assert TEMPLATE_ID in registered_lifecycle_template_ids()
    assert lifecycle_variant_ids(TEMPLATE_ID) == VARIANT_IDS
    assert template.evidence_lifecycle is not None
    assert [checkpoint.checkpoint_id for checkpoint in template.evidence_lifecycle.checkpoints] == [
        "baseline_analysis",
        "revision_analysis",
        "closeout_review",
    ]


@pytest.mark.parametrize("variant_id", VARIANT_IDS)
def test_materialized_interaction_package_is_byte_identical_and_source_bound(tmp_path: Path, variant_id: str) -> None:
    template = get_template(TEMPLATE_ID)
    first = materialize_lifecycle_template(template, tmp_path / "first", variant_id=variant_id)
    second = materialize_lifecycle_template(template, tmp_path / "second", variant_id=variant_id)

    assert _tree_bytes(first) == _tree_bytes(second)
    assert validated_ssc03_hydraulic_interaction_variant(first)["variant_id"] == variant_id

    baseline = first / "hidden" / "hydraulic" / "packages" / "baseline"
    revision = first / "hidden" / "hydraulic" / "packages" / "revision"
    baseline_request = build_hydraulic_run_request(baseline, scenario_id="design-10yr")
    revision_request = build_hydraulic_run_request(revision, scenario_id="design-10yr")
    if variant_id == "administrative_no_op":
        assert baseline_request == revision_request
    else:
        assert baseline_request.run_id != revision_request.run_id


def test_public_catalogues_are_bounded_and_hidden_resolver_contains_no_gold_answers(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    lifecycle = _read_json(package / "lifecycle.json")
    checkpoints = lifecycle["checkpoints"]
    assert isinstance(checkpoints, list)
    baseline = checkpoints[0]["conditional_operations"]
    revision = checkpoints[1]["conditional_operations"]

    assert baseline["operation_budget"] == 6
    assert len(baseline["operations"]) == 6
    assert revision["operation_budget"] == 7
    assert [item["operation_id"] for item in revision["operations"]] == [
        "source-revision.current",
        "hydrology.design-10yr",
        "hydrology.major-100yr",
        "detention-outlet.design-10yr.declared-outlet",
        "detention-outlet.major-100yr.declared-outlet",
        "network-hgl.design-10yr.declared-tailwater",
        "network-hgl.major-100yr.declared-tailwater",
    ]

    public_text = (package / "lifecycle.json").read_text(encoding="utf-8").lower()
    for forbidden in ("expected", "gold", "source_path", "ready_to_issue", "affected_stage"):
        assert forbidden not in public_text

    resolver = _read_json(package / "hidden" / "lifecycle-operation-resolutions.json")
    assert resolver["variant_id"] == "tailwater_revision"
    assert resolver["baseline_package_path"] == "hidden/hydraulic/packages/baseline"
    assert resolver["revision_package_path"] == "hidden/hydraulic/packages/revision"
    assert "expected" not in json.dumps(resolver).lower()


def test_public_instructions_define_the_structured_submission_without_topology_answers(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="major_idf_revision",
    )

    for checkpoint_id in ("baseline_analysis", "revision_analysis", "closeout_review"):
        instruction = (package / "instructions" / f"{checkpoint_id}.md").read_text(encoding="utf-8")
        for required in (
            "visible_source_state_sha256",
            "selected_operations",
            "accepted_decisions",
            "screening_ready",
            "not_screening_ready",
            "claim_boundary",
        ):
            assert required in instruction
        for forbidden in ("major-100yr is affected", "design chain is reusable", "expected recomputation"):
            assert forbidden not in instruction.lower()


def test_variant_validation_rejects_revision_package_tampering(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="major_idf_revision",
    )
    source_path = package / "hidden" / "hydraulic" / "packages" / "revision" / "source" / "source-state.json"
    source = _read_json(source_path)
    source["payload"]["scenarios"][1]["rainfall_intensity_mm_h"] = 121.0
    source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="variant identity"):
        validated_ssc03_hydraulic_interaction_variant(package)
