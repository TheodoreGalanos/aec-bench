# ABOUTME: Integration-tests materialization, execution, identity, and verification of hydraulic calculations.
# ABOUTME: Covers deterministic bytes, physical sensitivity, and localized tamper rejection.

from __future__ import annotations

import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.lifecycles.stormwater_design.hydraulics.identity import canonical_json_sha256
from aec_bench.lifecycles.stormwater_design.hydraulics.models import (
    HydraulicRunRequest,
    HydraulicRunResult,
    HydraulicSourcePayload,
    HydraulicSourceState,
    HydraulicTimeSeries,
    build_source_state_contract,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.package import (
    HydraulicArtifactIntegrityError,
    build_hydraulic_run_request,
    execute_hydraulic_calculation,
    materialize_hydraulic_package,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.source import build_source_state
from aec_bench.lifecycles.stormwater_design.hydraulics.verifier import build_verification_record, verify_hydraulic_run

SOURCE_ID = "stormwater-detention-network"
CANONICAL_RUNTIME_DEPENDENCIES = {
    "pydantic": "2.11.10",
    "python_cache_tag": "cpython-313",
    "python_implementation": "CPython",
    "python_version": "3.13.2",
}
EXPECTED_MAJOR_PACKAGE_MANIFEST = {
    "artifact_sha256": {
        "README.md": "2ba094a3f6de26e168023e910705fc089dcfaaefdeec1fdd8079e7e3432210dc",
        "engine/identity.json": "acc960f15c8152746e38df61026395fdde1ccf0d3484976756606cebf73f77ab",
        "source/source-state.json": "7e361a26f66854e79bfcc9ddeb4cee023b6f2edeacce1ba9a38bdf953253f4c4",
    },
    "package_sha256": "115c5efaf30458799b2836859d7da49bca83b5d3f8724d1fcd5979dbe99d675c",
    "schema_version": "1",
    "source_id": SOURCE_ID,
}
EXPECTED_MAJOR_RUN_ARTIFACTS = {
    "report.md": "366f149ca4a4a631c4c10e71915895fdba118062ea6ade8b42f2f208cae77c91",
    "request.json": "28ad0d85386c13a186ae7b66be8921e6b4c29d52a631694a33d48468a2093078",
    "results.json": "a608a7daa38d41072ea426d6c1384aa71fe09e813144ff8132d8e85193ef2152",
    "timeseries.json": "d3e6538e8ffbce6e1317d85da79be945dddc8839cbc507b6928ec00eb284a611",
}
EXPECTED_MAJOR_RUN_ID = "hydraulic-a13fde0a31ca0cbe6e324a0fc5ceb4d3e555828d2f6ff9ba0cfd341e363cc8f7"


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _rebuild_state(state: HydraulicSourceState, payload: HydraulicSourcePayload) -> HydraulicSourceState:
    return build_source_state_contract(
        source_id=state.source_id,
        title=state.title,
        description=state.description,
        claim_boundary=state.claim_boundary,
        reference=state.reference,
        payload=payload,
        section_revisions={section.section_name: (section.source_id, section.revision) for section in state.sections},
    )


def _run_results(package: Path, run: Path, *, scenario_id: str) -> tuple[HydraulicRunRequest, dict[str, Any]]:
    request = build_hydraulic_run_request(package, scenario_id=scenario_id)
    execute_hydraulic_calculation(package, run, request)
    payload = json.loads((run / "results.json").read_text(encoding="utf-8"))
    return request, cast(dict[str, Any], payload)


def test_materialized_package_and_repeated_run_are_byte_identical(tmp_path: Path) -> None:
    first_package = materialize_hydraulic_package(build_source_state(), tmp_path / "package-a")
    second_package = materialize_hydraulic_package(build_source_state(), tmp_path / "package-b")
    first_request = build_hydraulic_run_request(first_package, scenario_id="major-100yr")
    second_request = build_hydraulic_run_request(second_package, scenario_id="major-100yr")
    first_run = execute_hydraulic_calculation(first_package, tmp_path / "run-a", first_request)
    second_run = execute_hydraulic_calculation(second_package, tmp_path / "run-b", second_request)

    assert _tree_bytes(first_package) == _tree_bytes(second_package)
    assert first_request == second_request
    assert _tree_bytes(first_run) == _tree_bytes(second_run)
    assert verify_hydraulic_run(first_package, first_run).passed is True


def test_canonical_major_evidence_matches_pinned_runtime_commitment(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    identity = json.loads((package / "engine" / "identity.json").read_text(encoding="utf-8"))
    if identity["runtime_dependencies"] != CANONICAL_RUNTIME_DEPENDENCIES:
        pytest.skip("fixed-byte commitment applies only to the recorded canonical evidence runtime")
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    package_manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))

    assert package_manifest == EXPECTED_MAJOR_PACKAGE_MANIFEST
    assert request.run_id == EXPECTED_MAJOR_RUN_ID
    assert run_manifest["run_id"] == EXPECTED_MAJOR_RUN_ID
    assert run_manifest["artifact_sha256"] == EXPECTED_MAJOR_RUN_ARTIFACTS


def test_engine_identity_binds_source_inventory_and_runtime_dependencies(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    identity = json.loads((package / "engine" / "identity.json").read_text(encoding="utf-8"))

    assert set(identity["source_inventory_sha256"]) == {
        "models.py",
        "identity.py",
        "calculation.py",
        "package.py",
        "report.py",
        "validators.py",
    }
    assert set(identity["runtime_dependencies"]) == {
        "pydantic",
        "python_cache_tag",
        "python_implementation",
        "python_version",
    }
    assert identity["runtime_dependencies"]["python_version"] == platform.python_version()
    assert identity["implementation_sha256"] == canonical_json_sha256(identity["source_inventory_sha256"])
    assert identity["runtime_dependency_sha256"] == canonical_json_sha256(identity["runtime_dependencies"])


def test_major_run_contains_named_hydraulic_outputs_and_passes_criteria(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))

    assert set(results["catchment_peak_flows_m3_s"]) == {"CATCH-A", "CATCH-B"}
    assert results["peak_orifice_flow_m3_s"] > 0.0
    assert results["peak_weir_flow_m3_s"] > 0.0
    assert set(results["maximum_pipe_velocity_m_s"]) == {"PIPE-OUT-01", "PIPE-OUT-02"}
    assert set(results["maximum_node_hgl_m"]) == {"PIT-OUTLET", "PIT-DOWNSTREAM", "OUTFALL"}
    assert results["maximum_storage_m3"] > 0.0
    assert results["minimum_freeboard_m"] > 0.0
    assert abs(results["continuity_error_m3"]) <= 0.001
    assert all(results["criteria"].values())


def test_design_run_uses_only_controlled_outlet_and_respects_total_release(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    _request, results = _run_results(package, tmp_path / "run", scenario_id="design-10yr")

    assert results["peak_weir_flow_m3_s"] == 0.0
    assert results["criteria"]["design_total_release"] is True
    assert results["criteria"]["emergency_weir_inactive"] is True


def test_verifier_rejects_a_tampered_result_before_trusting_reported_pass(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    result_path = run / "results.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["criteria"] = {name: True for name in payload["criteria"]}
    payload["minimum_freeboard_m"] = -10.0
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(HydraulicArtifactIntegrityError, match="artifact hash mismatch: results.json"):
        verify_hydraulic_run(package, run)


def test_rewritten_manifest_cannot_bless_a_false_result(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    result_path = run / "results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["minimum_freeboard_m"] = -10.0
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path = run / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["results.json"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(HydraulicArtifactIntegrityError, match="independent hydraulic recomputation"):
        verify_hydraulic_run(package, run)


def test_rewritten_package_manifest_cannot_drop_an_artifact(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    readme = package / "README.md"
    readme.write_text("rewritten but intentionally unbound\n", encoding="utf-8")
    manifest_path = package / "package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["artifact_sha256"]["README.md"]
    manifest["package_sha256"] = canonical_json_sha256(
        {"source_id": manifest["source_id"], "artifact_sha256": manifest["artifact_sha256"]}
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(HydraulicArtifactIntegrityError, match="package manifest"):
        build_hydraulic_run_request(package, scenario_id="design-10yr")


def test_run_output_cannot_overlap_immutable_package(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")

    with pytest.raises(ValueError, match="must not overlap"):
        execute_hydraulic_calculation(package, package / "run", request)


def test_verification_is_not_published_inside_the_computation_run(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))

    assert "verification.json" not in manifest["artifact_sha256"]
    assert not (run / "verification.json").exists()
    verification = verify_hydraulic_run(package, run)
    assert verification.passed is True
    assert verification.run_manifest_sha256 == hashlib.sha256((run / "run-manifest.json").read_bytes()).hexdigest()
    assert set(verification.verifier_source_inventory_sha256) == {
        "models.py",
        "identity.py",
        "calculation.py",
        "package.py",
        "report.py",
        "validators.py",
        "verifier.py",
    }


def test_routed_event_matches_independent_triangular_volume_and_mass_balance(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    _request, results = _run_results(package, tmp_path / "run", scenario_id="design-10yr")
    source = json.loads((package / "source" / "source-state.json").read_text(encoding="utf-8"))
    scenario = next(item for item in source["payload"]["scenarios"] if item["scenario_id"] == "design-10yr")
    time_series = json.loads((tmp_path / "run" / "timeseries.json").read_text(encoding="utf-8"))
    time_step_s = scenario["time_step_s"]
    expected_triangular_inflow_m3 = results["peak_total_inflow_m3_s"] * scenario["storm_duration_s"] / 2.0
    routed_inflow_m3 = sum(step["total_inflow_m3_s"] * time_step_s for step in time_series["steps"])
    routed_outflow_m3 = sum(step["total_outflow_m3_s"] * time_step_s for step in time_series["steps"])
    final_storage_m3 = time_series["steps"][-1]["storage_m3"]

    assert routed_inflow_m3 == pytest.approx(expected_triangular_inflow_m3, abs=0.01)
    assert routed_inflow_m3 - routed_outflow_m3 == pytest.approx(final_storage_m3, abs=0.01)


def test_two_step_coupled_run_matches_a_hand_worked_oracle(tmp_path: Path) -> None:
    baseline = build_source_state()
    catchments = tuple(
        catchment.model_copy(update={"area_ha": 1.0, "runoff_coefficient": 0.5})
        for catchment in baseline.payload.catchments
    )
    scenarios = list(baseline.payload.scenarios)
    scenarios[0] = scenarios[0].model_copy(
        update={
            "rainfall_intensity_mm_h": 72.0,
            "climate_factor": 1.0,
            "storm_duration_s": 120,
            "time_step_s": 60,
        }
    )
    basin = baseline.payload.basin.model_copy(
        update={
            "bottom_elevation_m": 0.0,
            "crest_elevation_m": 1.0,
            "bottom_area_m2": 100.0,
            "top_area_m2": 100.0,
            "initial_depth_m": 0.0,
        }
    )
    orifice = baseline.payload.outlet.orifice.model_copy(
        update={"diameter_m": 0.1, "discharge_coefficient": 0.6, "centre_elevation_m": 0.0}
    )
    weir = baseline.payload.outlet.emergency_weir.model_copy(
        update={"crest_elevation_m": 0.9, "length_m": 1.0, "discharge_coefficient": 0.6}
    )
    outlet = baseline.payload.outlet.model_copy(update={"orifice": orifice, "emergency_weir": weir})
    pit = baseline.payload.network.pits[0].model_copy(update={"node_id": "PIT-HAND", "rim_elevation_m": 1.0})
    pipe = baseline.payload.network.pipes[0].model_copy(
        update={
            "pipe_id": "PIPE-HAND",
            "upstream_node_id": "PIT-HAND",
            "downstream_node_id": "OUTFALL-HAND",
            "diameter_m": 0.1,
            "length_m": 10.0,
            "slope_m_per_m": 0.01,
            "mannings_n": 0.01,
            "minor_loss_coefficient": 0.0,
        }
    )
    network = baseline.payload.network.model_copy(
        update={
            "pits": (pit,),
            "pipes": (pipe,),
            "tailwater_node_id": "OUTFALL-HAND",
            "tailwater_elevation_m": 0.0,
        }
    )
    payload = HydraulicSourcePayload.model_validate(
        baseline.payload.model_dump(mode="json")
        | {
            "catchments": [catchment.model_dump(mode="json") for catchment in catchments],
            "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
            "basin": basin.model_dump(mode="json"),
            "outlet": outlet.model_dump(mode="json"),
            "network": network.model_dump(mode="json"),
        }
    )
    package = materialize_hydraulic_package(
        _rebuild_state(baseline, payload),
        tmp_path / "package",
    )
    _request, result = _run_results(package, tmp_path / "run", scenario_id="design-10yr")
    time_series = json.loads((tmp_path / "run" / "timeseries.json").read_text(encoding="utf-8"))

    # Closed-form hand calculation: the one-pipe loss is C*q^2, so the coupled
    # orifice equation has q = K*sqrt(H / (1 + K^2*C)) at the second step.
    peak_per_catchment_m3_s = 0.5 * 72.0 * 1.0 / 360.0
    midpoint_inflow_m3_s = 2.0 * peak_per_catchment_m3_s * 0.5
    expected_first_storage_m3 = midpoint_inflow_m3_s * 60.0
    starting_second_depth_m = expected_first_storage_m3 / 100.0
    pipe_area_m2 = math.pi * 0.1**2 / 4.0
    hydraulic_radius_m = 0.1 / 4.0
    orifice_factor = 0.6 * pipe_area_m2 * math.sqrt(2.0 * 9.81)
    pipe_loss_factor = 10.0 * 0.01**2 / (pipe_area_m2**2 * hydraulic_radius_m ** (4.0 / 3.0))
    expected_second_outflow_m3_s = orifice_factor * math.sqrt(
        starting_second_depth_m / (1.0 + orifice_factor**2 * pipe_loss_factor)
    )
    expected_pit_hgl_m = pipe_loss_factor * expected_second_outflow_m3_s**2
    expected_velocity_m_s = expected_second_outflow_m3_s / pipe_area_m2
    expected_capacity_m3_s = pipe_area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(0.01) / 0.01
    expected_second_storage_m3 = (
        expected_first_storage_m3 + (midpoint_inflow_m3_s - expected_second_outflow_m3_s) * 60.0
    )
    expected_final_depth_m = expected_second_storage_m3 / 100.0
    expected_freeboard_m = 1.0 - expected_final_depth_m
    expected_hgl_clearance_m = 1.0 - expected_pit_hgl_m
    saved = pytest.approx

    assert time_series["steps"][0]["storage_m3"] == saved(expected_first_storage_m3, rel=0.0, abs=5.1e-7)
    assert time_series["steps"][1]["orifice_flow_m3_s"] == saved(expected_second_outflow_m3_s, rel=0.0, abs=5.1e-7)
    assert time_series["steps"][1]["node_hgl_m"]["PIT-HAND"] == saved(expected_pit_hgl_m, rel=0.0, abs=5.1e-7)
    assert time_series["steps"][1]["pipe_velocity_m_s"]["PIPE-HAND"] == saved(
        expected_velocity_m_s, rel=0.0, abs=5.1e-7
    )
    assert time_series["steps"][1]["pipe_capacity_m3_s"]["PIPE-HAND"] == saved(
        expected_capacity_m3_s, rel=0.0, abs=5.1e-7
    )
    assert time_series["steps"][1]["storage_m3"] == saved(expected_second_storage_m3, rel=0.0, abs=5.1e-7)
    assert time_series["steps"][1]["water_depth_m"] == saved(expected_final_depth_m, rel=0.0, abs=5.1e-7)
    assert result["minimum_freeboard_m"] == saved(expected_freeboard_m, rel=0.0, abs=5.1e-7)
    assert result["minimum_hgl_clearance_m"] == saved(expected_hgl_clearance_m, rel=0.0, abs=5.1e-7)
    assert result["peak_weir_flow_m3_s"] == 0.0
    assert result["peak_uncontrolled_spill_m3_s"] == 0.0
    assert result["continuity_error_m3"] == 0.0
    assert all(step["outlet_converged"] for step in time_series["steps"])


def test_tailwater_change_changes_run_identity_and_hgl_but_not_hydrology(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    changed_network = baseline_state.payload.network.model_copy(
        update={"tailwater_elevation_m": baseline_state.payload.network.tailwater_elevation_m + 0.2}
    )
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json") | {"network": changed_network.model_dump(mode="json")}
    )
    changed_state = _rebuild_state(baseline_state, changed_payload)
    baseline_package = materialize_hydraulic_package(build_source_state(), tmp_path / "baseline-package")
    changed_package = materialize_hydraulic_package(
        changed_state,
        tmp_path / "changed-package",
    )

    baseline_request, baseline = _run_results(
        baseline_package,
        tmp_path / "baseline-run",
        scenario_id="design-10yr",
    )
    changed_request, changed = _run_results(
        changed_package,
        tmp_path / "changed-run",
        scenario_id="design-10yr",
    )

    assert baseline_request.run_id != changed_request.run_id
    assert baseline["catchment_peak_flows_m3_s"] == changed["catchment_peak_flows_m3_s"]
    assert changed["maximum_node_hgl_m"]["PIT-OUTLET"] > baseline["maximum_node_hgl_m"]["PIT-OUTLET"]


def test_outlet_geometry_change_updates_only_source_bound_run(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    changed_orifice = baseline_state.payload.outlet.orifice.model_copy(update={"diameter_m": 0.35})
    changed_outlet = baseline_state.payload.outlet.model_copy(update={"orifice": changed_orifice})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json") | {"outlet": changed_outlet.model_dump(mode="json")}
    )
    changed_state = _rebuild_state(baseline_state, changed_payload)
    baseline_package = materialize_hydraulic_package(build_source_state(), tmp_path / "baseline-package")
    changed_package = materialize_hydraulic_package(
        changed_state,
        tmp_path / "changed-package",
    )

    baseline_request, baseline = _run_results(
        baseline_package,
        tmp_path / "baseline-run",
        scenario_id="major-100yr",
    )
    changed_request, changed = _run_results(
        changed_package,
        tmp_path / "changed-run",
        scenario_id="major-100yr",
    )

    assert baseline_request.run_id != changed_request.run_id
    assert changed["peak_orifice_flow_m3_s"] < baseline["peak_orifice_flow_m3_s"]
    assert changed["maximum_storage_m3"] > baseline["maximum_storage_m3"]


def test_rainfall_change_updates_hydrology_storage_and_run_identity(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    scenarios = list(baseline_state.payload.scenarios)
    scenarios[0] = scenarios[0].model_copy(update={"rainfall_intensity_mm_h": 85.0})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json")
        | {"scenarios": [scenario.model_dump(mode="json") for scenario in scenarios]}
    )
    changed_state = _rebuild_state(baseline_state, changed_payload)
    baseline_package = materialize_hydraulic_package(build_source_state(), tmp_path / "baseline-package")
    changed_package = materialize_hydraulic_package(
        changed_state,
        tmp_path / "changed-package",
    )

    baseline_request, baseline = _run_results(
        baseline_package,
        tmp_path / "baseline-run",
        scenario_id="design-10yr",
    )
    changed_request, changed = _run_results(
        changed_package,
        tmp_path / "changed-run",
        scenario_id="design-10yr",
    )

    assert baseline_request.run_id != changed_request.run_id
    assert changed["peak_total_inflow_m3_s"] > baseline["peak_total_inflow_m3_s"]
    assert changed["maximum_storage_m3"] > baseline["maximum_storage_m3"]


def test_high_tailwater_never_reports_positive_flow_uphill(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    changed_network = baseline_state.payload.network.model_copy(update={"tailwater_elevation_m": 41.6})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json") | {"network": changed_network.model_dump(mode="json")}
    )
    package = materialize_hydraulic_package(
        _rebuild_state(baseline_state, changed_payload),
        tmp_path / "package",
    )
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    time_series = json.loads((run / "timeseries.json").read_text(encoding="utf-8"))

    for step in time_series["steps"]:
        structured_flow = step["orifice_flow_m3_s"] + step["weir_flow_m3_s"]
        if structured_flow > 0.000001:
            assert step["node_hgl_m"]["PIT-OUTLET"] < step["water_surface_elevation_m"]


def test_extreme_rainfall_produces_a_valid_run_with_failed_storage_gate(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    scenarios = list(baseline_state.payload.scenarios)
    scenarios[1] = scenarios[1].model_copy(update={"rainfall_intensity_mm_h": 500.0})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json")
        | {"scenarios": [scenario.model_dump(mode="json") for scenario in scenarios]}
    )
    package = materialize_hydraulic_package(
        _rebuild_state(baseline_state, changed_payload),
        tmp_path / "package",
    )
    request = build_hydraulic_run_request(package, scenario_id="major-100yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    verification = verify_hydraulic_run(package, run)

    assert verification.passed is False
    assert verification.gates["storage_capacity"].passed is False


def test_calculation_and_verifier_use_the_same_rounded_values_at_a_criterion_threshold(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    changed_criteria = baseline_state.payload.criteria.model_copy(update={"maximum_pipe_velocity_m_s": 0.5051579})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json") | {"criteria": changed_criteria.model_dump(mode="json")}
    )
    package = materialize_hydraulic_package(
        _rebuild_state(baseline_state, changed_payload),
        tmp_path / "package",
    )
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    verification = verify_hydraulic_run(package, run)

    assert results["criteria"]["pipe_velocity"] is False
    assert verification.gates["pipe_velocity"].passed is False
    assert verification.gates["reported_criteria"].passed is True


@pytest.mark.parametrize(
    ("scenario_id", "failed_gate"),
    [
        ("design-10yr", "continuity"),
        ("design-10yr", "freeboard"),
        ("design-10yr", "hgl_clearance"),
        ("design-10yr", "outlet_convergence"),
        ("design-10yr", "pipe_capacity"),
        ("design-10yr", "pipe_velocity"),
        ("design-10yr", "storage_capacity"),
        ("design-10yr", "design_total_release"),
        ("design-10yr", "emergency_weir_inactive"),
        ("major-100yr", "emergency_weir_activated"),
    ],
)
def test_verifier_derives_each_physical_failure_gate(
    tmp_path: Path,
    scenario_id: str,
    failed_gate: str,
) -> None:
    source = build_source_state()
    package = materialize_hydraulic_package(source, tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id=scenario_id)
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    result = HydraulicRunResult.model_validate(json.loads((run / "results.json").read_text(encoding="utf-8")))
    time_series = HydraulicTimeSeries.model_validate(json.loads((run / "timeseries.json").read_text(encoding="utf-8")))
    criteria = source.payload.criteria
    result_updates: dict[str, Any] = {}

    if failed_gate == "continuity":
        result_updates["continuity_error_m3"] = criteria.maximum_continuity_error_m3 + 1.0
    elif failed_gate == "freeboard":
        result_updates["minimum_freeboard_m"] = criteria.minimum_freeboard_m - criteria.level_tolerance_m - 0.1
    elif failed_gate == "hgl_clearance":
        result_updates["minimum_hgl_clearance_m"] = criteria.minimum_hgl_clearance_m - criteria.level_tolerance_m - 0.1
    elif failed_gate == "outlet_convergence":
        first_step = time_series.steps[0].model_copy(update={"outlet_converged": False})
        time_series = time_series.model_copy(update={"steps": (first_step, *time_series.steps[1:])})
    elif failed_gate == "pipe_capacity":
        first_pipe = next(iter(result.pipe_capacity_m3_s))
        capacities = dict(result.pipe_capacity_m3_s)
        capacities[first_pipe] = result.peak_structured_outflow_m3_s - criteria.flow_tolerance_m3_s - 0.1
        result_updates["pipe_capacity_m3_s"] = capacities
    elif failed_gate == "pipe_velocity":
        first_pipe = next(iter(result.maximum_pipe_velocity_m_s))
        velocities = dict(result.maximum_pipe_velocity_m_s)
        velocities[first_pipe] = criteria.maximum_pipe_velocity_m_s + criteria.velocity_tolerance_m_s + 0.1
        result_updates["maximum_pipe_velocity_m_s"] = velocities
    elif failed_gate == "storage_capacity":
        result_updates["peak_uncontrolled_spill_m3_s"] = criteria.flow_tolerance_m3_s + 0.1
    elif failed_gate == "design_total_release":
        result_updates["peak_structured_outflow_m3_s"] = (
            criteria.maximum_design_release_m3_s + criteria.flow_tolerance_m3_s + 0.01
        )
    elif failed_gate == "emergency_weir_inactive":
        result_updates["peak_weir_flow_m3_s"] = criteria.flow_tolerance_m3_s + 0.01
    elif failed_gate == "emergency_weir_activated":
        result_updates["peak_weir_flow_m3_s"] = 0.0
    else:
        raise AssertionError(f"unhandled failure gate: {failed_gate}")

    reported_criteria = dict(result.criteria)
    reported_criteria[failed_gate] = False
    changed_result = result.model_copy(update=result_updates | {"criteria": reported_criteria})
    verification = build_verification_record(
        source,
        changed_result,
        time_series,
        run_manifest_sha256="0" * 64,
    )

    failed_physical_gates = {
        name for name, gate in verification.gates.items() if name != "reported_criteria" and not gate.passed
    }
    assert failed_physical_gates == {failed_gate}
    assert verification.gates["reported_criteria"].passed is True


def test_verifier_rejects_false_reported_criteria_when_physical_gates_pass(tmp_path: Path) -> None:
    source = build_source_state()
    package = materialize_hydraulic_package(source, tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    result = HydraulicRunResult.model_validate(json.loads((run / "results.json").read_text(encoding="utf-8")))
    time_series = HydraulicTimeSeries.model_validate(json.loads((run / "timeseries.json").read_text(encoding="utf-8")))
    reported_criteria = dict(result.criteria)
    reported_criteria["freeboard"] = False
    changed_result = result.model_copy(update={"criteria": reported_criteria})

    verification = build_verification_record(
        source,
        changed_result,
        time_series,
        run_manifest_sha256="0" * 64,
    )

    assert all(gate.passed for name, gate in verification.gates.items() if name != "reported_criteria")
    assert verification.gates["reported_criteria"].passed is False
    assert verification.passed is False


def test_stale_request_is_rejected_against_changed_source_state(tmp_path: Path) -> None:
    baseline_state = build_source_state()
    baseline_package = materialize_hydraulic_package(build_source_state(), tmp_path / "baseline-package")
    stale_request = build_hydraulic_run_request(baseline_package, scenario_id="design-10yr")
    changed_network = baseline_state.payload.network.model_copy(update={"tailwater_elevation_m": 40.7})
    changed_payload = HydraulicSourcePayload.model_validate(
        baseline_state.payload.model_dump(mode="json") | {"network": changed_network.model_dump(mode="json")}
    )
    changed_package = materialize_hydraulic_package(
        _rebuild_state(baseline_state, changed_payload),
        tmp_path / "changed-package",
    )

    with pytest.raises(HydraulicArtifactIntegrityError, match="request does not match"):
        execute_hydraulic_calculation(changed_package, tmp_path / "run", stale_request)


def test_verifier_rejects_missing_report_artifact(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    (run / "report.md").unlink()

    with pytest.raises(HydraulicArtifactIntegrityError, match="missing artifact: report.md"):
        verify_hydraulic_run(package, run)


def test_verifier_rejects_tampered_source_state(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    source_path = package / "source" / "source-state.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["payload"]["network"]["tailwater_elevation_m"] += 0.1
    source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(HydraulicArtifactIntegrityError, match="artifact hash mismatch: source/source-state.json"):
        verify_hydraulic_run(package, run)


def test_verifier_rejects_symlinked_package_artifact(tmp_path: Path) -> None:
    package = materialize_hydraulic_package(build_source_state(), tmp_path / "package")
    request = build_hydraulic_run_request(package, scenario_id="design-10yr")
    run = execute_hydraulic_calculation(package, tmp_path / "run", request)
    source_path = package / "source" / "source-state.json"
    external_copy = tmp_path / "external-source-state.json"
    external_copy.write_bytes(source_path.read_bytes())
    source_path.unlink()
    source_path.symlink_to(external_copy)

    with pytest.raises(HydraulicArtifactIntegrityError, match="symlink is not allowed"):
        verify_hydraulic_run(package, run)
