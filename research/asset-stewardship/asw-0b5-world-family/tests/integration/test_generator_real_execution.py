# ABOUTME: Exercises one canonical W1 case through the real solver lifecycle and official output library.
# ABOUTME: Verifies exact settings, periods, semantic series, diagnostics, identities, and research-only scope.

from __future__ import annotations

import os
from pathlib import Path

from generator import engine, execution, rendering, request
from sensitivity import catalogue, engine_variants

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)
PROBE_DECLARATION = (
    B5_ROOT / "declarations" / "w4-probe-catalogue.json"
)


def test_real_forced_case_executes_extracts_and_canonicalizes(tmp_path: Path) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"
    receipt_path = Path(receipt_value)
    raw = request.build_anchor_request(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        case_id="G21_OBSTRUCTION_TRIGGER",
        engine_identity=engine.request_engine_identity(receipt_path),
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
    )

    result = execution.execute_case(
        request.read_request(raw),
        receipt_path=receipt_path,
        workspace=tmp_path / "G21",
    )

    assert result["case_id"] == "G21_OBSTRUCTION_TRIGGER"
    assert len(result["segments"]) == 1
    segment = result["segments"][0]
    assert segment["period_count"] == 120
    assert segment["diagnostics"]["warnings"] == []
    assert segment["diagnostics"]["errors"] == []
    assert segment["diagnostics"]["steps_not_converging_percent"] == "0.00"
    assert segment["diagnostics"]["maximum_trials"] == 50
    assert segment["setting_trace"]["pump_a"] == [1] * 120
    assert segment["setting_trace"]["pump_b"] == [0] * 120
    assert list(segment["semantic"]["series"]) == list(request.SERIES_OUTPUTS)
    assert segment["semantic"]["series"]["wet_well_volume_m3"]["unit"] == "m³"
    assert segment["semantic"]["series"]["pump_a_flow_m3_s"]["unit"] == "m³/s"
    assert segment["semantic"]["promotable"] is False
    assert set(segment["curve_evidence"]) == {
        "pump_a_engine_curve_sha256",
        "pump_a_original_curve_sha256",
        "pump_b_engine_curve_sha256",
        "pump_b_original_curve_sha256",
    }
    assert b"/private/" not in segment["semantic_bytes"]
    assert b"/Users/" not in segment["semantic_bytes"]


def test_real_report_step_diagnostic_replays_on_its_declared_grid(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, (
        "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"
    )

    result = execution.execute_diagnostic_cases(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        case_ids=("G21_OBSTRUCTION_TRIGGER",),
        configuration=rendering.EngineConfiguration(
            report_step_s=2,
        ),
        receipt_path=Path(receipt_value),
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        workspace=tmp_path / "report-two",
    )

    assert result["configuration"]["report_step_s"] == 2
    assert result["engine_execution_count"] == 2
    assert all(result["replay"].values())
    for replay in result["replays"]:
        segment = replay["cases"]["G21_OBSTRUCTION_TRIGGER"][
            "segments"
        ][0]
        assert segment["period_count"] == 60
        assert len(segment["setting_trace"]["pump_a"]) == 60
        assert segment["semantic"]["series"]["time_s"]["values"][-1] == (
            120
        )


def test_real_curve_diagnostic_passes_independent_variant_checks(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, (
        "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"
    )
    declaration = catalogue.read_probe_catalogue(
        PROBE_DECLARATION.read_bytes()
    )
    case_ids = tuple(declaration["engine_case_ids"])
    results = {}
    for item in declaration["engine_variants"][:3:2]:
        results[item["variant_id"]] = (
            execution.execute_diagnostic_cases(
                authority_bytes=W1_DECLARATION.read_bytes(),
                catalogue_bytes=W2_CATALOGUE.read_bytes(),
                case_ids=case_ids,
                configuration=rendering.EngineConfiguration(
                    **item["configuration"]
                ),
                receipt_path=Path(receipt_value),
                repair_bytes=W2_W4_REPAIR.read_bytes(),
                solver_convergence_bytes=(
                    SOLVER_CONVERGENCE.read_bytes()
                ),
                workspace=tmp_path / item["variant_id"],
            )
        )

    result = engine_variants.evaluate(
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
        variant_results=results,
        required_variant_ids=(
            "ENG.00.base",
            "ENG.02.curve-64",
        ),
    )

    assert result["terminal_state"] == "engine-variants-pass"
    assert result["first_failure"] == "none"
    assert result["evaluations"]["ENG.02.curve-64"][
        "curve_resolution"
    ]["outcome"] == "pass"
