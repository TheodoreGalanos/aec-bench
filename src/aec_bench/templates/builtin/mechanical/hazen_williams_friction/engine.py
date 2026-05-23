# ABOUTME: Hazen-Williams pipe friction computation engine.
# ABOUTME: Calculates head loss and pressure loss for pressurised water pipe flow.

_G = 9.81
_HAZEN_WILLIAMS_COEFFICIENT = 10.67


def _validate_inputs(
    pipe_length_m: float,
    pipe_internal_diameter_mm: float,
    flow_rate_l_s: float,
    hazen_williams_c: float,
    fluid_density_kg_m3: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if pipe_length_m <= 0:
        msg = "pipe_length_m must be > 0"
        raise ValueError(msg)
    if pipe_internal_diameter_mm <= 0:
        msg = "pipe_internal_diameter_mm must be > 0"
        raise ValueError(msg)
    if flow_rate_l_s <= 0:
        msg = "flow_rate_l_s must be > 0"
        raise ValueError(msg)
    if hazen_williams_c <= 0:
        msg = "hazen_williams_c must be > 0"
        raise ValueError(msg)
    if fluid_density_kg_m3 <= 0:
        msg = "fluid_density_kg_m3 must be > 0"
        raise ValueError(msg)


def compute(
    pipe_length_m: float,
    pipe_internal_diameter_mm: float,
    flow_rate_l_s: float,
    hazen_williams_c: float,
    fluid_density_kg_m3: float,
) -> dict[str, float]:
    """Compute Hazen-Williams head loss and pressure loss.

    Returns a dict with keys: flow_rate_m3_s, head_loss_m,
    pressure_loss_kpa, hydraulic_gradient_m_per_m.
    """
    _validate_inputs(
        pipe_length_m,
        pipe_internal_diameter_mm,
        flow_rate_l_s,
        hazen_williams_c,
        fluid_density_kg_m3,
    )

    flow_rate_m3_s = flow_rate_l_s / 1000.0
    diameter_m = pipe_internal_diameter_mm / 1000.0
    head_loss_m = (
        _HAZEN_WILLIAMS_COEFFICIENT
        * pipe_length_m
        * flow_rate_m3_s**1.852
        / (hazen_williams_c**1.852 * diameter_m**4.871)
    )
    pressure_loss_kpa = fluid_density_kg_m3 * _G * head_loss_m / 1000.0
    hydraulic_gradient_m_per_m = head_loss_m / pipe_length_m

    return {
        "flow_rate_m3_s": round(flow_rate_m3_s, 3),
        "head_loss_m": round(head_loss_m, 2),
        "pressure_loss_kpa": round(pressure_loss_kpa, 2),
        "hydraulic_gradient_m_per_m": round(hydraulic_gradient_m_per_m, 4),
    }
