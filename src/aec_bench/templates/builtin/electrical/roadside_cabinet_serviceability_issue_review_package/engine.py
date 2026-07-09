# ABOUTME: Engine for the SSC-01 roadside cabinet serviceability issue review package.
# ABOUTME: Derives source-pack files, cabinet evidence, review statuses, and golden fixtures.

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
    "hgl_level_m": 0.01,
    "inundation_level_m": 0.01,
    "minimum_freeboard_m": 0.01,
    "flood_freeboard_margin_target_m": 0.01,
    "enclosure_capacity_w_at_reference_temp": 10.0,
    "reference_temperature_c": 0.1,
    "event_temperature_c": 0.1,
    "derate_pct_per_c": 0.01,
    "thermal_margin_target_w": 5.0,
    "thermal_deficit_w": 5.0,
    "battery_efficiency": 0.01,
    "required_backup_h": 0.1,
    "battery_runtime_margin_h": 0.1,
    "bess_power_margin_kw": 0.1,
    "voltage_drop_margin_percent": 0.1,
    "feeder_length_km": 0.01,
    "conductor_resistance_ohm_km": 0.01,
    "feeder_voltage_v": 1.0,
    "power_factor": 0.01,
    "road_lighting_power_w": 10.0,
    "annual_operating_hours": 10.0,
    "lit_area_m2": 10.0,
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
    """Return params with floats snapped to grid and hidden variants cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    controlling_water_level = max(p["hgl_level_m"], p["inundation_level_m"])
    cabinet_pad_level = _q(
        controlling_water_level + p["minimum_freeboard_m"] + p["flood_freeboard_margin_target_m"],
        0.01,
    )
    cabinet_freeboard = cabinet_pad_level - controlling_water_level
    flood_freeboard_margin = cabinet_freeboard - p["minimum_freeboard_m"]

    derate_fraction = p["derate_pct_per_c"] / 100.0 * (p["event_temperature_c"] - p["reference_temperature_c"])
    thermal_derated_capacity = p["enclosure_capacity_w_at_reference_temp"] * (1.0 - derate_fraction)
    if variant == "thermal_capacity_deficient":
        critical_load = _ceil_to(thermal_derated_capacity + p["thermal_deficit_w"], 5.0)
    else:
        critical_load = _floor_to(thermal_derated_capacity - p["thermal_margin_target_w"], 5.0)
    thermal_margin = thermal_derated_capacity - critical_load
    thermal_utilization = critical_load / thermal_derated_capacity

    battery_capacity = _ceil_to(
        (p["required_backup_h"] + p["battery_runtime_margin_h"]) * critical_load / 1000.0 / p["battery_efficiency"],
        0.1,
    )
    battery_runtime = battery_capacity * p["battery_efficiency"] / (critical_load / 1000.0)
    battery_margin = battery_runtime - p["required_backup_h"]
    bess_inverter_capacity = _ceil_to(critical_load / 1000.0 + p["bess_power_margin_kw"], 0.1)
    bess_power_margin = bess_inverter_capacity - critical_load / 1000.0
    bess_energy_margin = battery_capacity * p["battery_efficiency"] - critical_load / 1000.0 * p["required_backup_h"]

    feeder_current = critical_load / (p["feeder_voltage_v"] * p["power_factor"])
    feeder_voltage_drop = (
        2.0 * p["feeder_length_km"] * p["conductor_resistance_ohm_km"] * feeder_current / p["feeder_voltage_v"] * 100.0
    )
    allowable_voltage_drop = _ceil_to(feeder_voltage_drop + p["voltage_drop_margin_percent"], 0.1)
    voltage_drop_margin = allowable_voltage_drop - feeder_voltage_drop
    road_lighting_aeci = p["road_lighting_power_w"] * p["annual_operating_hours"] / 1000.0 / p["lit_area_m2"]

    return {
        "params": p,
        "variant": variant,
        "controlling_water_level": controlling_water_level,
        "cabinet_pad_level": cabinet_pad_level,
        "cabinet_freeboard": cabinet_freeboard,
        "flood_freeboard_margin": flood_freeboard_margin,
        "thermal_derated_capacity": thermal_derated_capacity,
        "critical_load": critical_load,
        "thermal_margin": thermal_margin,
        "thermal_utilization": thermal_utilization,
        "battery_capacity": battery_capacity,
        "battery_runtime": battery_runtime,
        "battery_margin": battery_margin,
        "bess_inverter_capacity": bess_inverter_capacity,
        "bess_power_margin": bess_power_margin,
        "bess_energy_margin": bess_energy_margin,
        "feeder_current": feeder_current,
        "feeder_voltage_drop": feeder_voltage_drop,
        "allowable_voltage_drop": allowable_voltage_drop,
        "voltage_drop_margin": voltage_drop_margin,
        "road_lighting_aeci": road_lighting_aeci,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_derating_rate": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_enclosure_derating_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "cabinet_event_mismatch": {
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
    "thermal_capacity_deficient": {
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

    result["cabinet_freeboard_m"] = state["cabinet_freeboard"]
    result["flood_freeboard_margin_m"] = state["flood_freeboard_margin"]
    if state["variant"] != "missing_derating_rate":
        result["thermal_derated_capacity_w"] = state["thermal_derated_capacity"]
        result["thermal_margin_w"] = state["thermal_margin"]
        result["thermal_utilization"] = state["thermal_utilization"]
    result["battery_runtime_h"] = state["battery_runtime"]
    result["battery_margin_h"] = state["battery_margin"]
    result["bess_power_margin_kw"] = state["bess_power_margin"]
    result["bess_energy_margin_kwh"] = state["bess_energy_margin"]
    result["feeder_voltage_drop_percent"] = state["feeder_voltage_drop"]
    result["voltage_drop_margin_percent"] = state["voltage_drop_margin"]
    result["road_lighting_aeci_kwh_m2_y"] = state["road_lighting_aeci"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    heat_rev = "Rev B"
    if variant == "stale_enclosure_derating_revision":
        heat_rev = "Rev B (current register basis; packet file is still Rev A)"
    return [
        ("CAB-SSC01-007", "Roadside cabinet setout and elevation", "Rev C", "Issued for review"),
        ("HGL-SSC01-007", "Flood HGL and inundation table", "Rev B", "Issued for review"),
        ("HEAT-SSC01-007", "Enclosure heat derating note", heat_rev, "Issued for review"),
        ("LOAD-SSC01-007", "Critical cabinet load schedule", "Rev B", "Issued for review"),
        ("BATT-SSC01-007", "Backup energy schedule", "Rev B", "Issued for review"),
        ("FEED-SSC01-007", "Feeder and access note", "Rev A", "Issued for review"),
        ("OPS-SSC01-007", "Owner serviceability criterion", "Rev A", "Current"),
        ("MEMO-SSC01-007", "Cabinet serviceability criteria memo", "Rev A", "Current"),
        ("CRIT-SSC01-007", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    comments = [
        (
            "C-01",
            "Electrical",
            "Confirm cabinet, HGL, heat derating, load, backup, and feeder sources refer to the same cabinet.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-02",
            "Operations",
            "Confirm flood, heat, and outage event case matches the owner serviceability criterion.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-03",
            "Electrical",
            "Confirm backup energy, voltage drop, and lighting AECI are traceable to source values.",
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
                "Resolve critical cabinet thermal serviceability comment before issue.",
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
                "Update cabinet maintenance access label on the package cover sheet.",
                "Open",
                "minor",
                "Electrical designer",
                "Carry cabinet access label update to the next issue.",
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
    """Render the source packet for one roadside cabinet serviceability review instance."""
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
        "# Document Register - DOC-REG-SSC01-07\n\n"
        "Issue package: roadside cabinet serviceability review package for CAB-SSC01-007 under OPS-SSC01-007.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll values are source-packet values for the current synthetic task-owned issue package.\n"
    )

    scenario_note = "CAB-SSC01-007 flood, heat, and outage case under OPS-SSC01-007."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "CAB-SSC01-007 table was copied from cabinet serviceability case CAB-SSC01-099; reviewer must verify "
            "whether the flood, heat, and outage event case belongs to CAB-SSC01-007."
        )
    cabinet_setout = f"""# Cabinet Setout And Elevation - CAB-SSC01-007 (Rev C)

