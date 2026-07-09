# ABOUTME: Engine for the SSC-01 review-first road visual operations issue review package.
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

_QUANT_STEPS = {
    "lighting_lux_01": 0.1,
    "lighting_lux_02": 0.1,
    "lighting_lux_03": 0.1,
    "lighting_lux_04": 0.1,
    "lighting_lux_05": 0.1,
    "lighting_lux_06": 0.1,
    "minimum_uniformity_margin": 0.01,
    "cctv_network_load_mbps": 0.1,
    "vms_network_load_mbps": 0.1,
    "sensor_network_load_mbps": 0.1,
    "controller_network_load_mbps": 0.1,
    "network_overhead_pct": 1.0,
    "network_headroom_margin_mbps": 0.5,
    "cctv_total_bitrate_mbps": 0.5,
    "storage_overhead_factor": 0.01,
    "cctv_poe_load_w": 1.0,
    "vms_poe_load_w": 1.0,
    "sensor_poe_load_w": 1.0,
    "poe_headroom_margin_w": 1.0,
    "poe_headroom_deficit_w": 1.0,
    "luminaire_power_w": 1.0,
    "device_ups_load_w": 1.0,
    "ups_efficiency": 0.01,
    "storm_sensor_level_m": 0.01,
    "water_level_margin_m": 0.01,
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
    quantized["retention_days"] = float(params["retention_days"])
    quantized["luminaire_count"] = float(params["luminaire_count"])
    quantized["ups_autonomy_h"] = float(params["ups_autonomy_h"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    lux_values = [p[f"lighting_lux_0{index}"] for index in range(1, 7)]
    average_illuminance = sum(lux_values) / len(lux_values)
    minimum_illuminance = min(lux_values)
    uniformity_ratio = minimum_illuminance / average_illuminance
    minimum_uniformity_ratio = max(0.5, _q(uniformity_ratio - p["minimum_uniformity_margin"], 0.01))

    base_network_load = (
        p["cctv_count"] * p["cctv_network_load_mbps"]
        + p["vms_network_load_mbps"]
        + p["sensor_network_load_mbps"]
        + p["controller_network_load_mbps"]
    )
    total_network_load = base_network_load * (1.0 + p["network_overhead_pct"] / 100.0)
    uplink_capacity = _ceil_to(total_network_load + p["network_headroom_margin_mbps"], 5.0)
    network_headroom = uplink_capacity - total_network_load

    total_cctv_storage = (
        p["cctv_total_bitrate_mbps"]
        * 24.0
        * 3600.0
        / 8.0
        / 1000.0
        * p["retention_days"]
        * p["storage_overhead_factor"]
        / 1000.0
    )

    poe_load = p["cctv_count"] * p["cctv_poe_load_w"] + p["vms_poe_load_w"] + p["sensor_poe_load_w"]
    if variant == "poe_budget_exceeded":
        poe_budget = _floor_to(poe_load - p["poe_headroom_deficit_w"], 1.0)
    else:
        poe_budget = _ceil_to(poe_load + p["poe_headroom_margin_w"], 1.0)
    poe_headroom = poe_budget - poe_load

    storm_alarm_threshold = p["storm_sensor_level_m"] + p["water_level_margin_m"]
    ups_energy = (
        (p["luminaire_count"] * p["luminaire_power_w"] + p["device_ups_load_w"])
        * p["ups_autonomy_h"]
        / p["ups_efficiency"]
        / 1000.0
    )

    return {
        "params": p,
        "variant": variant,
        "lux_values": lux_values,
        "average_illuminance": average_illuminance,
        "minimum_illuminance": minimum_illuminance,
        "uniformity_ratio": uniformity_ratio,
        "minimum_uniformity_ratio": minimum_uniformity_ratio,
        "base_network_load": base_network_load,
        "total_network_load": total_network_load,
        "uplink_capacity": uplink_capacity,
        "network_headroom": network_headroom,
        "total_cctv_storage": total_cctv_storage,
        "poe_load": poe_load,
        "poe_budget": poe_budget,
        "poe_headroom": poe_headroom,
        "storm_alarm_threshold": storm_alarm_threshold,
        "ups_energy": ups_energy,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_poe_switch_budget": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_lighting_grid_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "device_register_mismatch": {
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
    "poe_budget_exceeded": {
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

    result["average_illuminance_lux"] = state["average_illuminance"]
    result["minimum_illuminance_lux"] = state["minimum_illuminance"]
    result["uniformity_ratio"] = state["uniformity_ratio"]
    result["minimum_uniformity_ratio"] = state["minimum_uniformity_ratio"]
    result["total_network_load_mbps"] = state["total_network_load"]
    result["network_headroom_mbps"] = state["network_headroom"]
    result["total_cctv_storage_tb"] = state["total_cctv_storage"]
    result["poe_load_w"] = state["poe_load"]
    if state["variant"] != "missing_poe_switch_budget":
        result["poe_headroom_w"] = state["poe_headroom"]
    result["water_level_margin_m"] = state["params"]["water_level_margin_m"]
    result["ups_energy_kwh"] = state["ups_energy"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    lighting_rev = "Rev C"
    if variant == "stale_lighting_grid_revision":
        lighting_rev = "Rev C (current register basis; packet file is still Rev B)"
    return [
        ("RD-SSC01-003", "Road segment visual operations basis", "Rev B", "Issued for review"),
        ("LGT-SSC01-003", "Lighting grid calculation output", lighting_rev, "Issued for review"),
        ("LUM-SSC01-003", "Luminaire group schedule", "Rev A", "Issued for review"),
        ("CCTV-SSC01-003", "CCTV schedule and recording basis", "Rev A", "Issued for review"),
        ("VMS-SSC01-003", "VMS field device schedule", "Rev A", "Issued for review"),
        ("NET-SSC01-003", "ITS network and storage schedule", "Rev B", "Issued for review"),
        ("PWR-SSC01-003", "PoE and UPS schedule", "Rev B", "Issued for review"),
        ("WLS-SSC01-003", "Storm water-level sensor schedule", "Rev A", "Issued for review"),
        ("OPS-SSC01-003", "Night storm operating case", "Rev A", "Issued for review"),
        ("CRIT-SSC01-003", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    comments = [
        ("C-01", "Lighting", "Confirm lighting grid values are current for RD-SSC01-003.", "Closed", "minor", "", ""),
        ("C-02", "ITS", "Confirm CCTV and VMS device counts match the network schedule.", "Closed", "minor", "", ""),
        ("C-03", "Power", "Confirm PoE and UPS values use the same field-device set.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Authority",
                "Resolve critical visual/ITS readiness comment before issue.",
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
                "Update VMS callout leader on the visual operations sheet.",
                "Open",
                "minor",
                "ITS designer",
                "Carry VMS leader update to the next issue.",
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
    """Render the source packet for one road visual operations review instance."""
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
        "# Document Register - DOC-REG-SSC01-03\n\n"
        "Issue package: road visual operations package for RD-SSC01-003 under OPS-SSC01-003.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll chainages are corridor chainages and all levels are AHD unless a source states otherwise.\n"
    )

    lighting_rev = "Rev B" if variant == "stale_lighting_grid_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_lighting_grid_revision":
        stale_note = (
            "\nRevision note: this lighting grid is still Rev B. The document register lists LGT-SSC01-003 "
            "Rev C as the current issue basis.\n"
        )
    grid_rows = [
        "| Grid point | Illuminance |",
        "|---|---|",
    ]
    for index, lux in enumerate(state["lux_values"], start=1):
        grid_rows.append(f"| Grid point LG-0{index} | {lux:.1f} lux |")
    road_lighting = f"""# Road Segment And Lighting Grid - LGT-SSC01-003 ({lighting_rev})

Road segment: RD-SSC01-003. Operating case: OPS-SSC01-003. Luminaire group: LUM-SSC01-003.
{stale_note}
{chr(10).join(grid_rows)}

| Item | Value |
|---|---|
| Claimed average illuminance | {state["average_illuminance"]:.2f} lux |
| Claimed minimum illuminance | {state["minimum_illuminance"]:.1f} lux |
| Claimed uniformity ratio | {state["uniformity_ratio"]:.3f} |
| Lighting calculation basis | six-point task-owned grid from LGT-SSC01-003 |
"""

    vms_register_id = "VMS-SSC01-099" if variant == "device_register_mismatch" else "VMS-SSC01-003"
    mismatch_note = ""
    if variant == "device_register_mismatch":
        mismatch_note = (
            "\nRegister note: the device register lists VMS-SSC01-099, while network and power schedules "
            "use VMS-SSC01-003 for this issue package.\n"
        )
    device_register = f"""# Device Register - DEV-REG-SSC01-003 (Rev B)

Road segment: RD-SSC01-003. Cabinet and power schedule: PWR-SSC01-003.
{mismatch_note}
| Device role | Object ID | Served object |
|---|---|---|
| Road segment | RD-SSC01-003 | OPS-SSC01-003 |
| Lighting grid | LGT-SSC01-003 | RD-SSC01-003 |
| Luminaire group | LUM-SSC01-003 | RD-SSC01-003 |
| CCTV schedule | CCTV-SSC01-003 | RD-SSC01-003 |
| VMS device | {vms_register_id} | RD-SSC01-003 |
| ITS network | NET-SSC01-003 | CCTV-SSC01-003 / VMS-SSC01-003 / WLS-SSC01-003 |
| Cabinet power/PoE | PWR-SSC01-003 | CCTV-SSC01-003 / VMS-SSC01-003 / WLS-SSC01-003 |
| Storm sensor | WLS-SSC01-003 | OPS-SSC01-003 |
| Operating case | OPS-SSC01-003 | night storm incident response |
"""

    network_storage = f"""# Network And Storage Schedule - NET-SSC01-003 (Rev B)

Road segment: RD-SSC01-003. Operating case: OPS-SSC01-003. VMS device: VMS-SSC01-003.

| Item | Value |
|---|---|
| Active CCTV cameras | {p["cctv_count"]} |
| CCTV network load per camera | {p["cctv_network_load_mbps"]:.1f} Mbps |
| VMS network load | {p["vms_network_load_mbps"]:.1f} Mbps |
| Storm sensor network load | {p["sensor_network_load_mbps"]:.1f} Mbps |
| Controller network load | {p["controller_network_load_mbps"]:.1f} Mbps |
| Network overhead | {p["network_overhead_pct"]:.0f} % |
| Uplink capacity | {state["uplink_capacity"]:.1f} Mbps |
| Total CCTV bitrate | {p["cctv_total_bitrate_mbps"]:.1f} Mbps |
| Retention period | {p["retention_days"]:.0f} days |
| Storage overhead factor | {p["storage_overhead_factor"]:.2f} |
| Claimed total network load | {state["total_network_load"]:.2f} Mbps |
| Claimed network headroom | {state["network_headroom"]:.2f} Mbps |
| Claimed CCTV storage | {state["total_cctv_storage"]:.3f} TB |
"""

    if variant == "missing_poe_switch_budget":
        poe_budget_line = "| PoE switch budget | pending vendor confirmation |"
        poe_claim = "Package claim: PoE adequacy is pending vendor confirmation."
    else:
        poe_budget_line = f"| PoE switch budget | {state['poe_budget']:.0f} W |"
        verdict = "adequate" if state["poe_headroom"] >= 0.0 else "package marks adequate; reviewer to verify"
        poe_claim = f"Package claim: PoE load is {verdict} with {state['poe_headroom']:.1f} W headroom."
    poe_ups = f"""# PoE And UPS Schedule - PWR-SSC01-003 (Rev B)

Road segment: RD-SSC01-003. Cabinet power basis uses CCTV-SSC01-003, VMS-SSC01-003, and WLS-SSC01-003.

| Item | Value |
|---|---|
| CCTV PoE load per camera | {p["cctv_poe_load_w"]:.0f} W |
| VMS PoE load | {p["vms_poe_load_w"]:.0f} W |
| Storm sensor PoE load | {p["sensor_poe_load_w"]:.0f} W |
{poe_budget_line}
| Luminaire count | {p["luminaire_count"]:.0f} |
| Luminaire power | {p["luminaire_power_w"]:.0f} W |
| Device UPS load | {p["device_ups_load_w"]:.0f} W |
| UPS autonomy | {p["ups_autonomy_h"]:.0f} h |
| UPS efficiency | {p["ups_efficiency"]:.2f} |
| Claimed PoE load | {state["poe_load"]:.1f} W |
| Claimed UPS energy | {state["ups_energy"]:.3f} kWh |

{poe_claim}
"""

    scenario_note = "OPS-SSC01-003 night storm incident response for RD-SSC01-003."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "OPS-SSC01-003 table was copied from corridor RD-SSC01-099; reviewer must verify whether the "
            "night storm operating case belongs to RD-SSC01-003."
        )
    storm_operations = f"""# Storm Operations Note - OPS-SSC01-003 (Rev A)

Operating case note: {scenario_note}

| Item | Value |
|---|---|
| Road segment | RD-SSC01-003 |
| Operating case | OPS-SSC01-003 |
| Storm sensor | WLS-SSC01-003 |
| Storm sensor level | {p["storm_sensor_level_m"]:.2f} m |
| Storm alarm threshold | {state["storm_alarm_threshold"]:.2f} m |
| Visual devices required in storm case | LUM-SSC01-003 / CCTV-SSC01-003 / VMS-SSC01-003 |
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-003 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Minimum uniformity ratio | {state["minimum_uniformity_ratio"]:.2f} |
| PoE headroom | must be greater than or equal to 0 W using PWR-SSC01-003 |
| Network headroom | must be greater than or equal to 0 Mbps using NET-SSC01-003 |
| CCTV storage | must be recomputed from bitrate, retention period, and storage overhead |
| Storm margin | alarm threshold must exceed current storm sensor level |
| UPS energy | must be recomputed from luminaire and device loads, autonomy, and efficiency |

## Assessment bases (source-owned methods)

- Average illuminance: arithmetic mean of the six LGT-SSC01-003 grid values.
- Uniformity ratio: minimum illuminance divided by average illuminance.
- Total network load: active CCTV cameras x CCTV network load per camera plus VMS, storm sensor, and controller
  load, then apply network overhead.
- Network headroom: uplink capacity minus total network load.
- CCTV storage: total CCTV bitrate x 24 h/day x retention days x storage overhead, converted to decimal TB.
  Divide by 8, then by 1000 twice; do not use 1024-based binary conversion.
- PoE load: CCTV count x CCTV PoE load per camera plus VMS PoE load plus storm sensor PoE load.
- PoE headroom: PoE switch budget minus PoE load.
- UPS energy: (luminaire count x luminaire power plus device UPS load) x autonomy / efficiency.

## Review discipline

- Use the review matrix definitions to classify source conflicts, missing values, stale revisions, and copied cases.
- Evidence values must be recomputed from the source-owned methods above.
- Missing or unrecomputable evidence values should be requested from the source document that owns the missing field.
- Every finding, information request, and carried action should cite one exact RLR item.

## Review comments

{_comments_table(variant)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/road-segment-and-lighting-grid.md": road_lighting,
        "sources/device-register.md": device_register,
        "sources/network-and-storage.md": network_storage,
        "sources/poe-and-ups-schedule.md": poe_ups,
        "sources/storm-operations-note.md": storm_operations,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_lighting_grid_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "LGT-SSC01-003",
        "object_id": "LGT-SSC01-003",
        "consequence": (
            "The lighting-grid file is Rev B while the document register identifies LGT-SSC01-003 Rev C "
            "as the current issue basis."
        ),
        "action": "Replace the stale lighting grid with LGT-SSC01-003 Rev C before issue.",
    },
    "device_register_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "DEV-REG-SSC01-003",
        "object_id": "VMS-SSC01-003",
        "consequence": ("The device register lists VMS-SSC01-099 while network and power schedules use VMS-SSC01-003."),
        "action": "Reconcile the VMS device identity across the register, network schedule, and PoE schedule.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "OPS-SSC01-003",
        "object_id": "OPS-SSC01-003",
        "consequence": "The night storm operating case text is copied from corridor RD-SSC01-099.",
        "action": "Reissue OPS-SSC01-003 with the RD-SSC01-003 operating scenario before issue.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-003",
        "object_id": "C-04",
        "consequence": "Critical visual/ITS readiness comment C-04 remains open without owner or action.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "poe_budget_exceeded": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "PWR-SSC01-003",
        "object_id": "PWR-SSC01-003",
        "consequence": "Recomputed field-device PoE load exceeds the PoE switch budget.",
        "action": "Increase PoE switch budget or revise the CCTV/VMS/storm-sensor device set before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    evidence_notes = {
        "RLR-01": "All seven source files are present with document IDs and revisions.",
        "RLR-02": (
            "RD-SSC01-003, LGT-SSC01-003, LUM-SSC01-003, CCTV-SSC01-003, VMS-SSC01-003, "
            "NET-SSC01-003, PWR-SSC01-003, WLS-SSC01-003, and OPS-SSC01-003 reconcile."
        ),
        "RLR-03": "Lighting average, minimum, and uniformity recompute from the current LGT-SSC01-003 grid.",
        "RLR-04": "PoE load and lighting uniformity clear the source-owned criteria for the same device set.",
        "RLR-05": "The night storm operating case is OPS-SSC01-003 for RD-SSC01-003.",
        "RLR-06": "Network headroom, CCTV storage, storm margin, and UPS energy are source-backed.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the review matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_poe_switch_budget":
        evidence_notes["RLR-04"] = (
            "PWR-SSC01-003 has pending vendor confirmation for PoE switch budget, so PoE headroom cannot be computed."
        )

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "average_illuminance_lux",
            "minimum_illuminance_lux",
            "uniformity_ratio",
            "minimum_uniformity_ratio",
            "total_network_load_mbps",
            "network_headroom_mbps",
            "total_cctv_storage_tb",
            "poe_load_w",
            "poe_headroom_w",
            "water_level_margin_m",
            "ups_energy_kwh",
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
    if variant == "missing_poe_switch_budget":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Missing PoE switch budget for PWR-SSC01-003",
                "source_id": "PWR-SSC01-003",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the VMS callout leader for comment C-05.",
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
            "road_segment": "RD-SSC01-003",
            "lighting_grid": "LGT-SSC01-003",
            "luminaire_group": "LUM-SSC01-003",
            "cctv_schedule": "CCTV-SSC01-003",
            "vms_device": "VMS-SSC01-003",
            "its_network": "NET-SSC01-003",
            "cabinet_power_poe": "PWR-SSC01-003",
            "storm_sensor": "WLS-SSC01-003",
            "operating_case": "OPS-SSC01-003",
            "datum": "AHD",
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
        "## Issue-Readiness Review - RD-SSC01-003 road visual operations package\n\n"
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
        "The road visual operations package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
