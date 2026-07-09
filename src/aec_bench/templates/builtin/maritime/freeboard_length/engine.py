# ABOUTME: IACS CSR-H Freeboard length (L_LL) computation engine.
# ABOUTME: Applies the greater-of 96%-waterline / stem-to-rudder-stock rule of Pt 1 Ch 1 Sec 4 §3.1.2.

# CSR-H 01 JUL 2025 Pt 1 Ch 1 Sec 4 §3.1.2:
# "The freeboard length L_LL, in m, is to be taken as 96% of the total length on a
# waterline at 85% of the least moulded depth measured from the top of the keel, or as
# the length from the fore side of the stem to the axis of the rudder stock on that
# waterline, if that be greater. For ships without a rudder stock, the length L_LL is
# to be taken as 96% of the waterline at 85% of the least moulded depth."
FREEBOARD_FRACTION = 0.96

# Sentinel default for stem_to_rudder_stock_axis_distance_m when the ship has no rudder
# stock (e.g. azimuth thruster vessels) and the parameter is not applicable.
_NO_RUDDER_STOCK_SENTINEL = None


def _normalize_has_rudder_stock(has_rudder_stock: bool | str) -> bool:
    """Normalize has_rudder_stock to a real bool.

    params.toml declares has_rudder_stock as an enum with values ["true", "false"]
    (bool is not a valid param type), so the generator passes it as a string. Direct
    or test callers may still pass a real bool. Accept both.
    """
    if isinstance(has_rudder_stock, bool):
        return has_rudder_stock
    normalized = has_rudder_stock.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    msg = f"has_rudder_stock must be 'true' or 'false', got {has_rudder_stock!r}"
    raise ValueError(msg)


def _validate_inputs(
    total_length_on_85pct_depth_waterline_m: float,
    has_rudder_stock: bool,
    stem_to_rudder_stock_axis_distance_m: float | None,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if total_length_on_85pct_depth_waterline_m <= 0:
        msg = "total_length_on_85pct_depth_waterline_m must be > 0"
        raise ValueError(msg)
    if has_rudder_stock:
        if stem_to_rudder_stock_axis_distance_m is None:
            msg = "stem_to_rudder_stock_axis_distance_m is required when has_rudder_stock is True"
            raise ValueError(msg)
        if stem_to_rudder_stock_axis_distance_m <= 0:
            msg = "stem_to_rudder_stock_axis_distance_m must be > 0"
            raise ValueError(msg)
        if stem_to_rudder_stock_axis_distance_m > total_length_on_85pct_depth_waterline_m:
            msg = "stem_to_rudder_stock_axis_distance_m must be <= total_length_on_85pct_depth_waterline_m"
            raise ValueError(msg)


def compute(
    total_length_on_85pct_depth_waterline_m: float,
    has_rudder_stock: bool | str,
    stem_to_rudder_stock_axis_distance_m: float | None = _NO_RUDDER_STOCK_SENTINEL,
) -> dict[str, float]:
    """Compute the IACS CSR-H Freeboard length L_LL per Pt 1 Ch 1 Sec 4 §3.1.2.

    L_LL is taken as 96% of the total length on a waterline at 85% of the least
    moulded depth measured from the top of the keel, or as the length from the fore
    side of the stem to the axis of the rudder stock on that waterline, whichever is
    greater. Ships without a rudder stock (e.g. fitted with azimuth thrusters) take
    L_LL equal to 96% of the waterline length directly.

    Returns a dict with key: freeboard_length_LLL_m.
    """
    has_rudder_stock = _normalize_has_rudder_stock(has_rudder_stock)

    _validate_inputs(
        total_length_on_85pct_depth_waterline_m,
        has_rudder_stock,
        stem_to_rudder_stock_axis_distance_m,
    )

    waterline_fraction = FREEBOARD_FRACTION * total_length_on_85pct_depth_waterline_m

    if has_rudder_stock:
        # _validate_inputs guarantees the measured distance is present and positive here;
        # assert narrows float | None -> float for the type checker.
        assert stem_to_rudder_stock_axis_distance_m is not None
        freeboard_length_lll = max(waterline_fraction, stem_to_rudder_stock_axis_distance_m)
    else:
        freeboard_length_lll = waterline_fraction

    return {
        "freeboard_length_LLL_m": round(freeboard_length_lll, 2),
    }
