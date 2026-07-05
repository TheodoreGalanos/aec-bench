# ABOUTME: Computes SSC-15 occupancy, fire, and product-class compliance metrics.
# ABOUTME: Combines occupant load, fire class, NAC, smoke exhaust, and authority evidence checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    floor_area_m2: float,
    occupant_area_factor_m2_per_person: float,
    product_class_capacity_persons: float,
    flame_spread_index: float,
    flame_spread_limit: float,
    smoke_developed_index: float,
    smoke_developed_limit: float,
    fire_resistance_rating_min: float,
    required_fire_resistance_min: float,
    nac_device_count: float,
    nac_current_per_device_a: float,
    nac_supply_capacity_a: float,
    smoke_exhaust_ach: float,
    required_smoke_exhaust_ach: float,
    authority_evidence_items: float,
    required_authority_evidence_items: float,
) -> dict[str, float]:
    _require_positive(
        floor_area_m2=floor_area_m2,
        occupant_area_factor_m2_per_person=occupant_area_factor_m2_per_person,
        product_class_capacity_persons=product_class_capacity_persons,
        flame_spread_limit=flame_spread_limit,
        smoke_developed_limit=smoke_developed_limit,
        fire_resistance_rating_min=fire_resistance_rating_min,
        required_fire_resistance_min=required_fire_resistance_min,
        nac_current_per_device_a=nac_current_per_device_a,
        nac_supply_capacity_a=nac_supply_capacity_a,
        smoke_exhaust_ach=smoke_exhaust_ach,
        required_smoke_exhaust_ach=required_smoke_exhaust_ach,
        required_authority_evidence_items=required_authority_evidence_items,
    )

    occupant_load_persons = floor_area_m2 / occupant_area_factor_m2_per_person
    product_class_capacity_margin_persons = product_class_capacity_persons - occupant_load_persons
    flame_spread_margin = flame_spread_limit - flame_spread_index
    smoke_developed_margin = smoke_developed_limit - smoke_developed_index
    fire_resistance_margin_min = fire_resistance_rating_min - required_fire_resistance_min
    nac_current_margin_a = nac_supply_capacity_a - nac_device_count * nac_current_per_device_a
    smoke_exhaust_ach_margin = smoke_exhaust_ach - required_smoke_exhaust_ach
    authority_evidence_fraction = authority_evidence_items / required_authority_evidence_items

    overall_pass_score = (
        1.0
        if (
            product_class_capacity_margin_persons >= 0.0
            and flame_spread_margin >= 0.0
            and smoke_developed_margin >= 0.0
            and fire_resistance_margin_min >= 0.0
            and nac_current_margin_a >= 0.0
            and smoke_exhaust_ach_margin >= 0.0
            and authority_evidence_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "occupant_load_persons": round(occupant_load_persons, 3),
        "product_class_capacity_margin_persons": round(product_class_capacity_margin_persons, 3),
        "flame_spread_margin": round(flame_spread_margin, 3),
        "smoke_developed_margin": round(smoke_developed_margin, 3),
        "fire_resistance_margin_min": round(fire_resistance_margin_min, 3),
        "nac_current_margin_a": round(nac_current_margin_a, 3),
        "smoke_exhaust_ach_margin": round(smoke_exhaust_ach_margin, 3),
        "authority_evidence_fraction": round(authority_evidence_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
