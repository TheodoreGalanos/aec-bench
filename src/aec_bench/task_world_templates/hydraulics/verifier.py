# ABOUTME: Independently verifies hydraulic run identities, artifacts, calculations, and criteria.
# ABOUTME: Rejects tampering before considering any pass flag stored in generated reports.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts import validators as validators_module
from aec_bench.task_world_templates.hydraulics import contracts as contracts_module
from aec_bench.task_world_templates.hydraulics import identity as identity_module
from aec_bench.task_world_templates.hydraulics import kernel
from aec_bench.task_world_templates.hydraulics import package as package_module
from aec_bench.task_world_templates.hydraulics import report as report_module
from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicRunManifest,
    HydraulicRunRequest,
    HydraulicRunResult,
    HydraulicSourceState,
    HydraulicTimeSeries,
    HydraulicVerificationGate,
    HydraulicVerificationRecord,
)
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256
from aec_bench.task_world_templates.hydraulics.package import (
    HydraulicWorldIntegrityError,
    _load_validated_package,
    _read_json,
    _sha256,
    _validate_file_set,
    build_hydraulic_run_request,
)
from aec_bench.task_world_templates.hydraulics.report import render_hydraulic_report

_RUN_MANIFEST = "run-manifest.json"
_RUN_ARTIFACTS = ("request.json", "results.json", "timeseries.json", "report.md")


def _verifier_source_inventory_sha256() -> dict[str, str]:
    return {
        "contracts.py": _sha256(Path(contracts_module.__file__)),
        "identity.py": _sha256(Path(identity_module.__file__)),
        "kernel.py": _sha256(Path(kernel.__file__)),
        "package.py": _sha256(Path(package_module.__file__)),
        "report.py": _sha256(Path(report_module.__file__)),
        "validators.py": _sha256(Path(validators_module.__file__)),
        "verifier.py": _sha256(Path(__file__)),
    }


def _derive_criteria(
    source: HydraulicSourceState,
    result: HydraulicRunResult,
    time_series: HydraulicTimeSeries,
) -> dict[str, bool]:
    criteria = source.payload.criteria
    scenario = next(item for item in source.payload.scenarios if item.scenario_id == result.scenario_id)
    derived = {
        "continuity": abs(result.continuity_error_m3) <= criteria.maximum_continuity_error_m3,
        "freeboard": result.minimum_freeboard_m + criteria.level_tolerance_m >= criteria.minimum_freeboard_m,
        "hgl_clearance": result.minimum_hgl_clearance_m + criteria.level_tolerance_m
        >= criteria.minimum_hgl_clearance_m,
        "outlet_convergence": all(step.outlet_converged for step in time_series.steps),
        "pipe_capacity": all(
            capacity + criteria.flow_tolerance_m3_s >= result.peak_structured_outflow_m3_s
            for capacity in result.pipe_capacity_m3_s.values()
        ),
        "pipe_velocity": all(
            velocity <= criteria.maximum_pipe_velocity_m_s + criteria.velocity_tolerance_m_s
            for velocity in result.maximum_pipe_velocity_m_s.values()
        ),
        "storage_capacity": result.peak_uncontrolled_spill_m3_s <= criteria.flow_tolerance_m3_s,
    }
    if scenario.role == "design":
        derived.update(
            {
                "design_total_release": result.peak_structured_outflow_m3_s
                <= criteria.maximum_design_release_m3_s + criteria.flow_tolerance_m3_s,
                "emergency_weir_inactive": result.peak_weir_flow_m3_s <= criteria.flow_tolerance_m3_s,
            }
        )
    else:
        derived["emergency_weir_activated"] = (
            result.peak_weir_flow_m3_s + criteria.flow_tolerance_m3_s >= criteria.minimum_major_weir_flow_m3_s
        )
    return derived


