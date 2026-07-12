# ABOUTME: Tests the real PR18 coupled run behind PR19 detention and HGL lifecycle operations.
# ABOUTME: Proves stage projections share one computation and selective reuse follows dependency hashes.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.hydraulics import (
    build_hydraulic_run_request,
    execute_hydraulic_world,
)
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
SCENARIO_IDS = ("design-10yr", "major-100yr")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _visible_sha(run: Path) -> str:
    return str(_read_json(run / "workspace" / "hydraulics" / "current-source.json")["visible_source_state_sha256"])


def _execute(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    session_id: str,
) -> dict[str, Any]:
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id=checkpoint_id,
        operation_id=operation_id,
        visible_source_state_sha256=_visible_sha(run),
        reason=f"Execute {operation_id} against the declared source.",
        session_id=session_id,
    )


def _prepare_baseline(tmp_path: Path, variant_id: str = "tailwater_revision") -> tuple[Path, Path]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id=variant_id,
    )
    run = tmp_path / "run"
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    return package, run


def _baseline_chain(package: Path, run: Path, scenario_id: str = "design-10yr") -> tuple[dict[str, Any], ...]:
    return (
        _execute(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id=f"hydrology.{scenario_id}",
            session_id="baseline.session-001",
        ),
        _execute(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id=f"detention-outlet.{scenario_id}.declared-outlet",
            session_id="baseline.session-001",
        ),
        _execute(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id=f"network-hgl.{scenario_id}.declared-tailwater",
            session_id="baseline.session-001",
        ),
    )


def _all_scenario_chains(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    session_id: str,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_IDS:
        for operation_id in (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        ):
            results[operation_id] = _execute(
                package,
                run,
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                session_id=session_id,
            )
    return results


def _operation_statuses(run: Path, checkpoint_id: str) -> dict[str, str]:
    catalog = _read_json(run / "workspace" / "checkpoints" / checkpoint_id / "operations.json")
    operations = catalog["operations"]
    assert isinstance(operations, list)
    return {str(item["operation_id"]): str(item["status"]) for item in operations}


def _advance_to_revision(package: Path, run: Path) -> None:
    submission = {
        "checkpoint_id": "baseline_analysis",
        "visible_source_state_sha256": _visible_sha(run),
        "selected_operations": {},
        "accepted_decisions": {},
        "readiness_decision": "baseline_complete",
        "claim_boundary": {},
    }
    path = run / "workspace" / "submissions" / "baseline_analysis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(submission), encoding="utf-8")
    submit_evidence_checkpoint(package, run)
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="revision.session-001",
        execution_mode="persistent_context",
    )


def test_coupled_detention_and_hgl_chain_matches_one_direct_pr18_run(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path)
    hydrology, detention, hgl = _baseline_chain(package, run)

    assert detention["prerequisite_action_ids"] == [hydrology["action_id"]]
    assert hgl["prerequisite_action_ids"] == [detention["action_id"]]
    detention_root = run / "lifecycle_operations" / str(detention["action_id"]) / "artifacts"
    detention_result = _read_json(detention_root / "detention-outlet.json")
    hgl_result = _read_json(run / "lifecycle_operations" / str(hgl["action_id"]) / "artifacts" / "network-hgl.json")
    direct_package = package / "hidden" / "hydraulic" / "packages" / "baseline"
    direct_request = build_hydraulic_run_request(direct_package, scenario_id="design-10yr")
    direct_run = execute_hydraulic_world(direct_package, tmp_path / "direct-run", direct_request)

    for artifact_name in ("request.json", "results.json", "timeseries.json", "report.md", "run-manifest.json"):
        assert (detention_root / "hydraulic-run" / artifact_name).read_bytes() == (
            direct_run / artifact_name
        ).read_bytes()
    direct_results = _read_json(direct_run / "results.json")
    assert hgl_result["hydraulic_run_id"] == direct_request.run_id
    assert hgl_result["maximum_node_hgl_m"] == direct_results["maximum_node_hgl_m"]
    assert hgl_result["minimum_hgl_clearance_m"] == direct_results["minimum_hgl_clearance_m"]
    assert set(detention_result["criteria"]) == {
        "continuity",
        "design_total_release",
        "emergency_weir_inactive",
        "freeboard",
        "outlet_convergence",
        "storage_capacity",
    }
    assert set(hgl_result["criteria"]) == {
        "hgl_clearance",
        "pipe_capacity",
        "pipe_velocity",
    }

    detention_workspace = run / "workspace" / "inbox" / "baseline_analysis" / "operations" / str(detention["action_id"])
    assert {
        path.relative_to(detention_workspace).as_posix() for path in detention_workspace.rglob("*") if path.is_file()
    } == {"detention-outlet.json"}
    hgl_workspace = run / "workspace" / "inbox" / "baseline_analysis" / "operations" / str(hgl["action_id"])
    assert {path.relative_to(hgl_workspace).as_posix() for path in hgl_workspace.rglob("*") if path.is_file()} == {
        "network-hgl.json",
        "report.md",
    }


