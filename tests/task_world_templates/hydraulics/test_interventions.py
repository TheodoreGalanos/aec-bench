# ABOUTME: Tests the bounded public intervention choices for the SSC-03 design-response lifecycle.
# ABOUTME: Proves each option changes declared source sections and produces distinct checked consequences.

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
from aec_bench.task_world_templates.hydraulics.interventions import (
    build_hydraulic_intervention_source_state,
    build_hydraulic_problem_source_state,
    get_hydraulic_intervention,
    list_hydraulic_intervention_ids,
)

INTERVENTION_IDS = (
    "controlled_orifice_resize",
    "emergency_weir_enlargement",
)


def _section_hashes(state: object) -> dict[str, str]:
    return {section.section_name: section.content_sha256 for section in state.sections}  # type: ignore[attr-defined]


def _run_result(tmp_path: Path, intervention_id: str, scenario_id: str) -> dict[str, Any]:
    source = build_hydraulic_intervention_source_state(intervention_id)
    package = materialize_hydraulic_world(source.world_id, tmp_path / intervention_id, source_state=source)
    request = build_hydraulic_run_request(package, scenario_id=scenario_id)
    run = execute_hydraulic_world(package, tmp_path / f"{intervention_id}-{scenario_id}", request)
    payload = json.loads((run / "results.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_intervention_registry_is_exact_public_and_answer_free() -> None:
    assert list_hydraulic_intervention_ids() == INTERVENTION_IDS

    for intervention_id in INTERVENTION_IDS:
        first = get_hydraulic_intervention(intervention_id)
        second = get_hydraulic_intervention(intervention_id)
        payload = first.model_dump(mode="json")

        assert first == second
        assert first is not second
        assert first.visibility == "public"
        assert "expected" not in json.dumps(payload)
        assert "pass" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("intervention_id", "changed_sections"),
    [
        ("controlled_orifice_resize", {"outlet"}),
        ("emergency_weir_enlargement", {"outlet"}),
    ],
)
def test_intervention_changes_only_declared_source_sections(
    intervention_id: str,
    changed_sections: set[str],
) -> None:
    problem = build_hydraulic_problem_source_state()
    intervention = get_hydraulic_intervention(intervention_id)
    revised = build_hydraulic_intervention_source_state(intervention_id)
    actual_changed = {
        section_name
        for section_name, content_hash in _section_hashes(problem).items()
        if _section_hashes(revised)[section_name] != content_hash
    }

    assert set(intervention.changed_sections) == changed_sections
    assert actual_changed == changed_sections
    assert revised.world_id == problem.world_id


@pytest.mark.parametrize(
    ("intervention_id", "scenario_id", "peak_outflow", "minimum_freeboard", "failed_criteria"),
    [
        ("controlled_orifice_resize", "design-10yr", 0.392365, 0.914051, set()),
        ("controlled_orifice_resize", "major-100yr", 1.617686, 0.303073, set()),
        ("emergency_weir_enlargement", "design-10yr", 0.321368, 0.834846, set()),
        (
            "emergency_weir_enlargement",
            "major-100yr",
            1.626967,
            0.337831,
            {"pipe_capacity"},
        ),
    ],
)
def test_intervention_scenario_matrix_has_distinct_physical_consequences(
    tmp_path: Path,
    intervention_id: str,
    scenario_id: str,
    peak_outflow: float,
    minimum_freeboard: float,
    failed_criteria: set[str],
) -> None:
    result = _run_result(tmp_path, intervention_id, scenario_id)

    assert result["peak_structured_outflow_m3_s"] == pytest.approx(peak_outflow, abs=1e-6)
    assert result["minimum_freeboard_m"] == pytest.approx(minimum_freeboard, abs=1e-6)
    assert {criterion_id for criterion_id, passed in result["criteria"].items() if not passed} == failed_criteria


def test_problem_source_requires_an_intervention_for_the_major_event(tmp_path: Path) -> None:
    source = build_hydraulic_problem_source_state()
    package = materialize_hydraulic_world(source.world_id, tmp_path / "problem", source_state=source)
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_world(package, tmp_path / "problem-run", request)
    result = json.loads((run / "results.json").read_text(encoding="utf-8"))

    assert {criterion_id for criterion_id, passed in result["criteria"].items() if not passed} == {
        "freeboard",
        "pipe_capacity",
    }
