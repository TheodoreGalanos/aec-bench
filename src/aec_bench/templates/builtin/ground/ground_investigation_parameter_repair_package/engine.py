# ABOUTME: Computes SSC-07 ground investigation parameter repair metrics.
# ABOUTME: Combines source conflict, repaired design checks, and comment closeout values.

from __future__ import annotations


def compute(
    cpt_phi_deg: float,
    lab_phi_deg: float,
    adopted_phi_deg: float,
    spt_n1_60: float,
    minimum_n1_60: float,
    applied_bearing_pressure_kpa: float,
    repaired_allowable_bearing_kpa: float,
    wall_sliding_fs: float,
    minimum_wall_sliding_fs: float,
    repaired_grid_resistance_ohm: float,
    maximum_grid_resistance_ohm: float,
    closed_comments: float,
    total_comments: float,
) -> dict[str, float]:
    """Compute parameter-repair source-pack metrics."""
    phi_source_delta_deg = abs(cpt_phi_deg - lab_phi_deg)
    spt_n1_60_margin = spt_n1_60 - minimum_n1_60
    bearing_utilization = applied_bearing_pressure_kpa / repaired_allowable_bearing_kpa
    bearing_margin_kpa = repaired_allowable_bearing_kpa - applied_bearing_pressure_kpa
    wall_sliding_fs_margin = wall_sliding_fs - minimum_wall_sliding_fs
    grid_resistance_margin_ohm = maximum_grid_resistance_ohm - repaired_grid_resistance_ohm
    comment_closeout_percent = closed_comments / total_comments * 100.0
    overall_pass_score = (
        1.0
        if (
            adopted_phi_deg <= min(cpt_phi_deg, lab_phi_deg)
            and spt_n1_60_margin >= 0.0
            and bearing_margin_kpa >= 0.0
            and wall_sliding_fs_margin >= 0.0
            and grid_resistance_margin_ohm >= 0.0
            and comment_closeout_percent >= 100.0
        )
        else 0.0
    )

    return {
        "phi_source_delta_deg": round(phi_source_delta_deg, 3),
        "adopted_phi_deg": round(adopted_phi_deg, 3),
        "spt_n1_60_margin": round(spt_n1_60_margin, 3),
        "bearing_utilization": round(bearing_utilization, 3),
        "bearing_margin_kpa": round(bearing_margin_kpa, 3),
        "wall_sliding_fs_margin": round(wall_sliding_fs_margin, 3),
        "grid_resistance_margin_ohm": round(grid_resistance_margin_ohm, 3),
        "comment_closeout_percent": round(comment_closeout_percent, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
