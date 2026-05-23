# ABOUTME: Tests for the infinite slope factor of safety engine compute function.
# ABOUTME: Validates dry/wet/cohesionless cases, special case reductions, and input validation.

from math import isclose, radians, tan
from pathlib import Path

import pytest

SLOPE_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin" / "ground" / "infinite_slope"
)


def _compute(**kwargs) -> dict[str, float]:
    """Import and call compute with given kwargs."""
    from aec_bench.templates.builtin.ground.infinite_slope.engine import compute

    return compute(**kwargs)


# Standard kwargs for a baseline dry cohesionless slope
_DRY_COHESIONLESS = {
    "slope_angle_deg": 25.0,
    "friction_angle_deg": 35.0,
    "cohesion_kpa": 0.0,
    "unit_weight_kn_m3": 18.0,
    "failure_depth_m": 3.0,
    "water_table_depth_m": 20.0,  # well below failure surface
}


def test_compute_dry_cohesionless() -> None:
    """Dry cohesionless slope: FoS = tan(phi') / tan(beta)."""
    result = _compute(**_DRY_COHESIONLESS)
    expected_fos = tan(radians(35.0)) / tan(radians(25.0))
    assert isclose(result["factor_of_safety"], expected_fos, rel_tol=0.01)
    assert isclose(result["pore_pressure_kpa"], 0.0, abs_tol=0.01)


def test_compute_dry_with_cohesion() -> None:
    """Dry slope with cohesion — FoS should be higher than cohesionless case."""
    result = _compute(**{**_DRY_COHESIONLESS, "cohesion_kpa": 10.0})
    cohesionless = _compute(**_DRY_COHESIONLESS)
    assert result["factor_of_safety"] > cohesionless["factor_of_safety"]
    assert isclose(result["pore_pressure_kpa"], 0.0, abs_tol=0.01)
    # Hand calc: beta=25, phi=35, c=10, gamma=18, z=3, no water
    # driving = 18 * 3 * sin(25) * cos(25) = 54 * 0.4226 * 0.9063 = 20.68
    # resisting = 10 + (18 * 3 * cos^2(25) - 0) * tan(35) = 10 + 44.35 * 0.7002 = 41.05
    # FoS = 41.05 / 20.68 = 1.985
    assert isclose(result["factor_of_safety"], 1.985, rel_tol=0.02)


def test_compute_with_water_table() -> None:
    """Water table within failure zone should reduce FoS compared to dry case."""
    dry = _compute(**_DRY_COHESIONLESS)
    wet = _compute(**{**_DRY_COHESIONLESS, "water_table_depth_m": 1.0})
    assert wet["factor_of_safety"] < dry["factor_of_safety"]
    assert wet["pore_pressure_kpa"] > 0


def test_compute_water_table_below_failure() -> None:
    """Water table below failure surface should give same result as dry."""
    dry = _compute(**_DRY_COHESIONLESS)
    deep_water = _compute(**{**_DRY_COHESIONLESS, "water_table_depth_m": 5.0})
    assert isclose(dry["factor_of_safety"], deep_water["factor_of_safety"], rel_tol=0.001)
    assert isclose(deep_water["pore_pressure_kpa"], 0.0, abs_tol=0.01)


def test_compute_fully_saturated() -> None:
    """Water table at surface (zw=0) should give maximum pore pressure."""
    result = _compute(
        **{
            **_DRY_COHESIONLESS,
            "cohesion_kpa": 10.0,
            "water_table_depth_m": 0.0,
        }
    )
    assert result["pore_pressure_kpa"] > 0
    assert result["factor_of_safety"] > 0


def test_compute_saturated_cohesionless() -> None:
    """Saturated cohesionless: FoS = ((gamma - gamma_w) / gamma) * tan(phi') / tan(beta)."""
    gamma = 18.0
    gamma_w = 9.81
    result = _compute(
        **{
            **_DRY_COHESIONLESS,
            "water_table_depth_m": 0.0,
        }
    )
    expected = ((gamma - gamma_w) / gamma) * tan(radians(35.0)) / tan(radians(25.0))
    assert isclose(result["factor_of_safety"], expected, rel_tol=0.01)


def test_compute_steep_slope_low_fos() -> None:
    """Steep slope with low friction angle should give FoS close to 1.0 or below."""
    result = _compute(
        **{
            "slope_angle_deg": 35.0,
            "friction_angle_deg": 30.0,
            "cohesion_kpa": 0.0,
            "unit_weight_kn_m3": 18.0,
            "failure_depth_m": 2.0,
            "water_table_depth_m": 20.0,
        }
    )
    # tan(30)/tan(35) = 0.577/0.700 = 0.824
    assert result["factor_of_safety"] < 1.0


def test_compute_returns_all_expected_fields() -> None:
    """Output should have exactly 4 keys."""
    result = _compute(**_DRY_COHESIONLESS)
    expected_keys = {"pore_pressure_kpa", "driving_stress_kpa", "resisting_stress_kpa", "factor_of_safety"}
    assert set(result.keys()) == expected_keys


def test_compute_is_pure() -> None:
    """Same inputs should produce identical outputs."""
    a = _compute(**_DRY_COHESIONLESS)
    b = _compute(**_DRY_COHESIONLESS)
    assert a == b


def test_compute_rejects_small_slope_angle() -> None:
    """Slope angle < 5 should raise ValueError."""
    with pytest.raises(ValueError, match="slope_angle_deg"):
        _compute(**{**_DRY_COHESIONLESS, "slope_angle_deg": 3.0})


def test_compute_rejects_negative_friction_angle() -> None:
    """Negative friction angle should raise ValueError."""
    with pytest.raises(ValueError, match="friction_angle_deg"):
        _compute(**{**_DRY_COHESIONLESS, "friction_angle_deg": -5.0})


def test_compute_rejects_negative_failure_depth() -> None:
    """Negative failure depth should raise ValueError."""
    with pytest.raises(ValueError, match="failure_depth_m"):
        _compute(**{**_DRY_COHESIONLESS, "failure_depth_m": -1.0})


def test_params_toml_loads_into_template_config() -> None:
    """Verify the hand-authored params.toml parses without error."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(SLOPE_TEMPLATE_DIR)
    assert config.meta.name == "infinite-slope"
    assert "slope_angle_deg" in config.params
    assert len(config.difficulty) >= 2
    assert len(config.archetypes) >= 2
