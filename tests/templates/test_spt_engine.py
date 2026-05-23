# ABOUTME: Tests for the SPT N-value correction engine compute function.
# ABOUTME: Validates correction factor lookups, overburden normalisation, and input validation.

from math import isclose
from pathlib import Path

import pytest

SPT_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin" / "ground" / "spt_corrections"
)


def _compute(**kwargs) -> dict[str, float]:
    """Import and call compute with given kwargs."""
    from aec_bench.templates.builtin.ground.spt_corrections.engine import compute

    return compute(**kwargs)


# Standard kwargs for a baseline test case
_BASELINE = {
    "raw_n_value": 20,
    "effective_overburden_kpa": 100.0,
    "hammer_type": "auto",
    "borehole_diameter_mm": "115",
    "sampler_type": "with_liner",
    "rod_length_m": 12.0,
}


def test_compute_auto_hammer_standard_borehole() -> None:
    """Auto hammer, 115mm borehole, with liner, >10m rod: CE=1.33, CB=1.0, CS=1.0, CR=1.0."""
    result = _compute(**_BASELINE)
    assert isclose(result["ce"], 1.33, rel_tol=0.01)
    assert isclose(result["cb"], 1.00, rel_tol=0.01)
    assert isclose(result["cs"], 1.00, rel_tol=0.01)
    assert isclose(result["cr"], 1.00, rel_tol=0.01)
    # N60 = 20 * 1.33 * 1.0 * 1.0 * 1.0 = 26.6
    assert isclose(result["n60"], 26.6, rel_tol=0.03)
    # CN = sqrt(100/100) = 1.0
    assert isclose(result["cn"], 1.0, rel_tol=0.03)
    # (N1)60 = 1.0 * 26.6 = 26.6
    assert isclose(result["n1_60"], 26.6, rel_tol=0.03)


def test_compute_safety_hammer() -> None:
    """Safety hammer should give CE=0.96."""
    result = _compute(**{**_BASELINE, "hammer_type": "safety"})
    assert isclose(result["ce"], 0.96, rel_tol=0.01)
    # N60 = 20 * 0.96 * 1.0 * 1.0 * 1.0 = 19.2
    assert isclose(result["n60"], 19.2, rel_tol=0.03)


def test_compute_donut_hammer() -> None:
    """Donut hammer should give CE=0.79."""
    result = _compute(**{**_BASELINE, "hammer_type": "donut"})
    assert isclose(result["ce"], 0.79, rel_tol=0.01)


def test_compute_large_borehole_correction() -> None:
    """200mm borehole should give CB=1.15."""
    result = _compute(**{**_BASELINE, "borehole_diameter_mm": "200"})
    assert isclose(result["cb"], 1.15, rel_tol=0.01)


def test_compute_without_liner() -> None:
    """Without liner should give CS=1.20."""
    result = _compute(**{**_BASELINE, "sampler_type": "without_liner"})
    assert isclose(result["cs"], 1.20, rel_tol=0.01)


def test_compute_short_rod_correction() -> None:
    """3m rod should give CR=0.75."""
    result = _compute(**{**_BASELINE, "rod_length_m": 3.0})
    assert isclose(result["cr"], 0.75, rel_tol=0.01)


def test_compute_long_rod_correction() -> None:
    """15m rod should give CR=1.00."""
    result = _compute(**{**_BASELINE, "rod_length_m": 15.0})
    assert isclose(result["cr"], 1.00, rel_tol=0.01)


def test_compute_cn_capped_at_2() -> None:
    """Very low overburden (10 kPa) should cap CN at 2.0, not sqrt(100/10)=3.16."""
    result = _compute(**{**_BASELINE, "effective_overburden_kpa": 10.0})
    assert isclose(result["cn"], 2.0, rel_tol=0.01)


def test_compute_returns_all_expected_fields() -> None:
    """Output should have exactly 7 keys."""
    result = _compute(**_BASELINE)
    expected_keys = {"ce", "cb", "cs", "cr", "n60", "cn", "n1_60"}
    assert set(result.keys()) == expected_keys


def test_compute_is_pure() -> None:
    """Same inputs should produce identical outputs."""
    a = _compute(**_BASELINE)
    b = _compute(**_BASELINE)
    assert a == b


def test_compute_rejects_negative_n_value() -> None:
    """Negative N value should raise ValueError."""
    with pytest.raises(ValueError, match="raw_n_value"):
        _compute(**{**_BASELINE, "raw_n_value": -1})


def test_compute_rejects_invalid_hammer_type() -> None:
    """Unknown hammer type should raise ValueError."""
    with pytest.raises(ValueError, match="hammer_type"):
        _compute(**{**_BASELINE, "hammer_type": "pneumatic"})


def test_params_toml_loads_into_template_config() -> None:
    """Verify the hand-authored params.toml parses without error."""
    from aec_bench.templates.registry import load_template

    config, _ = load_template(SPT_TEMPLATE_DIR)
    assert config.meta.name == "spt-corrections"
    assert "raw_n_value" in config.params
    assert len(config.difficulty) >= 2
    assert len(config.archetypes) >= 2
