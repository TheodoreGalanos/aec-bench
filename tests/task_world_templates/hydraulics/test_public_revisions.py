# ABOUTME: Tests the four public SSC-03 hydraulic interaction revision variants.
# ABOUTME: Proves each fixture changes only its declared physical dependency topology.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.hydraulics import (
    build_hydraulic_run_request,
    execute_hydraulic_world,
    materialize_hydraulic_world,
)
from aec_bench.task_world_templates.hydraulics.revisions import (
    build_hydraulic_revision_source_state,
    get_hydraulic_revision,
    list_hydraulic_revision_ids,
)
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state

REVISION_IDS = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)


def _section_hashes(state: object) -> dict[str, str]:
    return {section.section_name: section.content_sha256 for section in state.sections}  # type: ignore[attr-defined]


def _run_result(tmp_path: Path, revision_id: str, scenario_id: str) -> dict[str, Any]:
    source = build_hydraulic_revision_source_state(revision_id)
    package = materialize_hydraulic_world(source.world_id, tmp_path / revision_id, source_state=source)
    request = build_hydraulic_run_request(package, scenario_id=scenario_id)
    run = execute_hydraulic_world(package, tmp_path / f"{revision_id}-run", request)
    payload = json.loads((run / "results.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_public_revision_registry_is_exact_and_returns_defensive_copies() -> None:
    assert list_hydraulic_revision_ids() == REVISION_IDS
    first = get_hydraulic_revision("tailwater_revision")
    second = get_hydraulic_revision("tailwater_revision")

    assert first == second
    assert first is not second
    assert first.visibility == "public"
    assert first.physical_section == "network"
    assert "expected" not in first.model_dump_json()


@pytest.mark.parametrize(
    ("revision_id", "physical_section"),
    [
        ("major_idf_revision", "scenarios"),
        ("tailwater_revision", "network"),
        ("outlet_geometry_revision", "outlet"),
    ],
)
def test_physical_revision_changes_only_its_declared_section(revision_id: str, physical_section: str) -> None:
    baseline = build_source_state()
    revised = build_hydraulic_revision_source_state(revision_id)
    changed = {
        section_name
        for section_name, content_hash in _section_hashes(baseline).items()
        if _section_hashes(revised)[section_name] != content_hash
    }

    assert changed == {physical_section}
    assert revised.world_id == baseline.world_id


def test_administrative_no_op_preserves_exact_hydraulic_source_state() -> None:
    baseline = build_source_state()
    revised = build_hydraulic_revision_source_state("administrative_no_op")

    assert revised == baseline
    assert get_hydraulic_revision("administrative_no_op").physical_section is None


@pytest.mark.parametrize(
    (
        "revision_id",
        "scenario_id",
        "peak_inflow",
        "peak_structured_outflow",
        "minimum_freeboard",
        "minimum_hgl_clearance",
        "failed_criteria",
    ),
    [
        ("administrative_no_op", "design-10yr", 1.071547, 0.321368, 0.834846, 1.388438, set()),
        ("administrative_no_op", "major-100yr", 1.442467, 1.416944, 0.326808, 1.152761, set()),
        ("major_idf_revision", "design-10yr", 1.071547, 0.321368, 0.834846, 1.388438, set()),
        (
            "major_idf_revision",
            "major-100yr",
            1.648533,
            1.620433,
            0.289305,
            0.984295,
            {"freeboard", "pipe_capacity"},
        ),
        (
            "outlet_geometry_revision",
            "design-10yr",
            1.071547,
            0.438656,
            0.963173,
            1.378458,
            {"design_total_release"},
        ),
        ("outlet_geometry_revision", "major-100yr", 1.442467, 1.412401, 0.355103, 1.156264, set()),
        ("tailwater_revision", "design-10yr", 1.071547, 0.260903, 0.695687, 0.992379, set()),
        ("tailwater_revision", "major-100yr", 1.442467, 1.416210, 0.310613, 0.753328, set()),
    ],
)
def test_public_revision_scenario_matrix_matches_the_declared_pr18_oracle(
    tmp_path: Path,
    revision_id: str,
    scenario_id: str,
    peak_inflow: float,
    peak_structured_outflow: float,
    minimum_freeboard: float,
    minimum_hgl_clearance: float,
    failed_criteria: set[str],
) -> None:
    result = _run_result(tmp_path, revision_id, scenario_id)
    criteria = result["criteria"]
    assert isinstance(criteria, dict)

    assert result["peak_total_inflow_m3_s"] == pytest.approx(peak_inflow, abs=1e-6)
    assert result["peak_structured_outflow_m3_s"] == pytest.approx(peak_structured_outflow, abs=1e-6)
    assert result["minimum_freeboard_m"] == pytest.approx(minimum_freeboard, abs=1e-6)
    assert result["minimum_hgl_clearance_m"] == pytest.approx(minimum_hgl_clearance, abs=1e-6)
    assert {criterion_id for criterion_id, passed in criteria.items() if not passed} == failed_criteria


def test_major_idf_revision_matches_the_declared_pr18_oracle(tmp_path: Path) -> None:
    result = _run_result(tmp_path, "major_idf_revision", "major-100yr")

    assert result["peak_total_inflow_m3_s"] == pytest.approx(1.648533, abs=1e-6)
    assert result["peak_structured_outflow_m3_s"] == pytest.approx(1.620433, abs=1e-6)
    assert result["minimum_freeboard_m"] == pytest.approx(0.289305, abs=1e-6)
    assert result["criteria"]["freeboard"] is False
    assert result["criteria"]["pipe_capacity"] is False


def test_tailwater_revision_changes_coupled_outputs_without_changing_hydrology(tmp_path: Path) -> None:
    baseline = build_source_state()
    revised = build_hydraulic_revision_source_state("tailwater_revision")
    result = _run_result(tmp_path, "tailwater_revision", "design-10yr")

    assert revised.payload.catchments == baseline.payload.catchments
    assert revised.payload.scenarios == baseline.payload.scenarios
    assert result["peak_structured_outflow_m3_s"] == pytest.approx(0.260903, abs=1e-6)
    criteria = result["criteria"]
    assert isinstance(criteria, dict)
    assert all(criteria.values())


def test_outlet_revision_exposes_the_design_release_consequence(tmp_path: Path) -> None:
    result = _run_result(tmp_path, "outlet_geometry_revision", "design-10yr")

    assert result["peak_structured_outflow_m3_s"] == pytest.approx(0.438656, abs=1e-6)
    assert result["criteria"]["design_total_release"] is False
