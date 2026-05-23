# ABOUTME: Minor head loss computation engine for pipe fittings.
# ABOUTME: Sums explicit K factors and converts them into head loss and equivalent length.

_G = 9.81


def _validate_inputs(
    fitting_1_k: float,
    fitting_1_quantity: float,
    fitting_2_k: float,
    fitting_2_quantity: float,
    fitting_3_k: float,
    fitting_3_quantity: float,
    flow_velocity_m_s: float,
    pipe_diameter_mm: float,
    darcy_friction_factor: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "fitting_1_k": fitting_1_k,
        "fitting_1_quantity": fitting_1_quantity,
        "fitting_2_k": fitting_2_k,
        "fitting_2_quantity": fitting_2_quantity,
        "fitting_3_k": fitting_3_k,
        "fitting_3_quantity": fitting_3_quantity,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if flow_velocity_m_s <= 0:
        msg = "flow_velocity_m_s must be > 0"
        raise ValueError(msg)
    if pipe_diameter_mm <= 0:
        msg = "pipe_diameter_mm must be > 0"
        raise ValueError(msg)
    if darcy_friction_factor <= 0:
        msg = "darcy_friction_factor must be > 0"
        raise ValueError(msg)


def compute(
    fitting_1_k: float,
    fitting_1_quantity: float,
    fitting_2_k: float,
    fitting_2_quantity: float,
    fitting_3_k: float,
    fitting_3_quantity: float,
    flow_velocity_m_s: float,
    pipe_diameter_mm: float,
    darcy_friction_factor: float,
) -> dict[str, float]:
    """Compute total minor head loss from explicit fitting K factors.

    Returns a dict with keys: total_k, velocity_head_m, total_minor_loss_m,
    equivalent_length_m.
    """
    _validate_inputs(
        fitting_1_k,
        fitting_1_quantity,
        fitting_2_k,
        fitting_2_quantity,
        fitting_3_k,
        fitting_3_quantity,
        flow_velocity_m_s,
        pipe_diameter_mm,
        darcy_friction_factor,
    )

    total_k = fitting_1_k * fitting_1_quantity + fitting_2_k * fitting_2_quantity + fitting_3_k * fitting_3_quantity
    velocity_head = flow_velocity_m_s**2 / (2.0 * _G)
    total_loss = total_k * velocity_head
    pipe_diameter_m = pipe_diameter_mm / 1000.0
    equivalent_length = total_loss * pipe_diameter_m / (darcy_friction_factor * velocity_head)

    return {
        "total_k": round(total_k, 2),
        "velocity_head_m": round(velocity_head, 2),
        "total_minor_loss_m": round(total_loss, 2),
        "equivalent_length_m": round(equivalent_length, 2),
    }
