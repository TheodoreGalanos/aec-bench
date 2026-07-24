# ABOUTME: Resolves declared lifecycle operations against immutable PR18 hydraulic packages.
# ABOUTME: Computes operation-specific dependency identities and bounded model-visible artifacts.

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle_state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationPlan,
    LifecycleOperationPrerequisiteError,
    LifecycleOperationSourceContext,
    current_lifecycle_operation_action,
)
from aec_bench.task_world_templates.contracts import EvidenceLifecycleSpec, LifecycleOperationSpec
from aec_bench.task_world_templates.hydraulics import (
    build_hydraulic_run_request,
    execute_hydraulic_world,
)
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256
from aec_bench.task_world_templates.hydraulics.kernel import rational_peak_flow

_DETENTION_CRITERION_IDS = {
    "continuity",
    "design_total_release",
    "emergency_weir_activated",
    "emergency_weir_inactive",
    "freeboard",
    "outlet_convergence",
    "storage_capacity",
}
_NETWORK_CRITERION_IDS = {
    "hgl_clearance",
    "pipe_capacity",
    "pipe_velocity",
}
_SOURCE_TRANSITION_KINDS = {
    "activate_source_intervention",
    "request_source_revision",
}


class Ssc03HydraulicOperationResolver:
    """Resolve the public SSC-03 operation graph without exposing hidden paths."""

    def __init__(self, package_dir: Path, run_dir: Path) -> None:
        self.package_dir = Path(package_dir)
        self.run_dir = Path(run_dir)
        self._manifest = _read_json(self.package_dir / "hidden" / "lifecycle-operation-resolutions.json")
        self._resolutions = {item["operation_id"]: item for item in self._manifest["operations"]}
        self._operation_specs = _load_operation_specs(self.package_dir / "lifecycle.json")
        if set(self._resolutions) != set(self._operation_specs):
            raise EvidenceLifecycleError("operation resolver does not match the public operation catalogue")
        self._configure_source_packages()
        for hydraulic_package in self._source_packages():
            build_hydraulic_run_request(hydraulic_package, scenario_id="design-10yr")

    def _configure_source_packages(self) -> None:
        """Bind the fixed baseline and revision packages for the calibration lifecycle."""
        self._baseline = self.package_dir / str(self._manifest["baseline_package_path"])
        self._revision = self.package_dir / str(self._manifest["revision_package_path"])

    def _source_packages(self) -> tuple[Path, ...]:
        """Return every immutable source package the resolver may activate."""
        return (self._baseline, self._revision)

    def _source_transition_operation_ids(self) -> frozenset[str]:
        """Return operation IDs that change the current source without calculation recursion."""
        return frozenset({"source-revision.current"})

    def _source_transition_kinds(self) -> frozenset[str]:
        """Return operation kinds handled by the task-specific source transition hook."""
        return frozenset({"request_source_revision"})

    def current_source(
        self,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationSourceContext:
        activated = next(
            (
                action
                for action in reversed(actions)
                if action.operation_kind == "request_source_revision"
                and action.outcome == LifecycleOperationOutcome.COMPLETED
            ),
            None,
        )
        revision_id = str(self._manifest["variant_id"]) if activated is not None else "baseline"
        package = self._revision if activated is not None else self._baseline
        return _source_context(package, revision_id=revision_id)

    def plan(
        self,
        operation: LifecycleOperationSpec,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationPlan:
        return self._plan_operation(
            operation,
            actions,
            source_before=self.current_source(actions),
            resolving=(),
        )

    def _plan_source_transition(
        self,
        operation: LifecycleOperationSpec,
        resolution: dict[str, Any],
        actions: Sequence[LifecycleOperationActionRecord],
        *,
        source_before: LifecycleOperationSourceContext,
    ) -> LifecycleOperationPlan:
        """Plan the calibration lifecycle's one fixed source revision."""
        del actions
        source_after = _source_context(self._revision, revision_id=str(self._manifest["variant_id"]))
        payload = {
            "schema_version": "1",
            "operation_id": operation.operation_id,
            "kind": operation.kind,
            "revision_id": resolution["revision_id"],
            "source_after": source_after.visible_source_state_sha256,
            "physical_source_after": source_after.physical_source_state_sha256,
        }
        return LifecycleOperationPlan(
            operation_id=operation.operation_id,
            operation_kind=operation.kind,
            disposition=LifecycleOperationDisposition.ACTIVATED,
            source_before=source_before,
            source_after=source_after,
            input_projection_sha256=canonical_json_sha256(payload),
            prerequisite_action_ids=(),
            model_visible_artifact_paths=("source-identity.json", "source-state.json"),
            payload=payload,
        )

    def _write_source_transition_artifacts(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
        """Publish the selected source state and its bounded visible identity."""
        _write_json(artifact_dir / "source-state.json", plan.source_after.source_state)
        _write_json(
            artifact_dir / "source-identity.json",
            _source_identity_payload(plan.source_after),
        )

    def _plan_operation(
        self,
        operation: LifecycleOperationSpec,
        actions: Sequence[LifecycleOperationActionRecord],
        *,
        source_before: LifecycleOperationSourceContext,
        resolving: tuple[str, ...],
    ) -> LifecycleOperationPlan:
        if operation.operation_id in resolving:
            raise EvidenceLifecycleError("operation prerequisite graph contains a cycle")
        resolution = self._resolutions.get(operation.operation_id)
        if resolution is None or resolution.get("kind") != operation.kind:
            raise EvidenceLifecycleError("operation resolver does not match the public operation catalogue")
        if operation.kind in self._source_transition_kinds():
            return self._plan_source_transition(
                operation,
                resolution,
                actions,
                source_before=source_before,
            )
        calculation_prerequisites = tuple(
            prerequisite_id
            for prerequisite_id in operation.prerequisite_operation_ids
            if prerequisite_id not in self._source_transition_operation_ids()
        )
        prerequisite_action_ids_list: list[str] = []
        visible_artifacts: tuple[str, ...]
        for prerequisite_id in calculation_prerequisites:
            prerequisite_spec = self._operation_specs.get(prerequisite_id)
            if prerequisite_spec is None:
                raise EvidenceLifecycleError("operation prerequisite is absent from the public catalogue")
            prerequisite_plan = self._plan_operation(
                prerequisite_spec,
                actions,
                source_before=source_before,
                resolving=resolving + (operation.operation_id,),
            )
            prerequisite_action = current_lifecycle_operation_action(actions, prerequisite_plan)
            if prerequisite_action is None:
                raise LifecycleOperationPrerequisiteError("operation prerequisites are incomplete")
            prerequisite_action_ids_list.append(prerequisite_action.action_id)
        prerequisite_action_ids = tuple(prerequisite_action_ids_list)
        if operation.kind == "run_hydrology":
            source_after = source_before
            scenario_id = str(resolution["scenario_id"])
            scenario = _selected_scenario(source_before.source_state, scenario_id)
            payload = {
                "schema_version": "1",
                "operation_id": operation.operation_id,
                "kind": operation.kind,
                "catchments": source_before.source_state["payload"]["catchments"],
                "scenario": scenario,
                "engine": _read_json(source_before.package_dir / "engine" / "identity.json"),
            }
            disposition = LifecycleOperationDisposition.COMPUTED
            visible_artifacts = ("hydrology.json",)
        elif operation.kind == "run_detention_outlet":
            source_after = source_before
            scenario_id = str(resolution["scenario_id"])
            scenario = _selected_scenario(source_before.source_state, scenario_id)
            hydrology_action = _action_by_id(actions, prerequisite_action_ids[0])
            payload = {
                "schema_version": "1",
                "operation_id": operation.operation_id,
                "kind": operation.kind,
                "hydrology": {
                    "action_id": hydrology_action.action_id,
                    "input_projection_sha256": hydrology_action.input_projection_sha256,
                    "artifact_sha256": [artifact.sha256 for artifact in hydrology_action.artifacts],
                },
                "scenario": scenario,
                "basin": source_before.source_state["payload"]["basin"],
                "outlet": source_before.source_state["payload"]["outlet"],
                "network": source_before.source_state["payload"]["network"],
                "criteria": source_before.source_state["payload"]["criteria"],
                "engine": _read_json(source_before.package_dir / "engine" / "identity.json"),
            }
            disposition = LifecycleOperationDisposition.COMPUTED
            visible_artifacts = ("detention-outlet.json",)
        elif operation.kind == "run_network_hgl":
            source_after = source_before
            detention_action = _action_by_id(actions, prerequisite_action_ids[0])
            payload = {
                "schema_version": "1",
                "operation_id": operation.operation_id,
                "kind": operation.kind,
                "detention_action_id": detention_action.action_id,
                "detention_result_manifest_sha256": detention_action.result_manifest_sha256,
                "network": source_before.source_state["payload"]["network"],
                "boundary_id": resolution["boundary_id"],
            }
            disposition = LifecycleOperationDisposition.COMPUTED
            visible_artifacts = ("network-hgl.json", "report.md")
        else:
            raise EvidenceLifecycleError(f"operation kind is not implemented yet: {operation.kind}")
        return LifecycleOperationPlan(
            operation_id=operation.operation_id,
            operation_kind=operation.kind,
            disposition=disposition,
            source_before=source_before,
            source_after=source_after,
            input_projection_sha256=canonical_json_sha256(payload),
            prerequisite_action_ids=prerequisite_action_ids,
            model_visible_artifact_paths=visible_artifacts,
            payload=payload,
        )

    def execute(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if plan.operation_kind in self._source_transition_kinds():
            self._write_source_transition_artifacts(plan, artifact_dir)
            return
        if plan.operation_kind == "run_hydrology":
            scenario = plan.payload["scenario"]
            catchments = plan.payload["catchments"]
            adjusted_intensity = float(scenario["rainfall_intensity_mm_h"]) * float(scenario["climate_factor"])
            peaks = {
                str(catchment["catchment_id"]): rational_peak_flow(
                    runoff_coefficient=float(catchment["runoff_coefficient"]),
                    rainfall_intensity_mm_h=adjusted_intensity,
                    area_ha=float(catchment["area_ha"]),
                )
                for catchment in catchments
            }
            peak_total = sum(peaks.values())
            duration = int(scenario["storm_duration_s"])
            time_step = int(scenario["time_step_s"])
            steps = [
                {
                    "time_s": (index + 1) * time_step,
                    "inflow_m3_s": _rounded(
                        peak_total * _triangular_fraction(index * time_step + time_step / 2.0, duration)
                    ),
                }
                for index in range(duration // time_step)
            ]
            _write_json(
                artifact_dir / "hydrology.json",
                {
                    "schema_version": "1",
                    "operation_id": plan.operation_id,
                    "scenario_id": scenario["scenario_id"],
                    "visible_source_state_sha256": plan.source_before.visible_source_state_sha256,
                    "physical_source_state_sha256": plan.source_before.physical_source_state_sha256,
                    "input_projection_sha256": plan.input_projection_sha256,
                    "catchment_peak_flows_m3_s": {key: _rounded(value) for key, value in sorted(peaks.items())},
                    "peak_total_inflow_m3_s": _rounded(peak_total),
                    "hydrograph": steps,
                },
            )
            return
        if plan.operation_kind == "run_detention_outlet":
            scenario_id = str(plan.payload["scenario"]["scenario_id"])
            request = build_hydraulic_run_request(plan.source_before.package_dir, scenario_id=scenario_id)
            hydraulic_run = execute_hydraulic_world(
                plan.source_before.package_dir,
                artifact_dir / "hydraulic-run",
                request,
            )
            result = _read_json(hydraulic_run / "results.json")
            detention_criteria, _network_criteria = _partition_criteria(result["criteria"])
            run_manifest_sha256 = _sha256(hydraulic_run / "run-manifest.json")
            _write_json(
                artifact_dir / "detention-outlet.json",
                {
                    "schema_version": "1",
                    "operation_id": plan.operation_id,
                    "scenario_id": scenario_id,
                    "visible_source_state_sha256": plan.source_before.visible_source_state_sha256,
                    "physical_source_state_sha256": plan.source_before.physical_source_state_sha256,
                    "input_projection_sha256": plan.input_projection_sha256,
                    "hydrology_action_id": plan.prerequisite_action_ids[0],
                    "hydraulic_run_id": request.run_id,
                    "hydraulic_run_manifest_sha256": run_manifest_sha256,
                    "peak_orifice_flow_m3_s": result["peak_orifice_flow_m3_s"],
                    "peak_weir_flow_m3_s": result["peak_weir_flow_m3_s"],
                    "peak_structured_outflow_m3_s": result["peak_structured_outflow_m3_s"],
                    "peak_total_outflow_m3_s": result["peak_total_outflow_m3_s"],
                    "maximum_storage_m3": result["maximum_storage_m3"],
                    "maximum_water_surface_elevation_m": result["maximum_water_surface_elevation_m"],
                    "minimum_freeboard_m": result["minimum_freeboard_m"],
                    "criteria": detention_criteria,
                },
            )
            return
        if plan.operation_kind == "run_network_hgl":
            detention_action_id = str(plan.payload["detention_action_id"])
            detention_root = self.run_dir / "lifecycle_operations" / detention_action_id / "artifacts"
            result = _read_json(detention_root / "hydraulic-run" / "results.json")
            _detention_criteria, network_criteria = _partition_criteria(result["criteria"])
            run_manifest_sha256 = _sha256(detention_root / "hydraulic-run" / "run-manifest.json")
            report = detention_root / "hydraulic-run" / "report.md"
            _write_json(
                artifact_dir / "network-hgl.json",
                {
                    "schema_version": "1",
                    "operation_id": plan.operation_id,
                    "scenario_id": result["scenario_id"],
                    "visible_source_state_sha256": plan.source_before.visible_source_state_sha256,
                    "physical_source_state_sha256": plan.source_before.physical_source_state_sha256,
                    "input_projection_sha256": plan.input_projection_sha256,
                    "detention_action_id": detention_action_id,
                    "hydraulic_run_id": result["run_id"],
                    "hydraulic_run_manifest_sha256": run_manifest_sha256,
                    "maximum_node_hgl_m": result["maximum_node_hgl_m"],
                    "minimum_hgl_clearance_m": result["minimum_hgl_clearance_m"],
                    "maximum_pipe_velocity_m_s": result["maximum_pipe_velocity_m_s"],
                    "pipe_capacity_m3_s": result["pipe_capacity_m3_s"],
                    "criteria": network_criteria,
                },
            )
            (artifact_dir / "report.md").write_bytes(report.read_bytes())
            return
        raise EvidenceLifecycleError(f"operation execution is not implemented: {plan.operation_kind}")


def _action_by_id(
    actions: Sequence[LifecycleOperationActionRecord],
    action_id: str,
) -> LifecycleOperationActionRecord:
    try:
        return next(action for action in actions if action.action_id == action_id)
    except StopIteration as exc:
        raise EvidenceLifecycleError("operation prerequisite action is missing") from exc


def _load_operation_specs(path: Path) -> dict[str, LifecycleOperationSpec]:
    lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(path))
    declared_operations = [
        operation
        for checkpoint in lifecycle.checkpoints
        if checkpoint.conditional_operations is not None
        for operation in checkpoint.conditional_operations.operations
    ]
    source_transition_ids = {
        operation.operation_id for operation in declared_operations if operation.kind in _SOURCE_TRANSITION_KINDS
    }
    operation_specs: dict[str, LifecycleOperationSpec] = {}
    for operation in declared_operations:
        calculation_prerequisites = tuple(
            prerequisite_id
            for prerequisite_id in operation.prerequisite_operation_ids
            if prerequisite_id not in source_transition_ids
        )
        normalized = operation.model_copy(
            update={"prerequisite_operation_ids": calculation_prerequisites},
            deep=True,
        )
        existing = operation_specs.get(operation.operation_id)
        if existing is not None and (
            existing.kind != normalized.kind
            or existing.prerequisite_operation_ids != normalized.prerequisite_operation_ids
        ):
            raise EvidenceLifecycleError("operation definition changes across public checkpoints")
        operation_specs[operation.operation_id] = normalized
    return operation_specs


def _source_context(package_dir: Path, *, revision_id: str) -> LifecycleOperationSourceContext:
    source_path = package_dir / "source" / "source-state.json"
    source = _read_json(source_path)
    physical_sha256 = _sha256(source_path)
    visible_sha256 = canonical_json_sha256(
        {
            "schema_version": "1",
            "physical_source_state_sha256": physical_sha256,
            "revision_id": revision_id,
        }
    )
    return LifecycleOperationSourceContext(
        revision_id=revision_id,
        package_dir=package_dir,
        physical_source_state_sha256=physical_sha256,
        visible_source_state_sha256=visible_sha256,
        source_state=source,
    )


def _source_identity_payload(source: LifecycleOperationSourceContext) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "revision_id": source.revision_id,
        "physical_source_state_sha256": source.physical_source_state_sha256,
        "visible_source_state_sha256": source.visible_source_state_sha256,
        "source_state": source.source_state,
    }


def _selected_scenario(source: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    try:
        return next(item for item in source["payload"]["scenarios"] if item["scenario_id"] == scenario_id)
    except StopIteration as exc:
        raise EvidenceLifecycleError("operation scenario is not declared by the active hydraulic source") from exc


def _triangular_fraction(time_s: float, duration_s: int) -> float:
    midpoint_s = duration_s / 2.0
    if time_s <= 0.0 or time_s >= duration_s:
        return 0.0
    if time_s <= midpoint_s:
        return time_s / midpoint_s
    return (duration_s - time_s) / midpoint_s


def _rounded(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if rounded == -0.0 else rounded


def _partition_criteria(criteria: dict[str, Any]) -> tuple[dict[str, bool], dict[str, bool]]:
    known = _DETENTION_CRITERION_IDS | _NETWORK_CRITERION_IDS
    unknown = set(criteria) - known
    if unknown:
        raise EvidenceLifecycleError("hydraulic result contains an unassigned criterion: " + ", ".join(sorted(unknown)))
    detention = {key: bool(value) for key, value in sorted(criteria.items()) if key in _DETENTION_CRITERION_IDS}
    network = {key: bool(value) for key, value in sorted(criteria.items()) if key in _NETWORK_CRITERION_IDS}
    return detention, network


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvidenceLifecycleError(f"expected JSON object: {path}")
    return payload
