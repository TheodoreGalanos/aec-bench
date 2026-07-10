# ABOUTME: Engine for the SSC-01 review-first intersection signal safety issue review package.
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
    "approach_speed_kmh": 0.5,
    "approach_grade_pct": 0.1,
    "reaction_time_s": 0.1,
    "braking_friction_coefficient": 0.01,
    "sight_distance_margin_m": 0.5,
    "yellow_reaction_time_s": 0.1,
    "yellow_deceleration_m_s2": 0.1,
    "intersection_width_m": 0.5,
    "all_red_speed_kmh": 0.5,
    "pedestrian_startup_time_s": 0.1,
    "crossing_width_m": 0.5,
    "pedestrian_walk_speed_m_s": 0.05,
    "pedestrian_clearance_margin_s": 0.1,
    "pedestrian_clearance_deficit_s": 0.1,
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
    quantized["design_vehicle_length_m"] = float(params["design_vehicle_length_m"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _signal_metrics(p: dict, speed_kmh: float) -> tuple[float, float]:
    speed_m_s = speed_kmh / 3.6
    grade_fraction = p["approach_grade_pct"] / 100.0
    yellow_denominator = 2.0 * p["yellow_deceleration_m_s2"] + 2.0 * _G * grade_fraction
    if yellow_denominator <= 0.0:
        msg = "yellow interval denominator must be positive"
        raise ValueError(msg)
    yellow = p["yellow_reaction_time_s"] + speed_m_s / yellow_denominator
    all_red = (p["intersection_width_m"] + p["design_vehicle_length_m"]) / (p["all_red_speed_kmh"] / 3.6)
    return yellow, all_red


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    speed_m_s = p["approach_speed_kmh"] / 3.6
    grade_fraction = p["approach_grade_pct"] / 100.0
    braking_denominator = 2.0 * _G * (p["braking_friction_coefficient"] + grade_fraction)
    if braking_denominator <= 0.0:
        msg = "braking denominator must be positive"
        raise ValueError(msg)

    braking_distance = speed_m_s**2 / braking_denominator
    stopping_distance = speed_m_s * p["reaction_time_s"] + braking_distance
    available_sight = _ceil_to(stopping_distance + p["sight_distance_margin_m"], 0.5)
    sight_margin = available_sight - stopping_distance

    yellow_interval, all_red_interval = _signal_metrics(p, p["approach_speed_kmh"])
    copied_speed = p["approach_speed_kmh"] + 15.0
    claimed_yellow_interval, claimed_all_red_interval = _signal_metrics(p, copied_speed)

    ped_required = p["pedestrian_startup_time_s"] + p["crossing_width_m"] / p["pedestrian_walk_speed_m_s"]
    if variant == "pedestrian_clearance_deficient":
        ped_available = _q(ped_required - p["pedestrian_clearance_deficit_s"], 0.1)
    else:
        ped_available = _q(ped_required + p["pedestrian_clearance_margin_s"], 0.1)
    ped_margin = ped_available - ped_required

    return {
        "params": p,
        "variant": variant,
        "speed_m_s": speed_m_s,
        "grade_fraction": grade_fraction,
        "braking_distance": braking_distance,
        "stopping_distance": stopping_distance,
        "available_sight": available_sight,
        "sight_margin": sight_margin,
        "yellow_interval": yellow_interval,
        "all_red_interval": all_red_interval,
        "copied_speed": copied_speed,
        "claimed_yellow_interval": claimed_yellow_interval,
        "claimed_all_red_interval": claimed_all_red_interval,
        "ped_required": ped_required,
        "ped_available": ped_available,
        "ped_margin": ped_margin,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_pedestrian_clearance": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_timing_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "approach_datum_mismatch": {
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
    "pedestrian_clearance_deficient": {
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

    result["stopping_distance_m"] = state["stopping_distance"]
    result["sight_distance_margin_m"] = state["sight_margin"]
    result["yellow_interval_s"] = state["yellow_interval"]
    result["all_red_interval_s"] = state["all_red_interval"]
    result["ped_clearance_required_s"] = state["ped_required"]
    if state["variant"] != "missing_pedestrian_clearance":
        result["ped_clearance_margin_s"] = state["ped_margin"]
    result["grade_adjusted_braking_distance_m"] = state["braking_distance"]
    return result


def _register_rows(_variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("INT-SSC01-002", "Intersection layout and approach identity", "Rev B", "Issued for review"),
        ("PROF-SSC01-002", "Northbound approach profile and speed basis", "Rev B", "Issued for review"),
        ("SIG-SSC01-002", "Signal timing sheet for SG-02", "Rev C", "Issued for review"),
        ("PED-SSC01-002", "Pedestrian crossing geometry and walking basis", "Rev A", "Issued for review"),
        ("SIGHT-SSC01-002", "Sight-distance obstruction note", "Rev A", "Issued for review"),
        ("CTRL-SSC01-002", "Controller timing handoff note", "Rev A", "Issued for review"),
        ("CRIT-SSC01-002", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the source packet for one intersection review instance."""
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
        "# Document Register - DOC-REG-SSC01-02\n\n"
        "Issue package: intersection signal safety package for INT-02, approach APP-NB-02.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll chainages are corridor chainages and all levels are AHD unless a source states otherwise.\n"
    )

    intersection_layout = """# Intersection Layout - INT-SSC01-002 (Rev B)

Intersection: INT-02, corridor RD-SSC01-001, northbound approach APP-NB-02.

| Item | Value |
|---|---|
| Intersection chainage | CH 0+480 |
| Approach under review | APP-NB-02 |
| Signal group | SG-02 |
| Pedestrian crossing | PED-X-02 |
| Signal controller | CTRL-02 |
| Timing case | CASE-AM-02 |
| Datum | AHD |

The package review scope is the APP-NB-02 approach, SG-02 signal group, and PED-X-02 pedestrian crossing.
"""

    datum_note = "Profile levels and chainages are on the AHD/corridor chainage basis."
    if variant == "approach_datum_mismatch":
        datum_note = (
            "Profile levels are on site datum (site datum = AHD + 0.250 m).\n"
            "Footer note: all approach profiles in this sheet are AHD."
        )

    approach_profile = f"""# Approach Profile - PROF-SSC01-002 (Rev B)

Approach: APP-NB-02 at INT-02, measured at CH 0+480. {datum_note}

| Item | Value |
|---|---|
| Approach design speed | {p["approach_speed_kmh"]:.1f} km/h |
| Signed approach grade | {p["approach_grade_pct"]:.1f} % |
| Reaction time | {p["reaction_time_s"]:.1f} s |
| Braking friction coefficient | {p["braking_friction_coefficient"]:.2f} |
"""

    signal_rev_header = "Rev B" if variant == "stale_timing_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_timing_revision":
        stale_note = (
            "\nRevision note: this timing sheet still cites SIG-BASIS-2024-04. "
            "The document register lists Rev C current timing basis SIG-BASIS-2025-02.\n"
        )

    if variant == "scenario_copy_forward":
        speed_basis = (
            f"| Assessment speed | {s['copied_speed']:.1f} km/h (copied from corridor eastbound approach APP-EB-99) |"
        )
        claimed_yellow = s["claimed_yellow_interval"]
        claimed_all_red = s["claimed_all_red_interval"]
    else:
        speed_basis = f"| Assessment speed | {p['approach_speed_kmh']:.1f} km/h (APP-NB-02 design speed) |"
        claimed_yellow = s["yellow_interval"]
        claimed_all_red = s["all_red_interval"]

    if variant == "missing_pedestrian_clearance":
        available_clearance_line = "| Available pedestrian clearance | pending controller export |"
        claimed_margin_line = "| Claimed pedestrian clearance margin | to be confirmed after controller export |"
    else:
        verdict = "adequate" if s["ped_margin"] >= 0.0 else "package marks adequate; reviewer to verify"
        available_clearance_line = f"| Available pedestrian clearance | {s['ped_available']:.1f} s |"
        claimed_margin_line = f"| Claimed pedestrian clearance margin | {s['ped_margin']:.2f} s - {verdict} |"

    signal_timing = f"""# Signal Timing Sheet - SIG-SSC01-002 ({signal_rev_header})

Timing case: CASE-AM-02, controller CTRL-02, signal group SG-02.
{stale_note}
| Item | Value |
|---|---|
{speed_basis}
| Yellow perception-reaction term | {p["yellow_reaction_time_s"]:.1f} s |
| Yellow deceleration rate | {p["yellow_deceleration_m_s2"]:.1f} m/s2 |
| Intersection width | {p["intersection_width_m"]:.1f} m |
| Design vehicle length | {p["design_vehicle_length_m"]:.1f} m |
| All-red clearance speed | {p["all_red_speed_kmh"]:.1f} km/h |
| Claimed yellow interval | {claimed_yellow:.2f} s |
| Claimed all-red interval | {claimed_all_red:.2f} s |
{available_clearance_line}
{claimed_margin_line}
"""

    pedestrian_crossing = f"""# Pedestrian Crossing - PED-SSC01-002 (Rev A)

Crossing: PED-X-02 across the APP-NB-02 approach at INT-02.

| Item | Value |
|---|---|
| Pedestrian startup allowance | {p["pedestrian_startup_time_s"]:.1f} s |
| Crossing width | {p["crossing_width_m"]:.1f} m |
| Pedestrian walk speed | {p["pedestrian_walk_speed_m_s"]:.2f} m/s |
"""

    sight_distance = f"""# Sight-Distance Note - SIGHT-SSC01-002 (Rev A)

Sight-distance case: SIGHT-APP-NB-02 for approach APP-NB-02 at INT-02.

| Item | Value |
|---|---|
| Available sight distance | {s["available_sight"]:.1f} m |
| Obstruction case | parked-service-vehicle clear zone retained |
| Sight-distance datum | AHD |
"""

    controller_handoff = """# Controller Handoff - CTRL-SSC01-002 (Rev A)

Controller: CTRL-02, timeplan TP-AM-02, timing case CASE-AM-02.

| Item | Value |
|---|---|
| Controller export | SG-02 / TP-AM-02 |
| Timing case source | CASE-AM-02 |
| Signal group under review | SG-02 |
| Pedestrian crossing under review | PED-X-02 |
| Approach under review | APP-NB-02 |
"""

    comments = [
        ("C-01", "Traffic", "Confirm yellow interval basis for APP-NB-02.", "Closed", "minor", "", ""),
        ("C-02", "Civil", "Confirm sight obstruction note covers the APP-NB-02 case.", "Closed", "minor", "", ""),
        ("C-03", "Signals", "Confirm SG-02 controller export matches CASE-AM-02.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Authority",
                "Verify pedestrian clearance for PED-X-02 before issue.",
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
                "Update the SG-02 callout leader on the intersection layout.",
                "Open",
                "minor",
                "Signals designer",
                "Carry layout leader update to next issue.",
            )
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, disc, text, status, crit, owner, action in comments:
        comment_lines.append(f"| {cid} | {disc} | {text} | {status} | {crit} | {owner} | {action} |")

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-002 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Available sight distance | must be greater than or equal to stopping distance |
| Available pedestrian clearance | must be greater than or equal to required pedestrian clearance |
| Yellow interval | must be calculated from APP-NB-02 approach speed and grade |
| All-red interval | must be calculated from intersection width, design vehicle length, and clearance speed |

## Assessment bases (source-owned methods)

- Stopping distance: d = v x reaction time + v^2 / (2g(f + G)), where v is APP-NB-02 speed in m/s and G is signed grade.
- Yellow interval: y = reaction term + v / (2a + 2gG), using APP-NB-02 approach speed, grade, and deceleration a.
- All-red interval: r = (intersection width + design vehicle length) / clearance speed.
- Pedestrian clearance: required = startup time + crossing width / pedestrian walk speed.
- Sight-distance margin: available sight distance minus stopping distance.

## Review comments

{chr(10).join(comment_lines)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/intersection-layout.md": intersection_layout,
        "sources/approach-profile.md": approach_profile,
        "sources/signal-timing-sheet.md": signal_timing,
        "sources/pedestrian-crossing.md": pedestrian_crossing,
        "sources/sight-distance-note.md": sight_distance,
        "sources/controller-handoff.md": controller_handoff,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_timing_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "SIG-SSC01-002",
        "object_id": "SG-02",
        "consequence": (
            "The signal timing sheet is Rev B and cites superseded timing basis SIG-BASIS-2024-04, "
            "while the document register lists Rev C as current."
        ),
        "action": "Reissue SIG-SSC01-002 at Rev C using SIG-BASIS-2025-02 before issue.",
    },
    "approach_datum_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "PROF-SSC01-002",
        "object_id": "APP-NB-02",
        "consequence": (
            "The approach profile contains contradictory datum notes, so the profile cannot be tied "
            "cleanly to the AHD intersection layout."
        ),
        "action": "Confirm the datum for PROF-SSC01-002 and reissue the approach profile on a single AHD basis.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "SIG-SSC01-002",
        "object_id": "CASE-AM-02",
        "consequence": (
            "The signal timing sheet uses an assessment speed copied from APP-EB-99 instead of the "
            "APP-NB-02 design speed, so the timing case is not traceable to this approach."
        ),
        "action": "Recalculate SG-02 yellow and all-red intervals using APP-NB-02 speed and record the case basis.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-002",
        "object_id": "C-04",
        "consequence": "Critical authority comment C-04 on PED-X-02 pedestrian clearance is open.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "pedestrian_clearance_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "SIG-SSC01-002",
        "object_id": "PED-X-02",
        "consequence": ("Recomputed available pedestrian clearance is below the required clearance for PED-X-02."),
        "action": "Increase SG-02 pedestrian clearance time or revise the crossing treatment before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All seven register documents are present with IDs and revisions (DOC-REG-SSC01-02).",
        "RLR-02": "INT-02, APP-NB-02, SG-02, PED-X-02, CTRL-02, CASE-AM-02, CH 0+480, and AHD reconcile.",
        "RLR-03": "Stopping distance, yellow interval, all-red interval, and sight-distance basis recompute.",
        "RLR-04": "Available sight distance and pedestrian clearance both clear the source-owned criteria.",
        "RLR-05": "The timing scenario uses the APP-NB-02 design speed and CASE-AM-02.",
        "RLR-06": "The controller handoff, SG-02 timing, and exported crossing values are internally consistent.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_pedestrian_clearance":
        evidence_notes["RLR-04"] = (
            "The available pedestrian clearance is pending controller export, so PED-X-02 clearance cannot be assessed."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "stopping_distance_m",
            "sight_distance_margin_m",
            "yellow_interval_s",
            "all_red_interval_s",
            "ped_clearance_required_s",
            "ped_clearance_margin_s",
            "grade_adjusted_braking_distance_m",
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
    if variant == "missing_pedestrian_clearance":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Available pedestrian clearance for SG-02 / PED-X-02",
                "source_id": "SIG-SSC01-002",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the SG-02 callout leader on INT-SSC01-002 for comment C-05.",
                "owner": "Signals designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "intersection": "INT-02",
            "approach": "APP-NB-02",
            "approach_chainage": "CH 0+480",
            "datum": "AHD",
            "signal_group": "SG-02",
            "pedestrian_crossing": "PED-X-02",
            "controller": "CTRL-02",
            "timing_case": "CASE-AM-02",
            "sight_distance_case": "SIGHT-APP-NB-02",
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
        "## Issue-Readiness Review - INT-02 intersection signal safety package\n\n"
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
        "The intersection signal safety package has been reviewed and is approved for issue. The design is "
        "fully compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
