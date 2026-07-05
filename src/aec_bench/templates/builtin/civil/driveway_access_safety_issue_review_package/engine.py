# ABOUTME: Engine for the SSC-01 driveway access safety issue review package.
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
_GUTTER_KU_SI = 0.376

_QUANT_STEPS = {
    "driveway_low_level_m": 0.01,
    "driveway_grade_pct_source": 0.1,
    "driveway_length_m": 0.1,
    "allowable_driveway_grade_pct": 0.1,
    "culvert_diameter_m": 0.05,
    "culvert_mannings_n": 0.001,
    "culvert_slope_pct": 0.1,
    "design_flow_m3_s": 0.01,
    "tailwater_level_m": 0.01,
    "headwater_base_depth_m": 0.01,
    "headwater_loss_factor_m": 0.01,
    "minimum_freeboard_m": 0.01,
    "freeboard_margin_target_m": 0.01,
    "freeboard_deficit_m": 0.01,
    "gutter_flow_m3_s": 0.01,
    "cross_slope_pct": 0.1,
    "longitudinal_slope_pct": 0.1,
    "gutter_mannings_n": 0.001,
    "spread_margin_target_m": 0.1,
    "access_speed_kmh": 1.0,
    "sight_reaction_time_s": 0.1,
    "braking_friction_coefficient": 0.01,
    "access_grade_pct": 0.1,
    "available_sight_margin_m": 1.0,
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid, avoiding float dust."""
    return round(round(value / step) * step, 10)


def _ceil_to(value: float, step: float) -> float:
    """Round a value up to the next step boundary."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with floats snapped to grid and hidden variants cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _culvert_capacity(diameter_m: float, mannings_n: float, slope_pct: float) -> float:
    """Compute full circular-pipe Manning capacity from source values."""
    area_m2 = math.pi * diameter_m**2 / 4.0
    hydraulic_radius_m = diameter_m / 4.0
    return area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(slope_pct / 100.0) / mannings_n


def _derive(raw_params: dict) -> dict:
    """Compute true metrics, derived criteria, and package claims for one packet."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    driveway_high_level = _q(
        p["driveway_low_level_m"] + p["driveway_grade_pct_source"] / 100.0 * p["driveway_length_m"],
        0.01,
    )
    driveway_grade = (driveway_high_level - p["driveway_low_level_m"]) / p["driveway_length_m"] * 100.0
    driveway_grade_margin = p["allowable_driveway_grade_pct"] - abs(driveway_grade)

    culvert_capacity = _culvert_capacity(p["culvert_diameter_m"], p["culvert_mannings_n"], p["culvert_slope_pct"])
    culvert_capacity_margin = culvert_capacity - p["design_flow_m3_s"]
    flow_capacity_ratio = p["design_flow_m3_s"] / culvert_capacity
    headwater_depth = p["headwater_base_depth_m"] + p["headwater_loss_factor_m"] * flow_capacity_ratio**2
    headwater_level = p["tailwater_level_m"] + headwater_depth

    freeboard_margin_target = p["freeboard_margin_target_m"]
    if variant == "access_freeboard_deficient":
        road_edge_level = _q(headwater_level + p["minimum_freeboard_m"] - p["freeboard_deficit_m"], 0.01)
    else:
        road_edge_level = _q(headwater_level + p["minimum_freeboard_m"] + freeboard_margin_target, 0.01)
    freeboard = road_edge_level - headwater_level
    freeboard_margin = freeboard - p["minimum_freeboard_m"]

    spread_width = (
        p["gutter_flow_m3_s"]
        * p["gutter_mannings_n"]
        / (
            _GUTTER_KU_SI
            * (p["cross_slope_pct"] / 100.0) ** (5.0 / 3.0)
            * math.sqrt(p["longitudinal_slope_pct"] / 100.0)
        )
    ) ** (3.0 / 8.0)
    allowable_spread = _ceil_to(spread_width + p["spread_margin_target_m"], 0.1)
    spread_margin = allowable_spread - spread_width

    access_speed_m_s = p["access_speed_kmh"] / 3.6
    grade_fraction = p["access_grade_pct"] / 100.0
    sight_distance_required = access_speed_m_s * p["sight_reaction_time_s"] + access_speed_m_s**2 / (
        2.0 * _G * (p["braking_friction_coefficient"] + grade_fraction)
    )
    available_sight_distance = _ceil_to(sight_distance_required + p["available_sight_margin_m"], 1.0)
    sight_distance_margin = available_sight_distance - sight_distance_required

    return {
        "params": p,
        "variant": variant,
        "driveway_high_level": driveway_high_level,
        "driveway_grade": driveway_grade,
        "driveway_grade_margin": driveway_grade_margin,
        "culvert_capacity": culvert_capacity,
        "culvert_capacity_margin": culvert_capacity_margin,
        "headwater_level": headwater_level,
        "road_edge_level": road_edge_level,
        "freeboard": freeboard,
        "freeboard_margin": freeboard_margin,
        "allowable_spread": allowable_spread,
        "spread_width": spread_width,
        "spread_margin": spread_margin,
        "sight_distance_required": sight_distance_required,
        "available_sight_distance": available_sight_distance,
        "sight_distance_margin": sight_distance_margin,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_road_edge_level": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_access_profile_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "culvert_chainage_mismatch": {
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
    "access_freeboard_deficient": {
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

    result["driveway_grade_percent"] = state["driveway_grade"]
    result["driveway_grade_margin_percent"] = state["driveway_grade_margin"]
    result["culvert_capacity_m3_s"] = state["culvert_capacity"]
    result["culvert_capacity_margin_m3_s"] = state["culvert_capacity_margin"]
    result["headwater_level_m"] = state["headwater_level"]
    if state["variant"] != "missing_road_edge_level":
        result["freeboard_m"] = state["freeboard"]
        result["freeboard_margin_m"] = state["freeboard_margin"]
    result["roadway_spread_m"] = state["spread_width"]
    result["spread_margin_m"] = state["spread_margin"]
    result["sight_distance_required_m"] = state["sight_distance_required"]
    result["sight_distance_margin_m"] = state["sight_distance_margin"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    access_rev = "Rev C"
    if variant == "stale_access_profile_revision":
        access_rev = "Rev C (current register basis; packet file is still Rev B)"
    return [
        ("ACCESS-SSC01-006", "Driveway access profile", access_rev, "Issued for review"),
        ("ROAD-SSC01-006", "Road edge and access chainage basis", "Rev B", "Issued for review"),
        ("CULV-SSC01-006", "Culvert drainage schedule", "Rev B", "Issued for review"),
        ("TAIL-SSC01-006", "Surface and tailwater table", "Rev B", "Issued for review"),
        ("SIGHT-SSC01-006", "Sight-distance note", "Rev A", "Issued for review"),
        ("OPS-SSC01-006", "Owner access operations criterion", "Rev A", "Current"),
        ("MEMO-SSC01-006", "Access safety criteria memo", "Rev A", "Current"),
        ("CRIT-SSC01-006", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    comments = [
        (
            "C-01",
            "Civil",
            "Confirm access profile, road edge basis, culvert schedule, and tailwater table use the same chainage.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-02",
            "Drainage",
            "Confirm culvert capacity, headwater, and freeboard are computed from the same design storm.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-03",
            "Traffic",
            "Confirm roadway spread and sight distance use the same access case and vehicle speed.",
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
                "Resolve critical driveway access and drainage comment before issue.",
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
                "Update driveway access label on the plan key.",
                "Open",
                "minor",
                "Civil designer",
                "Carry access label update to the next issue.",
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
    """Render the source packet for one driveway access safety review instance."""
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
        "# Document Register - DOC-REG-SSC01-06\n\n"
        "Issue package: driveway access safety review package for ACCESS-SSC01-006 under OPS-SSC01-006.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll values are source-packet values for the current synthetic task-owned issue package.\n"
    )

    scenario_note = "ACCESS-SSC01-006 service driveway access case."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "ACCESS-SSC01-006 table was copied from access case ACCESS-SSC01-099; reviewer must verify "
            "whether the storm and vehicle case belongs to ACCESS-SSC01-006."
        )

    access_rev = "Rev B" if variant == "stale_access_profile_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_access_profile_revision":
        stale_note = (
            "\nRevision note: this access profile is still Rev B. The document register lists "
            "ACCESS-SSC01-006 Rev C as the current issue basis.\n"
        )
    road_edge_line = (
        "| Road edge level | pending road edge survey confirmation |"
        if variant == "missing_road_edge_level"
        else f"| Road edge level | {state['road_edge_level']:.2f} m |"
    )
    road_edge_claim = (
        "Package claim: road-edge freeboard is pending road edge survey confirmation."
        if variant == "missing_road_edge_level"
        else f"Package claim: ACCESS-SSC01-006 has {state['freeboard_margin']:.3f} m freeboard margin."
    )
    access_profile = f"""# Access Profile - ACCESS-SSC01-006 ({access_rev})

Access case note: {scenario_note}
Road edge basis: ROAD-SSC01-006. Owner case: OPS-SSC01-006.
{stale_note}
| Item | Value |
|---|---|
| Access chainage | Ch 12+360 |
| Driveway low level | {p["driveway_low_level_m"]:.2f} m |
| Driveway high level | {state["driveway_high_level"]:.2f} m |
| Driveway length | {p["driveway_length_m"]:.1f} m |
{road_edge_line}

{road_edge_claim}
"""

    culvert_chainage = "Ch 12+405" if variant == "culvert_chainage_mismatch" else "Ch 12+360"
    mismatch_note = ""
    if variant == "culvert_chainage_mismatch":
        mismatch_note = (
            "\nMembership note: CULV-SSC01-006 is scheduled at Ch 12+405 while ACCESS-SSC01-006 and "
            "ROAD-SSC01-006 are at Ch 12+360.\n"
        )
    culvert_schedule = f"""# Culvert Drainage Schedule - CULV-SSC01-006 (Rev B)

Associated access profile: ACCESS-SSC01-006. Culvert chainage: {culvert_chainage}.
{mismatch_note}
| Item | Value |
|---|---|
| Culvert diameter | {p["culvert_diameter_m"]:.2f} m |
| Culvert Manning n | {p["culvert_mannings_n"]:.3f} |
| Culvert slope | {p["culvert_slope_pct"]:.1f} % |
| Design flow | {p["design_flow_m3_s"]:.2f} m3/s |
| Claimed culvert capacity | {state["culvert_capacity"]:.3f} m3/s |
| Claimed capacity margin | {state["culvert_capacity_margin"]:.3f} m3/s |

Package claim: CULV-SSC01-006 has adequate full-flow capacity for ACCESS-SSC01-006.
"""

    tailwater_table = f"""# Surface And Tailwater Table - TAIL-SSC01-006 (Rev B)

Access case: ACCESS-SSC01-006. Culvert: CULV-SSC01-006. Road edge basis: ROAD-SSC01-006.

| Item | Value |
|---|---|
| Tailwater level | {p["tailwater_level_m"]:.2f} m |
| Base headwater depth | {p["headwater_base_depth_m"]:.2f} m |
| Headwater loss factor | {p["headwater_loss_factor_m"]:.2f} m |
| Claimed headwater level | {state["headwater_level"]:.3f} m |

Package claim: TAIL-SSC01-006 provides the controlling headwater basis for ACCESS-SSC01-006.
"""

    spread_note = f"""# Roadway Spread Note - ROAD-SSC01-006 (Rev B)

Access case: ACCESS-SSC01-006. Road edge: ROAD-SSC01-006.

| Item | Value |
|---|---|
| Gutter flow | {p["gutter_flow_m3_s"]:.2f} m3/s |
| Cross slope | {p["cross_slope_pct"]:.1f} % |
| Longitudinal slope | {p["longitudinal_slope_pct"]:.1f} % |
| Gutter Manning n | {p["gutter_mannings_n"]:.3f} |
| Claimed roadway spread | {state["spread_width"]:.3f} m |

Package claim: ROAD-SSC01-006 keeps spread within the access path criterion.
"""

    sight_note = f"""# Sight-Distance Note - SIGHT-SSC01-006 (Rev A)

Access case: ACCESS-SSC01-006. Owner case: OPS-SSC01-006.

| Item | Value |
|---|---|
| Access speed | {p["access_speed_kmh"]:.0f} km/h |
| Sight reaction time | {p["sight_reaction_time_s"]:.1f} s |
| Braking friction coefficient | {p["braking_friction_coefficient"]:.2f} |
| Access grade | {p["access_grade_pct"]:.1f} % |
| Available sight distance | {state["available_sight_distance"]:.0f} m |
| Claimed sight distance required | {state["sight_distance_required"]:.3f} m |

Package claim: SIGHT-SSC01-006 clears the access sight-distance criterion.
"""

    owner_criterion = f"""# Owner Access Criterion - OPS-SSC01-006 (Rev A)

Owner criterion for issue of ACCESS-SSC01-006.

| Criterion | Value |
|---|---|
| Required access case | ACCESS-SSC01-006 service driveway |
| Maximum driveway grade | {p["allowable_driveway_grade_pct"]:.1f} % |
| Minimum culvert capacity margin | greater than or equal to 0 m3/s using CULV-SSC01-006 |
| Minimum road-edge freeboard | {p["minimum_freeboard_m"]:.2f} m |
| Maximum spread across access path | {state["allowable_spread"]:.1f} m |
| Minimum sight-distance margin | greater than or equal to 0 m using SIGHT-SSC01-006 |
| Issue-readiness rule | no critical findings or unresolved critical information requests |
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC01-006 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Driveway grade margin | must be greater than or equal to 0 percent using ACCESS-SSC01-006 |
| Culvert capacity margin | must be greater than or equal to 0 m3/s using CULV-SSC01-006 |
| Freeboard margin | must be greater than or equal to 0 m using ACCESS-SSC01-006 / ROAD-SSC01-006 |
| Roadway spread margin | must be greater than or equal to 0 m using ROAD-SSC01-006 |
| Sight-distance margin | must be greater than or equal to 0 m using SIGHT-SSC01-006 |

## Assessment bases (source-owned methods)

- Driveway grade: driveway high level minus driveway low level, divided by driveway length, times 100.
- Culvert capacity: Manning full circular pipe capacity using area, hydraulic radius as diameter divided by 4,
  slope as a fraction, and the culvert Manning n.
- Headwater level: tailwater plus base headwater depth plus ratio-squared headwater loss factor multiplied by
  design flow divided by culvert capacity squared.
- Freeboard: road edge level minus headwater level.
- Freeboard margin: freeboard minus minimum road-edge freeboard.
- Roadway spread: triangular-gutter spread with SI coefficient 0.376, gutter flow, gutter Manning n, cross slope,
  and longitudinal slope.
- Sight distance: speed converted from km/h to m/s by dividing by 3.6, plus grade-adjusted braking distance using
  9.81, braking friction coefficient, and access grade fraction.

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
        "sources/access-profile.md": access_profile,
        "sources/culvert-drainage-schedule.md": culvert_schedule,
        "sources/surface-tailwater-table.md": tailwater_table,
        "sources/roadway-spread-note.md": spread_note,
        "sources/sight-distance-note.md": sight_note,
        "sources/owner-access-criterion.md": owner_criterion,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_access_profile_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "ACCESS-SSC01-006",
        "object_id": "ACCESS-SSC01-006",
        "consequence": (
            "The access profile file is Rev B while the document register identifies ACCESS-SSC01-006 Rev C "
            "as the current issue basis."
        ),
        "action": "Replace the stale access profile with ACCESS-SSC01-006 Rev C before issue.",
    },
    "culvert_chainage_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "CULV-SSC01-006",
        "object_id": "CULV-SSC01-006",
        "consequence": "CULV-SSC01-006 is scheduled at Ch 12+405 while the access and road edge are at Ch 12+360.",
        "action": "Reconcile culvert chainage with ACCESS-SSC01-006 and ROAD-SSC01-006 before issue.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "ACCESS-SSC01-006",
        "object_id": "ACCESS-SSC01-006",
        "consequence": "The access profile text is copied from access case ACCESS-SSC01-099.",
        "action": "Reissue ACCESS-SSC01-006 and OPS-SSC01-006 with the current access storm and vehicle case.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-006",
        "object_id": "C-04",
        "consequence": "Critical driveway access and drainage comment C-04 remains open without owner or action.",
        "action": "Assign an owner and close C-04 before issue.",
    },
    "access_freeboard_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "ACCESS-SSC01-006",
        "object_id": "ROAD-SSC01-006",
        "consequence": "Recomputed road-edge freeboard is below the minimum freeboard criterion.",
        "action": "Raise the road edge, reduce headwater, or revise the driveway drainage basis before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    evidence_notes = {
        "RLR-01": "All eight source files are present with document IDs and revisions.",
        "RLR-02": (
            "ACCESS-SSC01-006, ROAD-SSC01-006, CULV-SSC01-006, TAIL-SSC01-006, SIGHT-SSC01-006, "
            "OPS-SSC01-006, MEMO-SSC01-006, and CRIT-SSC01-006 reconcile."
        ),
        "RLR-03": "Access profile, culvert capacity, and headwater basis are current and recomputable.",
        "RLR-04": "Driveway grade, culvert capacity, and road-edge freeboard clear the access criteria.",
        "RLR-05": "The access storm and vehicle case is ACCESS-SSC01-006 under OPS-SSC01-006.",
        "RLR-06": "Roadway spread and sight distance are source-backed for the same access case.",
        "RLR-07": "All review comments are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the review matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_road_edge_level":
        evidence_notes["RLR-04"] = (
            "ACCESS-SSC01-006 / ROAD-SSC01-006 has pending road edge survey confirmation, so freeboard margin "
            "cannot be computed."
        )

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "driveway_grade_percent",
            "driveway_grade_margin_percent",
            "culvert_capacity_m3_s",
            "culvert_capacity_margin_m3_s",
            "headwater_level_m",
            "freeboard_m",
            "freeboard_margin_m",
            "roadway_spread_m",
            "spread_margin_m",
            "sight_distance_required_m",
            "sight_distance_margin_m",
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
    if variant == "missing_road_edge_level":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Missing road edge level for ACCESS-SSC01-006 at ROAD-SSC01-006",
                "source_id": "ACCESS-SSC01-006 / ROAD-SSC01-006",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the driveway access label for comment C-05.",
                "owner": "Civil designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "driveway_access": "ACCESS-SSC01-006",
            "road_edge_basis": "ROAD-SSC01-006",
            "culvert": "CULV-SSC01-006",
            "tailwater_basis": "TAIL-SSC01-006",
            "sight_distance_basis": "SIGHT-SSC01-006",
            "owner_access_criterion": "OPS-SSC01-006",
            "criteria_memo": "MEMO-SSC01-006 / CRIT-SSC01-006",
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
        "## Issue-Readiness Review - ACCESS-SSC01-006 driveway access safety package\n\n"
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
        "The driveway access safety package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
