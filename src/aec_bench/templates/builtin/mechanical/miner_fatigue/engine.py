# ABOUTME: Miner fatigue computation engine for cumulative damage checks.
# ABOUTME: Sums explicit cycle ratios and reports remaining damage margin.


def _validate_inputs(*values: float) -> None:
    """Raise ValueError for invalid input parameters."""
    for value in values:
        if value < 0:
            msg = "cycle counts must be >= 0"
            raise ValueError(msg)


def compute(
    applied_cycles_1: float,
    allowable_cycles_1: float,
    applied_cycles_2: float,
    allowable_cycles_2: float,
    applied_cycles_3: float,
    allowable_cycles_3: float,
) -> dict[str, float]:
    """Compute cumulative Miner damage from three cycle bins.

    Returns a dict with keys: damage_bin_1, damage_bin_2, damage_bin_3,
    cumulative_damage, remaining_damage_margin, fatigue_satisfies.
    """
    _validate_inputs(
        applied_cycles_1,
        allowable_cycles_1,
        applied_cycles_2,
        allowable_cycles_2,
        applied_cycles_3,
        allowable_cycles_3,
    )
    for allowable in (allowable_cycles_1, allowable_cycles_2, allowable_cycles_3):
        if allowable <= 0:
            msg = "allowable cycle counts must be > 0"
            raise ValueError(msg)

    damage_1 = applied_cycles_1 / allowable_cycles_1
    damage_2 = applied_cycles_2 / allowable_cycles_2
    damage_3 = applied_cycles_3 / allowable_cycles_3
    cumulative_damage = damage_1 + damage_2 + damage_3
    remaining_margin = 1.0 - cumulative_damage
    fatigue_satisfies = 1.0 if cumulative_damage <= 1.0 else 0.0

    return {
        "damage_bin_1": round(damage_1, 4),
        "damage_bin_2": round(damage_2, 4),
        "damage_bin_3": round(damage_3, 4),
        "cumulative_damage": round(cumulative_damage, 4),
        "remaining_damage_margin": round(remaining_margin, 4),
        "fatigue_satisfies": round(fatigue_satisfies, 2),
    }
