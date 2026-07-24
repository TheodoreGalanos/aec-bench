# ABOUTME: Tests that an archived intervention selection controls the later hydraulic source transition.
# ABOUTME: Proves hydrology is reused while outlet-dependent evidence recomputes against the chosen option.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention import TEMPLATE_ID

SCENARIO_IDS = ("design-10yr", "major-100yr")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _visible_source_sha256(run: Path) -> str:
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
        visible_source_state_sha256=_visible_source_sha256(run),
        reason=f"Exercise {operation_id} against the declared source.",
        session_id=session_id,
    )


def _execute_scenario_chains(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    session_id: str,
) -> dict[str, dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_IDS:
        for operation_id in (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        ):
            actions[operation_id] = _execute(
                package,
                run,
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                session_id=session_id,
            )
    return actions


def _archive_problem_analysis(package: Path, run: Path) -> dict[str, dict[str, Any]]:
    context = prepare_evidence_checkpoint(package, run)
    assert context["checkpoint_id"] == "problem_analysis"
    session_id = "problem.session-001"
    open_checkpoint_attempt(package, run, session_id=session_id, execution_mode="fresh_context")
    actions = _execute_scenario_chains(
        package,
        run,
        checkpoint_id="problem_analysis",
        session_id=session_id,
    )
    _write_json(
        run / "workspace" / "submissions" / "problem_analysis.json",
        {
            "checkpoint_id": "problem_analysis",
            "visible_source_state_sha256": _visible_source_sha256(run),
            "selected_operations": {key: value["action_id"] for key, value in actions.items()},
            "accepted_decisions": [],
            "readiness_decision": "not_screening_ready",
            "claim_boundary": {},
        },
    )
    submit_evidence_checkpoint(package, run)
    return actions


def _archive_selection(package: Path, run: Path, intervention_id: str) -> str:
    context = prepare_evidence_checkpoint(package, run)
    assert context["checkpoint_id"] == "intervention_selection"
    submission = run / "workspace" / "submissions" / "intervention_selection.json"
    _write_json(
        submission,
        {
            "checkpoint_id": "intervention_selection",
            "visible_source_state_sha256": _visible_source_sha256(run),
            "selected_intervention_id": intervention_id,
            "selection_basis": "Select the bounded outlet response for coupled verification.",
            "claim_boundary": {},
        },
    )
    submit_evidence_checkpoint(package, run)
    archived = run / "episodes" / "intervention_selection" / "submission.json"
    return hashlib.sha256(archived.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "intervention_id",
    ["controlled_orifice_resize", "emergency_weir_enlargement"],
)
def test_archived_selection_controls_source_and_selective_recomputation(
    tmp_path: Path,
    intervention_id: str,
) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    run = tmp_path / "run"
    problem_actions = _archive_problem_analysis(package, run)
    selection_sha256 = _archive_selection(package, run, intervention_id)
    context = prepare_evidence_checkpoint(package, run)
    assert context["checkpoint_id"] == "intervention_analysis"
    problem_source_sha256 = str(
        _read_json(run / "workspace" / "hydraulics" / "current-source.json")["physical_source_state_sha256"]
    )
    session_id = "intervention.session-001"
    open_checkpoint_attempt(package, run, session_id=session_id, execution_mode="fresh_context")

    activation = _execute(
        package,
        run,
        checkpoint_id="intervention_analysis",
        operation_id="source-intervention.selected",
        session_id=session_id,
    )
    option_source = (
        package
        / "hidden"
        / "hydraulic"
        / "packages"
        / "interventions"
        / intervention_id
        / "source"
        / "source-state.json"
    )

    assert activation["outcome"] == "completed"
    assert activation["disposition"] == "activated"
    assert activation["physical_source_state_before_sha256"] == problem_source_sha256
    assert activation["physical_source_state_after_sha256"] == hashlib.sha256(option_source.read_bytes()).hexdigest()
    source_identity = _read_json(
        run / "lifecycle_operations" / str(activation["action_id"]) / "artifacts" / "source-identity.json"
    )
    assert source_identity["revision_id"] == intervention_id
    assert source_identity["selection_submission_sha256"] == selection_sha256

    current_actions = _execute_scenario_chains(
        package,
        run,
        checkpoint_id="intervention_analysis",
        session_id=session_id,
    )
    for scenario_id in SCENARIO_IDS:
        hydrology = current_actions[f"hydrology.{scenario_id}"]
        detention = current_actions[f"detention-outlet.{scenario_id}.declared-outlet"]
        hgl = current_actions[f"network-hgl.{scenario_id}.declared-tailwater"]
        assert hydrology["outcome"] == "already_current"
        assert hydrology["retained_from_action_id"] == problem_actions[f"hydrology.{scenario_id}"]["action_id"]
        assert hydrology["budget_consumed"] == 0
        assert detention["outcome"] == "completed"
        assert detention["budget_consumed"] == 1
        assert hgl["outcome"] == "completed"
        assert hgl["budget_consumed"] == 1


def test_undeclared_archived_selection_fails_before_intervention_release(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    run = tmp_path / "run"
    _archive_problem_analysis(package, run)
    _archive_selection(package, run, "invented_outlet_option")

    with pytest.raises(EvidenceLifecycleError, match="selection is not declared"):
        prepare_evidence_checkpoint(package, run)


def test_archived_selection_cannot_be_changed_after_submission(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    run = tmp_path / "run"
    _archive_problem_analysis(package, run)
    _archive_selection(package, run, "controlled_orifice_resize")
    archived = run / "episodes" / "intervention_selection" / "submission.json"
    payload = _read_json(archived)
    payload["selection_basis"] = "Change the archived choice after submission."
    _write_json(archived, payload)

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed"):
        prepare_evidence_checkpoint(package, run)


def test_selection_tampering_after_checkpoint_release_cannot_activate_an_option(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(get_template(TEMPLATE_ID), tmp_path / "package")
    run = tmp_path / "run"
    _archive_problem_analysis(package, run)
    _archive_selection(package, run, "controlled_orifice_resize")
    context = prepare_evidence_checkpoint(package, run)
    assert context["checkpoint_id"] == "intervention_analysis"
    session_id = "intervention.session-001"
    open_checkpoint_attempt(package, run, session_id=session_id, execution_mode="fresh_context")
    archived = run / "episodes" / "intervention_selection" / "submission.json"
    original = archived.read_bytes()
    payload = _read_json(archived)
    payload["selected_intervention_id"] = "emergency_weir_enlargement"
    _write_json(archived, payload)

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed"):
        _execute(
            package,
            run,
            checkpoint_id="intervention_analysis",
            operation_id="source-intervention.selected",
            session_id=session_id,
        )

    archived.write_bytes(original)
    state = read_evidence_lifecycle_state(package, run)
    checkpoint = next(item for item in state["checkpoint_runs"] if item["checkpoint_id"] == "intervention_analysis")
    assert checkpoint["operation_actions"] == []
    assert checkpoint["operation_budget_remaining"] == 7
