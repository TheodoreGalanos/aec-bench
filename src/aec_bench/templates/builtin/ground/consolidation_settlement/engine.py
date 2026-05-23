# ABOUTME: Terzaghi 1D consolidation settlement computation engine.
# ABOUTME: Calculates primary consolidation settlement for NC and OC clay layers.

import math


def _validate_inputs(
    clay_thickness_m: float,
    compression_index_cc: float,
    recompression_index_cr: float,
    initial_void_ratio_e0: float,
    preconsolidation_pressure_kpa: float,
    initial_effective_stress_kpa: float,
    final_effective_stress_kpa: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if clay_thickness_m <= 0:
        msg = "clay_thickness_m must be > 0"
        raise ValueError(msg)
    if compression_index_cc <= 0:
        msg = "compression_index_cc must be > 0"
        raise ValueError(msg)
    if recompression_index_cr < 0:
        msg = "recompression_index_cr must be >= 0"
        raise ValueError(msg)
    if recompression_index_cr >= compression_index_cc:
        msg = "recompression_index_cr must be < compression_index_cc"
        raise ValueError(msg)
    if initial_void_ratio_e0 <= 0:
        msg = "initial_void_ratio_e0 must be > 0"
        raise ValueError(msg)
    if preconsolidation_pressure_kpa <= 0:
        msg = "preconsolidation_pressure_kpa must be > 0"
        raise ValueError(msg)
    if initial_effective_stress_kpa <= 0:
        msg = "initial_effective_stress_kpa must be > 0"
        raise ValueError(msg)
    if final_effective_stress_kpa <= initial_effective_stress_kpa:
        msg = "final_effective_stress_kpa must be > initial_effective_stress_kpa"
        raise ValueError(msg)


def compute(
    clay_thickness_m: float,
    compression_index_cc: float,
    recompression_index_cr: float,
    initial_void_ratio_e0: float,
    preconsolidation_pressure_kpa: float,
    initial_effective_stress_kpa: float,
    final_effective_stress_kpa: float,
) -> dict[str, float]:
    """Compute primary consolidation settlement using Terzaghi's 1D theory.

    Three cases based on overconsolidation ratio (OCR):
    1. NC (OCR <= 1): settlement along virgin compression line (Cc)
    2. OC, stays OC (sigma_vf <= sigma_p): settlement along recompression line (Cr)
    3. OC, becomes NC (sigma_vf > sigma_p): two-part settlement (Cr then Cc)

    Returns a dict with keys: ocr, settlement_mm.
    """
    _validate_inputs(
        clay_thickness_m,
        compression_index_cc,
        recompression_index_cr,
        initial_void_ratio_e0,
        preconsolidation_pressure_kpa,
        initial_effective_stress_kpa,
        final_effective_stress_kpa,
    )

    ocr = preconsolidation_pressure_kpa / initial_effective_stress_kpa
    h = clay_thickness_m
    e0 = initial_void_ratio_e0
    cc = compression_index_cc
    cr = recompression_index_cr
    sigma_v0 = initial_effective_stress_kpa
    sigma_vf = final_effective_stress_kpa
    sigma_p = preconsolidation_pressure_kpa

    if ocr <= 1.0:
        # Case 1: Normally consolidated — use Cc for entire stress range
        settlement_m = (cc * h / (1.0 + e0)) * math.log10(sigma_vf / sigma_v0)
    elif sigma_vf <= sigma_p:
        # Case 2: Overconsolidated, stays OC — use Cr for entire range
        settlement_m = (cr * h / (1.0 + e0)) * math.log10(sigma_vf / sigma_v0)
    else:
        # Case 3: OC becomes NC — two-part: Cr up to sigma_p, then Cc beyond
        recompression_part = (cr * h / (1.0 + e0)) * math.log10(sigma_p / sigma_v0)
        virgin_part = (cc * h / (1.0 + e0)) * math.log10(sigma_vf / sigma_p)
        settlement_m = recompression_part + virgin_part

    # Convert to mm
    settlement_mm = settlement_m * 1000.0

    return {
        "ocr": round(ocr, 2),
        "settlement_mm": round(settlement_mm, 2),
    }