Cabinet serviceability note: {scenario_note}
Flood basis: HGL-SSC01-007. Heat basis: HEAT-SSC01-007. Owner case: OPS-SSC01-007.

| Item | Value |
|---|---|
| Cabinet ID | CAB-SSC01-007 |
| Cabinet chainage | Ch 12+740 |
| Cabinet pad level | {state["cabinet_pad_level"]:.2f} m |
| Cable-entry level | {state["cabinet_pad_level"] + 0.18:.2f} m |
| Maintenance access route | FEED-SSC01-007 service shoulder route |

Package claim: CAB-SSC01-007 has {state["flood_freeboard_margin"]:.3f} m flood freeboard margin.
"""

    flood_cabinet = "CAB-SSC01-071" if variant == "cabinet_event_mismatch" else "CAB-SSC01-007"
    mismatch_note = ""
    if variant == "cabinet_event_mismatch":
        mismatch_note = (
            "\nMembership note: HGL-SSC01-007 is labelled for CAB-SSC01-071 while the setout, load, backup, "
            "and feeder sources identify CAB-SSC01-007.\n"
        )
    flood_table = f"""# Flood HGL And Inundation Table - HGL-SSC01-007 (Rev B)

Associated cabinet: {flood_cabinet}. Owner event case: OPS-SSC01-007.
{mismatch_note}
| Item | Value |
|---|---|
| HGL level | {p["hgl_level_m"]:.2f} m |
| Inundation level | {p["inundation_level_m"]:.2f} m |
| Controlling water level | {state["controlling_water_level"]:.2f} m |
| Claimed cabinet freeboard | {state["cabinet_freeboard"]:.3f} m |
| Claimed flood freeboard margin | {state["flood_freeboard_margin"]:.3f} m |

