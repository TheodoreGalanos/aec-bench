# ABOUTME: Computes SSC-07 ground structural-electrical safety metrics from source-pack values.
# ABOUTME: Combines SPT/CPT interpretation, shallow bearing capacity, and earthing-grid checks.

from __future__ import annotations

import math
from typing import Literal

_CE_TABLE: dict[str, float] = {
    "auto": 1.33,
    "safety": 0.96,
    "donut": 0.79,
}

_CB_TABLE: dict[str, float] = {
    "65": 1.00,
    "115": 1.00,
    "150": 1.05,
    "200": 1.15,
}

_CS_TABLE: dict[str, float] = {
    "with_liner": 1.00,
    "without_liner": 1.20,
}

_CR_BOUNDARIES: tuple[tuple[float, float], ...] = (
    (4.0, 0.75),
    (6.0, 0.85),
    (10.0, 0.95),
)

_FACTOR_TABLE: tuple[tuple[float, float, float, float], ...] = (
    (0.0, 5.7, 1.0, 0.0),
    (5.0, 7.3, 1.6, 0.5),
    (10.0, 9.6, 2.7, 1.2),
    (15.0, 12.9, 4.4, 2.5),
    (20.0, 17.7, 7.4, 5.0),
    (25.0, 25.1, 12.7, 9.7),
    (30.0, 37.2, 22.5, 19.7),
    (34.0, 52.6, 36.5, 36.0),
    (35.0, 57.8, 41.4, 42.4),
    (40.0, 95.7, 81.3, 100.4),
    (45.0, 172.3, 173.3, 297.5),
    (48.0, 258.3, 287.9, 780.1),
    (50.0, 347.5, 415.1, 1153.2),
)

_GAMMA_W = 9.81
_PA_KPA = 100.0
_NKT = 14.0
_IC_BOUNDARY = 2.6


def _require_positive(**values: float) -> None:
    """Raise ValueError when any supplied value is not strictly positive."""
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def _rod_length_factor(rod_length_m: float) -> float:
    """Return the SPT rod length correction factor."""
    for boundary, factor in _CR_BOUNDARIES:
        if rod_length_m < boundary:
            return factor
    return 1.0


def _spt_values(
    *,
    raw_n_value: int,
    effective_overburden_kpa: float,
    hammer_type: str,
    borehole_diameter_mm: str,
    sampler_type: str,
    rod_length_m: float,
) -> tuple[float, float]:
    """Compute N60 and N1,60 from source SPT values."""
    if raw_n_value <= 0:
        msg = "raw_n_value must be > 0"
        raise ValueError(msg)
    _require_positive(effective_overburden_kpa=effective_overburden_kpa, rod_length_m=rod_length_m)
    if hammer_type not in _CE_TABLE:
        msg = f"hammer_type must be one of {list(_CE_TABLE)}"
        raise ValueError(msg)
    if borehole_diameter_mm not in _CB_TABLE:
        msg = f"borehole_diameter_mm must be one of {list(_CB_TABLE)}"
        raise ValueError(msg)
    if sampler_type not in _CS_TABLE:
        msg = f"sampler_type must be one of {list(_CS_TABLE)}"
        raise ValueError(msg)

    n60 = (
        raw_n_value
        * _CE_TABLE[hammer_type]
        * _CB_TABLE[borehole_diameter_mm]
        * _CS_TABLE[sampler_type]
        * _rod_length_factor(rod_length_m)
    )
    cn = min(math.sqrt(_PA_KPA / effective_overburden_kpa), 2.0)
    return n60, n60 * cn


def _cpt_values(
    *,
    qc_mpa: float,
    fs_kpa: float,
    u2_kpa: float,
    cpt_depth_m: float,
    total_unit_weight_kn_m3: float,
    water_table_depth_m: float,
    net_area_ratio: float,
) -> tuple[float, float, float]:
    """Compute corrected cone resistance, behavior index, and CPT-derived phi."""
    _require_positive(
        qc_mpa=qc_mpa,
        cpt_depth_m=cpt_depth_m,
        total_unit_weight_kn_m3=total_unit_weight_kn_m3,
        net_area_ratio=net_area_ratio,
    )
    if fs_kpa < 0:
        msg = "fs_kpa must be >= 0"
        raise ValueError(msg)
    if water_table_depth_m < 0:
        msg = "water_table_depth_m must be >= 0"
        raise ValueError(msg)
    if net_area_ratio > 1.0:
        msg = "net_area_ratio must be <= 1.0"
        raise ValueError(msg)

    qt_mpa = qc_mpa + (u2_kpa / 1000.0) * (1.0 - net_area_ratio)
    qt_kpa = qt_mpa * 1000.0
    sigma_v0 = total_unit_weight_kn_m3 * cpt_depth_m
    pore_pressure_kpa = _GAMMA_W * max(cpt_depth_m - water_table_depth_m, 0.0)
    sigma_prime_v0 = sigma_v0 - pore_pressure_kpa
    if sigma_prime_v0 <= 0:
        msg = "effective vertical stress must be > 0"
        raise ValueError(msg)

    q_net_kpa = qt_kpa - sigma_v0
    qt_norm = q_net_kpa / sigma_prime_v0
    fr_norm = 100.0 if q_net_kpa <= 0 else fs_kpa / q_net_kpa * 100.0
    ic = math.sqrt((3.47 - math.log10(max(qt_norm, 1.0))) ** 2 + (math.log10(max(fr_norm, 0.1)) + 1.22) ** 2)
    if ic > _IC_BOUNDARY:
        phi_deg = 0.0
    else:
        phi_deg = 17.6 + 11.0 * math.log10(max(qt_norm, 1.0))
    return qt_mpa, ic, phi_deg


