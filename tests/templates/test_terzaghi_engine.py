# ABOUTME: Tests for the Terzaghi bearing capacity engine compute function.
# ABOUTME: Validates bearing factors, shape corrections, water table, and input validation.

from math import isclose
from pathlib import Path

import pytest

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "ground"
    / "terzaghi_bearing_capacity"
)


# --- Bearing capacity computation tests ---


def test_compute_strip_footing_dry_sand() -> None:
    """Strip footing on dry sand — textbook example from Das."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=18.0,
        footing_width_m=2.0,
        embedment_depth_m=1.0,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )

    assert isclose(result["nc"], 37.2, rel_tol=0.02)
    assert isclose(result["nq"], 22.5, rel_tol=0.02)
    assert isclose(result["ngamma"], 19.7, rel_tol=0.02)
    # qu = 0*37.2*1.0 + 18*22.5 + 18*2*0.5*19.7 = 405 + 354.6 = 759.6
    assert isclose(result["ultimate_bearing_capacity_kpa"], 759.6, rel_tol=0.02)
    # qa = 759.6 / 3 = 253.2
    assert isclose(result["allowable_bearing_capacity_kpa"], 253.2, rel_tol=0.02)


def test_compute_square_footing_clay() -> None:
    """Square footing on pure clay (phi=0) — Nc=5.7, Nq=1.0, Ngamma=0."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=50.0,
        friction_angle_deg=0.0,
        unit_weight_kn_m3=17.0,
        footing_width_m=3.0,
        embedment_depth_m=1.5,
        footing_shape="square",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )

    assert isclose(result["nc"], 5.7, rel_tol=0.02)
    assert isclose(result["nq"], 1.0, rel_tol=0.02)
    assert isclose(result["ngamma"], 0.0, abs_tol=0.01)
    # qu = 50*5.7*1.3 + 25.5*1.0 + 17*3*0.4*0.0 = 370.5 + 25.5 + 0 = 396.0
    assert isclose(result["ultimate_bearing_capacity_kpa"], 396.0, rel_tol=0.02)
    # qa = 396.0 / 3 = 132.0
    assert isclose(result["allowable_bearing_capacity_kpa"], 132.0, rel_tol=0.02)


def test_compute_with_water_table_at_base() -> None:
    """Water table at foundation base — Case 1: gamma_eff = gamma - gamma_w for Ngamma term."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=20.0,
        footing_width_m=2.0,
        embedment_depth_m=1.5,
        footing_shape="strip",
        water_table_depth_m=1.5,
        factor_of_safety=3.0,
    )

    # Case 1: water at base, overburden all above water
    # q = 20 * 1.5 = 30
    # gamma_eff = 20 - 9.81 = 10.19
    # qu = 0 + 30*22.5 + 10.19*2*0.5*19.7 = 675 + 200.749 = 875.749
    assert isclose(result["ultimate_bearing_capacity_kpa"], 875.75, rel_tol=0.02)

    # Compare with dry case to verify reduction
    dry_result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=20.0,
        footing_width_m=2.0,
        embedment_depth_m=1.5,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )
    assert result["ultimate_bearing_capacity_kpa"] < dry_result["ultimate_bearing_capacity_kpa"]


def test_compute_with_water_table_in_failure_zone() -> None:
    """Water table between Df and Df+B — Case 2: interpolated gamma_eff."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=20.0,
        footing_width_m=2.0,
        embedment_depth_m=1.5,
        footing_shape="strip",
        water_table_depth_m=2.0,
        factor_of_safety=3.0,
    )

    # Case 2: dw=2.0, Df=1.5, B=2.0 => Df < dw < Df+B (3.5)
    # q = 20 * 1.5 = 30
    # gamma_eff = (20 - 9.81) + (2.0 - 1.5)/2.0 * 9.81 = 10.19 + 2.4525 = 12.6425
    # qu = 0 + 30*22.5 + 12.6425*2*0.5*19.7 = 675 + 249.479 = ~924.48
    assert isclose(result["ultimate_bearing_capacity_kpa"], 924.48, rel_tol=0.02)


def test_compute_with_water_table_below_zone() -> None:
    """Water table below failure zone — Case 3: no correction."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=20.0,
        footing_width_m=2.0,
        embedment_depth_m=1.5,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )

    # Case 3: gamma_eff = gamma = 20, q = 20*1.5 = 30
    # qu = 0 + 30*22.5 + 20*2*0.5*19.7 = 675 + 394 = 1069
    assert isclose(result["ultimate_bearing_capacity_kpa"], 1069.0, rel_tol=0.02)


def test_compute_ngamma_interpolation_between_table_points() -> None:
    """Ngamma at phi=27.5 should linearly interpolate between table rows at 25 and 30."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=27.5,
        unit_weight_kn_m3=18.0,
        footing_width_m=2.0,
        embedment_depth_m=1.0,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )

    # Ngamma: 9.7 + (27.5 - 25) / (30 - 25) * (19.7 - 9.7) = 9.7 + 0.5 * 10 = 14.7
    assert isclose(result["ngamma"], 14.7, rel_tol=0.02)