Package claim: HGL-SSC01-007 gives the controlling water level for CAB-SSC01-007.
"""

    heat_rev = "Rev A" if variant == "stale_enclosure_derating_revision" else "Rev B"
    stale_note = ""
    if variant == "stale_enclosure_derating_revision":
        stale_note = (
            "\nRevision note: this enclosure derating note is still Rev A. The document register lists "
            "HEAT-SSC01-007 Rev B as the current issue basis.\n"
        )
    derating_rate_line = (
        "| Derating rate | pending heat derating rate confirmation |"
        if variant == "missing_derating_rate"
        else f"| Derating rate | {p['derate_pct_per_c']:.2f} % per C |"
    )
    thermal_claim = (
        "Package claim: enclosure heat derating cannot be confirmed until the derating rate is supplied."
        if variant == "missing_derating_rate"
        else f"Package claim: HEAT-SSC01-007 has {state['thermal_margin']:.3f} W thermal margin."
    )
    enclosure_derating = f"""# Enclosure Derating Note - HEAT-SSC01-007 ({heat_rev})

Associated cabinet: CAB-SSC01-007. Critical load source: LOAD-SSC01-007.
{stale_note}
| Item | Value |
|---|---|
| Reference enclosure capacity | {p["enclosure_capacity_w_at_reference_temp"]:.0f} W |
| Reference temperature | {p["reference_temperature_c"]:.1f} C |
| Event temperature | {p["event_temperature_c"]:.1f} C |
{derating_rate_line}
| Claimed thermal derated capacity | {state["thermal_derated_capacity"]:.3f} W |
| Claimed thermal margin | {state["thermal_margin"]:.3f} W |

{thermal_claim}
"""

    load_backup = f"""# Critical Load And Backup Schedule - LOAD-SSC01-007 / BATT-SSC01-007 (Rev B)

Associated cabinet: CAB-SSC01-007. Owner event case: OPS-SSC01-007.

| Item | Value |
|---|---|
| Critical load | {state["critical_load"]:.0f} W |
| Battery capacity | {state["battery_capacity"]:.1f} kWh |
| Battery efficiency | {p["battery_efficiency"]:.2f} |
| BESS inverter capacity | {state["bess_inverter_capacity"]:.1f} kW |
| Claimed battery runtime | {state["battery_runtime"]:.3f} h |
| Claimed BESS power margin | {state["bess_power_margin"]:.3f} kW |
| Claimed BESS energy margin | {state["bess_energy_margin"]:.3f} kWh |

