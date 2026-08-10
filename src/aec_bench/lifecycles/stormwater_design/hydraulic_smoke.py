# ABOUTME: Provides deterministic hydraulic evidence helpers for stormwater lifecycle smoke runs.
# ABOUTME: Keeps shared qualification behaviour outside either concrete task smoke driver.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from aec_bench.lifecycles.runtime.lifecycle import execute_lifecycle_operation, read_evidence_lifecycle_state
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import SCENARIO_IDS, ClaimBoundary

CLAIM_BOUNDARY = ClaimBoundary(
    evidence_class="benchmark_owned_synthetic_screening",
    solver_fidelity="not_swmm_equivalent",
    authority_status="no_authority_approval",
    standards_status="no_standards_compliance_claim",
    project_evidence_status="not_project_design_evidence",
    model_evidence_status="no_model_performance_holdout_or_transfer_result",
    learning_status="no_post_training_or_continual_learning_result",
).model_dump(mode="json")


def execute_calculation_operations(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    session_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_IDS:
        for operation_id in (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        ):
            actions[operation_id] = execute_operation(
                package,
                run,
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                session_id=session_id,
                operation_resolver=operation_resolver,
            )
    return actions


def execute_operation(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    session_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    return execute_lifecycle_operation(
        package,
        run,
        operation_resolver=operation_resolver,
        checkpoint_id=checkpoint_id,
        operation_id=operation_id,
        visible_source_state_sha256=visible_source_sha256(run),
        reason=f"Smoke {operation_id} against the declared source.",
        session_id=session_id,
    )


def build_scenario_decision(
    run: Path,
    actions: dict[str, dict[str, Any]],
    *,
    scenario_id: str,
    phase: str,
) -> dict[str, Any]:
    hydrology = _origin_action_id(actions[f"hydrology.{scenario_id}"])
    detention = _origin_action_id(actions[f"detention-outlet.{scenario_id}.declared-outlet"])
    hgl = _origin_action_id(actions[f"network-hgl.{scenario_id}.declared-tailwater"])
    detention_result = read_json_object(
        run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json"
    )
    hgl_result = read_json_object(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
    criteria = dict(detention_result["criteria"]) | dict(hgl_result["criteria"])
    failed_criteria = sorted(key for key, passed in criteria.items() if not passed)
    return {
        "decision_id": f"decision.{scenario_id}.{phase}",
        "scenario_id": scenario_id,
        "hydrology_action_id": hydrology,
        "detention_action_id": detention,
        "hgl_action_id": hgl,
        "hydraulic_run_id": detention_result["hydraulic_run_id"],
        "screening_outcome": "criteria_not_met" if failed_criteria else "criteria_met",
        "failed_criteria": failed_criteria,
    }


def selected_operations(actions: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {operation_id: str(action["action_id"]) for operation_id, action in sorted(actions.items())}


def readiness(decisions: list[dict[str, Any]]) -> str:
    return (
        "not_screening_ready"
        if any(decision["screening_outcome"] == "criteria_not_met" for decision in decisions)
        else "screening_ready"
    )


def run_references(
    package: Path,
    run: Path,
    selected: dict[str, str],
    *,
    operation_resolver: LifecycleOperationResolver,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    actions_by_id = {
        str(action["action_id"]): action
        for checkpoint in read_evidence_lifecycle_state(
            package,
            run,
            operation_resolver=operation_resolver,
        )["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
    }
    runs: dict[str, dict[str, str]] = {}
    reports: dict[str, dict[str, str]] = {}
    for scenario_id in SCENARIO_IDS:
        detention_operation = f"detention-outlet.{scenario_id}.declared-outlet"
        hgl_operation = f"network-hgl.{scenario_id}.declared-tailwater"
        selected_detention = actions_by_id[selected[detention_operation]]
        selected_hgl = actions_by_id[selected[hgl_operation]]
        detention = _origin_action_id(selected_detention)
        hgl = _origin_action_id(selected_hgl)
        detention_result = read_json_object(
            run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json"
        )
        hgl_result = read_json_object(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
        report = run / "lifecycle_operations" / hgl / "artifacts" / "report.md"
        runs[scenario_id] = {
            "selected_operation_action_id": str(selected_detention["action_id"]),
            "canonical_detention_action_id": detention,
            "hydraulic_run_id": str(detention_result["hydraulic_run_id"]),
            "run_manifest_sha256": str(detention_result["hydraulic_run_manifest_sha256"]),
        }
        reports[scenario_id] = {
            "selected_operation_action_id": str(selected_hgl["action_id"]),
            "canonical_hgl_action_id": hgl,
            "hydraulic_run_id": str(hgl_result["hydraulic_run_id"]),
            "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        }
    return runs, reports


def visible_source_sha256(run: Path) -> str:
    source = read_json_object(run / "workspace" / "operations" / "current-source.json")
    return str(source["visible_source_state_sha256"])


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _origin_action_id(action: dict[str, Any]) -> str:
    return str(action.get("retained_from_action_id") or action["action_id"])
