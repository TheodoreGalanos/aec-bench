# ABOUTME: Tests for the IACS CSR-H Block coefficient (C_B) engine compute function.
# ABOUTME: Validates worked examples across ship types and input validation.

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
    / "block_coefficient"
)


# --- Block coefficient computation tests ---


def test_compute_capesize_bulk_carrier_worked_example() -> None:
    """Capesize bulk carrier: Delta=180000 t, L=280 m, B=45 m, T_SC=18 m -> C_B=0.77."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    result = compute(
        moulded_displacement_t=180000.0,
        rule_length_L_m=280.0,
        moulded_breadth_B_m=45.0,
        scantling_draught_TSC_m=18.0,
    )

    assert isclose(result["block_coefficient_CB"], 0.77, rel_tol=1e-9)


def test_compute_vlcc_tanker_worked_example() -> None:
    """VLCC tanker: Delta=366000 t, L=330 m, B=60 m, T_SC=22 m -> C_B=0.82."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    result = compute(
        moulded_displacement_t=366000.0,
        rule_length_L_m=330.0,
        moulded_breadth_B_m=60.0,
        scantling_draught_TSC_m=22.0,
    )

    assert isclose(result["block_coefficient_CB"], 0.82, rel_tol=1e-9)


def test_compute_container_ship_worked_example() -> None:
    """Container ship: Delta=125000 t, L=310 m, B=45 m, T_SC=13.5 m -> C_B=0.65 (finer hull)."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    result = compute(
        moulded_displacement_t=125000.0,
        rule_length_L_m=310.0,
        moulded_breadth_B_m=45.0,
        scantling_draught_TSC_m=13.5,
    )

    assert isclose(result["block_coefficient_CB"], 0.65, rel_tol=1e-9)


def test_compute_general_cargo_worked_example() -> None:
    """General cargo ship: Delta=23500 t, L=150 m, B=23 m, T_SC=9 m -> C_B=0.74."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    result = compute(
        moulded_displacement_t=23500.0,
        rule_length_L_m=150.0,
        moulded_breadth_B_m=23.0,
        scantling_draught_TSC_m=9.0,
    )

    assert isclose(result["block_coefficient_CB"], 0.74, rel_tol=1e-9)


def test_compute_returns_only_expected_key() -> None:
    """Output dict has exactly the one scored key."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    result = compute(
        moulded_displacement_t=180000.0,
        rule_length_L_m=280.0,
        moulded_breadth_B_m=45.0,
        scantling_draught_TSC_m=18.0,
    )

    assert set(result.keys()) == {"block_coefficient_CB"}


def test_compute_is_pure() -> None:
    """Same inputs produce identical outputs — function is deterministic and pure."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    kwargs = {
        "moulded_displacement_t": 190000.0,
        "rule_length_L_m": 280.0,
        "moulded_breadth_B_m": 45.0,
        "scantling_draught_TSC_m": 18.0,
    }

    result_a = compute(**kwargs)
    result_b = compute(**kwargs)

    assert result_a == result_b


# --- Validation tests ---


def test_compute_rejects_non_positive_moulded_displacement() -> None:
    """Non-positive moulded displacement raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="moulded_displacement_t"):
        compute(
            moulded_displacement_t=0.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_negative_moulded_displacement() -> None:
    """Negative moulded displacement raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="moulded_displacement_t"):
        compute(
            moulded_displacement_t=-1000.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_non_positive_rule_length() -> None:
    """Non-positive Rule length raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="rule_length_L_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=0.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_negative_rule_length() -> None:
    """Negative Rule length raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="rule_length_L_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=-280.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_non_positive_moulded_breadth() -> None:
    """Non-positive moulded breadth raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="moulded_breadth_B_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=0.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_negative_moulded_breadth() -> None:
    """Negative moulded breadth raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="moulded_breadth_B_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=-45.0,
            scantling_draught_TSC_m=18.0,
        )


def test_compute_rejects_non_positive_scantling_draught() -> None:
    """Non-positive scantling draught raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="scantling_draught_TSC_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=0.0,
        )


def test_compute_rejects_negative_scantling_draught() -> None:
    """Negative scantling draught raises ValueError."""
    from aec_bench.templates.builtin.maritime.block_coefficient.engine import compute

    with pytest.raises(ValueError, match="scantling_draught_TSC_m"):
        compute(
            moulded_displacement_t=180000.0,
            rule_length_L_m=280.0,
            moulded_breadth_B_m=45.0,
            scantling_draught_TSC_m=-18.0,
        )


# --- params.toml loading test ---


def test_params_toml_loads_into_template_config() -> None:
    """params.toml is loadable by the registry and has correct structure."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(TEMPLATE_DIR)
    assert config.meta.name == "block-coefficient"
    assert config.meta.discipline == "maritime"
    assert "moulded_displacement_t" in config.params
    assert "block_coefficient_CB" in config.outputs
    assert len(config.difficulty) >= 2
    for preset in config.difficulty.values():
        for arch_name in preset.archetypes:
            assert arch_name in config.archetypes
