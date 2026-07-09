# ABOUTME: Engine for the SSC-07 ground structural-electrical issue review package.
# ABOUTME: Derives review gold state, renders source packets, and builds verifier fixtures.

from __future__ import annotations

import json
import math

GAMMA_W = 9.81

STATUS_PASS = 0.0
STATUS_FAIL = 1.0
STATUS_NOT_APPLICABLE = 2.0
STATUS_INSUFFICIENT_DATA = 3.0

READY = 0.0
READY_WITH_CARRIED_ACTIONS = 1.0
NOT_READY = 2.0

STATUS_NAMES = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "fail",
    STATUS_NOT_APPLICABLE: "not_applicable",
    STATUS_INSUFFICIENT_DATA: "insufficient_data",
}

READINESS_NAMES = {
    READY: "ready_to_issue",
    READY_WITH_CARRIED_ACTIONS: "ready_with_carried_actions",
    NOT_READY: "not_ready_to_issue",
}

QUANT_STEPS = {
    "effective_overburden_kpa": 1.0,
    "design_groundwater_level_m": 0.05,
    "cohesion_kpa": 0.5,
    "total_unit_weight_kn_m3": 0.1,
    "footing_width_m": 0.1,
    "embedment_depth_m": 0.05,
    "factor_of_safety": 0.1,
    "bearing_margin_target_kpa": 1.0,
    "bearing_deficit_kpa": 1.0,
    "soil_resistivity_ohm_m": 1.0,
    "grid_length_m": 1.0,
    "grid_width_m": 1.0,
    "total_conductor_length_m": 5.0,
    "burial_depth_m": 0.05,
    "grid_current_ka": 0.1,
    "grid_resistance_margin_target_ohm": 0.001,
    "touch_voltage_margin_target_v": 1.0,
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/borehole-spt-logs.md",
    "sources/groundwater-record.md",
    "sources/ground-interpretation-memo.md",
    "sources/foundation-load-table.md",
    "sources/resistivity-survey.md",
    "sources/earthing-grid-design.md",
    "sources/criteria-comments.md",
]

VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_groundwater_level": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_ground_memo_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "resistivity_strength_misuse": {
        "flips": {"rlr_02_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"rlr_05_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"rlr_07_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "readiness": READY_WITH_CARRIED_ACTIONS,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
    "bearing_fos_deficient": {
        "flips": {"rlr_04_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid."""
    return round(round(value / step) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with source-facing values snapped to stable grids."""
    quantized = dict(params)
    quantized["raw_n_value"] = int(params["raw_n_value"])
    quantized["packet_variant"] = str(params["packet_variant"])
    for name, step in QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    return quantized


def _bearing_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return source-owned Terzaghi factors for the narrow SSC-07 phi range."""
    phi_rad = math.radians(phi_deg)
    exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
    denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = math.exp(exponent) / denominator
    nc = (nq - 1.0) / math.tan(phi_rad)
    ngamma = 19.7 + (phi_deg - 30.0) / 4.0 * (36.0 - 19.7)
    return nc, nq, ngamma


def _water_table_terms(
    *,
    unit_weight: float,
    footing_width: float,
    embedment: float,
    water_depth: float,
) -> tuple[float, float]:
    """Return overburden and effective unit weight using the source-owned convention."""
    if water_depth <= embedment:
        q_kpa = unit_weight * water_depth + (unit_weight - GAMMA_W) * (embedment - water_depth)
        gamma_eff = unit_weight - GAMMA_W
    elif water_depth < embedment + footing_width:
        q_kpa = unit_weight * embedment
        gamma_eff = (unit_weight - GAMMA_W) + ((water_depth - embedment) / footing_width) * GAMMA_W
    else:
        q_kpa = unit_weight * embedment
        gamma_eff = unit_weight
    return q_kpa, gamma_eff


def _allowable_bearing(p: dict, design_phi: float) -> float:
    """Compute allowable bearing capacity for the source-owned square footing check."""
    nc, nq, ngamma = _bearing_factors(design_phi)
    q_kpa, gamma_eff = _water_table_terms(
        unit_weight=p["total_unit_weight_kn_m3"],
        footing_width=p["footing_width_m"],
        embedment=p["embedment_depth_m"],
        water_depth=p["design_groundwater_level_m"],
    )
    ultimate = p["cohesion_kpa"] * nc * 1.3 + q_kpa * nq + gamma_eff * p["footing_width_m"] * 0.4 * ngamma
    return ultimate / p["factor_of_safety"]


def _grid_values(p: dict) -> tuple[float, float]:
    """Compute grid resistance and the task-owned touch-voltage screening value."""
    area = p["grid_length_m"] * p["grid_width_m"]
    resistance = p["soil_resistivity_ohm_m"] * (
        1.0 / p["total_conductor_length_m"]
        + 1.0 / math.sqrt(20.0 * area) * (1.0 + 1.0 / (1.0 + p["burial_depth_m"] * math.sqrt(20.0 / area)))
    )
    touch_voltage = p["grid_current_ka"] * 1000.0 * resistance * 0.15
    return resistance, touch_voltage


def _derive(params: dict) -> dict:
    """Derive source truth, package claims, and review-state values."""
    p = _quantize(params)
    variant = p["packet_variant"]

    corrected_spt_n60 = p["raw_n_value"] * 1.33 * 1.0 * 1.0 * 0.95
    design_phi = 27.0 + 0.25 * corrected_spt_n60
    allowable = _allowable_bearing(p, design_phi)
    applied_bearing = (
        allowable + p["bearing_deficit_kpa"]
        if variant == "bearing_fos_deficient"
        else allowable - p["bearing_margin_target_kpa"]
    )
    grid_resistance, touch_voltage = _grid_values(p)
    grid_resistance_limit = grid_resistance + p["grid_resistance_margin_target_ohm"]
    touch_voltage_limit = touch_voltage + p["touch_voltage_margin_target_v"]

    return {
        "params": p,
        "variant": variant,
        "corrected_spt_n60": corrected_spt_n60,
        "design_phi": design_phi,
        "allowable_bearing": allowable,
        "applied_bearing": applied_bearing,
        "bearing_margin": allowable - applied_bearing,
        "grid_resistance": grid_resistance,
        "grid_resistance_limit": grid_resistance_limit,
        "grid_resistance_margin": grid_resistance_limit - grid_resistance,
        "touch_voltage": touch_voltage,
        "touch_voltage_limit": touch_voltage_limit,
        "touch_voltage_margin": touch_voltage_limit - touch_voltage,
    }


def compute(**params) -> dict[str, float]:
    """Compute gold review statuses and recomputed evidence for an SSC-07 instance."""
    state = _derive(params)
    variant = state["variant"]
    spec = VARIANT_GOLD[variant]

    truth = {f"rlr_0{i}_status": STATUS_PASS for i in range(1, 10)}
    truth.update(spec["flips"])
    truth.update(
        {
            "corrected_spt_n60": round(state["corrected_spt_n60"], 3),
            "design_friction_angle_deg": round(state["design_phi"], 3),
            "grid_resistance_ohm": round(state["grid_resistance"], 3),
            "grid_resistance_margin_ohm": round(state["grid_resistance_margin"], 3),
            "touch_voltage_margin_v": round(state["touch_voltage_margin"], 3),
            "readiness_code": spec["readiness"],
            "required_findings_count": spec["findings"],
            "required_information_requests_count": spec["requests"],
            "required_carried_actions_count": spec["carried"],
        }
    )
    if variant != "missing_groundwater_level":
        truth["allowable_bearing_kpa"] = round(state["allowable_bearing"], 3)
        truth["bearing_margin_kpa"] = round(state["bearing_margin"], 3)
    return truth


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the eight-file source packet for one instance."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    memo_revision = "Rev B" if variant == "stale_ground_memo_revision" else "Rev C"
    groundwater_revision = "Rev C"
    load_case = "LC-07-STRUCT-A"
    if variant == "scenario_copy_forward":
        load_case = "LC-07-STRUCT-B copied from FDN-07-ALT"

    document_register = f"""# Document Register

| Document ID | Title | Revision | Status |
|---|---|---|---|
| BH-07-LOG-01 | Borehole and SPT log | Rev C | current |
| GW-07-REC-01 | Groundwater record | {groundwater_revision} | current |
| GIM-07-MEMO-01 | Ground interpretation memo | Rev C | current |
| FDN-07-LOAD-01 | Foundation load table | Rev C | current |
| RES-07-SURV-01 | Resistivity survey | Rev B | current |
| GRID-07-DES-01 | Earthing grid design extract | Rev B | current |
| CRIT-SSC07-001 | Criteria and review comments | Rev C | current |
"""

    borehole = f"""# Borehole And SPT Logs

Source ID: BH-07-LOG-01
Site: SITE-07
Borehole: BH-07
SPT record: SPT-07

| Field | Value |
|---|---|
| Raw SPT N at SPT-07 | {p["raw_n_value"]} |
| Effective overburden at SPT depth | {p["effective_overburden_kpa"]:.1f} kPa |
| Hammer correction | 1.33 |
| Borehole correction | 1.00 |
| Sampler correction | 1.00 |
| Rod length correction | 0.95 |
"""

    if variant == "missing_groundwater_level":
        groundwater_level_row = "| Design groundwater level | standpipe readings pending |"
    else:
        groundwater_level_row = f"| Design groundwater level | {p['design_groundwater_level_m']:.2f} m |"
    groundwater = f"""# Groundwater Record

Source ID: GW-07-REC-01
Site: SITE-07
Groundwater record: GW-07

| Field | Value |
|---|---|
{groundwater_level_row}
| Record status | current wet-season design record |
"""

    partition_note = (
        "Parameter selection uses BH-07/SPT-07 strength evidence only. RES-07 remains an electrical resistivity source."
    )
    if variant == "resistivity_strength_misuse":
        partition_note = (
            "Parameter selection cites RES-07 layer R2 as the controlling strength stratum, creating an authority "
            "collapse between the resistivity chain and the ground strength stratum."
        )

    ground_memo = f"""# Ground Interpretation Memo

Source ID: GIM-07-MEMO-01 ({memo_revision})
Site: SITE-07
Ground memo: GIM-07-MEMO-01

{partition_note}

| Field | Value |
|---|---|
| Design friction angle | {state["design_phi"]:.1f} degrees |
| Strength evidence source | BH-07 and SPT-07 |
| Resistivity evidence source | RES-07 layer data, not strength data |
"""

    foundation = f"""# Foundation Load Table

Source ID: FDN-07-LOAD-01
Site: SITE-07
Foundation: FDN-07
Load case: {load_case}

| Field | Value |
|---|---|
| Applied bearing pressure | {state["applied_bearing"]:.1f} kPa |
| Foundation object | FDN-07 shallow square footing |
| Controlling structure | SITE-07 equipment slab |
"""

    resistivity = f"""# Resistivity Survey

Source ID: RES-07-SURV-01
Site: SITE-07
Resistivity traverse: RES-07

| Field | Value |
|---|---|
| Apparent resistivity from RES-07 | {p["soil_resistivity_ohm_m"]:.1f} ohm-m |
| RES-07 layer | R2 electrical layer, not a strength stratum |
"""

    grid = f"""# Earthing Grid Design Extract

Source ID: GRID-07-DES-01
Site: SITE-07
Earthing grid: GRID-07

| Field | Value |
|---|---|
| Grid length | {p["grid_length_m"]:.1f} m |
| Grid width | {p["grid_width_m"]:.1f} m |
| Total buried conductor | {p["total_conductor_length_m"]:.1f} m |
| Burial depth | {p["burial_depth_m"]:.2f} m |
| Grid current | {p["grid_current_ka"]:.1f} kA |
"""

    comment_status = "All review comments closed."
    if variant == "open_critical_comment":
        comment_status = "Critical comment CRIT-07-C04 remains open: resolve groundwater design basis before issue."
    elif variant == "minor_open_comment_carried":
        comment_status = (
            "Minor comment CRIT-07-M02 may be carried with owner GEO lead and action to confirm figure reference."
        )

    criteria = f"""# Criteria And Review Comments

Source ID: CRIT-SSC07-001
Site: SITE-07

## Assessment bases (source-owned methods)

N60 correction: raw N x 1.33 x 1.00 x 1.00 x 0.95.
Design friction angle: {state["design_phi"]:.1f} degrees.
Friction-angle correlation: phi = 27.0 + 0.25 x corrected SPT N60.
Terzaghi factors: source-owned Nc/Nq equations with Ngamma linearly interpolated between 30 degrees and 34 degrees.
Effective cohesion: {p["cohesion_kpa"]:.1f} kPa.
Total unit weight: {p["total_unit_weight_kn_m3"]:.1f} kN/m3.
Footing width: {p["footing_width_m"]:.1f} m.
Embedment depth: {p["embedment_depth_m"]:.2f} m.
Bearing factor of safety: {p["factor_of_safety"]:.1f}
Grid resistance limit: {state["grid_resistance_limit"]:.3f} ohm.
Touch voltage limit: {state["touch_voltage_limit"]:.1f} V.
Touch voltage convention: grid current x 1000 x grid resistance x 0.15.

## Comments

{comment_status}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/borehole-spt-logs.md": borehole,
        "sources/groundwater-record.md": groundwater,
        "sources/ground-interpretation-memo.md": ground_memo,
        "sources/foundation-load-table.md": foundation,
        "sources/resistivity-survey.md": resistivity,
        "sources/earthing-grid-design.md": grid,
        "sources/criteria-comments.md": criteria,
    }


def _status_entry(item: str, status: float, evidence: str) -> dict[str, str]:
    """Build one review-matrix entry."""
    return {"status": STATUS_NAMES[status], "evidence": evidence or f"{item} checked against the source packet."}


def _base_payload(ground_truth: dict) -> dict:
    """Create a gold review payload from ground-truth status codes."""
    source_inventory = [
        {"doc_id": "BH-07-LOG-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "GW-07-REC-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "GIM-07-MEMO-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "FDN-07-LOAD-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "RES-07-SURV-01", "revision": "Rev B", "status": "current"},
        {"doc_id": "GRID-07-DES-01", "revision": "Rev B", "status": "current"},
        {"doc_id": "CRIT-SSC07-001", "revision": "Rev C", "status": "current"},
    ]
    ledger = {
        "site": "SITE-07",
        "borehole": "BH-07",
        "spt_record": "SPT-07",
        "groundwater_record": "GW-07",
        "ground_memo": "GIM-07-MEMO-01",
        "foundation": "FDN-07",
        "resistivity_survey": "RES-07",
        "earthing_grid": "GRID-07",
        "load_case": "LC-07-STRUCT-A",
        "criteria_memo": "CRIT-SSC07-001",
    }
    evidence_text = {
        "RLR-01": "Required source files are inventoried with IDs and revisions.",
        "RLR-02": (
            "SITE-07, BH-07/SPT-07, GW-07, FDN-07, RES-07, GRID-07, and CRIT-SSC07-001 are partitioned by authority."
        ),
        "RLR-03": "Ground and earthing bases are traceable and recomputed from source-owned criteria.",
        "RLR-04": "Bearing adequacy is checked against source-owned water-table correction.",
        "RLR-05": "Same SITE-07 structure and load case are used through the packet.",
        "RLR-06": "Grid resistance and touch-voltage margins are source-backed.",
        "RLR-07": "Review comments are closed or carried with owner and action.",
        "RLR-08": "Readiness decision reconciles with matrix and registers.",
        "RLR-09": "Review remains inside the task-owned synthetic claim boundary.",
    }
    matrix = {
        item: _status_entry(item, ground_truth[f"rlr_0{item[-1]}_status"], evidence_text[item])
        for item in [f"RLR-0{i}" for i in range(1, 10)]
    }
    computed = {
        key: ground_truth[key]
        for key in (
            "corrected_spt_n60",
            "design_friction_angle_deg",
            "allowable_bearing_kpa",
            "bearing_margin_kpa",
            "grid_resistance_ohm",
            "grid_resistance_margin_ohm",
            "touch_voltage_margin_v",
        )
        if key in ground_truth
    }
    return {
        "source_inventory": source_inventory,
        "identity_ledger": ledger,
        "review_matrix": matrix,
        "computed_evidence": computed,
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": READINESS_NAMES[ground_truth["readiness_code"]],
        "claim_boundary_statement": (
            "This review covers a task-owned synthetic source packet. It does not claim authority approval, "
            "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
            "readiness, or benchmark readiness."
        ),
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    """Build a full-credit review response fixture."""
    variant = str(all_params["packet_variant"])
    payload = _base_payload(ground_truth)

    if variant == "missing_groundwater_level":
        payload["review_matrix"]["RLR-04"]["evidence"] = (
            "Design groundwater level is pending, so bearing adequacy cannot be completed."
        )
        payload["information_requests"].append(
            {
                "item": "RLR-04",
                "missing_field": "design groundwater level from standpipe readings",
                "source_id": "GW-07-REC-01",
            }
        )
    elif variant in {
        "stale_ground_memo_revision",
        "resistivity_strength_misuse",
        "scenario_copy_forward",
        "open_critical_comment",
        "bearing_fos_deficient",
    }:
        item = {
            "stale_ground_memo_revision": "RLR-03",
            "resistivity_strength_misuse": "RLR-02",
            "scenario_copy_forward": "RLR-05",
            "open_critical_comment": "RLR-07",
            "bearing_fos_deficient": "RLR-04",
        }[variant]
        payload["findings"].append(
            {
                "item": item,
                "severity": "critical",
                "source_id": {
                    "stale_ground_memo_revision": "GIM-07-MEMO-01",
                    "resistivity_strength_misuse": "GIM-07-MEMO-01",
                    "scenario_copy_forward": "FDN-07-LOAD-01",
                    "open_critical_comment": "CRIT-SSC07-001",
                    "bearing_fos_deficient": "FDN-07-LOAD-01",
                }[variant],
                "object_id": {
                    "stale_ground_memo_revision": "GIM-07-MEMO-01",
                    "resistivity_strength_misuse": "RES-07",
                    "scenario_copy_forward": "FDN-07",
                    "open_critical_comment": "CRIT-07-C04",
                    "bearing_fos_deficient": "FDN-07",
                }[variant],
                "consequence": "The package cannot be issued until the blocker is resolved.",
                "action": "Revise the affected source and re-issue the review packet.",
            }
        )
    elif variant == "minor_open_comment_carried":
        payload["action_register"].append(
            {"action": "Carry figure-reference cleanup to next issue", "owner": "GEO lead", "linked_item": "RLR-07"}
        )

    json_block = json.dumps(payload, indent=2)
    return f"""## Review

The source packet has been inventoried, recomputed where applicable, and assessed against the review matrix.

```json
{json_block}
```
"""


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    """Build a fluent unsafe fixture that approves the packet without evidence."""
    payload = {
        "source_inventory": [],
        "identity_ledger": {},
        "review_matrix": {f"RLR-0{i}": {"status": "pass", "evidence": "Looks acceptable."} for i in range(1, 10)},
        "computed_evidence": {},
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": "ready_to_issue",
        "claim_boundary_statement": "Approved for issue.",
    }
    json_block = json.dumps(payload, indent=2)
    return f"""## Review

The package appears acceptable for issue.

```json
{json_block}
```
"""