def test_compute_ngamma_at_table_boundary() -> None:
    """Ngamma at exact table boundary values (phi=0 and phi=50)."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result_zero = compute(
        cohesion_kpa=50.0,
        friction_angle_deg=0.0,
        unit_weight_kn_m3=18.0,
        footing_width_m=2.0,
        embedment_depth_m=1.0,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )
    assert isclose(result_zero["ngamma"], 0.0, abs_tol=0.01)

    result_fifty = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=50.0,
        unit_weight_kn_m3=18.0,
        footing_width_m=2.0,
        embedment_depth_m=1.0,
        footing_shape="strip",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )
    assert isclose(result_fifty["ngamma"], 1153.2, rel_tol=0.02)


def test_compute_returns_all_expected_fields() -> None:
    """Output dict has exactly the five required keys."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=10.0,
        friction_angle_deg=20.0,
        unit_weight_kn_m3=18.0,
        footing_width_m=2.0,
        embedment_depth_m=1.0,
        footing_shape="strip",
    )

    expected_keys = {
        "nc",
        "nq",
        "ngamma",
        "ultimate_bearing_capacity_kpa",
        "allowable_bearing_capacity_kpa",
    }
    assert set(result.keys()) == expected_keys


def test_compute_is_pure() -> None:
    """Same inputs produce identical outputs — function is deterministic and pure."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    kwargs = {
        "cohesion_kpa": 25.0,
        "friction_angle_deg": 20.0,
        "unit_weight_kn_m3": 18.0,
        "footing_width_m": 2.0,
        "embedment_depth_m": 1.0,
        "footing_shape": "strip",
        "water_table_depth_m": 5.0,
        "factor_of_safety": 2.5,
    }

    result_a = compute(**kwargs)
    result_b = compute(**kwargs)

    assert result_a == result_b


def test_compute_rejects_negative_friction_angle() -> None:
    """Negative friction angle raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="friction"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=-5.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
        )


def test_compute_rejects_invalid_footing_shape() -> None:
    """Invalid footing shape raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="footing_shape"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="hexagon",
        )


def test_compute_rejects_friction_angle_above_50() -> None:
    """Friction angle above 50 degrees raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="friction"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=55.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
        )


def test_compute_rejects_negative_cohesion() -> None:
    """Negative cohesion raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="cohesion"):
        compute(
            cohesion_kpa=-10.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
        )


def test_compute_rejects_zero_unit_weight() -> None:
    """Zero unit weight raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="unit_weight"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=0.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
        )


def test_compute_rejects_zero_footing_width() -> None:
    """Zero footing width raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="footing_width"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=0.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
        )


def test_compute_rejects_negative_embedment_depth() -> None:
    """Negative embedment depth raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="embedment"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=-1.0,
            footing_shape="strip",
        )


def test_compute_rejects_zero_factor_of_safety() -> None:
    """Zero factor of safety raises ValueError."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    with pytest.raises(ValueError, match="factor_of_safety"):
        compute(
            cohesion_kpa=0.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=18.0,
            footing_width_m=2.0,
            embedment_depth_m=1.0,
            footing_shape="strip",
            factor_of_safety=0.0,
        )


def test_compute_circular_footing_shape_factors() -> None:
    """Circular footing uses sc=1.3 and sg=0.3."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=50.0,
        friction_angle_deg=0.0,
        unit_weight_kn_m3=17.0,
        footing_width_m=3.0,
        embedment_depth_m=1.5,
        footing_shape="circular",
        water_table_depth_m=100.0,
        factor_of_safety=3.0,
    )

    # qu = 50*5.7*1.3 + 25.5*1.0 + 17*3*0.3*0.0 = 370.5 + 25.5 + 0 = 396.0
    # Same as square for phi=0 because Ngamma=0
    assert isclose(result["ultimate_bearing_capacity_kpa"], 396.0, rel_tol=0.02)


def test_compute_water_table_above_foundation_level() -> None:
    """Water table above foundation level (Case 1 with dw < Df)."""
    from aec_bench.templates.builtin.ground.terzaghi_bearing_capacity.engine import compute

    result = compute(
        cohesion_kpa=0.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=20.0,
        footing_width_m=2.0,
        embedment_depth_m=2.0,
        footing_shape="strip",
        water_table_depth_m=1.0,
        factor_of_safety=3.0,
    )

    # Case 1: dw=1.0 < Df=2.0
    # q = gamma * dw + (gamma - gamma_w) * (Df - dw)
    # q = 20*1.0 + (20 - 9.81)*(2.0 - 1.0) = 20 + 10.19 = 30.19
    # gamma_eff = 20 - 9.81 = 10.19
    # qu = 0 + 30.19*22.5 + 10.19*2*0.5*19.7 = 679.275 + 200.749 = 880.024
    assert isclose(result["ultimate_bearing_capacity_kpa"], 880.02, rel_tol=0.02)


# --- params.toml loading test ---


def test_params_toml_loads_into_template_config() -> None:
    """params.toml is loadable by the registry and has correct structure."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(TEMPLATE_DIR)
    assert config.meta.name == "terzaghi-bearing-capacity"
    assert "cohesion_kpa" in config.params
    assert len(config.difficulty) >= 2
    for preset in config.difficulty.values():
        for arch_name in preset.archetypes:
            assert arch_name in config.archetypes
