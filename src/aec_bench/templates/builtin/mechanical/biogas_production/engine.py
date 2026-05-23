# ABOUTME: Biogas production computation engine for sludge handling checks.
# ABOUTME: Calculates biogas, methane volume, and methane energy from VS destruction.


def _validate_inputs(
    volatile_solids_feed_kg_d: float,
    volatile_solids_destruction_pct: float,
    biogas_yield_m3_kg_vs: float,
    methane_fraction: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if volatile_solids_feed_kg_d < 0:
        msg = "volatile_solids_feed_kg_d must be >= 0"
        raise ValueError(msg)
    if not 0 <= volatile_solids_destruction_pct <= 100:
        msg = "volatile_solids_destruction_pct must be between 0 and 100"
        raise ValueError(msg)
    if biogas_yield_m3_kg_vs < 0:
        msg = "biogas_yield_m3_kg_vs must be >= 0"
        raise ValueError(msg)
    if not 0 <= methane_fraction <= 1:
        msg = "methane_fraction must be between 0 and 1"
        raise ValueError(msg)


def compute(
    volatile_solids_feed_kg_d: float,
    volatile_solids_destruction_pct: float,
    biogas_yield_m3_kg_vs: float,
    methane_fraction: float,
) -> dict[str, float]:
    """Compute daily biogas and methane production.

    Returns a dict with keys: volatile_solids_destroyed_kg_d, biogas_m3_d,
    methane_m3_d, methane_energy_kwh_d.
    """
    _validate_inputs(
        volatile_solids_feed_kg_d,
        volatile_solids_destruction_pct,
        biogas_yield_m3_kg_vs,
        methane_fraction,
    )

    vs_destroyed = volatile_solids_feed_kg_d * volatile_solids_destruction_pct / 100.0
    biogas = vs_destroyed * biogas_yield_m3_kg_vs
    methane = biogas * methane_fraction
    methane_energy = methane * 9.97

    return {
        "volatile_solids_destroyed_kg_d": round(vs_destroyed, 2),
        "biogas_m3_d": round(biogas, 2),
        "methane_m3_d": round(methane, 2),
        "methane_energy_kwh_d": round(methane_energy, 2),
    }
