# ABOUTME: Tests for the IACS CSR-H Rule length (L) engine compute function.
# ABOUTME: Validates the 96%/97% clamp regimes, the no-rudder-stock case, and input validation.

from math import isclose
from pathlib import Path

import pytest

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin" / "maritime" / "rule_length"
)


# --- Rule length computation tests ---


def test_compute_measured_distance_between_bounds_returns_measured() -> None:
    """Measured distance within [0.96L, 0.97L] is used as-is (no clamp applied)."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    # extreme = 200 m -> lower = 192.0, upper = 194.0; measured = 193.0 is inside.
    result = compute(
        extreme_length_on_waterline_at_TSC_m=200.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_distance_m=193.0,
    )

    assert isclose(result["rule_length_L_m"], 193.0, rel_tol=1e-9)


def test_compute_measured_distance_below_lower_bound_clamps_to_96_percent() -> None:
    """Measured distance below 0.96 x extreme length is clamped up to the lower bound."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    # extreme = 200 m -> lower = 192.0; measured = 180.0 is below lower bound.
    result = compute(
        extreme_length_on_waterline_at_TSC_m=200.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_distance_m=180.0,
    )

    assert isclose(result["rule_length_L_m"], 192.0, rel_tol=1e-9)


def test_compute_measured_distance_above_upper_bound_clamps_to_97_percent() -> None:
    """Measured distance above 0.97 x extreme length is clamped down to the upper bound."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    # extreme = 200 m -> upper = 194.0; measured = 199.0 exceeds upper bound.
    result = compute(
        extreme_length_on_waterline_at_TSC_m=200.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_distance_m=199.0,
    )

    assert isclose(result["rule_length_L_m"], 194.0, rel_tol=1e-9)


def test_compute_no_rudder_stock_returns_97_percent() -> None:
    """Ships without a rudder stock (e.g. azimuth thrusters) take L = 0.97 x extreme length."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    result = compute(
        extreme_length_on_waterline_at_TSC_m=150.0,
        has_rudder_stock=False,
    )

    assert isclose(result["rule_length_L_m"], 145.5, rel_tol=1e-9)


def test_compute_returns_only_expected_key() -> None:
    """Output dict has exactly the one scored key."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    result = compute(
        extreme_length_on_waterline_at_TSC_m=200.0,
        has_rudder_stock=True,
        stem_to_rudder_stock_distance_m=193.0,
    )

    assert set(result.keys()) == {"rule_length_L_m"}


def test_compute_is_pure() -> None:
    """Same inputs produce identical outputs — function is deterministic and pure."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    kwargs = {
        "extreme_length_on_waterline_at_TSC_m": 210.0,
        "has_rudder_stock": True,
        "stem_to_rudder_stock_distance_m": 195.0,
    }

    result_a = compute(**kwargs)
    result_b = compute(**kwargs)

    assert result_a == result_b


# --- Validation tests ---


def test_compute_rejects_non_positive_extreme_length() -> None:
    """Non-positive extreme length raises ValueError."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    with pytest.raises(ValueError, match="extreme_length_on_waterline_at_TSC_m"):
        compute(
            extreme_length_on_waterline_at_TSC_m=0.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_distance_m=100.0,
        )


def test_compute_rejects_negative_extreme_length() -> None:
    """Negative extreme length raises ValueError."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    with pytest.raises(ValueError, match="extreme_length_on_waterline_at_TSC_m"):
        compute(
            extreme_length_on_waterline_at_TSC_m=-50.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_distance_m=40.0,
        )


def test_compute_rejects_non_positive_stem_to_rudder_stock_distance() -> None:
    """Non-positive measured distance raises ValueError when has_rudder_stock is True."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_distance_m"):
        compute(
            extreme_length_on_waterline_at_TSC_m=200.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_distance_m=0.0,
        )


def test_compute_rejects_measured_distance_exceeding_extreme_length() -> None:
    """Measured distance greater than the extreme length raises ValueError."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_distance_m"):
        compute(
            extreme_length_on_waterline_at_TSC_m=200.0,
            has_rudder_stock=True,
            stem_to_rudder_stock_distance_m=205.0,
        )


def test_compute_rejects_missing_stem_to_rudder_stock_distance_when_has_rudder_stock() -> None:
    """Omitting the measured distance when has_rudder_stock is True raises ValueError."""
    from aec_bench.templates.builtin.maritime.rule_length.engine import compute

    with pytest.raises(ValueError, match="stem_to_rudder_stock_distance_m"):
        compute(
            extreme_length_on_waterline_at_TSC_m=200.0,
            has_rudder_stock=True,
        )


# --- params.toml loading test ---


def test_params_toml_loads_into_template_config() -> None:
    """params.toml is loadable by the registry and has correct structure."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(TEMPLATE_DIR)
    assert config.meta.name == "rule-length"
    assert config.meta.discipline == "maritime"
    assert "extreme_length_on_waterline_at_TSC_m" in config.params
    assert "rule_length_L_m" in config.outputs
    assert len(config.difficulty) >= 2
    for preset in config.difficulty.values():
        for arch_name in preset.archetypes:
            assert arch_name in config.archetypes
