# ABOUTME: Provides deterministic hydraulic evidence helpers for stormwater lifecycle smoke runs.
# ABOUTME: Keeps shared qualification behaviour outside either concrete task smoke driver.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.lifecycles.runtime.lifecycle import execute_lifecycle_operation
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import CLAIM_BOUNDARY as CLAIM_BOUNDARY
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import SCENARIO_IDS


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
    detention = _origin_action_id(actions[f"detention-outlet.{scenario_id}.declared-outlet"])
    hgl = _origin_action_id(actions[f"network-hgl.{scenario_id}.declared-tailwater"])
    detention_result = read_json_object(
        run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json"
    )
    hgl_result = read_json_object(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
    criteria = dict(detention_result["criteria"]) | dict(hgl_result["criteria"])
    failed_criteria = sorted(key for key, passed in criteria.items() if not passed)
    return {
        "scenario_id": scenario_id,
        "evidence_checkpoint": f"{phase}_analysis",
        "screening_outcome": "criteria_not_met" if failed_criteria else "criteria_met",
        "failed_criteria": failed_criteria,
    }


def readiness(decisions: list[dict[str, Any]]) -> str:
    return (
        "not_screening_ready"
        if any(decision["screening_outcome"] == "criteria_not_met" for decision in decisions)
        else "screening_ready"
    )


def source_revision(run: Path) -> str:
    source = read_json_object(run / "workspace" / "operations" / "current-source.json")
    return str(source["revision_id"])


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
