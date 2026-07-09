# ABOUTME: Tests for the IACS CSR-H Freeboard length (L_LL) engine compute function.
# ABOUTME: Validates the greater-of regime, the no-rudder-stock case, and input validation.

from math import isclose
from pathlib import Path

import pytest

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "maritime"
    / "freeboard_length"
)


# --- Freeboard length computation tests ---


def test_compute_stem_to_rudder_stock_distance_governs() -> None:
    """Measured stem-to-rudder-stock-axis distance exceeds 96% of the waterline length,
    so it governs the greater-of."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    # total = 225.0 -> 0.96 x total = 216.0; measured = 220.0 exceeds it.
    result = compute(
        total_length_on_85pct_depth_waterline_m=225.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_axis_distance_m=220.0,
    )

    assert isclose(result["freeboard_length_LLL_m"], 220.0, rel_tol=1e-9)


def test_compute_waterline_fraction_governs() -> None:
    """Measured stem-to-rudder-stock-axis distance is below 96% of the waterline length,
    so 96% of the waterline length governs instead (the greater-of flips)."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    # total = 180.0 -> 0.96 x total = 172.8; measured = 170.0 is below it.
    result = compute(
        total_length_on_85pct_depth_waterline_m=180.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_axis_distance_m=170.0,
    )

    assert isclose(result["freeboard_length_LLL_m"], 172.8, rel_tol=1e-9)


def test_compute_no_rudder_stock_returns_96_percent() -> None:
    """Ships without a rudder stock (e.g. azimuth thrusters) take L_LL = 0.96 x total length."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    result = compute(
        total_length_on_85pct_depth_waterline_m=200.0,
        has_rudder_stock=False,
    )

    assert isclose(result["freeboard_length_LLL_m"], 192.0, rel_tol=1e-9)


def test_compute_accepts_string_false_for_has_rudder_stock() -> None:
    """The generator passes has_rudder_stock as the string 'false' (params.toml enum values
    are ["true", "false"] since bool is not a valid param type); this must behave identically
    to the Python bool False."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    result = compute(
        total_length_on_85pct_depth_waterline_m=200.0,
        has_rudder_stock="false",
    )

    assert isclose(result["freeboard_length_LLL_m"], 192.0, rel_tol=1e-9)


def test_compute_accepts_string_true_for_has_rudder_stock() -> None:
    """The generator passes has_rudder_stock as the string 'true'; the measured distance
    below the waterline fraction must still let the waterline fraction govern."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    result = compute(
        total_length_on_85pct_depth_waterline_m=180.0,
        has_rudder_stock="true",
        stem_to_rudder_stock_axis_distance_m=170.0,
    )

    assert isclose(result["freeboard_length_LLL_m"], 172.8, rel_tol=1e-9)


def test_compute_rejects_invalid_has_rudder_stock_string() -> None:
    """A has_rudder_stock string other than 'true'/'false' raises ValueError."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="has_rudder_stock"):
        compute(
            total_length_on_85pct_depth_waterline_m=200.0,
            has_rudder_stock="maybe",
        )


def test_compute_returns_only_expected_key() -> None:
    """Output dict has exactly the one scored key."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    result = compute(
        total_length_on_85pct_depth_waterline_m=200.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_axis_distance_m=195.0,
    )

    assert set(result.keys()) == {"freeboard_length_LLL_m"}


def test_compute_is_pure() -> None:
    """Same inputs produce identical outputs — function is deterministic and pure."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    result_a = compute(
        total_length_on_85pct_depth_waterline_m=210.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_axis_distance_m=205.0,
    )
    result_b = compute(
        total_length_on_85pct_depth_waterline_m=210.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_axis_distance_m=205.0,
    )

    assert result_a == result_b


# --- Validation tests ---


def test_compute_rejects_non_positive_total_length() -> None:
    """Non-positive total length raises ValueError."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="total_length_on_85pct_depth_waterline_m"):
        compute(
            total_length_on_85pct_depth_waterline_m=0.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_axis_distance_m=100.0,
        )


def test_compute_rejects_negative_total_length() -> None:
    """Negative total length raises ValueError."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="total_length_on_85pct_depth_waterline_m"):
        compute(
            total_length_on_85pct_depth_waterline_m=-50.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_axis_distance_m=40.0,
        )


def test_compute_rejects_non_positive_stem_to_rudder_stock_axis_distance() -> None:
    """Non-positive measured distance raises ValueError when has_rudder_stock is True."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_axis_distance_m"):
        compute(
            total_length_on_85pct_depth_waterline_m=200.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_axis_distance_m=0.0,
        )


def test_compute_rejects_measured_distance_exceeding_total_length() -> None:
    """Measured distance greater than the total length raises ValueError."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_axis_distance_m"):
        compute(
            total_length_on_85pct_depth_waterline_m=200.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_axis_distance_m=205.0,
        )


def test_compute_rejects_missing_stem_to_rudder_stock_axis_distance_when_has_rudder_stock() -> None:
    """Omitting the measured distance when has_rudder_stock is True raises ValueError."""
    from aec_bench.templates.builtin.maritime.freeboard_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_axis_distance_m"):
        compute(
            total_length_on_85pct_depth_waterline_m=200.0,
            has_rudder_stock=True,
        )


# --- params.toml loading test ---


def test_params_toml_loads_into_template_config() -> None:
    """params.toml is loadable by the registry and has correct structure."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(TEMPLATE_DIR)
    assert config.meta.name == "freeboard-length"
    assert config.meta.discipline == "maritime"
    assert "total_length_on_85pct_depth_waterline_m" in config.params
    assert "freeboard_length_LLL_m" in config.outputs
    assert len(config.difficulty) >= 2
    for preset in config.difficulty.values():
        for arch_name in preset.archetypes:
            assert arch_name in config.archetypes