def _interpolate_ngamma(phi_deg: float) -> float:
    """Linearly interpolate Terzaghi Ngamma from the local lookup table."""
    clamped_phi = max(0.0, min(50.0, phi_deg))
    for i in range(len(_FACTOR_TABLE) - 1):
        phi_lo = _FACTOR_TABLE[i][0]
        phi_hi = _FACTOR_TABLE[i + 1][0]
        if phi_lo <= clamped_phi <= phi_hi:
            val_lo = _FACTOR_TABLE[i][3]
            val_hi = _FACTOR_TABLE[i + 1][3]
            fraction = (clamped_phi - phi_lo) / (phi_hi - phi_lo)
            return val_lo + fraction * (val_hi - val_lo)
    return _FACTOR_TABLE[-1][3]


def _bearing_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return Terzaghi Nc, Nq, and Ngamma for a friction angle."""
    if phi_deg < 0 or phi_deg > 50:
        msg = "governing_phi_deg must be between 0 and 50"
        raise ValueError(msg)
    if phi_deg == 0.0:
        return 5.7, 1.0, 0.0

    phi_rad = math.radians(phi_deg)
    exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
    denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = math.exp(exponent) / denominator
    nc = (nq - 1.0) / math.tan(phi_rad)
    return nc, nq, _interpolate_ngamma(phi_deg)


def _water_table_correction(
    *,
    unit_weight_kn_m3: float,
    embedment_depth_m: float,
    footing_width_m: float,
    water_table_depth_m: float,
) -> tuple[float, float]:
    """Return overburden pressure and effective unit weight for bearing."""
    if water_table_depth_m <= embedment_depth_m:
        q_kpa = unit_weight_kn_m3 * water_table_depth_m + (unit_weight_kn_m3 - _GAMMA_W) * (
            embedment_depth_m - water_table_depth_m
        )
        gamma_eff = unit_weight_kn_m3 - _GAMMA_W
    elif water_table_depth_m < embedment_depth_m + footing_width_m:
        q_kpa = unit_weight_kn_m3 * embedment_depth_m
        gamma_eff = (unit_weight_kn_m3 - _GAMMA_W) + (
            (water_table_depth_m - embedment_depth_m) / footing_width_m
        ) * _GAMMA_W
    else:
        q_kpa = unit_weight_kn_m3 * embedment_depth_m
        gamma_eff = unit_weight_kn_m3
    return q_kpa, gamma_eff


def _bearing_values(
    *,
    cohesion_kpa: float,
    governing_phi_deg: float,
    total_unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: str,
    water_table_depth_m: float,
    factor_of_safety: float,
) -> float:
    """Compute allowable Terzaghi bearing capacity for the source footing."""
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    _require_positive(
        total_unit_weight_kn_m3=total_unit_weight_kn_m3,
        footing_width_m=footing_width_m,
        factor_of_safety=factor_of_safety,
    )
    if embedment_depth_m < 0:
        msg = "embedment_depth_m must be >= 0"
        raise ValueError(msg)
    shape_factors = {
        "strip": (1.0, 0.5),
        "square": (1.3, 0.4),
        "circular": (1.3, 0.3),
    }
    if footing_shape not in shape_factors:
        msg = f"footing_shape must be one of {list(shape_factors)}"
        raise ValueError(msg)

    nc, nq, ngamma = _bearing_factors(governing_phi_deg)
    sc, sg = shape_factors[footing_shape]
    q_kpa, gamma_eff = _water_table_correction(
        unit_weight_kn_m3=total_unit_weight_kn_m3,
        embedment_depth_m=embedment_depth_m,
        footing_width_m=footing_width_m,
        water_table_depth_m=water_table_depth_m,
    )
    ultimate_bearing_capacity_kpa = cohesion_kpa * nc * sc + q_kpa * nq + gamma_eff * footing_width_m * sg * ngamma
    return ultimate_bearing_capacity_kpa / factor_of_safety


def _grid_values(
    *,
    soil_resistivity_ohm_m: float,
    grid_length_m: float,
    grid_width_m: float,
    total_conductor_length_m: float,
    burial_depth_m: float,
    grid_current_ka: float,
) -> tuple[float, float]:
    """Compute grounding-grid resistance and ground potential rise."""
    _require_positive(
        soil_resistivity_ohm_m=soil_resistivity_ohm_m,
        grid_length_m=grid_length_m,
        grid_width_m=grid_width_m,
        total_conductor_length_m=total_conductor_length_m,
        burial_depth_m=burial_depth_m,
        grid_current_ka=grid_current_ka,
    )

    grid_area_m2 = grid_length_m * grid_width_m
    conductor_term = 1.0 / total_conductor_length_m
    area_factor = 1.0 / math.sqrt(20.0 * grid_area_m2)
    depth_factor = 1.0 + 1.0 / (1.0 + burial_depth_m * math.sqrt(20.0 / grid_area_m2))
    grid_resistance_ohm = soil_resistivity_ohm_m * (conductor_term + area_factor * depth_factor)
    ground_potential_rise_v = grid_current_ka * 1000.0 * grid_resistance_ohm
    return grid_resistance_ohm, ground_potential_rise_v


def compute(
    raw_n_value: int,
    effective_overburden_kpa: float,
    hammer_type: str,
    borehole_diameter_mm: str,
    sampler_type: str,
    rod_length_m: float,
    minimum_design_n1_60: float,
    qc_mpa: float,
    fs_kpa: float,
    u2_kpa: float,
    cpt_depth_m: float,
    total_unit_weight_kn_m3: float,
    water_table_depth_m: float,
    net_area_ratio: float,
    interpreted_design_phi_deg: float,
    cohesion_kpa: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "square", "circular"],
    factor_of_safety: float,
    applied_bearing_pressure_kpa: float,
    soil_resistivity_ohm_m: float,
    grid_length_m: float,
    grid_width_m: float,
    total_conductor_length_m: float,
    burial_depth_m: float,
    grid_current_ka: float,
    gpr_limit_v: float,
) -> dict[str, float]:
    """Compute SSC-07 source-pack ground and earthing metrics."""
    _require_positive(
        minimum_design_n1_60=minimum_design_n1_60,
        applied_bearing_pressure_kpa=applied_bearing_pressure_kpa,
        gpr_limit_v=gpr_limit_v,
    )
    if interpreted_design_phi_deg < 0 or interpreted_design_phi_deg > 50:
        msg = "interpreted_design_phi_deg must be between 0 and 50"
        raise ValueError(msg)

    spt_n60, spt_n1_60 = _spt_values(
        raw_n_value=raw_n_value,
        effective_overburden_kpa=effective_overburden_kpa,
        hammer_type=hammer_type,
        borehole_diameter_mm=borehole_diameter_mm,
        sampler_type=sampler_type,
        rod_length_m=rod_length_m,
    )
    cpt_qt_mpa, cpt_ic, cpt_phi_deg = _cpt_values(
        qc_mpa=qc_mpa,
        fs_kpa=fs_kpa,
        u2_kpa=u2_kpa,
        cpt_depth_m=cpt_depth_m,
        total_unit_weight_kn_m3=total_unit_weight_kn_m3,
        water_table_depth_m=water_table_depth_m,
        net_area_ratio=net_area_ratio,
    )
    governing_phi_deg = min(interpreted_design_phi_deg, cpt_phi_deg)
    allowable_bearing_capacity_kpa = _bearing_values(
        cohesion_kpa=cohesion_kpa,
        governing_phi_deg=governing_phi_deg,
        total_unit_weight_kn_m3=total_unit_weight_kn_m3,
        footing_width_m=footing_width_m,
        embedment_depth_m=embedment_depth_m,
        footing_shape=footing_shape,
        water_table_depth_m=water_table_depth_m,
        factor_of_safety=factor_of_safety,
    )
    grid_resistance_ohm, ground_potential_rise_v = _grid_values(
        soil_resistivity_ohm_m=soil_resistivity_ohm_m,
        grid_length_m=grid_length_m,
        grid_width_m=grid_width_m,
        total_conductor_length_m=total_conductor_length_m,
        burial_depth_m=burial_depth_m,
        grid_current_ka=grid_current_ka,
    )

    spt_n1_60_margin = spt_n1_60 - minimum_design_n1_60
    bearing_margin_kpa = allowable_bearing_capacity_kpa - applied_bearing_pressure_kpa
    gpr_margin_v = gpr_limit_v - ground_potential_rise_v
    overall_pass_score = 1.0 if spt_n1_60_margin >= 0 and bearing_margin_kpa >= 0 and gpr_margin_v >= 0 else 0.0

    return {
        "spt_n60": round(spt_n60, 3),
        "spt_n1_60": round(spt_n1_60, 3),
        "spt_n1_60_margin": round(spt_n1_60_margin, 3),
        "cpt_qt_mpa": round(cpt_qt_mpa, 3),
        "cpt_ic": round(cpt_ic, 3),
        "cpt_phi_deg": round(cpt_phi_deg, 3),
        "governing_phi_deg": round(governing_phi_deg, 3),
        "allowable_bearing_capacity_kpa": round(allowable_bearing_capacity_kpa, 3),
        "bearing_utilization": round(applied_bearing_pressure_kpa / allowable_bearing_capacity_kpa, 3),
        "bearing_margin_kpa": round(bearing_margin_kpa, 3),
        "grid_resistance_ohm": round(grid_resistance_ohm, 3),
        "ground_potential_rise_v": round(ground_potential_rise_v, 3),
        "gpr_margin_v": round(gpr_margin_v, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
