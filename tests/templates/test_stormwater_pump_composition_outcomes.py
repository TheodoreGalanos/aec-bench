# ABOUTME: Tests task-owned component and integration projections for the A04 pump composition target.
# ABOUTME: Keeps learning assessment independent from the verifier's task-specific field structure.

import pytest

from aec_bench.templates.builtin.mechanical.stormwater_pump_station_control_backup_energy_package.outcomes import (
    component_a_correct,
    component_b_correct,
    composition_outcome,
    integration_correct,
)


def test_component_projections_distinguish_headloss_power_and_integration() -> None:
    headloss_only = {
        "hazen_williams_loss_m": 1.0,
        "rising_main_velocity_m_s": 1.0,
        "total_dynamic_head_m": 0.0,
        "hydraulic_power_kw": 0.0,
        "motor_input_power_kw": 0.0,
    }
    power_only = {
        "hazen_williams_loss_m": 0.0,
        "rising_main_velocity_m_s": 0.0,
        "total_dynamic_head_m": 0.0,
        "hydraulic_power_kw": 1.0,
        "motor_input_power_kw": 1.0,
    }
    composed = {field: 1.0 for field in headloss_only}

    assert component_a_correct(headloss_only) == 1.0
    assert component_b_correct(headloss_only) == 0.0
    assert integration_correct(headloss_only) == 0.0
    assert component_a_correct(power_only) == 0.0
    assert component_b_correct(power_only) == 1.0
    assert integration_correct(power_only) == 0.0
    assert integration_correct(composed) == 1.0


@pytest.mark.parametrize(
    "details",
    (
        None,
        {},
        {"hazen_williams_loss_m": True, "rising_main_velocity_m_s": 1.0},
        {"hazen_williams_loss_m": 1.1, "rising_main_velocity_m_s": 1.0},
    ),
)
def test_component_projection_rejects_unavailable_or_invalid_evidence(details: dict[str, object] | None) -> None:
    assert component_a_correct(details) is None


@pytest.mark.parametrize(("reward", "expected"), ((0.0, 0.0), (0.54, 0.54), (1, 1.0)))
def test_composition_outcome_accepts_bounded_numeric_reward(reward: object, expected: float) -> None:
    assert composition_outcome(reward) == expected


@pytest.mark.parametrize("reward", (None, True, -0.1, 1.1, "1.0"))
def test_composition_outcome_rejects_invalid_reward(reward: object) -> None:
    assert composition_outcome(reward) is None
