# ABOUTME: Computes SSC-18 protection-control bridge metrics.
# ABOUTME: Combines CT secondary current, 4-20 mA scaling, pickup margins, and feeder checks.

from __future__ import annotations


def compute(
    primary_current_a: float,
    ct_primary_a: float,
    ct_secondary_a: float,
    lower_range_current_a: float,
    upper_range_current_a: float,
    pickup_current_a: float,
    fault_current_ka: float,
    transformer_ratio_error_pct: float,
    feeder_full_load_a: float,
    breaker_trip_a: float,
) -> dict[str, float]:
    """Compute deterministic protection-control bridge checks."""
    span_a = upper_range_current_a - lower_range_current_a
    if span_a <= 0:
        msg = "upper_range_current_a must be greater than lower_range_current_a"
        raise ValueError(msg)
    if ct_primary_a <= 0:
        msg = "ct_primary_a must be > 0"
        raise ValueError(msg)

    def signal(current_a: float) -> float:
        return 4.0 + 16.0 * ((current_a - lower_range_current_a) / span_a)

    ct_secondary_current_a = primary_current_a / ct_primary_a * ct_secondary_a
    measurement_signal_ma = signal(primary_current_a)
    pickup_signal_ma = signal(pickup_current_a)
    pickup_margin_a = pickup_current_a - primary_current_a
    fault_pickup_ratio = fault_current_ka * 1000.0 / pickup_current_a
    feeder_load_margin_a = breaker_trip_a - feeder_full_load_a
    ct_error_current_a = primary_current_a * transformer_ratio_error_pct / 100.0
    trip_signal_headroom_ma = 20.0 - pickup_signal_ma
    overall_pass_score = 1.0 if pickup_margin_a >= 0.0 and feeder_load_margin_a >= 0.0 else 0.0

    return {
        "ct_secondary_current_a": round(ct_secondary_current_a, 3),
        "measurement_signal_ma": round(measurement_signal_ma, 3),
        "pickup_signal_ma": round(pickup_signal_ma, 3),
        "pickup_margin_a": round(pickup_margin_a, 3),
        "fault_pickup_ratio": round(fault_pickup_ratio, 3),
        "feeder_load_margin_a": round(feeder_load_margin_a, 3),
        "ct_error_current_a": round(ct_error_current_a, 3),
        "trip_signal_headroom_ma": round(trip_signal_headroom_ma, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
