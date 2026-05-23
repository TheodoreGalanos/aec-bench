# ABOUTME: Computes wireless received signal level and link margin.
# ABOUTME: Uses free-space path loss plus explicit obstacle losses.

import math


def _validate_inputs(
    transmit_power_dbm: float,
    transmit_antenna_gain_dbi: float,
    distance_m: float,
    frequency_ghz: float,
    receive_antenna_gain_dbi: float,
    obstacle_losses_db: float,
    required_receive_sensitivity_dbm: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if distance_m <= 0:
        msg = "distance_m must be > 0"
        raise ValueError(msg)
    if frequency_ghz <= 0:
        msg = "frequency_ghz must be > 0"
        raise ValueError(msg)
    if obstacle_losses_db < 0:
        msg = "obstacle_losses_db must be >= 0"
        raise ValueError(msg)
    for name, value in {
        "transmit_power_dbm": transmit_power_dbm,
        "transmit_antenna_gain_dbi": transmit_antenna_gain_dbi,
        "receive_antenna_gain_dbi": receive_antenna_gain_dbi,
        "required_receive_sensitivity_dbm": required_receive_sensitivity_dbm,
    }.items():
        if not -200 <= value <= 200:
            msg = f"{name} must be a realistic dB value"
            raise ValueError(msg)


def compute(
    transmit_power_dbm: float,
    transmit_antenna_gain_dbi: float,
    distance_m: float,
    frequency_ghz: float,
    receive_antenna_gain_dbi: float,
    obstacle_losses_db: float,
    required_receive_sensitivity_dbm: float,
) -> dict[str, float]:
    """Compute free-space path loss, received signal, and link margin."""
    _validate_inputs(
        transmit_power_dbm,
        transmit_antenna_gain_dbi,
        distance_m,
        frequency_ghz,
        receive_antenna_gain_dbi,
        obstacle_losses_db,
        required_receive_sensitivity_dbm,
    )

    distance_km = distance_m / 1000.0
    frequency_mhz = frequency_ghz * 1000.0
    free_space_path_loss_db = 32.44 + 20.0 * math.log10(distance_km) + 20.0 * math.log10(frequency_mhz)
    total_path_loss_db = free_space_path_loss_db + obstacle_losses_db
    received_signal_level_dbm = (
        transmit_power_dbm + transmit_antenna_gain_dbi + receive_antenna_gain_dbi - total_path_loss_db
    )
    link_margin_db = received_signal_level_dbm - required_receive_sensitivity_dbm

    return {
        "free_space_path_loss_db": round(free_space_path_loss_db, 2),
        "total_path_loss_db": round(total_path_loss_db, 2),
        "received_signal_level_dbm": round(received_signal_level_dbm, 2),
        "link_margin_db": round(link_margin_db, 2),
    }