def test_tailwater_revision_reuses_hydrology_and_recomputes_coupled_chain(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path, "tailwater_revision")
    baseline_hydrology, baseline_detention, _baseline_hgl = _baseline_chain(package, run)
    old_visible_sha = _visible_sha(run)
    _advance_to_revision(package, run)

    revision = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )
    new_visible_sha = _visible_sha(run)
    reused_hydrology = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="hydrology.design-10yr",
        session_id="revision.session-001",
    )
    revised_detention = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="detention-outlet.design-10yr.declared-outlet",
        session_id="revision.session-001",
    )
    revised_hgl = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="network-hgl.design-10yr.declared-tailwater",
        session_id="revision.session-001",
    )

    assert revision["disposition"] == "activated"
    assert new_visible_sha != old_visible_sha
    assert reused_hydrology["outcome"] == "already_current"
    assert reused_hydrology["retained_from_action_id"] == baseline_hydrology["action_id"]
    assert reused_hydrology["budget_consumed"] == 0
    assert revised_detention["outcome"] == "completed"
    assert revised_detention["input_projection_sha256"] != baseline_detention["input_projection_sha256"]
    assert revised_detention["prerequisite_action_ids"] == [baseline_hydrology["action_id"]]
    assert revised_hgl["prerequisite_action_ids"] == [revised_detention["action_id"]]


def test_major_operation_projections_partition_every_pr18_criterion(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path)
    _hydrology, detention, hgl = _baseline_chain(package, run, "major-100yr")
    detention_action_id = str(detention["action_id"])
    hgl_action_id = str(hgl["action_id"])
    detention_root = run / "lifecycle_operations" / detention_action_id / "artifacts"
    hgl_root = run / "lifecycle_operations" / hgl_action_id / "artifacts"
    complete = _read_json(detention_root / "hydraulic-run" / "results.json")["criteria"]
    detention_criteria = _read_json(detention_root / "detention-outlet.json")["criteria"]
    hgl_criteria = _read_json(hgl_root / "network-hgl.json")["criteria"]

    assert set(detention_criteria).isdisjoint(hgl_criteria)
    assert set(detention_criteria) | set(hgl_criteria) == set(complete)


@pytest.mark.parametrize(
    ("variant_id", "reused_operation_ids"),
    [
        (
            "administrative_no_op",
            {
                "hydrology.design-10yr",
                "detention-outlet.design-10yr.declared-outlet",
                "network-hgl.design-10yr.declared-tailwater",
                "hydrology.major-100yr",
                "detention-outlet.major-100yr.declared-outlet",
                "network-hgl.major-100yr.declared-tailwater",
            },
        ),
        (
            "major_idf_revision",
            {
                "hydrology.design-10yr",
                "detention-outlet.design-10yr.declared-outlet",
                "network-hgl.design-10yr.declared-tailwater",
            },
        ),
        (
            "outlet_geometry_revision",
            {"hydrology.design-10yr", "hydrology.major-100yr"},
        ),
        (
            "tailwater_revision",
            {"hydrology.design-10yr", "hydrology.major-100yr"},
        ),
    ],
)
def test_revision_matrix_reuses_only_current_dependency_projections(
    tmp_path: Path,
    variant_id: str,
    reused_operation_ids: set[str],
) -> None:
    package, run = _prepare_baseline(tmp_path, variant_id)
    baseline = _all_scenario_chains(
        package,
        run,
        checkpoint_id="baseline_analysis",
        session_id="baseline.session-001",
    )
    old_visible_sha = _visible_sha(run)
    _advance_to_revision(package, run)

    revision = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )
    revised = _all_scenario_chains(
        package,
        run,
        checkpoint_id="revision_analysis",
        session_id="revision.session-001",
    )

    assert revision["outcome"] == "completed"
    assert revision["disposition"] == "activated"
    assert revision["visible_source_state_after_sha256"] != old_visible_sha
    assert (revision["physical_source_state_after_sha256"] == revision["physical_source_state_before_sha256"]) is (
        variant_id == "administrative_no_op"
    )
    for operation_id, action in revised.items():
        baseline_action = baseline[operation_id]
        if operation_id in reused_operation_ids:
            assert action["outcome"] == "already_current"
            assert action["retained_from_action_id"] == baseline_action["action_id"]
            assert action["input_projection_sha256"] == baseline_action["input_projection_sha256"]
            assert action["budget_consumed"] == 0
        else:
            assert action["outcome"] == "completed"
            assert action["retained_from_action_id"] is None
            assert action["input_projection_sha256"] != baseline_action["input_projection_sha256"]
            assert action["budget_consumed"] == 1
    assert revised["network-hgl.major-100yr.declared-tailwater"]["budget_after"] == (
        6 - (len(revised) - len(reused_operation_ids))
    )


