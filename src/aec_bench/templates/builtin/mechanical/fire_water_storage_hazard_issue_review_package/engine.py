# ABOUTME: Engine for the SSC-19 review-first fire-water storage and hazard issue package.
# ABOUTME: Derives packet state, variant gold review statuses, source-pack files, and golden fixtures.

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
    "storage_height_m": 0.1,
    "remote_area_adjustment_m2": 1.0,
    "storage_margin_m3": 1.0,
    "storage_deficit_m3": 1.0,
    "pump_capacity_margin_l_min": 50.0,
    "tank_volume_mismatch_delta_m3": 5.0,
}

_CLASS_TABLE = {
    "Ordinary Storage": {
        "density": 8.1,
        "base_area": 185.0,
        "hose": 950.0,
        "duration": 60.0,
    },
    "Storage Class II": {
        "density": 12.2,
        "base_area": 230.0,
        "hose": 1900.0,
        "duration": 90.0,
    },
    "Storage Class III": {
        "density": 16.3,
        "base_area": 280.0,
        "hose": 1900.0,
        "duration": 120.0,
    },
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid, avoiding float dust."""
    return round(round(value / step) * step, 10)


def _ceil_to(value: float, step: float) -> float:
    """Round a value up to the next step boundary."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with floats snapped to grid and enums cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _true_class(storage_height_m: float) -> str:
    if storage_height_m <= 6.5:
        return "Storage Class II"
    return "Storage Class III"


def _lower_class(class_name: str) -> str:
    if class_name == "Storage Class III":
        return "Storage Class II"
    return "Ordinary Storage"


def _class_values(class_name: str, area_adjustment_m2: float) -> dict[str, float]:
    entry = _CLASS_TABLE[class_name]
    area = _q(entry["base_area"] + area_adjustment_m2, 1.0)
    density = entry["density"]
    hose = entry["hose"]
    duration = entry["duration"]
    sprinkler = density * area
    total = sprinkler + hose
    volume = total * duration / 1000.0
    return {
        "density": density,
        "area": area,
        "hose": hose,
        "duration": duration,
        "sprinkler": sprinkler,
        "total": total,
        "volume": volume,
    }


def _derive(raw_params: dict) -> dict:
    """Compute the full packet state: true metrics, derived criteria, and claims."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    true_class = _true_class(p["storage_height_m"])
    claimed_class = _lower_class(true_class) if variant == "storage_deficient_under_true_class" else true_class
    true_values = _class_values(true_class, p["remote_area_adjustment_m2"])
    claimed_values = _class_values(claimed_class, p["remote_area_adjustment_m2"])

    if variant == "storage_deficient_under_true_class":
        available_storage = _q(true_values["volume"] - p["storage_deficit_m3"], 1.0)
    else:
        available_storage = _ceil_to(true_values["volume"] + p["storage_margin_m3"], 1.0)
    storage_margin = available_storage - true_values["volume"]

    demand_sheet_storage = available_storage
    if variant == "tank_volume_mismatch":
        demand_sheet_storage = available_storage + p["tank_volume_mismatch_delta_m3"]

    pump_capacity = _ceil_to(true_values["total"] + p["pump_capacity_margin_l_min"], 50.0)
    pump_capacity_margin = pump_capacity - true_values["total"]

    claimed_required_volume = claimed_values["volume"]
    claimed_storage_margin = demand_sheet_storage - claimed_required_volume

    return {
        "params": p,
        "variant": variant,
        "true_class": true_class,
        "claimed_class": claimed_class,
        "true_values": true_values,
        "claimed_values": claimed_values,
        "available_storage": available_storage,
        "demand_sheet_storage": demand_sheet_storage,
        "storage_margin": storage_margin,
        "pump_capacity": pump_capacity,
        "pump_capacity_margin": pump_capacity_margin,
        "claimed_required_volume": claimed_required_volume,
        "claimed_storage_margin": claimed_storage_margin,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_commodity_classification": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_hazard_basis_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "tank_volume_mismatch": {
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
    "storage_deficient_under_true_class": {
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

    if state["variant"] == "missing_commodity_classification":
        result["hose_allowance_l_min"] = 1900.0
        return result

    true_values = state["true_values"]
    result["design_density_mm_min"] = true_values["density"]
    result["design_area_m2"] = true_values["area"]
    result["sprinkler_demand_l_min"] = true_values["sprinkler"]
    result["hose_allowance_l_min"] = true_values["hose"]
    result["required_duration_min"] = true_values["duration"]
    result["required_volume_m3"] = true_values["volume"]
    result["storage_volume_margin_m3"] = state["storage_margin"]
    result["pump_capacity_margin_l_min"] = state["pump_capacity_margin"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("HAZ-19-ARR-01", "Hazard and storage arrangement", "Rev C", "Issued for review"),
        ("SPR-19-DMD-01", "Sprinkler and hydrant demand sheet", "Rev B", "Issued for review"),
        ("TANK-19-SCH-01", "Tank and fire pump schedule", "Rev B", "Issued for review"),
        ("CASE-19-FIRE-01", "Fire strategy operating case", "Rev A", "Issued for review"),
        ("WS-19-BASIS-01", "Water-supply basis", "Rev A", "Issued for review"),
        ("CRIT-SSC19-001", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the seven-file source packet for one instance."""
    s = _derive(all_params)
    p = s["params"]
    variant = s["variant"]
    claimed_values = s["claimed_values"]

    register_lines = [
        "| Document ID | Title | Revision | Status |",
        "|---|---|---|---|",
    ]
    for doc_id, title, rev, status in _register_rows(variant):
        register_lines.append(f"| {doc_id} | {title} | {rev} | {status} |")
    document_register = (
        "# Document Register - DOC-REG-SSC19-01\n\n"
        "Issue package: fire-water hazard, sprinkler demand, storage, and pump review for AHJ-19.\n\n"
        + "\n".join(register_lines)
        + "\n"
    )

    hazard_revision = "Rev B" if variant == "stale_hazard_basis_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_hazard_basis_revision":
        stale_note = (
            "\nNote: this hazard arrangement sheet is Rev B. The document register lists "
            "HAZ-19-ARR-01 Rev C as the current issue for review.\n"
        )

    if variant == "missing_commodity_classification":
        certificate_line = "| Commodity classification certificate | commodity classification certificate pending |"
    else:
        certificate_line = "| Commodity classification certificate | CERT-19-COM-01 current for HAZ-19 |"

    hazard_arrangement = f"""# Hazard And Storage Arrangement - HAZ-19-ARR-01 ({hazard_revision})

Building: BLDG-19. Hazard arrangement: HAZ-19. Sprinkler system: SPR-19.

| Item | Value |
|---|---|
| Commodity | cartoned unexpanded plastic goods |
| Rack arrangement | single-row rack with transverse flues |
| Storage height | {p["storage_height_m"]:.1f} m |
{certificate_line}
| Fire strategy case | AHJ-19-CASE-A |
{stale_note}
"""

    demand_origin = "AHJ-19-CASE-A fire strategy"
    if variant == "scenario_copy_forward":
        demand_origin = "copied from BLDG-17 strategy case; AHJ-19 selection record pending"

    sprinkler_demand = f"""# Sprinkler And Hydrant Demand Sheet - SPR-19-DMD-01 (Rev B)

Demand sheet for sprinkler system SPR-19 and hazard arrangement HAZ-19.

| Item | Value |
|---|---|
| Demand scenario source | {demand_origin} |
| Package selected hazard class | {s["claimed_class"]} |
| Package design density | {claimed_values["density"]:.1f} mm/min |
| Package design area | {claimed_values["area"]:.0f} m2 |
| Package hose allowance | {claimed_values["hose"]:.0f} L/min |
| Package required duration | {claimed_values["duration"]:.0f} min |
| Package required volume | {s["claimed_required_volume"]:.1f} m3 |
| Demand-sheet tank volume | {s["demand_sheet_storage"]:.1f} m3 |
| Package storage margin | {s["claimed_storage_margin"]:.1f} m3 |
"""

    tank_schedule = f"""# Tank And Fire Pump Schedule - TANK-19-SCH-01 (Rev B)

Tank TANK-19 and fire pump PUMP-19 serve sprinkler system SPR-19.

| Item | Value |
|---|---|
| Fire-water tank | TANK-19 |
| Available fire-water storage | {s["available_storage"]:.1f} m3 |
| Fire pump | PUMP-19 |
| Fire pump rated capacity | {s["pump_capacity"]:.0f} L/min |
| Pump service | AHJ-19-CASE-A |
"""

    fire_strategy = """# Fire Strategy Operating Case - CASE-19-FIRE-01 (Rev A)

Fire strategy case: AHJ-19-CASE-A for BLDG-19 storage fire-water review.

| Item | Value |
|---|---|
| Building | BLDG-19 |
| Hazard arrangement | HAZ-19 |
| Sprinkler system | SPR-19 |
| Tank | TANK-19 |
| Pump | PUMP-19 |
| Water-supply basis | WS-19 |
"""

    water_supply = """# Water-Supply Basis - WS-19-BASIS-01 (Rev A)

Water-supply basis WS-19 supports fire pump PUMP-19 for AHJ-19-CASE-A.

| Item | Value |
|---|---|
| Water-supply basis | WS-19 |
| Minimum residual pressure note | pump-rated demand must not exceed PUMP-19 capacity |
| Storage basis | TANK-19 usable fire-water storage only |
"""

    comments = [
        ("C-01", "Fire", "Confirm rack arrangement and storage height are recorded.", "Closed", "minor", "", ""),
        ("C-02", "Mechanical", "Confirm TANK-19 usable volume basis.", "Closed", "minor", "", ""),
        ("C-03", "AHJ", "Confirm AHJ-19-CASE-A duration table is cited.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "AHJ",
                "Confirm AHJ acceptance path for high-bay storage classification.",
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
                "Add TANK-19 tag to the storage plan legend.",
                "Open",
                "minor",
                "Fire protection designer",
                "Update legend at next revision (carried action, due next issue)",
            )
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, disc, text, status, crit, owner, action in comments:
        comment_lines.append(f"| {cid} | {disc} | {text} | {status} | {crit} | {owner} | {action} |")

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC19-001 (Rev A)

## Hazard classification table

| Storage condition | Design density | Base design area | Hose allowance | Duration |
|---|---|---|---|---|
| Ordinary Storage, certificate-supported storage height up to 6.5 m | 8.1 mm/min | 185 m2 | 950 L/min | 60 min |
| Storage Class II, storage height up to 6.5 m | 12.2 mm/min | 230 m2 | 1900 L/min | 90 min |
| Storage Class III, storage height above 6.5 m | 16.3 mm/min | 280 m2 | 1900 L/min | 120 min |

Remote-area adjustment for HAZ-19: {p["remote_area_adjustment_m2"]:.0f} m2.

## Assessment bases (source-owned methods)

- True hazard class: classify from commodity evidence and storage height using the table above.
- Design area: class base design area plus the HAZ-19 remote-area adjustment.
- Sprinkler demand: design density x design area. In these units, mm/min x m2 = L/min.
- Total fire-water demand: sprinkler demand plus hose allowance.
- Required storage volume: total fire-water demand x duration / 1000.
- Storage margin: available fire-water storage minus required storage volume.
- Pump capacity margin: PUMP-19 rated capacity minus total fire-water demand.

## Review comments

{chr(10).join(comment_lines)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/hazard-storage-arrangement.md": hazard_arrangement,
        "sources/sprinkler-hydrant-demand.md": sprinkler_demand,
        "sources/tank-pump-schedule.md": tank_schedule,
        "sources/fire-strategy-operating-case.md": fire_strategy,
        "sources/water-supply-basis.md": water_supply,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_hazard_basis_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "HAZ-19-ARR-01",
        "object_id": "HAZ-19",
        "consequence": (
            "The hazard arrangement source is Rev B while the document register lists Rev C, so the hazard "
            "classification basis is not traceable to the current package."
        ),
        "action": "Reissue HAZ-19-ARR-01 at Rev C or reconcile the register before issue.",
    },
    "tank_volume_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "SPR-19-DMD-01",
        "object_id": "TANK-19",
        "consequence": "The demand sheet tank volume does not match the usable storage in TANK-19-SCH-01.",
        "action": "Reconcile the TANK-19 usable volume between the demand sheet and tank schedule.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "SPR-19-DMD-01",
        "object_id": "AHJ-19-CASE-A",
        "consequence": "The demand scenario source is copied from another building without the AHJ-19 case record.",
        "action": "Provide the AHJ-19 fire strategy selection record and reissue the demand basis.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC19-001",
        "object_id": "C-04",
        "consequence": "Critical AHJ comment C-04 is open with no owner or agreed action.",
        "action": "Assign an owner and closure path for C-04 before issue.",
    },
    "storage_deficient_under_true_class": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "TANK-19-SCH-01",
        "object_id": "TANK-19",
        "consequence": (
            "Recomputed required storage under the true hazard class exceeds TANK-19 available storage; "
            "the package claim uses a lower hazard class."
        ),
        "action": "Reclassify HAZ-19 using CRIT-SSC19-001 and increase storage or reduce the accepted demand basis.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All six register documents are present with IDs and revisions in DOC-REG-SSC19-01.",
        "RLR-02": "BLDG-19, HAZ-19, CERT-19, SPR-19, TANK-19, PUMP-19, WS-19, and AHJ-19 reconcile.",
        "RLR-03": "Hazard class, density, area, hose allowance, duration, and demand are source-backed.",
        "RLR-04": "Storage volume and pump capacity clear the CRIT-SSC19-001 criteria.",
        "RLR-05": "AHJ-19-CASE-A and HAZ-19 are used across hazard, demand, tank, pump, and water-supply files.",
        "RLR-06": "PUMP-19 rated capacity is source-backed and clears total fire-water demand.",
        "RLR-07": "All review comments in CRIT-SSC19-001 are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_commodity_classification":
        evidence_notes["RLR-04"] = (
            "The commodity classification certificate is pending, so the true hazard class and storage demand "
            "cannot be determined."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "design_density_mm_min",
            "design_area_m2",
            "sprinkler_demand_l_min",
            "hose_allowance_l_min",
            "required_duration_min",
            "required_volume_m3",
            "storage_volume_margin_m3",
            "pump_capacity_margin_l_min",
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
    if variant == "missing_commodity_classification":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "commodity classification certificate for HAZ-19",
                "source_id": "HAZ-19-ARR-01",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: add TANK-19 tag to the storage plan legend (comment C-05).",
                "owner": "Fire protection designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "building": "BLDG-19",
            "hazard_arrangement": "HAZ-19",
            "commodity_evidence": "CERT-19-COM-01",
            "sprinkler_system": "SPR-19",
            "tank": "TANK-19",
            "pump": "PUMP-19",
            "water_supply_basis": "WS-19",
            "fire_strategy_case": "AHJ-19-CASE-A",
            "criteria_memo": "CRIT-SSC19-001",
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
        "## Issue-Readiness Review - fire-water storage HAZ-19\n\n"
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
        "The fire-water storage package has been reviewed and is approved for issue. The design is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
