# ABOUTME: Independently checks extracted B3 probe series without calling SWMM hydraulic helpers.
# ABOUTME: Limits conclusions to diagnostic period, finiteness, standby, storage, flooding, and mirror identities.

from __future__ import annotations

import math
from typing import Any


class VerificationError(RuntimeError):
    """Raised when extracted probe semantics violate a B3 diagnostic identity."""


_FLOAT_OUTPUT_ABSOLUTE_TOLERANCE = 1.0e-5


def _series_mapping(result: dict[str, object]) -> dict[str, list[float]]:
    raw = result.get("series")
    if not isinstance(raw, dict):
        raise VerificationError("result has no semantic series mapping")
    expected_names = {
        "wet_well_depth_m",
        "wet_well_volume_m3",
        "wet_well_flooding_lps",
        "pump_a_flow_lps",
        "pump_b_flow_lps",
        "force_main_flow_lps",
    }
    if set(raw) != expected_names:
        raise VerificationError(f"semantic series allowlist differs: {sorted(raw)!r}")
    series: dict[str, list[float]] = {}
    for name, values in raw.items():
        if not isinstance(values, list) or any(
            isinstance(value, bool) or not isinstance(value, int | float) for value in values
        ):
            raise VerificationError(f"{name} is not a numeric series")
        series[str(name)] = [float(value) for value in values]
    return series


def _require_metadata(result: dict[str, object], key: str, expected_type: type[Any]) -> Any:
    value = result.get(key)
    if not isinstance(value, expected_type):
        raise VerificationError(f"{key} is missing or has the wrong type")
    return value


def _all_close(left: list[float], right: list[float]) -> bool:
    return len(left) == len(right) and all(
        math.isclose(
            left_value,
            right_value,
            rel_tol=0.0,
            abs_tol=_FLOAT_OUTPUT_ABSOLUTE_TOLERANCE,
        )
        for left_value, right_value in zip(left, right, strict=True)
    )


def verify_probe(result: dict[str, object], wet_well_plan_area_m2: float) -> dict[str, bool]:
    """Check one real-engine probe using only extracted series and physical identities."""
    period_count = _require_metadata(result, "period_count", int)
    expected_periods = _require_metadata(result, "expected_period_count", int)
    active_pump = _require_metadata(result, "active_pump", str)
    inactive_pump = _require_metadata(result, "inactive_pump", str)
    if {active_pump, inactive_pump} != {"PUMP_A", "PUMP_B"}:
        raise VerificationError("probe does not contain one active and one inactive B1 pump")
    if period_count != expected_periods:
        raise VerificationError(f"period count is {period_count}, expected {expected_periods}")

    series = _series_mapping(result)
    if any(len(values) != period_count for values in series.values()):
        raise VerificationError("one or more series lengths differ from the period count")
    if any(not math.isfinite(value) for values in series.values() for value in values):
        raise VerificationError("one or more semantic series contain a non-finite value")

    active_name = "pump_a_flow_lps" if active_pump == "PUMP_A" else "pump_b_flow_lps"
    inactive_name = "pump_a_flow_lps" if inactive_pump == "PUMP_A" else "pump_b_flow_lps"
    inactive_zero = all(abs(value) <= _FLOAT_OUTPUT_ABSOLUTE_TOLERANCE for value in series[inactive_name])
    if not inactive_zero:
        raise VerificationError("inactive pump has nonzero exported flow")
    active_positive = any(value > _FLOAT_OUTPUT_ABSOLUTE_TOLERANCE for value in series[active_name])
    if not active_positive:
        raise VerificationError("active pump never has positive exported flow")

    flooding_zero = all(abs(value) <= _FLOAT_OUTPUT_ABSOLUTE_TOLERANCE for value in series["wet_well_flooding_lps"])
    if not flooding_zero:
        raise VerificationError("diagnostic wet well has exported flooding")

    volume_identity = all(
        math.isclose(
            volume,
            wet_well_plan_area_m2 * depth,
            rel_tol=_FLOAT_OUTPUT_ABSOLUTE_TOLERANCE,
            abs_tol=_FLOAT_OUTPUT_ABSOLUTE_TOLERANCE,
        )
        for depth, volume in zip(
            series["wet_well_depth_m"],
            series["wet_well_volume_m3"],
            strict=True,
        )
    )
    if not volume_identity:
        raise VerificationError("cylindrical depth/volume identity does not hold in exported series")

    return {
        "period_count_exact": True,
        "all_series_finite": True,
        "inactive_pump_zero_flow": True,
        "active_pump_positive_flow": True,
        "cylindrical_volume_identity": True,
        "no_flooding": True,
    }


def verify_mirrored_probes(
    a_duty: dict[str, object],
    b_duty: dict[str, object],
) -> dict[str, bool]:
    """Compare separate probes after swapping only the active pump label."""
    a_series = _series_mapping(a_duty)
    b_series = _series_mapping(b_duty)
    active_match = _all_close(a_series["pump_a_flow_lps"], b_series["pump_b_flow_lps"])
    if not active_match:
        raise VerificationError("active-pump series differ after the label swap")
    inactive_match = _all_close(a_series["pump_b_flow_lps"], b_series["pump_a_flow_lps"])
    if not inactive_match:
        raise VerificationError("inactive-pump series differ after the label swap")
    wet_well_match = all(
        _all_close(a_series[name], b_series[name])
        for name in (
            "wet_well_depth_m",
            "wet_well_volume_m3",
            "wet_well_flooding_lps",
        )
    )
    if not wet_well_match:
        raise VerificationError("wet-well series differ after the label swap")
    force_main_match = _all_close(
        a_series["force_main_flow_lps"],
        b_series["force_main_flow_lps"],
    )
    if not force_main_match:
        raise VerificationError("force-main series differ after the label swap")
    return {
        "active_pump_series_match": True,
        "inactive_pump_series_match": True,
        "wet_well_series_match": True,
        "force_main_series_match": True,
    }
