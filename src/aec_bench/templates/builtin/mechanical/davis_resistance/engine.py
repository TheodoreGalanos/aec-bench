# ABOUTME: Davis train resistance computation engine.
# ABOUTME: Calculates resistance force and tractive power from speed and Davis coefficients.


def _validate_inputs(
    train_mass_t: float,
    speed_km_h: float,
    coefficient_a_n_t: float,
    coefficient_b_n_t_km_h: float,
    coefficient_c_n_t_km_h2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if train_mass_t <= 0:
        msg = "train_mass_t must be > 0"
        raise ValueError(msg)
    if speed_km_h < 0:
        msg = "speed_km_h must be >= 0"
        raise ValueError(msg)
    if coefficient_a_n_t < 0:
        msg = "coefficient_a_n_t must be >= 0"
        raise ValueError(msg)
    if coefficient_b_n_t_km_h < 0:
        msg = "coefficient_b_n_t_km_h must be >= 0"
        raise ValueError(msg)
    if coefficient_c_n_t_km_h2 < 0:
        msg = "coefficient_c_n_t_km_h2 must be >= 0"
        raise ValueError(msg)


def compute(
    train_mass_t: float,
    speed_km_h: float,
    coefficient_a_n_t: float,
    coefficient_b_n_t_km_h: float,
    coefficient_c_n_t_km_h2: float,
) -> dict[str, float]:
    """Compute Davis resistance and tractive power.

    Returns a dict with keys: speed_m_s, resistance_n_per_t,
    total_resistance_kn, tractive_power_kw.
    """
    _validate_inputs(
        train_mass_t,
        speed_km_h,
        coefficient_a_n_t,
        coefficient_b_n_t_km_h,
        coefficient_c_n_t_km_h2,
    )

    speed_m_s = speed_km_h / 3.6
    resistance_n_per_t = (
        coefficient_a_n_t + coefficient_b_n_t_km_h * speed_km_h + coefficient_c_n_t_km_h2 * speed_km_h**2
    )
    total_resistance_kn = resistance_n_per_t * train_mass_t / 1000.0
    tractive_power_kw = total_resistance_kn * speed_m_s

    return {
        "speed_m_s": round(speed_m_s, 2),
        "resistance_n_per_t": round(resistance_n_per_t, 2),
        "total_resistance_kn": round(total_resistance_kn, 2),
        "tractive_power_kw": round(tractive_power_kw, 2),
    }
