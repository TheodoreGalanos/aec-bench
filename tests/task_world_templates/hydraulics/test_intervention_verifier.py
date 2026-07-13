# ABOUTME: Tests complete task-owned verification of both SSC-03 intervention trajectories.
# ABOUTME: Separates honest evidence handling from whether the selected design response solves the problem.

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import read_evidence_lifecycle_state, run_evidence_lifecycle
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import (
    materialize_lifecycle_template,
    verify_lifecycle_template,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_smoke import (
    _run_references,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention import TEMPLATE_ID
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention_smoke import (
    build_ssc03_hydraulic_intervention_smoke_environment,
    write_ssc03_hydraulic_intervention_smoke_submission,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention_verifier import (
    _invalid_contract_result,
)
from tests.support.lifecycle_episode import deterministic_episode_environment

EXPECTED_GATES = {
    "checkpoint_contract",
    "selection_grounding",
    "operation_evidence_integrity",
    "selective_recomputation",
    "decision_update",
    "intervention_effectiveness",
    "run_propagation",
    "report_propagation",
    "memo_propagation",
    "final_readiness",
    "claim_boundary",
}


def test_invalid_submission_contract_returns_a_zero_reward_failure() -> None:
    result = _invalid_contract_result("invalid intervention submission")

    assert result["passed"] is False
    assert result["overall"] == "fail"
    assert result["reward"] == 0.0
    assert result["gates"]["checkpoint_contract"]["failures"] == ["invalid intervention submission"]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_policy(tmp_path: Path, intervention_id: str) -> tuple[Path, Path, dict[str, Any]]:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / f"package-{intervention_id}")
    run = tmp_path / f"run-{intervention_id}"
    environment = build_ssc03_hydraulic_intervention_smoke_environment(
        package,
        selected_intervention_id=intervention_id,
    )

    lifecycle = run_evidence_lifecycle(package, run, episode_environment=environment)
    verification = verify_lifecycle_template(package, run)

    assert lifecycle["status"] == "complete"
    return package, run, verification


def test_feasible_intervention_completes_the_real_lifecycle(tmp_path: Path) -> None:
    _package, run, result = _run_policy(tmp_path, "controlled_orifice_resize")

    state = read_evidence_lifecycle_state(_package, run)
    actions = [action for checkpoint in state["checkpoint_runs"] for action in checkpoint["operation_actions"]]
    closeout = _read_json(run / "episodes" / "closeout_review" / "submission.json")

    assert result["passed"] is True
    assert result["overall"] == "pass"
    assert result["reward"] == 1.0
    assert set(result["gates"]) == EXPECTED_GATES
    assert all(gate["passed"] for gate in result["gates"].values())
    assert len(actions) == 13
    assert closeout["selected_intervention_id"] == "controlled_orifice_resize"
    assert closeout["readiness_decision"] == "screening_ready"


def test_infeasible_intervention_is_honestly_recorded_but_does_not_solve_the_task(tmp_path: Path) -> None:
    _package, run, result = _run_policy(tmp_path, "emergency_weir_enlargement")
    closeout = _read_json(run / "episodes" / "closeout_review" / "submission.json")

    assert result["passed"] is False
    assert result["overall"] == "fail"
    assert result["reward"] == 0.5
    assert set(result["gates"]) == EXPECTED_GATES
    assert result["gates"]["intervention_effectiveness"]["passed"] is False
    assert result["gates"]["intervention_effectiveness"]["failures"] == [
        "emergency_weir_enlargement.major-100yr.pipe_capacity"
    ]
    assert all(gate["passed"] for gate_id, gate in result["gates"].items() if gate_id != "intervention_effectiveness")
    assert closeout["selected_intervention_id"] == "emergency_weir_enlargement"
    assert closeout["readiness_decision"] == "not_screening_ready"


def test_two_bounded_policies_diverge_from_the_same_problem_source(tmp_path: Path) -> None:
    _feasible_package, feasible_run, _feasible_result = _run_policy(tmp_path, "controlled_orifice_resize")
    _infeasible_package, infeasible_run, _infeasible_result = _run_policy(
        tmp_path,
        "emergency_weir_enlargement",
    )

    feasible_state = read_evidence_lifecycle_state(_feasible_package, feasible_run)
    infeasible_state = read_evidence_lifecycle_state(_infeasible_package, infeasible_run)
    feasible_actions = {
        action["operation_id"]: action
        for checkpoint in feasible_state["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
        if checkpoint["checkpoint_id"] == "intervention_analysis"
    }
    infeasible_actions = {
        action["operation_id"]: action
        for checkpoint in infeasible_state["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
        if checkpoint["checkpoint_id"] == "intervention_analysis"
    }
    feasible_activation = feasible_actions["source-intervention.selected"]
    infeasible_activation = infeasible_actions["source-intervention.selected"]
    feasible_major = _read_json(
        feasible_run
        / "lifecycle_operations"
        / feasible_actions["detention-outlet.major-100yr.declared-outlet"]["action_id"]
        / "artifacts"
        / "detention-outlet.json"
    )
    infeasible_major = _read_json(
        infeasible_run
        / "lifecycle_operations"
        / infeasible_actions["detention-outlet.major-100yr.declared-outlet"]["action_id"]
        / "artifacts"
        / "detention-outlet.json"
    )

    assert (
        feasible_activation["physical_source_state_before_sha256"]
        == infeasible_activation["physical_source_state_before_sha256"]
    )
    assert (
        feasible_activation["physical_source_state_after_sha256"]
        != infeasible_activation["physical_source_state_after_sha256"]
    )
    assert feasible_major["peak_structured_outflow_m3_s"] == pytest.approx(1.617686, abs=1e-6)
    assert infeasible_major["peak_structured_outflow_m3_s"] == pytest.approx(1.626967, abs=1e-6)


def test_undeclared_duplicate_package_cannot_hijack_verifier_lookup(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    declared = package / "hidden" / "hydraulic" / "packages" / "interventions" / "controlled_orifice_resize"
    undeclared = package / "hidden" / "hydraulic" / "packages" / "aaa"
    shutil.copytree(declared, undeclared)
    (undeclared / "engine" / "identity.json").unlink()
    run = tmp_path / "run"
    environment = build_ssc03_hydraulic_intervention_smoke_environment(
        package,
        selected_intervention_id="controlled_orifice_resize",
    )

    run_evidence_lifecycle(package, run, episode_environment=environment)
    result = verify_lifecycle_template(package, run)

    assert result["passed"] is True
    assert result["reward"] == 1.0


def test_omitting_the_failing_major_chain_cannot_bypass_the_reward_cap(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    run = tmp_path / "run"
    full_selected: dict[str, str] = {}

    def execute(context: dict[str, Any]) -> dict[str, str]:
        checkpoint_id = str(context["checkpoint_id"])
        submission_path = Path(str(context["submission_path"]))
        if checkpoint_id != "closeout_review":
            write_ssc03_hydraulic_intervention_smoke_submission(
                package,
                run,
                checkpoint_id,
                str(context["session_id"]),
                submission_path,
                selected_intervention_id="emergency_weir_enlargement",
            )
            if checkpoint_id == "intervention_analysis":
                submission = _read_json(submission_path)
                selected = cast(dict[str, str], submission["selected_operations"])
                full_selected.update(selected)
                submission["selected_operations"] = {
                    key: value for key, value in selected.items() if "major-100yr" not in key
                }
                submission["readiness_decision"] = "screening_ready"
                _write_json(submission_path, submission)
            return {"status": "completed"}

        intervention = _read_json(run / "episodes" / "intervention_analysis" / "submission.json")
        run_reference, report_reference = _run_references(package, run, full_selected)
        run_reference = {"design-10yr": run_reference["design-10yr"]}
        report_reference = {"design-10yr": report_reference["design-10yr"]}
        selected_operations = cast(dict[str, str], intervention["selected_operations"])
        decisions = cast(list[dict[str, Any]], intervention["accepted_decisions"])
        lineage = cast(list[dict[str, str]], intervention["supersession_lineage"])
        claim = cast(dict[str, str], intervention["claim_boundary"])
        visible_source = str(intervention["visible_source_state_sha256"])
        memo = {
            "selected_intervention_id": "emergency_weir_enlargement",
            "visible_source_state_sha256": visible_source,
            "run_reference": copy.deepcopy(run_reference),
            "report_reference": copy.deepcopy(report_reference),
            "decision_ids": {"design-10yr": "decision.design-10yr.intervention"},
            "supersession_lineage": copy.deepcopy(lineage),
            "readiness_decision": "screening_ready",
            "claim_boundary": copy.deepcopy(claim),
        }
        _write_json(
            submission_path,
            {
                "checkpoint_id": "closeout_review",
                "selected_intervention_id": "emergency_weir_enlargement",
                "visible_source_state_sha256": visible_source,
                "selected_operations": selected_operations,
                "run_reference": run_reference,
                "report_reference": report_reference,
                "memo": memo,
                "accepted_decisions": decisions,
                "supersession_lineage": lineage,
                "readiness_decision": "screening_ready",
                "claim_boundary": claim,
            },
        )
        return {"status": "completed"}

    run_evidence_lifecycle(
        package,
        run,
        episode_environment=deterministic_episode_environment(execute),
    )
    result = verify_lifecycle_template(package, run)

    assert result["reward"] <= 0.5
    for gate_id in (
        "operation_evidence_integrity",
        "selective_recomputation",
        "decision_update",
        "intervention_effectiveness",
        "run_propagation",
        "report_propagation",
        "memo_propagation",
        "final_readiness",
    ):
        assert result["gates"][gate_id]["passed"] is False
    assert result["gates"]["intervention_effectiveness"]["failures"] == [
        "emergency_weir_enlargement.major-100yr.evidence_missing"
    ]
