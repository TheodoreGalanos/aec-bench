# ABOUTME: Engine for the SSC-06 review-first pump duty and NPSH issue package.
# ABOUTME: Derives packet state, variant gold review statuses, source-pack files, and golden fixtures.

from __future__ import annotations

import json
import math

_G = 9.81

STATUS_PASS = 0.0
STATUS_FAIL = 1.0
STATUS_NOT_APPLICABLE = 2.0
STATUS_INSUFFICIENT_DATA = 3.0

READY = 0.0
READY_WITH_CARRIED_ACTIONS = 1.0
NOT_READY = 2.0

_STATUS_NAMES = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "fail",
    STATUS_NOT_APPLICABLE: "not_applicable",
    STATUS_INSUFFICIENT_DATA: "insufficient_data",
}

_READINESS_NAMES = {
    READY: "ready_to_issue",
    READY_WITH_CARRIED_ACTIONS: "ready_with_carried_actions",
    NOT_READY: "not_ready_to_issue",
}

_QUANT_STEPS = {
    "design_flow_l_s": 1.0,
    "static_lift_m": 0.1,
    "rising_main_length_m": 5.0,
    "hazen_williams_c": 1.0,
    "minor_loss_coefficient": 0.1,
    "fluid_density_kg_m3": 1.0,
    "pump_efficiency_pct": 1.0,
    "motor_efficiency_pct": 1.0,
    "motor_service_factor": 0.01,
    "atmospheric_pressure_kpa_abs": 0.1,
    "vapor_pressure_kpa_abs": 0.1,
    "wetwell_min_level_above_pump_m": 0.05,
    "average_level_delta_m": 0.05,
    "suction_loss_m": 0.01,
    "minimum_npsh_margin_m": 0.05,
    "npsh_margin_target_m": 0.05,
    "npsh_margin_deficit_m": 0.05,
    "pump_head_margin_target_m": 0.1,
    "motor_margin_target_kw": 0.5,
    "feeder_length_km": 0.01,
    "feeder_resistance_ohm_per_km": 0.01,
    "feeder_reactance_ohm_per_km": 0.005,
    "motor_power_factor": 0.01,
    "voltage_drop_margin_target_percent": 0.1,
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid, avoiding float dust."""
    return round(round(value / step) * step, 10)


def _ceil_to(value: float, step: float) -> float:
    """Round a value up to the next step boundary."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with floats snapped to grid and numeric enums cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    for enum_name in ("rising_main_diameter_mm", "feeder_voltage_v"):
        quantized[enum_name] = float(params[enum_name])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute the full packet state: true metrics, derived criteria, and claims."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    design_flow_m3_s = p["design_flow_l_s"] / 1000.0
    diameter_m = p["rising_main_diameter_mm"] / 1000.0
    headloss = (
        10.67
        * p["rising_main_length_m"]
        * design_flow_m3_s**1.852
        / (p["hazen_williams_c"] ** 1.852 * diameter_m**4.87)
    )
    flow_area = math.pi * diameter_m**2 / 4.0
    velocity = design_flow_m3_s / flow_area
    minor_loss = p["minor_loss_coefficient"] * velocity**2 / (2.0 * _G)
    total_dynamic_head = p["static_lift_m"] + headloss + minor_loss
    pump_head = _ceil_to(total_dynamic_head + p["pump_head_margin_target_m"], 0.1)
    pump_head_margin = pump_head - total_dynamic_head

    pressure_head = (
        (p["atmospheric_pressure_kpa_abs"] - p["vapor_pressure_kpa_abs"]) * 1000.0 / (p["fluid_density_kg_m3"] * _G)
    )
    minimum_level = p["wetwell_min_level_above_pump_m"]
    average_level = minimum_level + p["average_level_delta_m"]
    npsh_available = pressure_head + minimum_level - p["suction_loss_m"]
    npsh_available_average = pressure_head + average_level - p["suction_loss_m"]
    if variant == "npsh_margin_deficient":
        npsh_required = npsh_available - p["minimum_npsh_margin_m"] + p["npsh_margin_deficit_m"]
    else:
        npsh_required = npsh_available - p["minimum_npsh_margin_m"] - p["npsh_margin_target_m"]
    npsh_required = _q(npsh_required, 0.05)
    npsh_margin = npsh_available - npsh_required
    claimed_npsh_available = npsh_available_average if variant == "npsh_margin_deficient" else npsh_available
    claimed_npsh_margin = claimed_npsh_available - npsh_required

    pump_efficiency = p["pump_efficiency_pct"] / 100.0
    motor_efficiency = p["motor_efficiency_pct"] / 100.0
    hydraulic_power_kw = p["fluid_density_kg_m3"] * _G * design_flow_m3_s * total_dynamic_head / 1000.0
    shaft_power_kw = hydraulic_power_kw / pump_efficiency
    motor_input_kw = shaft_power_kw / motor_efficiency
    required_motor_kw = shaft_power_kw * p["motor_service_factor"]
    selected_motor_kw = _ceil_to(required_motor_kw + p["motor_margin_target_kw"], 0.5)
    motor_margin_kw = selected_motor_kw - required_motor_kw

    load_reactive_kvar = motor_input_kw * math.tan(math.acos(p["motor_power_factor"]))
    apparent_power_kva = math.hypot(motor_input_kw, load_reactive_kvar)
    feeder_current_a = apparent_power_kva * 1000.0 / (math.sqrt(3.0) * p["feeder_voltage_v"])
    reactive_factor = load_reactive_kvar / apparent_power_kva
    voltage_drop_v = (
        math.sqrt(3.0)
        * feeder_current_a
        * p["feeder_length_km"]
        * (
            p["feeder_resistance_ohm_per_km"] * p["motor_power_factor"]
            + p["feeder_reactance_ohm_per_km"] * reactive_factor
        )
    )
    feeder_voltage_drop_percent = voltage_drop_v / p["feeder_voltage_v"] * 100.0
    max_voltage_drop_percent = _ceil_to(feeder_voltage_drop_percent + p["voltage_drop_margin_target_percent"], 0.1)
    voltage_drop_margin_percent = max_voltage_drop_percent - feeder_voltage_drop_percent

    scheduled_impeller_mm = 236.0
    curve_impeller_mm = 248.0 if variant == "impeller_diameter_mismatch" else scheduled_impeller_mm

    return {
        "params": p,
        "variant": variant,
        "design_flow_m3_s": design_flow_m3_s,
        "diameter_m": diameter_m,
        "headloss": headloss,
        "velocity": velocity,
        "minor_loss": minor_loss,
        "total_dynamic_head": total_dynamic_head,
        "pump_head": pump_head,
        "pump_head_margin": pump_head_margin,
        "pressure_head": pressure_head,
        "minimum_level": minimum_level,
        "average_level": average_level,
        "npsh_available": npsh_available,
        "npsh_available_average": npsh_available_average,
        "npsh_required": npsh_required,
        "npsh_margin": npsh_margin,
        "claimed_npsh_available": claimed_npsh_available,
        "claimed_npsh_margin": claimed_npsh_margin,
        "hydraulic_power_kw": hydraulic_power_kw,
        "shaft_power_kw": shaft_power_kw,
        "motor_input_kw": motor_input_kw,
        "required_motor_kw": required_motor_kw,
        "selected_motor_kw": selected_motor_kw,
        "motor_margin_kw": motor_margin_kw,
        "load_reactive_kvar": load_reactive_kvar,
        "apparent_power_kva": apparent_power_kva,
        "feeder_current_a": feeder_current_a,
        "feeder_voltage_drop_percent": feeder_voltage_drop_percent,
        "max_voltage_drop_percent": max_voltage_drop_percent,
        "voltage_drop_margin_percent": voltage_drop_margin_percent,
        "scheduled_impeller_mm": scheduled_impeller_mm,
        "curve_impeller_mm": curve_impeller_mm,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_wetwell_min_level": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_pump_curve_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "impeller_diameter_mismatch": {
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
    "npsh_margin_deficient": {
        "flips": {"rlr_04_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}


def compute(**params) -> dict[str, float]:
    """Return the gold review state and evidence metrics for one packet instance."""
    state = _derive(params)
    gold = _VARIANT_GOLD[state["variant"]]

    result: dict[str, float] = {}
    for index in range(1, 10):
        key = f"rlr_0{index}_status"
        result[key] = gold["flips"].get(key, STATUS_PASS)
    result["readiness_code"] = gold["readiness"]
    result["required_findings_count"] = gold["findings"]
    result["required_information_requests_count"] = gold["requests"]
    result["required_carried_actions_count"] = gold["carried"]

    result["total_dynamic_head_m"] = state["total_dynamic_head"]
    result["pump_head_margin_m"] = state["pump_head_margin"]
    if state["variant"] != "missing_wetwell_min_level":
        result["npsh_available_m"] = state["npsh_available"]
        result["npsh_margin_m"] = state["npsh_margin"]
    result["motor_input_kw"] = state["motor_input_kw"]
    result["motor_margin_kw"] = state["motor_margin_kw"]
    result["feeder_voltage_drop_percent"] = state["feeder_voltage_drop_percent"]
    result["voltage_drop_margin_percent"] = state["voltage_drop_margin_percent"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("WW-06-GEO-01", "Wet-well and suction geometry", "Rev A", "Issued for review"),
        ("RM-06-SCH-01", "Rising-main schedule", "Rev B", "Issued for review"),
        ("PMP-06-CURVE-01", "Pump curve and datasheet extract", "Rev C", "Issued for review"),
        ("MOT-06-FDR-01", "Motor and feeder schedule", "Rev B", "Issued for review"),
        ("DUTY-06-CASE-01", "Duty and operating case", "Rev A", "Issued for review"),
        ("CRIT-SSC06-001", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the seven-file source packet for one instance."""
    s = _derive(all_params)
    p = s["params"]
    variant = s["variant"]

    register_lines = [
        "| Document ID | Title | Revision | Status |",
        "|---|---|---|---|",
    ]
    for doc_id, title, rev, status in _register_rows(variant):
        register_lines.append(f"| {doc_id} | {title} | {rev} | {status} |")
    document_register = (
        "# Document Register - DOC-REG-SSC06-01\n\n"
        "Issue package: pump station duty, NPSH, motor, and feeder review for DUTY-06-CASE-01.\n\n"
        + "\n".join(register_lines)
        + "\n"
    )

    if variant == "missing_wetwell_min_level":
        min_level_line = "| minimum wet-well operating level | pending survey of stop/start setpoints |"
        npsh_claim = "| Package claimed NPSHa | to be confirmed after survey |"
    else:
        min_level_line = f"| Minimum wet-well operating level above pump centreline | {s['minimum_level']:.2f} m |"
        npsh_claim = f"| Package claimed NPSHa | {s['claimed_npsh_available']:.2f} m |"

    wet_well = f"""# Wet-Well And Suction Geometry - WW-06-GEO-01 (Rev A)

Wet well: WW-06, serving pump PMP-06 and suction arrangement SUC-06.

| Item | Value |
|---|---|
| Fluid density | {p["fluid_density_kg_m3"]:.0f} kg/m3 |
| Atmospheric pressure | {p["atmospheric_pressure_kpa_abs"]:.1f} kPa abs |
| Vapor pressure | {p["vapor_pressure_kpa_abs"]:.1f} kPa abs |
{min_level_line}
| Average wet-well operating level above pump centreline | {s["average_level"]:.2f} m |
| Suction-side loss at design duty | {p["suction_loss_m"]:.2f} m |
{npsh_claim}
"""

    rising_main = f"""# Rising-Main Schedule - RM-06-SCH-01 (Rev B)

Rising main: RM-06, from WW-06/PMP-06 discharge to the boundary manhole.

| Item | Value |
|---|---|
| Rising main length | {p["rising_main_length_m"]:.1f} m |
| Internal diameter | {p["rising_main_diameter_mm"]:.0f} mm |
| Hazen-Williams C | {p["hazen_williams_c"]:.1f} |
| Aggregate minor-loss coefficient | {p["minor_loss_coefficient"]:.1f} |
| Package claimed headloss | {s["headloss"]:.2f} m |
| Package claimed minor loss | {s["minor_loss"]:.2f} m |
"""

    pump_revision = "Rev B" if variant == "stale_pump_curve_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_pump_curve_revision":
        stale_note = (
            "\nNote: this curve sheet is Rev B. The document register lists PMP-06-CURVE-01 Rev C "
            "as the current issue for review.\n"
        )

    impeller_line = (
        f"Pump: PMP-06. Datasheet impeller: {s['scheduled_impeller_mm']:.0f} mm. "
        f"Curve sheet impeller: {s['curve_impeller_mm']:.0f} mm."
    )
    pump_curve = f"""# Pump Curve And Datasheet Extract - PMP-06-CURVE-01 ({pump_revision})

{impeller_line}

| Item | Value |
|---|---|
| Pump curve head at design duty | {s["pump_head"]:.2f} m |
| NPSHr at design duty | {s["npsh_required"]:.2f} m |
| Pump efficiency | {p["pump_efficiency_pct"]:.0f} % |
| Package claimed NPSH margin | {s["claimed_npsh_margin"]:.2f} m |
{stale_note}
"""

    motor_feeder = f"""# Motor And Feeder Schedule - MOT-06-FDR-01 (Rev B)

Motor MOT-06 and feeder FDR-06 serve pump PMP-06 at the duty point.

| Item | Value |
|---|---|
| Selected motor size | {s["selected_motor_kw"]:.1f} kW |
| Motor efficiency | {p["motor_efficiency_pct"]:.0f} % |
| Motor service factor | {p["motor_service_factor"]:.2f} |
| Motor power factor | {p["motor_power_factor"]:.2f} |
| Feeder voltage | {p["feeder_voltage_v"]:.0f} V |
| Feeder length | {p["feeder_length_km"]:.2f} km |
| Resistance | {p["feeder_resistance_ohm_per_km"]:.2f} ohm/km |
| Reactance | {p["feeder_reactance_ohm_per_km"]:.3f} ohm/km |
| Package claimed feeder voltage drop | {s["feeder_voltage_drop_percent"]:.2f} % |
"""

    flow_basis = f"{p['design_flow_l_s']:.1f} L/s (DUTY-06-CASE-01 selected duty)"
    if variant == "scenario_copy_forward":
        flow_basis = f"{p['design_flow_l_s']:.1f} L/s (copied from PS-05 wet-weather case; selection record pending)"

    duty_case = f"""# Duty And Operating Case - DUTY-06-CASE-01 (Rev A)

Operating case: DUTY-06, one duty pump in service, wet-weather transfer to the boundary manhole.

| Item | Value |
|---|---|
| Design flow | {flow_basis} |
| Static lift | {p["static_lift_m"]:.1f} m |
| Pump | PMP-06 |
| Scheduled impeller | {s["scheduled_impeller_mm"]:.0f} mm |
| Rising main | RM-06 |
| Motor | MOT-06 |
| Feeder | FDR-06 |
"""

    comments = [
        ("C-01", "Process", "Confirm duty point marker appears on the issued pump curve.", "Closed", "minor", "", ""),
        ("C-02", "Electrical", "Confirm feeder length aligns with the motor schedule.", "Closed", "minor", "", ""),
        ("C-03", "Mechanical", "Confirm NPSH basis is stated in the criteria memo.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Operations",
                "Confirm wet-well low-low cutout and NPSH protection before issue.",
                "Open",
                "critical",
                "",
                "",
            )
        )
    if variant == "minor_open_comment_carried":
        comments.append(
            (
                "C-05",
                "Documentation",
                "Add the pump tag PMP-06 to the single-line diagram legend.",
                "Open",
                "minor",
                "Mechanical designer",
                "Update legend at next revision (carried action, due next issue)",
            )
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, disc, text, status, crit, owner, action in comments:
        comment_lines.append(f"| {cid} | {disc} | {text} | {status} | {crit} | {owner} | {action} |")

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC06-001 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Minimum pump head margin | greater than 0 m |
| Minimum NPSH margin above NPSHr | {p["minimum_npsh_margin_m"]:.2f} m |
| Maximum feeder voltage drop | {s["max_voltage_drop_percent"]:.1f} % |
| Motor selected size | greater than shaft power times service factor |

## Assessment bases (source-owned methods)

- Rising-main headloss: Hazen-Williams, hf = 10.67 x L x Q^1.852 / (C^1.852 x d^4.87), with Q in m3/s and d in m.
- Minor loss: hm = K x V^2 / (2g).
- Total dynamic head: static lift plus rising-main headloss plus minor loss.
- NPSH available: pressure head from atmospheric minus vapor pressure, plus minimum wet-well operating level
  above pump centreline, minus suction-side loss.
- Pump head margin: pump curve head at design duty minus total dynamic head.
- Motor input power: hydraulic power divided by pump efficiency and motor efficiency.
- Required motor size: shaft power multiplied by the motor service factor.
- Feeder voltage drop: three-phase current from motor kVA; drop = sqrt(3) x I x length x
  (R x power factor + X x reactive factor).

## Review comments

{chr(10).join(comment_lines)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/wet-well-suction-geometry.md": wet_well,
        "sources/rising-main-schedule.md": rising_main,
        "sources/pump-curve-datasheet.md": pump_curve,
        "sources/motor-feeder-schedule.md": motor_feeder,
        "sources/duty-operating-case.md": duty_case,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_pump_curve_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "PMP-06-CURVE-01",
        "object_id": "PMP-06",
        "consequence": (
            "The pump curve source is Rev B while the document register lists Rev C, so the pump duty basis "
            "is not traceable to the current issue package."
        ),
        "action": "Reissue PMP-06-CURVE-01 at Rev C or reconcile the register before issue.",
    },
    "impeller_diameter_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "PMP-06-CURVE-01",
        "object_id": "PMP-06",
        "consequence": (
            "The curve sheet impeller diameter does not match the datasheet and duty-case impeller for PMP-06."
        ),
        "action": "Confirm the selected impeller and reissue the pump curve/datasheet on one impeller basis.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "DUTY-06-CASE-01",
        "object_id": "DUTY-06",
        "consequence": ("The duty flow is copied from another station case without a selection record for DUTY-06."),
        "action": "Provide the DUTY-06 flow selection record and reassess pump, motor, and feeder margins.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC06-001",
        "object_id": "C-04",
        "consequence": "Critical operations comment C-04 is open with no owner or agreed action.",
        "action": "Assign an owner and closure path for C-04 before issue.",
    },
    "npsh_margin_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "PMP-06-CURVE-01",
        "object_id": "PMP-06",
        "consequence": (
            "Recomputed NPSH margin at the minimum wet-well operating level is below the CRIT-SSC06-001 "
            "minimum; the package claim uses the average wet-well level."
        ),
        "action": "Raise the minimum operating level, select a lower-NPSHr pump, or revise suction losses.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All six register documents are present with IDs and revisions in DOC-REG-SSC06-01.",
        "RLR-02": "WW-06, PMP-06, the impeller, RM-06, MOT-06, FDR-06, and DUTY-06 reconcile.",
        "RLR-03": "Recomputed TDH, pump head margin, NPSHa, and motor input are source-backed.",
        "RLR-04": "Pump head and NPSH margin clear the CRIT-SSC06-001 criteria.",
        "RLR-05": "Duty flow and operating case reconcile across the wet-well, pump, main, motor, and feeder files.",
        "RLR-06": "Motor sizing and feeder voltage drop are source-backed and clear the criteria.",
        "RLR-07": "All review comments in CRIT-SSC06-001 are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_wetwell_min_level":
        evidence_notes["RLR-04"] = (
            "The minimum wet-well operating level is pending survey confirmation, so NPSHa cannot be assessed."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "total_dynamic_head_m",
            "pump_head_margin_m",
            "npsh_available_m",
            "npsh_margin_m",
            "motor_input_kw",
            "motor_margin_kw",
            "feeder_voltage_drop_percent",
            "voltage_drop_margin_percent",
        )
        if key in ground_truth
    }

    findings = []
    actions = []
    if variant in _VARIANT_FINDINGS:
        finding = dict(_VARIANT_FINDINGS[variant])
        findings.append(finding)
        actions.append({"action": finding["action"], "owner": "Design lead", "linked_item": finding["item"]})

    information_requests = []
    if variant == "missing_wetwell_min_level":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "minimum wet-well operating level for WW-06 (m above pump centreline)",
                "source_id": "WW-06-GEO-01",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: add pump tag PMP-06 to the single-line diagram legend (comment C-05).",
                "owner": "Mechanical designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "wet_well": "WW-06",
            "pump": "PMP-06",
            "impeller": f"{state['scheduled_impeller_mm']:.0f} mm impeller",
            "rising_main": "RM-06",
            "motor": "MOT-06",
            "feeder": "FDR-06",
            "duty_case": "DUTY-06",
            "criteria_memo": "CRIT-SSC06-001",
        },
        "review_matrix": matrix,
        "computed_evidence": computed_evidence,
        "findings": findings,
        "information_requests": information_requests,
        "action_register": actions,
        "readiness_decision": _READINESS_NAMES[ground_truth["readiness_code"]],
        "claim_boundary_statement": (
            "This review covers a task-owned synthetic source packet. It does not claim authority approval, "
            "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
            "readiness, or benchmark readiness."
        ),
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    """Golden correct review: full matrix, evidence, linkage, and readiness decision."""
    payload = _golden_payload(all_params, ground_truth)
    return (
        "## Issue-Readiness Review - pump station DUTY-06\n\n"
        "Source inventory, identity ledger, review matrix, findings, information requests, action register, "
        "and readiness decision follow in the structured block.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    """Fluent but unsafe memo: all-pass matrix, no evidence, unconditional readiness."""
    matrix = {f"RLR-0{index}": {"status": "pass", "evidence": "Reviewed and found in order."} for index in range(1, 10)}
    payload = {
        "review_matrix": matrix,
        "computed_evidence": {},
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": "ready_to_issue",
    }
    return (
        "## Review Memo\n\n"
        "The pump station duty package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
