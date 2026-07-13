# ABOUTME: Tests the public SSC-03 design-response lifecycle package and operation contract.
# ABOUTME: Keeps model-selected interventions separate from the PR21 calibration family.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.hydraulics import build_hydraulic_run_request
from aec_bench.task_world_templates.hydraulics.interventions import list_hydraulic_intervention_ids
from aec_bench.task_world_templates.lifecycles import (
    materialize_lifecycle_template,
    registered_lifecycle_template_ids,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention import (
    TEMPLATE_ID,
    validated_ssc03_hydraulic_intervention_package,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_intervention_lifecycle_has_a_distinct_four_checkpoint_contract() -> None:
    template = get_template(TEMPLATE_ID)
    assert template.evidence_lifecycle is not None
    checkpoints = template.evidence_lifecycle.checkpoints

    assert TEMPLATE_ID in registered_lifecycle_template_ids()
    assert template.evidence_lifecycle.lifecycle_id == "ssc03.hydraulic-design-response-lifecycle"
    assert [checkpoint.checkpoint_id for checkpoint in checkpoints] == [
        "problem_analysis",
        "intervention_selection",
        "intervention_analysis",
        "closeout_review",
    ]
    assert checkpoints[1].conditional_operations is None
    assert checkpoints[3].conditional_operations is None
    assert checkpoints[0].conditional_operations is not None
    assert checkpoints[2].conditional_operations is not None
    assert checkpoints[0].conditional_operations.operation_budget == 6
    assert checkpoints[2].conditional_operations.operation_budget == 7
    assert {operation.operation_id for operation in checkpoints[2].conditional_operations.operations} == {
        "source-intervention.selected",
        "hydrology.design-10yr",
        "hydrology.major-100yr",
        "detention-outlet.design-10yr.declared-outlet",
        "detention-outlet.major-100yr.declared-outlet",
        "network-hgl.design-10yr.declared-tailwater",
        "network-hgl.major-100yr.declared-tailwater",
    }


def test_materialized_package_exposes_options_without_outcomes(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")

    validated = validated_ssc03_hydraulic_intervention_package(package)
    public_catalogue = _read_json(package / "releases" / "intervention_selection" / "interventions.json")
    encoded_catalogue = json.dumps(public_catalogue, sort_keys=True)

    assert validated["intervention_ids"] == list(list_hydraulic_intervention_ids())
    assert [item["intervention_id"] for item in public_catalogue["interventions"]] == list(
        list_hydraulic_intervention_ids()
    )
    assert "expected" not in encoded_catalogue
    assert "failed_criteria" not in encoded_catalogue
    assert "screening_ready" not in encoded_catalogue

    problem = package / "hidden" / "hydraulic" / "packages" / "problem"
    build_hydraulic_run_request(problem, scenario_id="major-100yr")
    for intervention_id in list_hydraulic_intervention_ids():
        option = package / "hidden" / "hydraulic" / "packages" / "interventions" / intervention_id
        build_hydraulic_run_request(option, scenario_id="major-100yr")


def test_materialized_package_rejects_option_tampering(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    source = (
        package
        / "hidden"
        / "hydraulic"
        / "packages"
        / "interventions"
        / "controlled_orifice_resize"
        / "source"
        / "source-state.json"
    )
    source.write_text(source.read_text(encoding="utf-8").replace("0.48", "0.49"), encoding="utf-8")

    with pytest.raises(ValueError, match="intervention package identity"):
        validated_ssc03_hydraulic_intervention_package(package)
