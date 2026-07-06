# ABOUTME: IACS CSR-H Rule length (L) computation engine.
# ABOUTME: Applies the 96%/97% extreme-waterline-length clamp of Pt 1 Ch 1 Sec 4 §3.1.1.

# CSR-H 01 JUL 2025 Pt 1 Ch 1 Sec 4 §3.1.1:
# "L is to be not less than 96% and need not exceed 97% of the extreme length on the
# waterline at the scantling draught T_SC."
LOWER_BOUND_FRACTION = 0.96

# CSR-H 01 JUL 2025 Pt 1 Ch 1 Sec 4 §3.1.1: upper cap on the Rule length L, see above.
UPPER_BOUND_FRACTION = 0.97

# Sentinel default for stem_to_rudder_stock_distance_m when the ship has no rudder
# stock (e.g. azimuth thruster vessels) and the parameter is not applicable.
_NO_RUDDER_STOCK_SENTINEL = None


def _validate_inputs(
    extreme_length_on_waterline_at_TSC_m: float,
    has_rudder_stock: bool,
    stem_to_rudder_stock_distance_m: float | None,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if extreme_length_on_waterline_at_TSC_m <= 0:
        msg = "extreme_length_on_waterline_at_TSC_m must be > 0"
        raise ValueError(msg)
    if has_rudder_stock:
        if stem_to_rudder_stock_distance_m is None:
            msg = "stem_to_rudder_stock_distance_m is required when has_rudder_stock is True"
            raise ValueError(msg)
        if stem_to_rudder_stock_distance_m <= 0:
            msg = "stem_to_rudder_stock_distance_m must be > 0"
            raise ValueError(msg)
        if stem_to_rudder_stock_distance_m > extreme_length_on_waterline_at_TSC_m:
            msg = "stem_to_rudder_stock_distance_m must be <= extreme_length_on_waterline_at_TSC_m"
            raise ValueError(msg)


def compute(
    extreme_length_on_waterline_at_TSC_m: float,
    has_rudder_stock: bool,
    stem_to_rudder_stock_distance_m: float | None = _NO_RUDDER_STOCK_SENTINEL,
) -> dict[str, float]:
    """Compute the IACS CSR-H Rule length L per Pt 1 Ch 1 Sec 4 §3.1.1.

    L is the distance, in m, measured on the waterline at the scantling draught T_SC
    from the forward side of the stem to the centre of the rudder stock, clamped to
    lie between 96% and 97% of the extreme length on the waterline at T_SC. Ships
    without a rudder stock (e.g. fitted with azimuth thrusters) take L equal to 97%
    of the extreme length.

    Returns a dict with key: rule_length_L_m.
    """
    _validate_inputs(
        extreme_length_on_waterline_at_TSC_m,
        has_rudder_stock,
        stem_to_rudder_stock_distance_m,
    )

    lower_bound = LOWER_BOUND_FRACTION * extreme_length_on_waterline_at_TSC_m
    upper_bound = UPPER_BOUND_FRACTION * extreme_length_on_waterline_at_TSC_m

    if has_rudder_stock:
        # _validate_inputs guarantees the measured distance is present and positive here;
        # assert narrows float | None -> float for the type checker.
        assert stem_to_rudder_stock_distance_m is not None
        rule_length_l = min(max(stem_to_rudder_stock_distance_m, lower_bound), upper_bound)
    else:
        rule_length_l = upper_bound

    return {
        "rule_length_L_m": round(rule_length_l, 3),
    }
