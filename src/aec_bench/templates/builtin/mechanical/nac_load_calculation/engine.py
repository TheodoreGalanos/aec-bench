# ABOUTME: NAC load computation engine for fire alarm notification circuits.
# ABOUTME: Sums appliance current, utilisation, spare capacity, and pass status.


def _validate_inputs(
    strobe_quantity: int,
    strobe_current_a: float,
    horn_quantity: int,
    horn_current_a: float,
    speaker_quantity: int,
    speaker_current_a: float,
    circuit_capacity_a: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    for name, value in {
        "strobe_quantity": strobe_quantity,
        "horn_quantity": horn_quantity,
        "speaker_quantity": speaker_quantity,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    for name, value in {
        "strobe_current_a": strobe_current_a,
        "horn_current_a": horn_current_a,
        "speaker_current_a": speaker_current_a,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)
    if circuit_capacity_a <= 0:
        msg = "circuit_capacity_a must be > 0"
        raise ValueError(msg)
    if strobe_quantity + horn_quantity + speaker_quantity <= 0:
        msg = "at least one notification appliance quantity must be > 0"
        raise ValueError(msg)


def compute(
    strobe_quantity: int,
    strobe_current_a: float,
    horn_quantity: int,
    horn_current_a: float,
    speaker_quantity: int,
    speaker_current_a: float,
    circuit_capacity_a: float,
) -> dict[str, float]:
    """Compute notification appliance circuit loading.

    Returns a dict with keys: total_load_a, utilisation_pct, spare_capacity_a,
    passes_capacity_check.
    """
    _validate_inputs(
        strobe_quantity,
        strobe_current_a,
        horn_quantity,
        horn_current_a,
        speaker_quantity,
        speaker_current_a,
        circuit_capacity_a,
    )

    total_load = (
        strobe_quantity * strobe_current_a + horn_quantity * horn_current_a + speaker_quantity * speaker_current_a
    )
    utilisation = total_load / circuit_capacity_a * 100.0
    spare_capacity = circuit_capacity_a - total_load

    return {
        "total_load_a": round(total_load, 2),
        "utilisation_pct": round(utilisation, 2),
        "spare_capacity_a": round(spare_capacity, 2),
        "passes_capacity_check": round(1.0 if total_load <= circuit_capacity_a else 0.0, 2),
    }