@pytest.mark.parametrize(
    ("variant_id", "expected_statuses"),
    [
        (
            "administrative_no_op",
            {
                "hydrology.design-10yr": "current_or_reusable",
                "detention-outlet.design-10yr.declared-outlet": "current_or_reusable",
                "network-hgl.design-10yr.declared-tailwater": "current_or_reusable",
                "hydrology.major-100yr": "current_or_reusable",
                "detention-outlet.major-100yr.declared-outlet": "current_or_reusable",
                "network-hgl.major-100yr.declared-tailwater": "current_or_reusable",
            },
        ),
        (
            "major_idf_revision",
            {
                "hydrology.design-10yr": "current_or_reusable",
                "detention-outlet.design-10yr.declared-outlet": "current_or_reusable",
                "network-hgl.design-10yr.declared-tailwater": "current_or_reusable",
                "hydrology.major-100yr": "available",
                "detention-outlet.major-100yr.declared-outlet": "prerequisites_incomplete",
                "network-hgl.major-100yr.declared-tailwater": "prerequisites_incomplete",
            },
        ),
        (
            "outlet_geometry_revision",
            {
                "hydrology.design-10yr": "current_or_reusable",
                "detention-outlet.design-10yr.declared-outlet": "available",
                "network-hgl.design-10yr.declared-tailwater": "prerequisites_incomplete",
                "hydrology.major-100yr": "current_or_reusable",
                "detention-outlet.major-100yr.declared-outlet": "available",
                "network-hgl.major-100yr.declared-tailwater": "prerequisites_incomplete",
            },
        ),
        (
            "tailwater_revision",
            {
                "hydrology.design-10yr": "current_or_reusable",
                "detention-outlet.design-10yr.declared-outlet": "available",
                "network-hgl.design-10yr.declared-tailwater": "prerequisites_incomplete",
                "hydrology.major-100yr": "current_or_reusable",
                "detention-outlet.major-100yr.declared-outlet": "available",
                "network-hgl.major-100yr.declared-tailwater": "prerequisites_incomplete",
            },
        ),
    ],
)
def test_revision_catalog_reports_dynamic_currentness(
    tmp_path: Path,
    variant_id: str,
    expected_statuses: dict[str, str],
) -> None:
    package, run = _prepare_baseline(tmp_path, variant_id)
    _all_scenario_chains(
        package,
        run,
        checkpoint_id="baseline_analysis",
        session_id="baseline.session-001",
    )
    _advance_to_revision(package, run)
    _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )

    statuses = _operation_statuses(run, "revision_analysis")

    assert statuses["source-revision.current"] == "current_or_reusable"
    assert {key: value for key, value in statuses.items() if key != "source-revision.current"} == expected_statuses


def test_affected_downstream_operation_rejects_stale_prerequisite(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path, "major_idf_revision")
    _baseline_chain(package, run, "major-100yr")
    _advance_to_revision(package, run)
    _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )

    stale = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="detention-outlet.major-100yr.declared-outlet",
        session_id="revision.session-001",
    )

    assert stale["outcome"] == "rejected"
    assert stale["rejection"] == "prerequisites_incomplete"
    assert stale["budget_consumed"] == 0
    assert stale["budget_before"] == stale["budget_after"]
    assert stale["artifacts"] == []


def test_repeated_source_activation_is_already_current_and_free(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path, "tailwater_revision")
    _advance_to_revision(package, run)
    first = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )

    repeated = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )

    assert repeated["outcome"] == "already_current"
    assert repeated["disposition"] == "reused"
    assert repeated["retained_from_action_id"] == first["action_id"]
    assert repeated["budget_consumed"] == 0


def test_revision_calculation_before_source_activation_is_rejected_for_free(tmp_path: Path) -> None:
    package, run = _prepare_baseline(tmp_path, "major_idf_revision")
    _advance_to_revision(package, run)

    rejected = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="hydrology.major-100yr",
        session_id="revision.session-001",
    )

    assert rejected["outcome"] == "rejected"
    assert rejected["rejection"] == "prerequisites_incomplete"
    assert rejected["budget_consumed"] == 0
    assert rejected["budget_before"] == rejected["budget_after"]
