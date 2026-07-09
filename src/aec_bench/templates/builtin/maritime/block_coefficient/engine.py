# ABOUTME: IACS CSR-H Block coefficient (C_B) computation engine.
# ABOUTME: Applies the displacement/(1.025*L*B*T_SC) ratio of Pt 1 Ch 1 Sec 4 §3.1.8.

# CSR-H 01 JUL 2025 Pt 1 Ch 1 Sec 4 §3.1.8: seawater density used in the block
# coefficient definition, C_B = Delta / (1.025 * L * B * T_SC).
SEAWATER_DENSITY_T_M3 = 1.025


def _validate_inputs(
    moulded_displacement_t: float,
    rule_length_L_m: float,
    moulded_breadth_B_m: float,
    scantling_draught_TSC_m: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if moulded_displacement_t <= 0:
        msg = "moulded_displacement_t must be > 0"
        raise ValueError(msg)
    if rule_length_L_m <= 0:
        msg = "rule_length_L_m must be > 0"
        raise ValueError(msg)
    if moulded_breadth_B_m <= 0:
        msg = "moulded_breadth_B_m must be > 0"
        raise ValueError(msg)
    if scantling_draught_TSC_m <= 0:
        msg = "scantling_draught_TSC_m must be > 0"
        raise ValueError(msg)


def compute(
    moulded_displacement_t: float,
    rule_length_L_m: float,
    moulded_breadth_B_m: float,
    scantling_draught_TSC_m: float,
) -> dict[str, float]:
    """Compute the IACS CSR-H Block coefficient C_B per Pt 1 Ch 1 Sec 4 §3.1.8.

    C_B is the block coefficient at the scantling draught T_SC:

        C_B = Delta / (1.025 * L * B * T_SC)

    where Delta is the moulded displacement of the ship at draught T_SC (in tonnes),
    L is the Rule length (m), B is the moulded breadth (m), and T_SC is the
    scantling draught (m).

    Returns a dict with key: block_coefficient_CB.
    """
    _validate_inputs(
        moulded_displacement_t,
        rule_length_L_m,
        moulded_breadth_B_m,
        scantling_draught_TSC_m,
    )

    block_coefficient_cb = moulded_displacement_t / (
        SEAWATER_DENSITY_T_M3 * rule_length_L_m * moulded_breadth_B_m * scantling_draught_TSC_m
    )

    return {
        "block_coefficient_CB": round(block_coefficient_cb, 2),
    }
