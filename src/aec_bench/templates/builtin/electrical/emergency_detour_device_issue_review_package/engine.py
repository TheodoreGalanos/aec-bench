# ABOUTME: Engine for the SSC-01 emergency detour device issue review package.
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

_FT_TO_M = 0.3048

_QUANT_STEPS = {
    "vms_character_height_in": 1.0,
    "detour_speed_kmh": 1.0,
    "reading_rate_chars_s": 0.1,
    "message_margin_chars": 1.0,
    "cctv_load_mbps": 0.1,
    "vms_load_mbps": 0.1,
    "radio_load_mbps": 0.1,
    "controller_load_mbps": 0.1,
    "network_overhead_pct": 1.0,
    "network_headroom_margin_mbps": 0.5,
    "rf_tx_power_dbm": 0.1,
    "rf_tx_gain_db": 0.1,
    "rf_rx_gain_db": 0.1,
    "rf_path_loss_db": 0.1,
    "rf_misc_loss_db": 0.1,
    "rf_fade_margin_db": 0.1,
    "rf_link_margin_db": 0.1,
    "critical_load_w": 5.0,
    "battery_efficiency": 0.01,
    "required_detour_duration_h": 0.1,
    "battery_runtime_margin_h": 0.1,
    "battery_runtime_deficit_h": 0.1,
    "feeder_length_km": 0.01,
    "conductor_resistance_ohm_km": 0.01,
    "power_factor": 0.01,
    "voltage_drop_margin_percent": 0.1,
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
    quantized["cctv_count"] = int(params["cctv_count"])
    quantized["vms_count"] = int(params["vms_count"])
    quantized["feeder_voltage_v"] = float(params["feeder_voltage_v"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    vms_reading_time = p["vms_character_height_in"] * 40.0 * _FT_TO_M / (p["detour_speed_kmh"] / 3.6)
    readable_chars = vms_reading_time * p["reading_rate_chars_s"]
    message_length = max(6.0, _floor_to(readable_chars - p["message_margin_chars"], 1.0))
    vms_message_margin = readable_chars - message_length

    base_network_load = (
        p["cctv_count"] * p["cctv_load_mbps"]
        + p["vms_count"] * p["vms_load_mbps"]
        + p["radio_load_mbps"]
        + p["controller_load_mbps"]
    )
    required_network = base_network_load * (1.0 + p["network_overhead_pct"] / 100.0)
    uplink_capacity = _ceil_to(required_network + p["network_headroom_margin_mbps"], 1.0)
    network_headroom = uplink_capacity - required_network

    rf_received_power = (
        p["rf_tx_power_dbm"]
        + p["rf_tx_gain_db"]
        + p["rf_rx_gain_db"]
        - p["rf_path_loss_db"]
        - p["rf_misc_loss_db"]
        - p["rf_fade_margin_db"]
    )
    rf_receiver_sensitivity = rf_received_power - p["rf_link_margin_db"]

    if variant == "battery_runtime_deficient":
        target_runtime = max(0.5, p["required_detour_duration_h"] - p["battery_runtime_deficit_h"])
        battery_capacity = _floor_to(target_runtime * (p["critical_load_w"] / 1000.0) / p["battery_efficiency"], 0.1)
    else:
        target_runtime = p["required_detour_duration_h"] + p["battery_runtime_margin_h"]
        battery_capacity = _ceil_to(target_runtime * (p["critical_load_w"] / 1000.0) / p["battery_efficiency"], 0.1)
    battery_runtime = battery_capacity * p["battery_efficiency"] / (p["critical_load_w"] / 1000.0)
    battery_margin = battery_runtime - p["required_detour_duration_h"]

    feeder_current = p["critical_load_w"] / (p["feeder_voltage_v"] * p["power_factor"])
    feeder_voltage_drop = (
        2.0 * p["feeder_length_km"] * p["conductor_resistance_ohm_km"] * feeder_current / p["feeder_voltage_v"] * 100.0
    )
    allowable_voltage_drop = _ceil_to(feeder_voltage_drop + p["voltage_drop_margin_percent"], 0.1)
    voltage_drop_margin = allowable_voltage_drop - feeder_voltage_drop

    return {
        "params": p,
        "variant": variant,
        "vms_reading_time": vms_reading_time,
        "message_length": message_length,
        "vms_message_margin": vms_message_margin,
        "base_network_load": base_network_load,
        "required_network": required_network,
        "uplink_capacity": uplink_capacity,
        "network_headroom": network_headroom,
        "rf_received_power": rf_received_power,
        "rf_receiver_sensitivity": rf_receiver_sensitivity,
        "battery_capacity": battery_capacity,
        "battery_runtime": battery_runtime,
        "battery_margin": battery_margin,
        "feeder_current": feeder_current,
        "feeder_voltage_drop": feeder_voltage_drop,
        "allowable_voltage_drop": allowable_voltage_drop,
        "voltage_drop_margin": voltage_drop_margin,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_closure_duration": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_detour_plan_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "device_inventory_mismatch": {
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
    "battery_runtime_deficient": {
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

    result["vms_reading_time_s"] = state["vms_reading_time"]
    result["vms_message_margin_chars"] = state["vms_message_margin"]
    result["required_network_mbps"] = state["required_network"]
    result["network_headroom_mbps"] = state["network_headroom"]
    result["rf_received_power_dbm"] = state["rf_received_power"]
    result["rf_link_margin_db"] = state["params"]["rf_link_margin_db"]
    result["battery_runtime_h"] = state["battery_runtime"]
    if state["variant"] != "missing_closure_duration":
        result["battery_margin_h"] = state["battery_margin"]
    result["feeder_voltage_drop_percent"] = state["feeder_voltage_drop"]
    result["voltage_drop_margin_percent"] = state["voltage_drop_margin"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    detour_rev = "Rev C"
    if variant == "stale_detour_plan_revision":
        detour_rev = "Rev C (current register basis; packet file is still Rev B)"
    return [
        ("OPS-SSC01-004", "Emergency closure scenario", "Rev B", "Issued for review"),
        ("DETOUR-SSC01-004", "Emergency detour plan", detour_rev, "Issued for review"),
        ("TMP-SSC01-004", "Traffic management plan", "Rev B", "Issued for review"),
        ("MSG-SSC01-004", "Detour VMS message library", "Rev A", "Issued for review"),
        ("VMS-SSC01-004", "VMS field device schedule", "Rev A", "Issued for review"),
        ("CCTV-SSC01-004", "CCTV closure monitoring schedule", "Rev A", "Issued for review"),
        ("RF-SSC01-004", "Temporary radio link budget", "Rev B", "Issued for review"),
        ("NET-SSC01-004", "ITS network uplink schedule", "Rev B", "Issued for review"),
        ("PWR-SSC01-004", "Roadside cabinet power continuity schedule", "Rev B", "Issued for review"),
        ("CRIT-SSC01-004", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    comments = [
        (
            "C-01",
            "Traffic",
            "Confirm detour plan and VMS message use the same closure scenario.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-02",
            "ITS",
            "Confirm CCTV, VMS, radio, and controller membership matches the inventory.",
            "Closed",
            "minor",
            "",
            "",
        ),
        ("C-03", "Power", "Confirm battery runtime uses the same critical device set.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Authority",
                "Resolve critical detour operations comment before issue.",
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
                "Update temporary CCTV callout on the detour layout.",
                "Open",
                "minor",
                "ITS designer",
                "Carry CCTV callout update to the next issue.",
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
    """Render the source packet for one emergency detour device review instance."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    register_lines = [
        "| Document ID | Title | Revision | Status |",
        "|---|---|---|---|",
    ]
    for doc_id, title, rev, status in _register_rows(variant):
        register_lines.append(f"| {doc_id} | {title} | {rev} | {status} |")
    document_scope = (
        "All chainages are corridor chainages and all devices serve DETOUR-SSC01-004 unless a source states otherwise."
    )
    document_register = (
        "# Document Register - DOC-REG-SSC01-04\n\n"
        "Issue package: emergency detour device package for DETOUR-SSC01-004 under OPS-SSC01-004.\n\n"
        + "\n".join(register_lines)
        + f"\n\n{document_scope}\n"
    )

    detour_rev = "Rev B" if variant == "stale_detour_plan_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_detour_plan_revision":
        stale_note = (
            "\nRevision note: this detour plan is still Rev B. The document register lists DETOUR-SSC01-004 "
            "Rev C as the current issue basis.\n"
        )
    scenario_note = "OPS-SSC01-004 emergency closure response for DETOUR-SSC01-004."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "OPS-SSC01-004 table was copied from closure OPS-SSC01-099; reviewer must verify whether the "
            "emergency closure case belongs to DETOUR-SSC01-004."
        )
    if variant == "missing_closure_duration":
        duration_line = "| Required closure duration | pending traffic operations confirmation |"
        duration_claim = "Package claim: battery runtime adequacy is pending traffic operations confirmation."
    else:
        duration_line = f"| Required closure duration | {p['required_detour_duration_h']:.1f} h |"
        duration_claim = (
            f"Package claim: required closure duration is {p['required_detour_duration_h']:.1f} h for OPS-SSC01-004."
        )
    detour_plan = f"""# Detour Plan - DETOUR-SSC01-004 ({detour_rev})

Operating case note: {scenario_note}
{stale_note}
| Item | Value |
|---|---|
| Closure scenario | OPS-SSC01-004 |
| Detour route | DETOUR-SSC01-004 |
| Traffic management plan | TMP-SSC01-004 |
| Detour approach speed | {p["detour_speed_kmh"]:.0f} km/h |
{duration_line}

{duration_claim}
"""

    message_library = f"""# Message Library - MSG-SSC01-004 (Rev A)

Detour route: DETOUR-SSC01-004. VMS device set: VMS-SSC01-004.

| Item | Value |
|---|---|
| Selected message | DETOUR USE RAMP B |
| VMS character height | {p["vms_character_height_in"]:.0f} in |
| Reading rate | {p["reading_rate_chars_s"]:.1f} chars/s |
| Message length | {state["message_length"]:.0f} chars |
| Claimed reading time | {state["vms_reading_time"]:.2f} s |
| Claimed message margin | {state["vms_message_margin"]:.2f} chars |
"""

    vms_inventory_id = "VMS-SSC01-099" if variant == "device_inventory_mismatch" else "VMS-SSC01-004"
    mismatch_note = ""
    if variant == "device_inventory_mismatch":
        mismatch_note = (
            "\nInventory note: the device inventory lists VMS-SSC01-099, while communications and power schedules "
            "use VMS-SSC01-004 for this issue package.\n"
        )
    device_inventory = f"""# Device Inventory - DEV-REG-SSC01-004 (Rev B)

Emergency closure scenario: OPS-SSC01-004. Detour route: DETOUR-SSC01-004.
{mismatch_note}
| Device role | Object ID | Served object |
|---|---|---|
| Closure scenario | OPS-SSC01-004 | DETOUR-SSC01-004 |
| Detour plan | DETOUR-SSC01-004 | OPS-SSC01-004 |
| Traffic management plan | TMP-SSC01-004 | OPS-SSC01-004 |
| VMS device set | {vms_inventory_id} | DETOUR-SSC01-004 |
| CCTV device set | CCTV-SSC01-004 | DETOUR-SSC01-004 |
| Communications link | RF-SSC01-004 | VMS-SSC01-004 / CCTV-SSC01-004 |
| Network uplink | NET-SSC01-004 | VMS-SSC01-004 / CCTV-SSC01-004 / RF-SSC01-004 |
| Cabinet power supply | PWR-SSC01-004 | VMS-SSC01-004 / CCTV-SSC01-004 / RF-SSC01-004 |
| Message library | MSG-SSC01-004 | VMS-SSC01-004 |
"""

    communications = f"""# Communications Topology - NET-SSC01-004 (Rev B)

Detour route: DETOUR-SSC01-004. Closure scenario: OPS-SSC01-004.

| Item | Value |
|---|---|
| Active CCTV cameras | {p["cctv_count"]} |
| CCTV network load per camera | {p["cctv_load_mbps"]:.1f} Mbps |
| Active VMS boards | {p["vms_count"]} |
| VMS network load per board | {p["vms_load_mbps"]:.1f} Mbps |
| Radio telemetry load | {p["radio_load_mbps"]:.1f} Mbps |
| Controller network load | {p["controller_load_mbps"]:.1f} Mbps |
| Network overhead | {p["network_overhead_pct"]:.0f} % |
| Uplink capacity | {state["uplink_capacity"]:.1f} Mbps |
| RF transmit power | {p["rf_tx_power_dbm"]:.1f} dBm |
| RF transmit antenna gain | {p["rf_tx_gain_db"]:.1f} dB |
| RF receive antenna gain | {p["rf_rx_gain_db"]:.1f} dB |
| RF path loss | {p["rf_path_loss_db"]:.1f} dB |
| RF miscellaneous loss | {p["rf_misc_loss_db"]:.1f} dB |
| RF fade margin | {p["rf_fade_margin_db"]:.1f} dB |
| RF receiver sensitivity | {state["rf_receiver_sensitivity"]:.1f} dBm |
| Claimed required network load | {state["required_network"]:.2f} Mbps |
| Claimed network headroom | {state["network_headroom"]:.2f} Mbps |
| Claimed RF received power | {state["rf_received_power"]:.2f} dBm |
| Claimed RF link margin | {p["rf_link_margin_db"]:.2f} dB |
"""

    runtime_verdict = "adequate" if state["battery_margin"] >= 0.0 else "package marks adequate; reviewer to verify"
    runtime_claim = (
        f"Package claim: battery runtime is {runtime_verdict} with {state['battery_margin']:.2f} h margin "
        "where duration is available."
    )
    power_schedule = f"""# Power Continuity Schedule - PWR-SSC01-004 (Rev B)

Detour route: DETOUR-SSC01-004. Critical device set: VMS-SSC01-004 / CCTV-SSC01-004 / RF-SSC01-004.

| Item | Value |
|---|---|
| Battery capacity | {state["battery_capacity"]:.1f} kWh |
| Battery efficiency | {p["battery_efficiency"]:.2f} |
| Critical device load | {p["critical_load_w"]:.0f} W |
| Feeder length | {p["feeder_length_km"]:.2f} km |
| Conductor resistance | {p["conductor_resistance_ohm_km"]:.2f} ohm/km |
| Feeder voltage | {p["feeder_voltage_v"]:.0f} V |
| Power factor | {p["power_factor"]:.2f} |
| Allowable voltage drop | {state["allowable_voltage_drop"]:.1f} % |
| Claimed battery runtime | {state["battery_runtime"]:.2f} h |
| Claimed feeder voltage drop | {state["feeder_voltage_drop"]:.3f} % |

{runtime_claim}
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-004 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| VMS message margin | must be greater than or equal to 0 chars using MSG-SSC01-004 |
| Network headroom | must be greater than or equal to 0 Mbps using NET-SSC01-004 |
| RF link margin | must be greater than or equal to 0 dB using RF-SSC01-004 |
| Battery runtime margin | must be greater than or equal to 0 h using OPS-SSC01-004 and PWR-SSC01-004 |
| Voltage-drop margin | must be greater than or equal to 0 percent using PWR-SSC01-004 |

## Assessment bases (source-owned methods)

- VMS reading time: character height x 40 feet per inch x 0.3048 metres per foot, divided by detour speed.
- VMS message margin: VMS reading time x reading rate minus message length.
- Required network load: CCTV count x CCTV network load per camera plus VMS count x VMS network load per board plus
  radio telemetry load and controller load, then apply network overhead.
- Network headroom: uplink capacity minus required network load.
- RF received power: dBm arithmetic; transmit power plus antenna gains minus path loss, miscellaneous loss, and fade
  margin.
- RF link margin: received power minus receiver sensitivity.
- Battery runtime: kWh x efficiency divided by load kW.
- Battery margin: battery runtime minus required closure duration.
- Feeder voltage drop: 2 x feeder length x conductor resistance x feeder current divided by feeder voltage x 100.
- Voltage-drop margin: allowable voltage drop minus computed voltage drop.

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
        "sources/detour-plan.md": detour_plan,
        "sources/message-library.md": message_library,
        "sources/device-inventory.md": device_inventory,
        "sources/communications-topology.md": communications,
        "sources/power-continuity-schedule.md": power_schedule,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_detour_plan_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "DETOUR-SSC01-004",
        "object_id": "DETOUR-SSC01-004",
        "consequence": (
            "The detour-plan file is Rev B while the document register identifies DETOUR-SSC01-004 Rev C "
            "as the current issue basis."
        ),
        "action": "Replace the stale detour plan with DETOUR-SSC01-004 Rev C before issue.",
    },
    "device_inventory_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "DEV-REG-SSC01-004",
        "object_id": "VMS-SSC01-004",
        "consequence": (
            "The device inventory lists VMS-SSC01-099 while communications and power schedules use VMS-SSC01-004."
        ),
        "action": "Reconcile the VMS device identity across inventory, communications, and power sources.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "DETOUR-SSC01-004",
        "object_id": "OPS-SSC01-004",
        "consequence": "The emergency closure scenario text is copied from closure OPS-SSC01-099.",
        "action": (
            "Reissue OPS-SSC01-004 and DETOUR-SSC01-004 with the current emergency closure scenario before issue."
        ),
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-004",
        "object_id": "C-04",
        "consequence": "Critical detour operations comment C-04 remains open without owner or action.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "battery_runtime_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "PWR-SSC01-004",
        "object_id": "PWR-SSC01-004",
        "consequence": "Recomputed battery runtime is less than the required emergency closure duration.",
        "action": "Increase backup supply capacity, reduce critical load, or revise the closure duration before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    evidence_notes = {
        "RLR-01": "All seven source files are present with document IDs and revisions.",
        "RLR-02": (
            "OPS-SSC01-004, DETOUR-SSC01-004, TMP-SSC01-004, VMS-SSC01-004, CCTV-SSC01-004, "
            "RF-SSC01-004, NET-SSC01-004, PWR-SSC01-004, and MSG-SSC01-004 reconcile."
        ),
        "RLR-03": "Detour speed, VMS character height, reading rate, and message length are current and recomputable.",
        "RLR-04": "Battery runtime clears the required closure duration for the same critical device set.",
        "RLR-05": "The emergency closure scenario is OPS-SSC01-004 for DETOUR-SSC01-004.",
        "RLR-06": "Network headroom, RF link margin, and feeder voltage-drop margin are source-backed.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the review matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_closure_duration":
        evidence_notes["RLR-04"] = (
            "OPS-SSC01-004 / DETOUR-SSC01-004 has pending traffic operations confirmation for required closure "
            "duration, so battery margin cannot be computed."
        )

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "vms_reading_time_s",
            "vms_message_margin_chars",
            "required_network_mbps",
            "network_headroom_mbps",
            "rf_received_power_dbm",
            "rf_link_margin_db",
            "battery_runtime_h",
            "battery_margin_h",
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
    if variant == "missing_closure_duration":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Missing required closure duration for OPS-SSC01-004 detour",
                "source_id": "OPS-SSC01-004",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the temporary CCTV callout for comment C-05.",
                "owner": "ITS designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "closure_scenario": "OPS-SSC01-004",
            "detour_plan": "DETOUR-SSC01-004",
            "traffic_management_plan": "TMP-SSC01-004",
            "vms_device_set": "VMS-SSC01-004",
            "cctv_device_set": "CCTV-SSC01-004",
            "communications_link": "RF-SSC01-004",
            "network_uplink": "NET-SSC01-004",
            "cabinet_power_supply": "PWR-SSC01-004",
            "message_library": "MSG-SSC01-004",
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
        "## Issue-Readiness Review - DETOUR-SSC01-004 emergency detour device package\n\n"
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
        "The emergency detour device package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
