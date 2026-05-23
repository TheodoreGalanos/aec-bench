# ABOUTME: Nitrification solids retention time computation engine.
# ABOUTME: Calculates required SRT from temperature-corrected nitrifier growth.


def _validate_inputs(
    max_specific_growth_d: float,
    theta: float,
    wastewater_temperature_c: float,
    ammonia_n_mg_l: float,
    half_saturation_n_mg_l: float,
    dissolved_oxygen_mg_l: float,
    oxygen_half_saturation_mg_l: float,
    decay_rate_d: float,
    safety_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if max_specific_growth_d <= 0:
        msg = "max_specific_growth_d must be > 0"
        raise ValueError(msg)
    if theta <= 0:
        msg = "theta must be > 0"
        raise ValueError(msg)
    if ammonia_n_mg_l <= 0:
        msg = "ammonia_n_mg_l must be > 0"
        raise ValueError(msg)
    if half_saturation_n_mg_l <= 0:
        msg = "half_saturation_n_mg_l must be > 0"
        raise ValueError(msg)
    if dissolved_oxygen_mg_l <= 0:
        msg = "dissolved_oxygen_mg_l must be > 0"
        raise ValueError(msg)
    if oxygen_half_saturation_mg_l <= 0:
        msg = "oxygen_half_saturation_mg_l must be > 0"
        raise ValueError(msg)
    if decay_rate_d < 0:
        msg = "decay_rate_d must be >= 0"
        raise ValueError(msg)
    if safety_factor <= 0:
        msg = "safety_factor must be > 0"
        raise ValueError(msg)

    temperature_factor = theta ** (wastewater_temperature_c - 20.0)
    corrected_growth = max_specific_growth_d * temperature_factor
    substrate_factor = ammonia_n_mg_l / (half_saturation_n_mg_l + ammonia_n_mg_l)
    oxygen_factor = dissolved_oxygen_mg_l / (oxygen_half_saturation_mg_l + dissolved_oxygen_mg_l)
    net_growth = corrected_growth * substrate_factor * oxygen_factor - decay_rate_d
    if net_growth <= 0:
        msg = "net nitrifier growth rate must be > 0"
        raise ValueError(msg)


def compute(
    max_specific_growth_d: float,
    theta: float,
    wastewater_temperature_c: float,
    ammonia_n_mg_l: float,
    half_saturation_n_mg_l: float,
    dissolved_oxygen_mg_l: float,
    oxygen_half_saturation_mg_l: float,
    decay_rate_d: float,
    safety_factor: float,
) -> dict[str, float]:
    """Compute required nitrification solids retention time.

    Returns a dict with keys: temperature_corrected_growth_d, substrate_factor,
    oxygen_factor, net_growth_d, required_srt_days.
    """
    _validate_inputs(
        max_specific_growth_d,
        theta,
        wastewater_temperature_c,
        ammonia_n_mg_l,
        half_saturation_n_mg_l,
        dissolved_oxygen_mg_l,
        oxygen_half_saturation_mg_l,
        decay_rate_d,
        safety_factor,
    )

    temperature_factor = theta ** (wastewater_temperature_c - 20.0)
    temperature_corrected_growth = max_specific_growth_d * temperature_factor
    substrate_factor = ammonia_n_mg_l / (half_saturation_n_mg_l + ammonia_n_mg_l)
    oxygen_factor = dissolved_oxygen_mg_l / (oxygen_half_saturation_mg_l + dissolved_oxygen_mg_l)
    net_growth = temperature_corrected_growth * substrate_factor * oxygen_factor - decay_rate_d
    required_srt_days = safety_factor / net_growth

    return {
        "temperature_corrected_growth_d": round(temperature_corrected_growth, 3),
        "substrate_factor": round(substrate_factor, 3),
        "oxygen_factor": round(oxygen_factor, 3),
        "net_growth_d": round(net_growth, 3),
        "required_srt_days": round(required_srt_days, 2),
    }
