# ABOUTME: Exercises one canonical W1 case through the real solver lifecycle and official output library.
# ABOUTME: Verifies exact settings, periods, semantic series, diagnostics, identities, and research-only scope.

from __future__ import annotations

import os
from pathlib import Path

from generator import engine, execution, request

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"


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
