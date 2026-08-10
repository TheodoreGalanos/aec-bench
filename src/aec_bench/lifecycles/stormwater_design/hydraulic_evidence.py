# ABOUTME: Validates hydraulic operation evidence shared by stormwater lifecycle tasks.
# ABOUTME: Owns common scenario records, transaction checks, and canonical evidence loading.

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.runtime.state import (
    LifecycleOperationActionRecord,
    LifecycleOperationOutcome,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.verifier import verify_hydraulic_run

type ScenarioId = Literal["design-10yr", "major-100yr"]
type ReadinessDecision = Literal["screening_ready", "not_screening_ready"]

SCENARIO_IDS: tuple[ScenarioId, ...] = ("design-10yr", "major-100yr")
CALCULATION_OPERATION_IDS = tuple(
    operation_id
    for scenario_id in SCENARIO_IDS
    for operation_id in (
        f"hydrology.{scenario_id}",
        f"detention-outlet.{scenario_id}.declared-outlet",
        f"network-hgl.{scenario_id}.declared-tailwater",
    )
)


class ClaimBoundary(StrictModel):
    evidence_class: Literal["benchmark_owned_synthetic_screening"]
    solver_fidelity: Literal["not_swmm_equivalent"]
    authority_status: Literal["no_authority_approval"]
    standards_status: Literal["no_standards_compliance_claim"]
    project_evidence_status: Literal["not_project_design_evidence"]
    model_evidence_status: Literal["no_model_performance_holdout_or_transfer_result"]
    learning_status: Literal["no_post_training_or_continual_learning_result"]


class ScenarioDecision(StrictModel):
    decision_id: NonEmptyStr
    scenario_id: ScenarioId
    hydrology_action_id: NonEmptyStr
    detention_action_id: NonEmptyStr
    hgl_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    screening_outcome: Literal["criteria_met", "criteria_not_met"]
    failed_criteria: tuple[NonEmptyStr, ...] = ()

    @field_validator("failed_criteria")
    @classmethod
    def validate_failed_criteria(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("failed criteria must be unique and sorted")
        return value


class DecisionSupersession(StrictModel):
    scenario_id: ScenarioId
    superseded_decision_id: NonEmptyStr
    replacement_decision_id: NonEmptyStr


class RunReference(StrictModel):
    selected_operation_action_id: NonEmptyStr
    canonical_detention_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    run_manifest_sha256: NonEmptyStr


class ReportReference(StrictModel):
    selected_operation_action_id: NonEmptyStr
    canonical_hgl_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    report_sha256: NonEmptyStr


@dataclass(frozen=True)
class ScenarioEvidence:
    scenario_id: ScenarioId
    hydrology_action_id: str
    detention_action_id: str
    hgl_action_id: str
    hydraulic_run_id: str
    failed_criteria: tuple[str, ...]
    run_reference: RunReference
    report_reference: ReportReference


def select_operation_actions(
    selected: dict[str, str],
    actions: dict[str, LifecycleOperationActionRecord],
    *,
    checkpoint_id: str,
    expected_operation_ids: set[str],
) -> tuple[dict[str, LifecycleOperationActionRecord], list[str]]:
    failures: list[str] = []
    if set(selected) != expected_operation_ids:
        failures.append(f"{checkpoint_id}.selected_operations.keys")
    resolved: dict[str, LifecycleOperationActionRecord] = {}
    for operation_id, action_id in selected.items():
        action = actions.get(action_id)
        if action is None:
            failures.append(f"{checkpoint_id}.selected_operations.{operation_id}.missing_action")
            continue
        if action.operation_id != operation_id or action.checkpoint_id != checkpoint_id:
            failures.append(f"{checkpoint_id}.selected_operations.{operation_id}.identity")
            continue
        resolved[operation_id] = action
    return resolved, failures


def operation_transaction_failures(
    run: Path,
    actions: Iterable[LifecycleOperationActionRecord],
) -> list[str]:
    failures: list[str] = []
    for action in actions:
        transaction = run / "lifecycle_operations" / action.action_id
        expected_entries = {"request.json", "action.json", "committed.json"}
        if action.outcome == LifecycleOperationOutcome.COMPLETED:
            expected_entries.update({"result-manifest.json", "artifacts"})
        actual_entries = {path.name for path in transaction.iterdir()}
        if actual_entries != expected_entries:
            failures.append(f"{action.action_id}.transaction_inventory")
            continue
        expected_request = {
            "schema_version": "1",
            "action_id": action.action_id,
            "checkpoint_id": action.requested_checkpoint_id,
            "operation_id": action.operation_id,
            "reason": action.reason,
        }
        actual_request = read_json_object(transaction / "request.json")
        supplied_source = actual_request.pop("visible_source_state_sha256", None)
        if actual_request != expected_request or not isinstance(supplied_source, str):
            failures.append(f"{action.action_id}.request")
        elif action.outcome != LifecycleOperationOutcome.REJECTED:
            if supplied_source != action.visible_source_state_before_sha256:
                failures.append(f"{action.action_id}.request_source")
        elif _rejection_projection_sha256(action.operation_id, supplied_source) != action.input_projection_sha256:
            failures.append(f"{action.action_id}.rejection_projection")
        if read_json_object(transaction / "action.json") != action.model_dump(mode="json"):
            failures.append(f"{action.action_id}.action")
        if read_json_object(transaction / "committed.json") != {
            "action_id": action.action_id,
            "status": "committed",
        }:
            failures.append(f"{action.action_id}.commit")
        if action.outcome != LifecycleOperationOutcome.COMPLETED:
            continue
        artifact_prefix = f"lifecycle_operations/{action.action_id}/artifacts/"
        artifact_sha256 = {
            artifact.path.removeprefix(artifact_prefix): artifact.sha256 for artifact in action.artifacts
        }
        if any(artifact.path == artifact.path.removeprefix(artifact_prefix) for artifact in action.artifacts):
            failures.append(f"{action.action_id}.artifact_path")
            continue
        expected_result = {
            "schema_version": "1",
            "action_id": action.action_id,
            "operation_id": action.operation_id,
            "input_projection_sha256": action.input_projection_sha256,
            "physical_source_state_sha256": action.physical_source_state_after_sha256,
            "visible_source_state_sha256": action.visible_source_state_after_sha256,
            "prerequisite_action_ids": list(action.prerequisite_action_ids),
            "artifact_sha256": artifact_sha256,
        }
        if read_json_object(transaction / "result-manifest.json") != expected_result:
            failures.append(f"{action.action_id}.result_manifest")
    return failures


def load_scenario_evidence(
    package: Path,
    run: Path,
    selected: dict[str, LifecycleOperationActionRecord],
) -> tuple[dict[str, ScenarioEvidence], list[str]]:
    evidence: dict[str, ScenarioEvidence] = {}
    failures: list[str] = []
    for scenario_id in SCENARIO_IDS:
        operation_ids = (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        )
        if any(operation_id not in selected for operation_id in operation_ids):
            failures.append(f"{scenario_id}.selected_operation_chain")
            continue
        hydrology_action = _canonical_action(selected[operation_ids[0]], run)
        detention_action = _canonical_action(selected[operation_ids[1]], run)
        hgl_action = _canonical_action(selected[operation_ids[2]], run)
        try:
            scenario_evidence = _verify_scenario_evidence(
                package,
                run,
                scenario_id,
                selected[operation_ids[1]],
                selected[operation_ids[2]],
                hydrology_action,
                detention_action,
                hgl_action,
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            failures.append(f"{scenario_id}.integrity:{exc}")
            continue
        evidence[scenario_id] = scenario_evidence
    return evidence, failures


def mapping_failures(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    return [] if actual == expected else [f"closeout_review.{label}"]


def expected_readiness(decisions: dict[str, ScenarioDecision]) -> ReadinessDecision:
    return (
        "not_screening_ready"
        if any(item.screening_outcome == "criteria_not_met" for item in decisions.values())
        else "screening_ready"
    )


def verification_gate(failures: list[str]) -> dict[str, Any]:
    unique = sorted(set(failures))
    return {"passed": not unique, "score": 1.0 if not unique else 0.0, "failures": unique}


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_action(
    selected: LifecycleOperationActionRecord,
    run: Path,
) -> LifecycleOperationActionRecord:
    action_id = selected.retained_from_action_id or selected.action_id
    return LifecycleOperationActionRecord.model_validate(
        read_json_object(run / "lifecycle_operations" / action_id / "action.json")
    )


def _verify_scenario_evidence(
    package: Path,
    run: Path,
    scenario_id: ScenarioId,
    selected_detention: LifecycleOperationActionRecord,
    selected_hgl: LifecycleOperationActionRecord,
    hydrology_action: LifecycleOperationActionRecord,
    detention_action: LifecycleOperationActionRecord,
    hgl_action: LifecycleOperationActionRecord,
) -> ScenarioEvidence:
    detention_root = run / "lifecycle_operations" / detention_action.action_id / "artifacts"
    hgl_root = run / "lifecycle_operations" / hgl_action.action_id / "artifacts"
    hydraulic_run = detention_root / "hydraulic-run"
    hydraulic_package = _package_for_physical_source(package, detention_action.physical_source_state_after_sha256)
    verification = verify_hydraulic_run(hydraulic_package, hydraulic_run)
    result = read_json_object(hydraulic_run / "results.json")
    time_series = read_json_object(hydraulic_run / "timeseries.json")
    hydrology = read_json_object(
        run / "lifecycle_operations" / hydrology_action.action_id / "artifacts" / "hydrology.json"
    )
    detention = read_json_object(detention_root / "detention-outlet.json")
    hgl = read_json_object(hgl_root / "network-hgl.json")
    if result["scenario_id"] != scenario_id or hydrology["scenario_id"] != scenario_id:
        raise ValueError("scenario identity mismatch")
    expected_hydrograph = [
        {"time_s": step["time_s"], "inflow_m3_s": step["total_inflow_m3_s"]} for step in time_series["steps"]
    ]
    if (
        hydrology["peak_total_inflow_m3_s"] != result["peak_total_inflow_m3_s"]
        or hydrology["hydrograph"] != expected_hydrograph
    ):
        raise ValueError("hydrology projection mismatch")
    criteria = dict(detention["criteria"]) | dict(hgl["criteria"])
    expected_criteria = {
        criterion: gate.passed for criterion, gate in verification.gates.items() if criterion != "reported_criteria"
    }
    if criteria != expected_criteria:
        raise ValueError("stage criteria do not reconcile with hydraulic verification")
    if detention["hydraulic_run_id"] != result["run_id"] or hgl["hydraulic_run_id"] != result["run_id"]:
        raise ValueError("stage run identity mismatch")
    report = hgl_root / "report.md"
    if report.read_bytes() != (hydraulic_run / "report.md").read_bytes():
        raise ValueError("HGL report does not match the coupled run")
    failed = tuple(sorted(criterion for criterion, passed in criteria.items() if not passed))
    return ScenarioEvidence(
        scenario_id=scenario_id,
        hydrology_action_id=hydrology_action.action_id,
        detention_action_id=detention_action.action_id,
        hgl_action_id=hgl_action.action_id,
        hydraulic_run_id=str(result["run_id"]),
        failed_criteria=failed,
        run_reference=RunReference(
            selected_operation_action_id=selected_detention.action_id,
            canonical_detention_action_id=detention_action.action_id,
            hydraulic_run_id=str(result["run_id"]),
            run_manifest_sha256=file_sha256(hydraulic_run / "run-manifest.json"),
        ),
        report_reference=ReportReference(
            selected_operation_action_id=selected_hgl.action_id,
            canonical_hgl_action_id=hgl_action.action_id,
            hydraulic_run_id=str(result["run_id"]),
            report_sha256=file_sha256(report),
        ),
    )


def _package_for_physical_source(package: Path, source_sha256: str) -> Path:
    candidates = _declared_hydraulic_packages(package)
    for candidate in candidates:
        if file_sha256(candidate / "source" / "source-state.json") == source_sha256:
            return candidate
    raise ValueError("operation physical source does not match an embedded hydraulic package")


def _declared_hydraulic_packages(package: Path) -> tuple[Path, ...]:
    manifest = read_json_object(package / "hidden" / "lifecycle-operation-resolutions.json")
    raw_paths: list[str] = []
    for key in ("baseline_package_path", "revision_package_path", "problem_package_path"):
        value = manifest.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError("hydraulic package path is invalid")
            raw_paths.append(value)
    intervention_paths = manifest.get("intervention_package_paths", {})
    if not isinstance(intervention_paths, dict) or any(
        not isinstance(value, str) for value in intervention_paths.values()
    ):
        raise ValueError("hydraulic intervention package paths are invalid")
    raw_paths.extend(str(intervention_paths[key]) for key in sorted(intervention_paths))
    if not raw_paths or len(raw_paths) != len(set(raw_paths)):
        raise ValueError("hydraulic package paths are absent or duplicated")
    package_root = package.resolve()
    candidates = tuple(package / raw_path for raw_path in raw_paths)
    if any(not candidate.resolve().is_relative_to(package_root) for candidate in candidates):
        raise ValueError("hydraulic package path escapes the lifecycle package")
    return candidates


def _rejection_projection_sha256(operation_id: str, supplied_visible_source_sha256: str) -> str:
    payload = json.dumps(
        {
            "schema_version": "1",
            "operation_id": operation_id,
            "supplied_visible_source_sha256": supplied_visible_source_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
