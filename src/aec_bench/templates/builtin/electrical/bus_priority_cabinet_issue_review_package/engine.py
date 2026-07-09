# ABOUTME: Engine for the SSC-01 bus-priority cabinet issue review package.
# ABOUTME: Derives packet state, source-pack files, review statuses, and golden fixtures.

from __future__ import annotations

import json
import math

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

_G = 9.81

_QUANT_STEPS = {
    "bus_approach_speed_kmh": 1.0,
    "bus_approach_grade_pct": 0.1,
    "yellow_reaction_time_s": 0.1,
    "yellow_deceleration_m_s2": 0.1,
    "intersection_width_m": 1.0,
    "bus_length_m": 1.0,
    "all_red_speed_kmh": 1.0,
    "bus_capacity_margin_target_pax_h": 10.0,
    "controller_load_w": 5.0,
    "detector_load_w": 1.0,
    "transit_radio_load_w": 5.0,
    "vms_load_w": 5.0,
    "signal_heads_load_w": 5.0,
    "cabinet_capacity_margin_w": 10.0,
    "cabinet_load_deficit_w": 10.0,
    "power_factor": 0.01,
    "feeder_length_km": 0.01,
    "conductor_resistance_ohm_km": 0.01,
    "voltage_drop_margin_target_percent": 0.1,
    "battery_efficiency": 0.01,
    "required_backup_h": 0.1,
    "battery_runtime_margin_h": 0.1,
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid, avoiding float dust."""
    return round(round(value / step) * step, 10)


def _ceil_to(value: float, step: float) -> float:
    """Round a value up to the next step boundary."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


def _floor_to(value: float, step: float) -> float:
    """Round a value down to the previous step boundary."""
    return round(math.floor(value / step + 1e-9) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with floats snapped to grid and numeric enums cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    quantized["buses_per_hour"] = int(params["buses_per_hour"])
    quantized["bus_occupancy_pax"] = int(params["bus_occupancy_pax"])
    quantized["detector_count"] = int(params["detector_count"])
    quantized["feeder_voltage_v"] = float(params["feeder_voltage_v"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    speed_m_s = p["bus_approach_speed_kmh"] / 3.6
    grade_fraction = p["bus_approach_grade_pct"] / 100.0
    yellow_denominator = 2.0 * p["yellow_deceleration_m_s2"] + 2.0 * _G * grade_fraction
    yellow_interval = p["yellow_reaction_time_s"] + speed_m_s / yellow_denominator
    all_red_interval = (p["intersection_width_m"] + p["bus_length_m"]) / (p["all_red_speed_kmh"] / 3.6)

    bus_capacity = float(p["buses_per_hour"] * p["bus_occupancy_pax"])
    demand_margin = min(p["bus_capacity_margin_target_pax_h"], bus_capacity - 50.0)
    peak_passenger_demand = _floor_to(bus_capacity - demand_margin, 10.0)
    bus_capacity_margin = bus_capacity - peak_passenger_demand

    cabinet_load = (
        p["controller_load_w"]
        + p["detector_count"] * p["detector_load_w"]
        + p["transit_radio_load_w"]
        + p["vms_load_w"]
        + p["signal_heads_load_w"]
    )
    if variant == "cabinet_load_exceeded":
        cabinet_capacity = _floor_to(cabinet_load - p["cabinet_load_deficit_w"], 10.0)
    else:
        cabinet_capacity = _ceil_to(cabinet_load + p["cabinet_capacity_margin_w"], 10.0)
    cabinet_load_margin = cabinet_capacity - cabinet_load

    feeder_current = cabinet_load / (p["feeder_voltage_v"] * p["power_factor"])
    feeder_voltage_drop = (
        2.0 * p["feeder_length_km"] * p["conductor_resistance_ohm_km"] * feeder_current / p["feeder_voltage_v"] * 100.0
    )
    allowable_voltage_drop = _ceil_to(feeder_voltage_drop + p["voltage_drop_margin_target_percent"], 0.1)
    voltage_drop_margin = allowable_voltage_drop - feeder_voltage_drop

    target_runtime = p["required_backup_h"] + p["battery_runtime_margin_h"]
    battery_capacity = _ceil_to(target_runtime * (cabinet_load / 1000.0) / p["battery_efficiency"], 0.1)
    battery_runtime = battery_capacity * p["battery_efficiency"] / (cabinet_load / 1000.0)
    battery_margin = battery_runtime - p["required_backup_h"]

    return {
        "params": p,
        "variant": variant,
        "yellow_interval": yellow_interval,
        "all_red_interval": all_red_interval,
        "peak_passenger_demand": peak_passenger_demand,
        "bus_capacity": bus_capacity,
        "bus_capacity_margin": bus_capacity_margin,
        "cabinet_load": cabinet_load,
        "cabinet_capacity": cabinet_capacity,
        "cabinet_load_margin": cabinet_load_margin,
        "feeder_current": feeder_current,
        "feeder_voltage_drop": feeder_voltage_drop,
        "allowable_voltage_drop": allowable_voltage_drop,
        "voltage_drop_margin": voltage_drop_margin,
        "battery_capacity": battery_capacity,
        "battery_runtime": battery_runtime,
        "battery_margin": battery_margin,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_cabinet_capacity": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_signal_timing_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "detector_controller_mismatch": {
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
    "cabinet_load_exceeded": {
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

    result["yellow_interval_s"] = state["yellow_interval"]
    result["all_red_interval_s"] = state["all_red_interval"]
    result["bus_handling_capacity_pax_h"] = state["bus_capacity"]
    result["bus_capacity_margin_pax_h"] = state["bus_capacity_margin"]
    result["cabinet_load_w"] = state["cabinet_load"]
    if state["variant"] != "missing_cabinet_capacity":
        result["cabinet_load_margin_w"] = state["cabinet_load_margin"]
    result["feeder_current_a"] = state["feeder_current"]
    result["feeder_voltage_drop_percent"] = state["feeder_voltage_drop"]
    result["voltage_drop_margin_percent"] = state["voltage_drop_margin"]
    result["battery_runtime_h"] = state["battery_runtime"]
    result["battery_margin_h"] = state["battery_margin"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    signal_rev = "Rev D"
    if variant == "stale_signal_timing_revision":
        signal_rev = "Rev D (current register basis; packet file is still Rev C)"
    return [
        ("BUS-SSC01-005", "Bus-priority operating scenario", "Rev B", "Issued for review"),
        ("SIG-SSC01-005", "Signal phasing and timing sheet", signal_rev, "Issued for review"),
        ("DET-SSC01-005", "Bus-priority detector schedule", "Rev A", "Issued for review"),
        ("CTRL-SSC01-005", "Signal controller configuration", "Rev A", "Issued for review"),
        ("CAB-SSC01-005", "Roadside cabinet load schedule", "Rev B", "Issued for review"),
        ("FEED-SSC01-005", "Cabinet feeder schedule", "Rev B", "Issued for review"),
        ("BATT-SSC01-005", "Backup supply schedule", "Rev B", "Issued for review"),
        ("OPS-SSC01-005", "Owner operations criterion", "Rev A", "Current"),
        ("CRIT-SSC01-005", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    comments = [
        (
            "C-01",
            "Traffic",
            "Confirm bus-priority operating scenario and signal timing sheet use the same peak period.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-02",
            "ITS",
            "Confirm detector set, controller configuration, and cabinet load schedule use matching equipment IDs.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-03",
            "Electrical",
            "Confirm cabinet load, feeder voltage drop, and backup runtime use the same load set.",
            "Closed",
            "minor",
            "",
            "",
        ),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Owner",
                "Resolve critical bus-priority operations comment before issue.",
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
                "Update controller label on the cabinet single-line diagram.",
                "Open",
                "minor",
                "Electrical designer",
                "Carry controller label update to the next issue.",
            )
        )

    lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, discipline, text, status, criticality, owner, action in comments:
        lines.append(f"| {cid} | {discipline} | {text} | {status} | {criticality} | {owner} | {action} |")
    return "\n".join(lines)


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the source packet for one bus-priority cabinet review instance."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    register_lines = [
        "| Document ID | Title | Revision | Status |",
        "|---|---|---|---|",
    ]
    for doc_id, title, rev, status in _register_rows(variant):
        register_lines.append(f"| {doc_id} | {title} | {rev} | {status} |")
    document_register = (
        "# Document Register - DOC-REG-SSC01-05\n\n"
        "Issue package: bus-priority corridor and cabinet package for BUS-SSC01-005 under OPS-SSC01-005.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll values are source-packet values for the current synthetic task-owned issue package.\n"
    )

    scenario_note = "BUS-SSC01-005 weekday AM peak bus-priority case."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "BUS-SSC01-005 table was copied from scenario BUS-SSC01-099; reviewer must verify whether the "
            "bus-priority operating case belongs to BUS-SSC01-005."
        )
    operations_plan = f"""# Bus-Priority Operations Plan - BUS-SSC01-005 (Rev B)

Operating case note: {scenario_note}

| Item | Value |
|---|---|
| Owner operations case | OPS-SSC01-005 |
| Bus-priority scenario | BUS-SSC01-005 |
| Priority period | Weekday AM peak |
| Scheduled priority buses | {p["buses_per_hour"]} buses/h |
| Design bus occupancy | {p["bus_occupancy_pax"]} passengers/bus |
| Peak passenger demand | {state["peak_passenger_demand"]:.0f} passengers/h |
| Design bus length | {p["bus_length_m"]:.0f} m |

Package claim: BUS-SSC01-005 meets the passenger-demand basis for OPS-SSC01-005.
"""

    signal_rev = "Rev C" if variant == "stale_signal_timing_revision" else "Rev D"
    stale_note = ""
    if variant == "stale_signal_timing_revision":
        stale_note = (
            "\nRevision note: this signal timing sheet is still Rev C. The document register lists SIG-SSC01-005 "
            "Rev D as the current issue basis.\n"
        )
    signal_sheet = f"""# Signal Phasing And Timing Sheet - SIG-SSC01-005 ({signal_rev})

Signal group: SG-BUS-05. Bus-priority scenario: BUS-SSC01-005.
{stale_note}
| Item | Value |
|---|---|
| Bus approach speed | {p["bus_approach_speed_kmh"]:.0f} km/h |
| Bus approach grade | {p["bus_approach_grade_pct"]:.1f} % |
| Yellow reaction time | {p["yellow_reaction_time_s"]:.1f} s |
| Yellow deceleration | {p["yellow_deceleration_m_s2"]:.1f} m/s2 |
| Intersection width | {p["intersection_width_m"]:.0f} m |
| Design bus length | {p["bus_length_m"]:.0f} m |
| All-red clearance speed | {p["all_red_speed_kmh"]:.0f} km/h |
| Claimed yellow interval | {state["yellow_interval"]:.2f} s |
| Claimed all-red interval | {state["all_red_interval"]:.2f} s |
"""

    detector_id = "DET-SSC01-099" if variant == "detector_controller_mismatch" else "DET-SSC01-005"
    mismatch_note = ""
    if variant == "detector_controller_mismatch":
        mismatch_note = (
            "\nMembership note: the detector/controller schedule lists DET-SSC01-099, while operations and cabinet "
            "loads use DET-SSC01-005 for this issue package.\n"
        )
    detector_schedule = f"""# Detector Controller Schedule - DET-CTRL-SSC01-005 (Rev A)

Bus-priority scenario: BUS-SSC01-005. Signal group: SG-BUS-05.
{mismatch_note}
| Device role | Object ID | Served object |
|---|---|---|
| Bus-priority scenario | BUS-SSC01-005 | OPS-SSC01-005 |
| Signal timing sheet | SIG-SSC01-005 | BUS-SSC01-005 |
| Bus-priority detector set | {detector_id} | SG-BUS-05 |
| Signal controller | CTRL-SSC01-005 | SG-BUS-05 / CAB-SSC01-005 |
| Roadside cabinet | CAB-SSC01-005 | CTRL-SSC01-005 / DET-SSC01-005 |
| Cabinet feeder | FEED-SSC01-005 | CAB-SSC01-005 |
| Backup supply | BATT-SSC01-005 | CAB-SSC01-005 |
"""

    if variant == "missing_cabinet_capacity":
        cabinet_capacity_line = "| Cabinet capacity | pending electrical cabinet schedule confirmation |"
        cabinet_claim = "Package claim: cabinet adequacy is pending electrical cabinet schedule confirmation."
    else:
        cabinet_capacity_line = f"| Cabinet capacity | {state['cabinet_capacity']:.0f} W |"
        cabinet_verdict = (
            "adequate" if state["cabinet_load_margin"] >= 0.0 else "package marks adequate; reviewer to verify"
        )
        cabinet_claim = (
            f"Package claim: cabinet load is {cabinet_verdict} with {state['cabinet_load_margin']:.2f} W margin."
        )
    cabinet_schedule = f"""# Cabinet Load Schedule - CAB-SSC01-005 (Rev B)

Cabinet serves BUS-SSC01-005, SIG-SSC01-005, DET-SSC01-005, and CTRL-SSC01-005.

| Item | Value |
|---|---|
| Controller load | {p["controller_load_w"]:.0f} W |
| Detector count | {p["detector_count"]} |
| Detector load per unit | {p["detector_load_w"]:.0f} W |
| Transit radio load | {p["transit_radio_load_w"]:.0f} W |
| VMS load | {p["vms_load_w"]:.0f} W |
| Signal heads load | {p["signal_heads_load_w"]:.0f} W |
{cabinet_capacity_line}
| Claimed cabinet load | {state["cabinet_load"]:.0f} W |

{cabinet_claim}
"""

    feeder_schedule = f"""# Feeder Backup Schedule - FEED-BATT-SSC01-005 (Rev B)

Cabinet feeder: FEED-SSC01-005. Backup supply: BATT-SSC01-005. Connected cabinet: CAB-SSC01-005.

| Item | Value |
|---|---|
| Feeder voltage | {p["feeder_voltage_v"]:.0f} V |
| Power factor | {p["power_factor"]:.2f} |
| Feeder length | {p["feeder_length_km"]:.2f} km |
| Conductor resistance | {p["conductor_resistance_ohm_km"]:.2f} ohm/km |
| Allowable voltage drop | {state["allowable_voltage_drop"]:.1f} % |
| Battery capacity | {state["battery_capacity"]:.1f} kWh |
| Battery efficiency | {p["battery_efficiency"]:.2f} |
| Required backup duration | {p["required_backup_h"]:.1f} h |
| Claimed feeder current | {state["feeder_current"]:.2f} A |
| Claimed feeder voltage drop | {state["feeder_voltage_drop"]:.3f} % |
| Claimed battery runtime | {state["battery_runtime"]:.2f} h |

Package claim: FEED-SSC01-005 and BATT-SSC01-005 are adequate for the CAB-SSC01-005 connected load.
"""

    owner_criterion = f"""# Owner Operations Criterion - OPS-SSC01-005 (Rev A)

Owner criterion for issue of BUS-SSC01-005.

| Criterion | Value |
|---|---|
| Required operations case | BUS-SSC01-005 weekday AM peak |
| Minimum bus-priority handling capacity | Peak passenger demand in BUS-SSC01-005 |
| Minimum cabinet load margin | greater than or equal to 0 W using CAB-SSC01-005 |
| Maximum feeder voltage drop | allowable voltage drop in FEED-SSC01-005 |
| Minimum backup duration | {p["required_backup_h"]:.1f} h using BATT-SSC01-005 |
| Issue-readiness rule | no critical findings or unresolved critical information requests |
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-005 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Yellow interval | must be greater than 0 s using SIG-SSC01-005 |
| All-red interval | must be greater than 0 s using SIG-SSC01-005 |
| Passenger capacity margin | must be greater than or equal to 0 passengers/h using BUS-SSC01-005 |
| Cabinet load margin | must be greater than or equal to 0 W using CAB-SSC01-005 |
| Voltage-drop margin | must be greater than or equal to 0 percent using FEED-SSC01-005 |
| Battery runtime margin | must be greater than or equal to 0 h using BATT-SSC01-005 |

## Assessment bases (source-owned methods)

- Yellow interval: reaction time plus speed converted from km/h to m/s by dividing by 3.6, divided by two times
  deceleration plus two times 9.81 times signed grade fraction.
- All-red interval: intersection width plus design bus length, divided by all-red clearance speed converted from km/h
  to m/s by dividing by 3.6.
- Passenger capacity: buses per hour times passengers per bus.
- Passenger capacity margin: bus handling capacity minus peak passenger demand.
- Cabinet load: controller load plus detector count times detector load per unit plus transit radio load, VMS load, and
  signal heads load.
- Cabinet load margin: cabinet capacity minus cabinet load.
- Feeder current: cabinet load divided by feeder voltage and power factor.
- Feeder voltage drop: 2 x feeder length x conductor resistance x feeder current divided by feeder voltage x 100.
- Voltage-drop margin: allowable voltage drop minus computed voltage drop.
- Battery runtime: kWh x efficiency divided by load kW, using W to kW conversion for cabinet load.
- Battery margin: battery runtime minus required backup duration.

## Review discipline

- Use the review matrix definitions to classify source conflicts, missing values, stale revisions, and copied scenarios.
- Evidence values must be recomputed from the source-owned methods above.
- Missing or unrecomputable evidence values should be requested from the source document that owns the missing field.
- Every finding, information request, and carried action should cite one exact RLR item.

## Review comments

{_comments_table(variant)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/bus-priority-operations-plan.md": operations_plan,
        "sources/signal-phasing-timing-sheet.md": signal_sheet,
        "sources/detector-controller-schedule.md": detector_schedule,
        "sources/cabinet-load-schedule.md": cabinet_schedule,
        "sources/feeder-backup-schedule.md": feeder_schedule,
        "sources/owner-operations-criterion.md": owner_criterion,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_signal_timing_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "SIG-SSC01-005",
        "object_id": "SIG-SSC01-005",
        "consequence": (
            "The signal timing file is Rev C while the document register identifies SIG-SSC01-005 Rev D "
            "as the current issue basis."
        ),
        "action": "Replace the stale signal phasing and timing sheet with SIG-SSC01-005 Rev D before issue.",
    },
    "detector_controller_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "DET-CTRL-SSC01-005",
        "object_id": "DET-SSC01-005",
        "consequence": (
            "The detector/controller schedule lists DET-SSC01-099 while operations and cabinet schedules use "
            "DET-SSC01-005."
        ),
        "action": "Reconcile detector and controller membership across operations, controller, and cabinet sources.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "BUS-SSC01-005",
        "object_id": "BUS-SSC01-005",
        "consequence": "The bus-priority operating scenario text is copied from scenario BUS-SSC01-099.",
        "action": "Reissue BUS-SSC01-005 and OPS-SSC01-005 with the current bus-priority operating case.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-005",
        "object_id": "C-04",
        "consequence": "Critical bus-priority operations comment C-04 remains open without owner or action.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "cabinet_load_exceeded": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "CAB-SSC01-005",
        "object_id": "CAB-SSC01-005",
        "consequence": "Recomputed cabinet load exceeds the available cabinet capacity.",
        "action": "Increase cabinet capacity, reduce connected load, or revise the equipment set before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    evidence_notes = {
        "RLR-01": "All eight source files are present with document IDs and revisions.",
        "RLR-02": (
            "BUS-SSC01-005, SIG-SSC01-005, DET-SSC01-005, CTRL-SSC01-005, CAB-SSC01-005, "
            "FEED-SSC01-005, BATT-SSC01-005, and OPS-SSC01-005 reconcile."
        ),
        "RLR-03": "Signal timing inputs are current and recomputable from SIG-SSC01-005.",
        "RLR-04": "Passenger capacity and cabinet load clear the source criteria for BUS-SSC01-005 / CAB-SSC01-005.",
        "RLR-05": "The bus-priority operating scenario is BUS-SSC01-005 under OPS-SSC01-005.",
        "RLR-06": "Feeder voltage drop and backup runtime are source-backed for the same cabinet load.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the review matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_cabinet_capacity":
        evidence_notes["RLR-04"] = (
            "CAB-SSC01-005 has pending electrical cabinet schedule confirmation for cabinet capacity, so cabinet "
            "load margin cannot be computed."
        )

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "yellow_interval_s",
            "all_red_interval_s",
            "bus_handling_capacity_pax_h",
            "bus_capacity_margin_pax_h",
            "cabinet_load_w",
            "cabinet_load_margin_w",
            "feeder_current_a",
            "feeder_voltage_drop_percent",
            "voltage_drop_margin_percent",
            "battery_runtime_h",
            "battery_margin_h",
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
    if variant == "missing_cabinet_capacity":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Missing cabinet capacity for CAB-SSC01-005",
                "source_id": "CAB-SSC01-005",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the controller label for comment C-05.",
                "owner": "Electrical designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "bus_priority_scenario": "BUS-SSC01-005",
            "signal_timing_basis": "SIG-SSC01-005",
            "detector_set": "DET-SSC01-005",
            "signal_controller": "CTRL-SSC01-005",
            "roadside_cabinet": "CAB-SSC01-005",
            "cabinet_feeder": "FEED-SSC01-005",
            "backup_supply": "BATT-SSC01-005",
            "owner_operations_criterion": "OPS-SSC01-005",
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
        "## Issue-Readiness Review - BUS-SSC01-005 bus-priority cabinet package\n\n"
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
        "The bus-priority cabinet package has been reviewed and is approved for issue. The design is fully compliant "
        "with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
