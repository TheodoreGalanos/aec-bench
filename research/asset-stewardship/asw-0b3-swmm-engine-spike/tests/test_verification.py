# ABOUTME: Tests independent diagnostic checks over extracted SWMM semantic series.
# ABOUTME: Verifies label symmetry and physical identities without certifying a B4 world family.

from __future__ import annotations

import math

import pytest
from asw_b3_swmm.verification import VerificationError, verify_mirrored_probes, verify_probe


def _result(active: str) -> dict[str, object]:
    inactive = "PUMP_B" if active == "PUMP_A" else "PUMP_A"
    area = math.pi
    return {
        "probe_id": "a_duty" if active == "PUMP_A" else "b_duty_label_probe",
        "active_pump": active,
        "inactive_pump": inactive,
        "engine_version": 52004,
        "flow_units": "LPS",
        "report_step_seconds": 60,
        "period_count": 3,
        "expected_period_count": 3,
        "series": {
            "wet_well_depth_m": [1.0, 0.9, 0.8],
            "wet_well_volume_m3": [area, 0.9 * area, 0.8 * area],
            "wet_well_flooding_lps": [0.0, 0.0, 0.0],
            "pump_a_flow_lps": [5.0, 5.0, 5.0] if active == "PUMP_A" else [0.0, 0.0, 0.0],
            "pump_b_flow_lps": [0.0, 0.0, 0.0] if active == "PUMP_A" else [5.0, 5.0, 5.0],
            "force_main_flow_lps": [5.0, 5.0, 5.0],
        },
    }


def test_probe_checks_finite_periods_standby_and_cylindrical_identity() -> None:
    findings = verify_probe(_result("PUMP_A"), wet_well_plan_area_m2=math.pi)

    assert findings["period_count_exact"] is True
    assert findings["all_series_finite"] is True
    assert findings["inactive_pump_zero_flow"] is True
    assert findings["active_pump_positive_flow"] is True
    assert findings["cylindrical_volume_identity"] is True
    assert findings["no_flooding"] is True


def test_probe_rejects_nonzero_standby_flow() -> None:
    result = _result("PUMP_A")
    result["series"]["pump_b_flow_lps"][1] = 0.1  # type: ignore[index]

    with pytest.raises(VerificationError, match="inactive pump"):
        verify_probe(result, wet_well_plan_area_m2=math.pi)


def test_probe_rejects_nonfinite_values() -> None:
    result = _result("PUMP_A")
    result["series"]["wet_well_depth_m"][1] = math.nan  # type: ignore[index]

    with pytest.raises(VerificationError, match="non-finite"):
        verify_probe(result, wet_well_plan_area_m2=math.pi)


def test_mirror_check_compares_hydraulics_after_label_swap() -> None:
    findings = verify_mirrored_probes(_result("PUMP_A"), _result("PUMP_B"))

    assert findings == {
        "active_pump_series_match": True,
        "inactive_pump_series_match": True,
        "wet_well_series_match": True,
        "force_main_series_match": True,
    }


def test_mirror_check_rejects_changed_hydraulics() -> None:
    b_result = _result("PUMP_B")
    b_result["series"]["force_main_flow_lps"][1] = 4.9  # type: ignore[index]

    with pytest.raises(VerificationError, match="force-main"):
        verify_mirrored_probes(_result("PUMP_A"), b_result)
