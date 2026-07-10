# ABOUTME: Engine for the SSC-01 corridor comment-response issue review package.
# ABOUTME: Derives packet state, variant gold review statuses, source-pack files, and golden fixtures.

from __future__ import annotations

import json
import math

_FT_TO_M = 0.3048

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
    "original_chainage_m": 0.5,
    "chainage_delta_m": 0.5,
    "revised_hgl_m": 0.005,
    "minimum_hgl_clearance_mm": 5.0,
    "hgl_clearance_margin_mm": 5.0,
    "pedestrian_startup_time_s": 0.1,
    "revised_crossing_width_m": 0.5,
    "pedestrian_walk_speed_m_s": 0.05,
    "ped_clearance_margin_s": 0.1,
    "approach_speed_kmh": 0.5,
    "reading_rate_chars_s": 0.1,
    "vms_message_margin_chars": 0.5,
    "revised_device_load_w": 25.0,
    "feeder_length_km": 0.01,
    "conductor_resistance_ohm_km": 0.02,
    "power_factor": 0.01,
    "voltage_drop_margin_percent": 0.1,
    "voltage_drop_deficit_percent": 0.1,
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
    quantized["vms_character_height_in"] = float(params["vms_character_height_in"])
    quantized["feeder_voltage_v"] = float(params["feeder_voltage_v"])
    quantized["review_comments_total"] = int(params["review_comments_total"])
    quantized["impacted_calculation_count"] = int(params["impacted_calculation_count"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _chainage_label(value: float) -> str:
    """Format corridor chainage as CH k+mmm.m for rendered sources."""
    kilometre = int(value // 1000.0)
    remainder = value - kilometre * 1000.0
    return f"CH {kilometre}+{remainder:05.1f}"


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    original_chainage = p["original_chainage_m"]
    revised_chainage = _q(original_chainage + p["chainage_delta_m"], 0.5)
    changed_chainage_delta = revised_chainage - original_chainage

    hgl_clearance = p["minimum_hgl_clearance_mm"] + p["hgl_clearance_margin_mm"]
    revised_road_level = _q(p["revised_hgl_m"] + hgl_clearance / 1000.0, 0.005)
    hgl_clearance = (revised_road_level - p["revised_hgl_m"]) * 1000.0
    hgl_clearance_margin = hgl_clearance - p["minimum_hgl_clearance_mm"]

    ped_required = p["pedestrian_startup_time_s"] + p["revised_crossing_width_m"] / p["pedestrian_walk_speed_m_s"]
    available_ped_clearance = _q(ped_required + p["ped_clearance_margin_s"], 0.1)
    ped_margin = available_ped_clearance - ped_required

    vms_reading_time = p["vms_character_height_in"] * 40.0 * _FT_TO_M / (p["approach_speed_kmh"] / 3.6)
    readable_chars = vms_reading_time * p["reading_rate_chars_s"]
    revised_message_length = max(12.0, _floor_to(readable_chars - p["vms_message_margin_chars"], 1.0))
    vms_message_margin = readable_chars - revised_message_length

    feeder_current = p["revised_device_load_w"] / (p["feeder_voltage_v"] * p["power_factor"])
    voltage_drop = (
        2.0 * p["feeder_length_km"] * p["conductor_resistance_ohm_km"] * feeder_current / p["feeder_voltage_v"] * 100.0
    )
    if variant == "unsupported_downstream_repair":
        allowable_voltage_drop = _floor_to(max(0.0, voltage_drop - p["voltage_drop_deficit_percent"]), 0.1)
    else:
        allowable_voltage_drop = _ceil_to(voltage_drop + p["voltage_drop_margin_percent"], 0.1)
    voltage_margin = allowable_voltage_drop - voltage_drop

    closed_comments = p["review_comments_total"]
    if variant in {"open_critical_comment", "minor_open_comment_carried"}:
        closed_comments -= 1
    comment_closeout = closed_comments / p["review_comments_total"] * 100.0

    copied_speed = _q(max(25.0, p["approach_speed_kmh"] - 10.0), 0.5)
    copied_reading_time = p["vms_character_height_in"] * 40.0 * _FT_TO_M / (copied_speed / 3.6)

    return {
        "params": p,
        "variant": variant,
        "original_chainage": original_chainage,
        "revised_chainage": revised_chainage,
        "changed_chainage_delta": changed_chainage_delta,
        "mismatch_chainage": _q(revised_chainage + 8.0, 0.5),
        "revised_road_level": revised_road_level,
        "hgl_clearance": hgl_clearance,
        "hgl_clearance_margin": hgl_clearance_margin,
        "ped_required": ped_required,
        "available_ped_clearance": available_ped_clearance,
        "ped_margin": ped_margin,
        "vms_reading_time": vms_reading_time,
        "readable_chars": readable_chars,
        "revised_message_length": revised_message_length,
        "vms_message_margin": vms_message_margin,
        "feeder_current": feeder_current,
        "voltage_drop": voltage_drop,
        "allowable_voltage_drop": allowable_voltage_drop,
        "voltage_margin": voltage_margin,
        "review_comments_closed": closed_comments,
        "comment_closeout": comment_closeout,
        "copied_speed": copied_speed,
        "copied_reading_time": copied_reading_time,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_revised_chainage": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_change_register_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "chainage_identity_mismatch": {
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
    "unsupported_downstream_repair": {
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

    if state["variant"] != "missing_revised_chainage":
        result["changed_chainage_delta_m"] = state["changed_chainage_delta"]
    result["hgl_clearance_mm"] = state["hgl_clearance"]
    result["hgl_clearance_margin_mm"] = state["hgl_clearance_margin"]
    result["ped_clearance_required_s"] = state["ped_required"]
    result["ped_clearance_margin_s"] = state["ped_margin"]
    result["vms_reading_time_s"] = state["vms_reading_time"]
    result["vms_message_margin_chars"] = state["vms_message_margin"]
    result["feeder_voltage_drop_percent"] = state["voltage_drop"]
    result["voltage_drop_margin_percent"] = state["voltage_margin"]
    result["comment_closeout_percent"] = state["comment_closeout"]
    result["impacted_calculation_count"] = float(state["params"]["impacted_calculation_count"])
    return result


def _register_rows(_variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("CMT-SSC01-008", "Comment register and change ledger", "Rev C", "Issued for review"),
        ("MARKUP-SSC01-008", "Marked-up plan and corridor long section", "Rev C", "Issued for review"),
        ("DRAIN-SSC01-008", "Drainage HGL recalculation for DRN-08", "Rev B", "Issued for review"),
        ("SIG-SSC01-008", "Signal and pedestrian recalculation for SG-08", "Rev B", "Issued for review"),
        ("VMS-SSC01-008", "VMS operations and message legibility note", "Rev A", "Issued for review"),
        ("FEED-SSC01-008", "ITS field feeder voltage-drop check", "Rev A", "Issued for review"),
        ("CRIT-SSC01-008", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the source packet for one corridor comment-response review instance."""
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
        "# Document Register - DOC-REG-SSC01-08\n\n"
        "Issue package: corridor comment-response package for RD-SSC01-001 and comment C-008.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll chainages are corridor chainages and all levels are AHD unless a source states otherwise.\n"
    )

    comment_rev = "Rev B" if variant == "stale_change_register_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_change_register_revision":
        stale_note = (
            "\nRevision note: this comment register still cites CMT-BASIS-2025-01. "
            "The document register lists Rev C current change basis CMT-BASIS-2025-04.\n"
        )

    comments = [
        ("C-001", "Civil", "Confirm drainage long-section update at C-008.", "Closed", "minor", "", ""),
        (
            "C-002",
            "Signals",
            "Confirm SG-08 pedestrian timing follows the revised crossing width.",
            "Closed",
            "minor",
            "",
            "",
        ),
        ("C-003", "ITS", "Confirm VMS-08 message legibility after speed-case update.", "Closed", "minor", "", ""),
        ("C-004", "Electrical", "Confirm FEED-08 voltage drop after added ITS load.", "Closed", "minor", "", ""),
    ]
    while len(comments) < p["review_comments_total"]:
        next_id = f"C-{len(comments) + 1:03d}"
        comments.append(
            (next_id, "Road", "Close editorial cross-reference in the response table.", "Closed", "minor", "", "")
        )
    if variant == "open_critical_comment":
        comments[-1] = (
            comments[-1][0],
            "Authority",
            "Resolve downstream feeder adequacy before issue.",
            "Open",
            "critical",
            "",
            "",
        )
    if variant == "minor_open_comment_carried":
        comments[-1] = (
            comments[-1][0],
            "Documentation",
            "Update C-008 leader text on the marked-up plan.",
            "Open",
            "minor",
            "Road design lead",
            "Carry leader-text update to the next issue.",
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, discipline, text, status, criticality, owner, action in comments:
        comment_lines.append(f"| {cid} | {discipline} | {text} | {status} | {criticality} | {owner} | {action} |")

    closure_sources = {
        "C-001": "Closed by DRAIN-SSC01-008 Rev B HGL recalculation at the revised C-008 chainage.",
        "C-002": "Closed by SIG-SSC01-008 Rev B pedestrian timing recalculation at the revised C-008 chainage.",
        "C-003": "Closed by VMS-SSC01-008 Rev A message legibility note for VMS-08.",
        "C-004": "Closed by FEED-SSC01-008 Rev A voltage-drop check for FEED-08.",
    }
    closure_lines = [
        "| ID | Closure evidence |",
        "|---|---|",
    ]
    for cid, _discipline, _text, status, _criticality, owner, action in comments:
        if status == "Closed":
            evidence = closure_sources.get(cid, "Closed by response-table update in CMT-SSC01-008 Rev C.")
        elif owner and action:
            evidence = f"Carried by {owner}: {action}"
        else:
            evidence = "No closure evidence, owner, or agreed action recorded."
        closure_lines.append(f"| {cid} | {evidence} |")

    comment_register = f"""# Comment Register - CMT-SSC01-008 ({comment_rev})

Response package: RD-SSC01-001 comment C-008, scenario CASE-08.
{stale_note}
## Change ledger

| Item | Value |
|---|---|
| Review comments total | {p["review_comments_total"]} |
| Review comments closed | {s["review_comments_closed"]} |
| Impacted calculation count | {p["impacted_calculation_count"]} |
| Changed road chainage object | C-008 |
| Impacted objects | DRN-08, SG-08, VMS-08, FEED-08 |

## Review comments

{chr(10).join(comment_lines)}

## Closure evidence

{chr(10).join(closure_lines)}
"""

    original_label = _chainage_label(s["original_chainage"])
    revised_label = _chainage_label(s["revised_chainage"])
    if variant == "missing_revised_chainage":
        revised_chainage_line = "| Revised comment chainage | pending survey/control confirmation |"
    else:
        revised_chainage_line = f"| Revised comment chainage | {revised_label} |"
    marked_up_plan = f"""# Marked-Up Plan And Long Section - MARKUP-SSC01-008 (Rev C)

Corridor: RD-SSC01-001. Comment: C-008. Datum: AHD. Scenario: CASE-08.

| Item | Value |
|---|---|
| Original comment chainage | {original_label} |
{revised_chainage_line}
| Road object | RD-SSC01-001 |
| Drainage object | DRN-08 |
| Signal group | SG-08 |
| VMS device | VMS-08 |
| Field feeder | FEED-08 |
| CASE-08 approach speed | {p["approach_speed_kmh"]:.1f} km/h |
| Datum | AHD |
"""

    drainage_chainage = s["mismatch_chainage"] if variant == "chainage_identity_mismatch" else s["revised_chainage"]
    drainage_note = "Drainage recalc uses the revised C-008 chainage from MARKUP-SSC01-008."
    if variant == "chainage_identity_mismatch":
        drainage_note = (
            "Drainage recalc references a different C-008 chainage than MARKUP-SSC01-008; identity needs resolution."
        )
    drainage_recalc = f"""# Drainage HGL Recalculation - DRAIN-SSC01-008 (Rev B)

Drainage object: DRN-08 on RD-SSC01-001 at {_chainage_label(drainage_chainage)}. Datum: AHD. {drainage_note}

| Item | Value |
|---|---|
| Revised road level | {s["revised_road_level"]:.3f} m AHD |
| Revised hydraulic grade line | {p["revised_hgl_m"]:.3f} m AHD |
| Minimum HGL clearance | {p["minimum_hgl_clearance_mm"]:.1f} mm |
| Claimed HGL clearance | {s["hgl_clearance"]:.2f} mm |
"""

    if variant == "missing_revised_chainage":
        signal_trace = (
            "Propagation trace: SIG-08 uses the revised crossing width, but the revised C-008 chainage is "
            "pending in MARKUP-SSC01-008."
        )
        vms_trace = (
            "Propagation trace: VMS-08 uses CASE-08, but the revised C-008 chainage is pending in MARKUP-SSC01-008."
        )
        feeder_trace = (
            "Propagation trace: FEED-08 covers the affected device set, but the revised C-008 chainage is "
            "pending in MARKUP-SSC01-008."
        )
    else:
        signal_trace = (
            f"Propagation trace: SIG-08 pedestrian recalculation applies at revised C-008 chainage "
            f"{revised_label} from MARKUP-SSC01-008."
        )
        vms_trace = (
            f"Propagation trace: VMS-08 legibility check applies at revised C-008 chainage "
            f"{revised_label} from MARKUP-SSC01-008."
        )
        feeder_trace = (
            f"Propagation trace: FEED-08 serves the affected DRN-08, SG-08, and VMS-08 device set at revised "
            f"C-008 chainage {revised_label} from MARKUP-SSC01-008."
        )

    signal_pedestrian_recalc = f"""# Signal And Pedestrian Recalculation - SIG-SSC01-008 (Rev B)

Signal group: SG-08. Corridor: RD-SSC01-001. Comment: C-008. Scenario: CASE-08.
{signal_trace}

| Item | Value |
|---|---|
| Pedestrian startup allowance | {p["pedestrian_startup_time_s"]:.1f} s |
| Revised crossing width | {p["revised_crossing_width_m"]:.1f} m |
| Pedestrian walk speed | {p["pedestrian_walk_speed_m_s"]:.2f} m/s |
| Available pedestrian clearance | {s["available_ped_clearance"]:.1f} s |
| Claimed pedestrian clearance margin | {s["ped_margin"]:.2f} s |
"""

    if variant == "scenario_copy_forward":
        speed_line = (
            f"| Assessment speed | {s['copied_speed']:.1f} km/h (copied from corridor RD-SSC01-099 closure case) |"
        )
        claimed_reading_time = s["copied_reading_time"]
    else:
        speed_line = f"| Approach speed | {p['approach_speed_kmh']:.1f} km/h |"
        claimed_reading_time = s["vms_reading_time"]
    vms_operations = f"""# VMS Operations Note - VMS-SSC01-008 (Rev A)

VMS device: VMS-08. Corridor: RD-SSC01-001. Scenario: CASE-08.
{vms_trace}

| Item | Value |
|---|---|
| VMS character height | {p["vms_character_height_in"]:.1f} in |
{speed_line}
| Reading rate | {p["reading_rate_chars_s"]:.1f} chars/s |
| Revised message length | {s["revised_message_length"]:.0f} chars |
| Claimed reading time | {claimed_reading_time:.2f} s |
"""

    claim_note = "Package claim: voltage drop is adequate using the revised device load."
    if variant == "unsupported_downstream_repair":
        claim_note = (
            "Package claim: voltage drop is adequate, but the note still references the previous ITS load "
            "instead of the revised connected device load below."
        )
    total_load = round(float(p["revised_device_load_w"]), 1)
    drainage_load = round(total_load * 0.18, 1)
    signal_load = round(total_load * 0.22, 1)
    vms_load = round(total_load - drainage_load - signal_load, 1)
    electrical_feeder = f"""# Electrical Feeder Check - FEED-SSC01-008 (Rev A)

Field feeder: FEED-08 serving DRN-08 telemetry, SG-08 interface, and VMS-08. Scenario: CASE-08.
{feeder_trace}
{claim_note}

| Item | Value |
|---|---|
| Revised connected device load | {p["revised_device_load_w"]:.1f} W |
| Feeder length | {p["feeder_length_km"]:.2f} km |
| Conductor resistance | {p["conductor_resistance_ohm_km"]:.2f} ohm/km |
| Feeder voltage | {p["feeder_voltage_v"]:.1f} V |
| Power factor | {p["power_factor"]:.2f} |
| Allowable voltage drop | {s["allowable_voltage_drop"]:.1f} % |
| Claimed voltage-drop margin | {s["voltage_margin"]:.2f} % |

## Load breakdown

| Device | Connected load |
|---|---|
| DRN-08 telemetry | {drainage_load:.1f} W |
| SG-08 interface | {signal_load:.1f} W |
| VMS-08 | {vms_load:.1f} W |
| Total revised connected device load | {total_load:.1f} W |
"""

    criteria_comments = """# Criteria Memo And Review Comments - CRIT-SSC01-008 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Chainage propagation | revised C-008 chainage must be traceable from markup into every affected calculation |
| HGL clearance | revised road level minus revised HGL must be greater than or equal to the minimum HGL clearance |
| Pedestrian clearance | available pedestrian clearance must be greater than or equal to required pedestrian clearance |
| VMS legibility | readable character capacity must be greater than or equal to revised message length |
| Feeder voltage drop | computed voltage drop must be less than or equal to allowable voltage drop |
| Comment closure | critical comments must be closed before issue; minor comments may be carried with owner and action |

## Assessment bases (source-owned methods)

- Changed chainage delta: revised comment chainage minus original comment chainage.
- HGL clearance: (revised road level - revised HGL) x 1000.
- Pedestrian clearance: required = startup time + revised crossing width / pedestrian walk speed.
- VMS reading time: character height in inches x 40 ft x 0.3048 / approach speed in m/s.
- VMS message margin: reading time x reading rate minus revised message length.
- Feeder current: revised connected device load / (feeder voltage x power factor).
- Feeder voltage drop percent: 2 x feeder length x conductor resistance x feeder current / feeder voltage x 100.
- Comment closeout percent: closed review comments / total review comments x 100.

## Review discipline

Apply the most specific review item for each defect using the review matrix definitions and the source evidence.
Copied scenario notes should be reviewed against the same matrix definitions and checked for independent effects
in adjacent source documents. RLR-08 is reviewer self-consistency, not package claim consistency.

Do not include missing or unrecomputable evidence keys with null, zero, or placeholder values. Missing or
unrecomputable source values should be requested from the source document that owns the missing field. Findings,
information requests, and linked actions should each reference one exact single RLR item, not a combined item list.

## Review note

Treat the packet as task-owned synthetic evidence. Do not claim authority approval, accepted project evidence,
or benchmark readiness.
"""

    return {
        "sources/document-register.md": document_register,
        "sources/comment-register.md": comment_register,
        "sources/marked-up-plan.md": marked_up_plan,
        "sources/drainage-recalc.md": drainage_recalc,
        "sources/signal-pedestrian-recalc.md": signal_pedestrian_recalc,
        "sources/vms-operations-note.md": vms_operations,
        "sources/electrical-feeder-check.md": electrical_feeder,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_change_register_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "CMT-SSC01-008",
        "object_id": "C-008",
        "consequence": (
            "The comment register is Rev B and cites superseded change basis CMT-BASIS-2025-01, "
            "while the document register lists Rev C as current."
        ),
        "action": "Reissue CMT-SSC01-008 at Rev C using CMT-BASIS-2025-04 before issue.",
    },
    "chainage_identity_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "DRAIN-SSC01-008",
        "object_id": "DRN-08",
        "consequence": (
            "DRAIN-SSC01-008 references a different C-008 chainage than the marked-up plan, "
            "so the drainage recalc cannot be tied cleanly to the comment response."
        ),
        "action": "Resolve the C-008 chainage across MARKUP-SSC01-008 and DRAIN-SSC01-008 before issue.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "VMS-SSC01-008",
        "object_id": "CASE-08",
        "consequence": (
            "The VMS operations note uses an assessment speed copied from RD-SSC01-099 instead of CASE-08, "
            "so the legibility check is not traceable to this corridor scenario."
        ),
        "action": "Recalculate VMS-08 reading time using the CASE-08 approach speed and record the scenario basis.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CMT-SSC01-008",
        "object_id": "C-008",
        "consequence": "A critical authority comment on FEED-08 downstream adequacy is open with no owner or action.",
        "action": "Assign an owner and close the critical C-008 comment before issue.",
    },
    "unsupported_downstream_repair": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "FEED-SSC01-008",
        "object_id": "FEED-08",
        "consequence": (
            "Recomputed FEED-08 voltage drop exceeds the allowable drop for the revised connected device load."
        ),
        "action": "Revise the feeder design or reduce the connected load before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All seven register documents are present with IDs and revisions (DOC-REG-SSC01-08).",
        "RLR-02": "RD-SSC01-001, C-008, DRN-08, SG-08, VMS-08, FEED-08, CASE-08, chainage, and AHD reconcile.",
        "RLR-03": (
            "Change ledger, impacted calculation count, and recalculation bases are traceable to current sources."
        ),
        "RLR-04": "The changed chainage propagates through HGL, pedestrian, VMS, feeder, and closeout checks.",
        "RLR-05": "Scenario CASE-08 is used across the signal, VMS, drainage, and feeder records.",
        "RLR-06": "FEED-08 and VMS-08 checks are source-backed and internally consistent with the revised device set.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_revised_chainage":
        evidence_notes["RLR-04"] = (
            "The revised C-008 chainage is pending survey/control confirmation, so propagation cannot be assessed."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    evidence_keys = (
        "changed_chainage_delta_m",
        "hgl_clearance_mm",
        "hgl_clearance_margin_mm",
        "ped_clearance_required_s",
        "ped_clearance_margin_s",
        "vms_reading_time_s",
        "vms_message_margin_chars",
        "feeder_voltage_drop_percent",
        "voltage_drop_margin_percent",
        "comment_closeout_percent",
        "impacted_calculation_count",
    )
    computed_evidence = {key: ground_truth[key] for key in evidence_keys if key in ground_truth}

    findings = []
    actions = []
    if variant in _VARIANT_FINDINGS:
        finding = dict(_VARIANT_FINDINGS[variant])
        findings.append(finding)
        actions.append({"action": finding["action"], "owner": "Design lead", "linked_item": finding["item"]})

    information_requests = []
    if variant == "missing_revised_chainage":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Revised C-008 chainage in MARKUP-SSC01-008",
                "source_id": "MARKUP-SSC01-008",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update C-008 leader text on MARKUP-SSC01-008.",
                "owner": "Road design lead",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "corridor": "RD-SSC01-001",
            "comment": "C-008",
            "original_chainage": _chainage_label(state["original_chainage"]),
            "revised_chainage": _chainage_label(state["revised_chainage"]),
            "datum": "AHD",
            "scenario": "CASE-08",
            "drainage_object": "DRN-08",
            "signal_group": "SG-08",
            "vms_device": "VMS-08",
            "field_feeder": "FEED-08",
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
        "## Issue-Readiness Review - RD-SSC01-001 corridor comment-response package\n\n"
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
        "The corridor comment-response package has been reviewed and is approved for issue. The design is "
        "fully compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