Package claim: LOAD-SSC01-007 and BATT-SSC01-007 clear the backup serviceability checks.
"""

    feeder_access = f"""# Feeder And Access Note - FEED-SSC01-007 (Rev A)

Associated cabinet: CAB-SSC01-007. Critical load source: LOAD-SSC01-007.

| Item | Value |
|---|---|
| Feeder length | {p["feeder_length_km"]:.2f} km |
| Conductor resistance | {p["conductor_resistance_ohm_km"]:.2f} ohm/km |
| Feeder voltage | {p["feeder_voltage_v"]:.0f} V |
| Power factor | {p["power_factor"]:.2f} |
| Claimed feeder current | {state["feeder_current"]:.3f} A |
| Claimed feeder voltage drop | {state["feeder_voltage_drop"]:.3f} % |
| Road lighting power | {p["road_lighting_power_w"]:.0f} W |
| Annual operating hours | {p["annual_operating_hours"]:.0f} h/y |
| Lit area | {p["lit_area_m2"]:.0f} m2 |
| Claimed road lighting AECI | {state["road_lighting_aeci"]:.3f} kWh/m2/y |
| Maintenance access route | service shoulder access remains open for the issue scenario |

Package claim: FEED-SSC01-007 clears feeder voltage drop and lighting energy checks for CAB-SSC01-007.
"""

    owner_criterion = f"""# Owner Serviceability Criterion - OPS-SSC01-007 (Rev A)

Owner criterion for issue of CAB-SSC01-007.

| Criterion | Value |
|---|---|
| Required cabinet | CAB-SSC01-007 |
| Required event case | 1% AEP flood plus design heat plus backup outage |
| Minimum cabinet freeboard | {p["minimum_freeboard_m"]:.2f} m |
| Thermal capacity rule | derated enclosure capacity must be greater than or equal to critical load |
| Required backup duration | {p["required_backup_h"]:.1f} h |
| Allowable voltage drop | {state["allowable_voltage_drop"]:.1f} % |
| Lighting AECI check | record AECI from FEED-SSC01-007 for operations review |
| Issue-readiness rule | no critical findings or unresolved critical information requests |
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-007 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Cabinet flood freeboard margin | must be greater than or equal to 0 m using CAB-SSC01-007 / HGL-SSC01-007 |
| Thermal margin | must be greater than or equal to 0 W using HEAT-SSC01-007 / LOAD-SSC01-007 |
| Battery runtime margin | must be greater than or equal to 0 h using LOAD-SSC01-007 / BATT-SSC01-007 |
| BESS power margin | must be greater than or equal to 0 kW using BATT-SSC01-007 |
| BESS energy margin | must be greater than or equal to 0 kWh using BATT-SSC01-007 |
| Feeder voltage-drop margin | must be greater than or equal to 0 percent using FEED-SSC01-007 |
| Road lighting AECI | must be recomputed and recorded from FEED-SSC01-007 |

## Assessment bases (source-owned methods)

- Controlling water level: the greater of HGL and inundation level.
- Cabinet freeboard: cabinet pad level minus controlling water level.
- Flood freeboard margin: cabinet freeboard minus minimum cabinet freeboard.
- Heat derating: reference capacity multiplied by the event-temperature derating factor from HEAT-SSC01-007.
- Thermal margin: thermal derated capacity minus critical load.
- Thermal utilization is a ratio, not a percent: critical load divided by thermal derated capacity.
- Battery runtime: kWh times efficiency divided by load kW.
- BESS energy margin: usable battery energy minus required load energy.
- Feeder voltage drop: 2 x length x resistance x current divided by voltage x 100.
- Road-lighting AECI: annual lighting energy divided by lit area.

## Review discipline

- Use the review matrix definitions to classify source conflicts, missing values, stale revisions, and copied cases.
- Evidence values must be recomputed from the source-owned methods above.
- Missing or unrecomputable evidence values should be requested from the source document that owns the missing field.
- RLR-08 checks whether the readiness decision reconciles with the review matrix, findings, information requests, and
  action register.
- Every finding, information request, and carried action should cite one exact RLR item.

## Review comments