def build_verification_record(
    source: HydraulicSourceState,
    result: HydraulicRunResult,
    time_series: HydraulicTimeSeries,
    *,
    run_manifest_sha256: str,
) -> HydraulicVerificationRecord:
    """Build gates independently from numeric results and source-owned criteria."""
    derived = _derive_criteria(source, result, time_series)
    gates = {
        criterion: HydraulicVerificationGate(
            passed=passed,
            diagnostics=() if passed else (f"criterion failed: {criterion}",),
        )
        for criterion, passed in sorted(derived.items())
    }
    criteria_consistent = result.criteria == derived
    gates["reported_criteria"] = HydraulicVerificationGate(
        passed=criteria_consistent,
        diagnostics=() if criteria_consistent else ("reported criteria do not match verifier derivation",),
    )
    source_inventory = _verifier_source_inventory_sha256()
    return HydraulicVerificationRecord(
        verifier_id="aec-bench.ssc03-hydraulic-world-verifier.v1",
        verifier_source_inventory_sha256=source_inventory,
        verifier_source_sha256=canonical_json_sha256(source_inventory),
        run_id=result.run_id,
        run_manifest_sha256=run_manifest_sha256,
        passed=all(gate.passed for gate in gates.values()),
        gates=gates,
    )


def verify_hydraulic_world(package_dir: Path, run_dir: Path) -> HydraulicVerificationRecord:
    """Reconcile immutable run evidence and recompute every hydraulic result."""
    package = Path(package_dir)
    run = Path(run_dir)
    source, package_manifest, engine = _load_validated_package(package)
    files = _validate_file_set(run, set(_RUN_ARTIFACTS) | {_RUN_MANIFEST})
    try:
        run_manifest = HydraulicRunManifest.model_validate(_read_json(files[_RUN_MANIFEST]))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HydraulicWorldIntegrityError("invalid run manifest") from exc
    for name, expected_hash in run_manifest.artifact_sha256.items():
        if _sha256(files[name]) != expected_hash:
            raise HydraulicWorldIntegrityError(f"artifact hash mismatch: {name}")

    request = HydraulicRunRequest.model_validate(_read_json(files["request.json"]))
    expected_request = build_hydraulic_run_request(package, scenario_id=request.scenario_id)
    if request != expected_request:
        raise HydraulicWorldIntegrityError("run request does not match current package identity")
    expected_manifest = HydraulicRunManifest(
        run_id=request.run_id,
        world_id=request.world_id,
        scenario_id=request.scenario_id,
        package_sha256=package_manifest.package_sha256,
        source_state_sha256=request.source_state_sha256,
        calculation_input_sha256=request.calculation_input_sha256,
        engine=engine,
        artifact_sha256={name: _sha256(files[name]) for name in _RUN_ARTIFACTS},
    )
    if run_manifest != expected_manifest:
        raise HydraulicWorldIntegrityError("run manifest does not match request and artifact identities")

    expected_result, expected_time_series = kernel.simulate_hydraulic_world(
        source=source,
        scenario_id=request.scenario_id,
        run_id=request.run_id,
        engine=engine,
        source_state_sha256=request.source_state_sha256,
        calculation_input_sha256=request.calculation_input_sha256,
    )
    actual_result = HydraulicRunResult.model_validate(_read_json(files["results.json"]))
    actual_time_series = HydraulicTimeSeries.model_validate(_read_json(files["timeseries.json"]))
    if actual_result != expected_result:
        raise HydraulicWorldIntegrityError("results do not match independent hydraulic recomputation")
    if actual_time_series != expected_time_series:
        raise HydraulicWorldIntegrityError("time series does not match independent hydraulic recomputation")
    if files["report.md"].read_text(encoding="utf-8") != render_hydraulic_report(source, request, expected_result):
        raise HydraulicWorldIntegrityError("report does not match canonical hydraulic results")
    expected_verification = build_verification_record(
        source,
        expected_result,
        expected_time_series,
        run_manifest_sha256=_sha256(files[_RUN_MANIFEST]),
    )
    return expected_verification
