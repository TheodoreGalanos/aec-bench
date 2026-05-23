# ABOUTME: Imperial Hazen-Williams sprinkler friction-loss computation engine.
# ABOUTME: Calculates pipe and equivalent-length pressure loss in psi.

_NFPA_HAZEN_WILLIAMS_COEFFICIENT = 4.52


def _validate_inputs(
    flow_rate_gpm: float,
    pipe_length_ft: float,
    pipe_internal_diameter_in: float,
    hazen_williams_c: float,
    fitting_equivalent_length_ft: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if flow_rate_gpm <= 0:
        msg = "flow_rate_gpm must be > 0"
        raise ValueError(msg)
    if pipe_length_ft <= 0:
        msg = "pipe_length_ft must be > 0"
        raise ValueError(msg)
    if pipe_internal_diameter_in <= 0:
        msg = "pipe_internal_diameter_in must be > 0"
        raise ValueError(msg)
    if hazen_williams_c <= 0:
        msg = "hazen_williams_c must be > 0"
        raise ValueError(msg)
    if fitting_equivalent_length_ft < 0:
        msg = "fitting_equivalent_length_ft must be >= 0"
        raise ValueError(msg)


def compute(
    flow_rate_gpm: float,
    pipe_length_ft: float,
    pipe_internal_diameter_in: float,
    hazen_williams_c: float,
    fitting_equivalent_length_ft: float,
) -> dict[str, float]:
    """Compute sprinkler pipe friction loss using the imperial Hazen-Williams form.

    Returns a dict with keys: friction_loss_per_ft_psi,
    equivalent_length_ft, pipe_friction_loss_psi, total_pressure_loss_psi.
    """
    _validate_inputs(
        flow_rate_gpm,
        pipe_length_ft,
        pipe_internal_diameter_in,
        hazen_williams_c,
        fitting_equivalent_length_ft,
    )

    friction_loss_per_ft = (
        _NFPA_HAZEN_WILLIAMS_COEFFICIENT
        * flow_rate_gpm**1.85
        / (hazen_williams_c**1.85 * pipe_internal_diameter_in**4.87)
    )
    equivalent_length_ft = pipe_length_ft + fitting_equivalent_length_ft
    pipe_friction_loss_psi = friction_loss_per_ft * pipe_length_ft
    total_pressure_loss_psi = friction_loss_per_ft * equivalent_length_ft

    return {
        "friction_loss_per_ft_psi": round(friction_loss_per_ft, 4),
        "equivalent_length_ft": round(equivalent_length_ft, 2),
        "pipe_friction_loss_psi": round(pipe_friction_loss_psi, 2),
        "total_pressure_loss_psi": round(total_pressure_loss_psi, 2),
    }
