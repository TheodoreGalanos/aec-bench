# ABOUTME: Computes theoretical and practical escalator passenger capacity.
# ABOUTME: Uses escalator speed, step pitch, step width, and loading factor.


def _validate_inputs(
    escalator_speed_m_s: float,
    step_width_mm: float,
    step_pitch_mm: float,
    practical_loading_factor_pct: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "escalator_speed_m_s": escalator_speed_m_s,
        "step_width_mm": step_width_mm,
        "step_pitch_mm": step_pitch_mm,
    }.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)
    if practical_loading_factor_pct <= 0 or practical_loading_factor_pct > 100:
        msg = "practical_loading_factor_pct must be > 0 and <= 100"
        raise ValueError(msg)


def compute(
    escalator_speed_m_s: float,
    step_width_mm: float,
    step_pitch_mm: float,
    practical_loading_factor_pct: float,
) -> dict[str, float]:
    """Compute escalator steps per second and passenger capacity."""
    _validate_inputs(
        escalator_speed_m_s,
        step_width_mm,
        step_pitch_mm,
        practical_loading_factor_pct,
    )

    steps_per_second = escalator_speed_m_s / (step_pitch_mm / 1000.0)
    persons_per_step = 1.0 if step_width_mm < 800.0 else 2.0
    theoretical_capacity_persons_per_h = steps_per_second * persons_per_step * 3600.0
    practical_capacity_persons_per_h = theoretical_capacity_persons_per_h * practical_loading_factor_pct / 100.0

    return {
        "steps_per_second": round(steps_per_second, 2),
        "persons_per_step": round(persons_per_step, 2),
        "theoretical_capacity_persons_per_h": round(theoretical_capacity_persons_per_h, 2),
        "practical_capacity_persons_per_h": round(practical_capacity_persons_per_h, 2),
    }