{_comments_table(variant)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/cabinet-setout-elevation.md": cabinet_setout,
        "sources/flood-inundation-table.md": flood_table,
        "sources/enclosure-derating-note.md": enclosure_derating,
        "sources/critical-load-backup-schedule.md": load_backup,
        "sources/feeder-access-note.md": feeder_access,
        "sources/owner-serviceability-criterion.md": owner_criterion,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_enclosure_derating_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "HEAT-SSC01-007",
        "object_id": "HEAT-SSC01-007",
        "consequence": (
            "The enclosure derating note is Rev A while the document register identifies HEAT-SSC01-007 Rev B "
            "as the current issue basis."
        ),
        "action": "Replace the stale enclosure derating note with HEAT-SSC01-007 Rev B before issue.",
    },
    "cabinet_event_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "HGL-SSC01-007",
        "object_id": "CAB-SSC01-071",
        "consequence": "HGL-SSC01-007 is labelled for CAB-SSC01-071 while the issue package is CAB-SSC01-007.",
        "action": "Reconcile the HGL cabinet membership with CAB-SSC01-007 before issue.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "CAB-SSC01-007",
        "object_id": "CAB-SSC01-007",
        "consequence": "The cabinet setout table is copied from cabinet serviceability case CAB-SSC01-099.",
        "action": "Reissue CAB-SSC01-007 and OPS-SSC01-007 with the current flood, heat, and outage case.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-007",
        "object_id": "C-04",
        "consequence": "Critical cabinet thermal serviceability comment C-04 remains open without owner or action.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "thermal_capacity_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "HEAT-SSC01-007",
        "object_id": "CAB-SSC01-007",
        "consequence": "Recomputed thermal derated capacity is below the critical cabinet load.",
        "action": "Reduce critical load, increase enclosure thermal capacity, or revise heat mitigation before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    evidence_notes = {
        "RLR-01": "All eight source files are present with document IDs and revisions.",
        "RLR-02": (
            "CAB-SSC01-007, HGL-SSC01-007, HEAT-SSC01-007, LOAD-SSC01-007, BATT-SSC01-007, "
            "FEED-SSC01-007, OPS-SSC01-007, MEMO-SSC01-007, and CRIT-SSC01-007 reconcile."
        ),
        "RLR-03": "Flood freeboard, heat derating, backup runtime, and feeder voltage-drop basis are current.",
        "RLR-04": "Flood freeboard and thermal derated capacity clear the cabinet serviceability criteria.",
        "RLR-05": "The flood, heat, and outage event case is CAB-SSC01-007 under OPS-SSC01-007.",
        "RLR-06": "Backup energy, BESS power, feeder voltage drop, access, and lighting AECI are source-backed.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the review matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_derating_rate":
        evidence_notes["RLR-04"] = (
            "HEAT-SSC01-007 has pending heat derating rate confirmation, so thermal margin cannot be computed."
        )

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "cabinet_freeboard_m",
            "flood_freeboard_margin_m",
            "thermal_derated_capacity_w",
            "thermal_margin_w",
            "thermal_utilization",
            "battery_runtime_h",
            "battery_margin_h",
            "bess_power_margin_kw",
            "bess_energy_margin_kwh",
            "feeder_voltage_drop_percent",
            "voltage_drop_margin_percent",
            "road_lighting_aeci_kwh_m2_y",
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
    if variant == "missing_derating_rate":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Missing heat derating rate for HEAT-SSC01-007",
                "source_id": "HEAT-SSC01-007",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the cabinet maintenance access label for comment C-05.",
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
            "cabinet": "CAB-SSC01-007",
            "flood_hgl_table": "HGL-SSC01-007",
            "heat_derating_note": "HEAT-SSC01-007",
            "critical_load_schedule": "LOAD-SSC01-007",
            "backup_energy_schedule": "BATT-SSC01-007",
            "feeder_access_note": "FEED-SSC01-007",
            "serviceability_scenario": "OPS-SSC01-007",
            "criteria_memo": "MEMO-SSC01-007 / CRIT-SSC01-007",
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
        "## Issue-Readiness Review - CAB-SSC01-007 roadside cabinet serviceability package\n\n"
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
        "The roadside cabinet serviceability package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
