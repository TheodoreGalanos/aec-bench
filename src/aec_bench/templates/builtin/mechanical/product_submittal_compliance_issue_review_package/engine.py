# ABOUTME: Engine for the SSC-15 review-first product submittal compliance issue package.
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
    "cev_limit": 0.001,
    "carbon_equivalent_margin": 0.001,
    "carbon_equivalent_deficit": 0.001,
    "required_yield_mpa": 5.0,
    "yield_strength_margin_mpa": 5.0,
    "required_tensile_mpa": 5.0,
    "tensile_strength_margin_mpa": 5.0,
}

_BASE_CHEMISTRY = {
    "mn": 1.20,
    "cr": 0.10,
    "mo": 0.03,
    "v": 0.02,
    "ni": 0.15,
    "cu": 0.20,
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


def _cev_from_chemistry(row: dict[str, float]) -> float:
    return row["c"] + row["mn"] / 6.0 + (row["cr"] + row["mo"] + row["v"]) / 5.0 + (row["ni"] + row["cu"]) / 15.0


def _chemistry_for_target(target_cev: float) -> dict[str, float]:
    fixed = (
        _BASE_CHEMISTRY["mn"] / 6.0
        + (_BASE_CHEMISTRY["cr"] + _BASE_CHEMISTRY["mo"] + _BASE_CHEMISTRY["v"]) / 5.0
        + (_BASE_CHEMISTRY["ni"] + _BASE_CHEMISTRY["cu"]) / 15.0
    )
    row = dict(_BASE_CHEMISTRY)
    row["c"] = _q(target_cev - fixed, 0.001)
    return row


def _derive(raw_params: dict) -> dict:
    """Compute the full packet state: true metrics, derived criteria, and claims."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    target_cev = (
        p["cev_limit"] + p["carbon_equivalent_deficit"]
        if variant == "carbon_equivalent_exceeds"
        else p["cev_limit"] - p["carbon_equivalent_margin"]
    )
    heat_b = _chemistry_for_target(target_cev)
    heat_a = _chemistry_for_target(target_cev - 0.018)

    yield_b = _ceil_to(p["required_yield_mpa"] + p["yield_strength_margin_mpa"], 5.0)
    tensile_b = _ceil_to(p["required_tensile_mpa"] + p["tensile_strength_margin_mpa"], 5.0)
    yield_a = yield_b + 10.0
    tensile_a = tensile_b + 10.0

    heats = {
        "HEAT-15-A": {**heat_a, "yield": yield_a, "tensile": tensile_a},
        "HEAT-15-B": {**heat_b, "yield": yield_b, "tensile": tensile_b},
    }
    application_heats = ["HEAT-15-A", "HEAT-15-B", "HEAT-15-B"]

    applied_rows = [heats[heat] for heat in application_heats]
    cev_values = [_cev_from_chemistry(row) for row in applied_rows]
    yield_values = [row["yield"] for row in applied_rows]
    tensile_values = [row["tensile"] for row in applied_rows]

    carbon_equivalent_max = max(cev_values)
    carbon_equivalent_margin = p["cev_limit"] - carbon_equivalent_max

    return {
        "params": p,
        "variant": variant,
        "heats": heats,
        "application_heats": application_heats,
        "carbon_equivalent_max": carbon_equivalent_max,
        "carbon_equivalent_margin": carbon_equivalent_margin,
        "yield_strength_margin_mpa": min(yield_values) - p["required_yield_mpa"],
        "tensile_strength_margin_mpa": min(tensile_values) - p["required_tensile_mpa"],
        "certificate_coverage_count": 2.0,
        "traceability_match_count": 3.0,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_heat_number": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_certificate_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "heat_number_mismatch": {
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
    "carbon_equivalent_exceeds": {
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

    result["certificate_coverage_count"] = state["certificate_coverage_count"]
    if state["variant"] == "missing_heat_number":
        return result

    result["carbon_equivalent_max"] = state["carbon_equivalent_max"]
    result["carbon_equivalent_margin"] = state["carbon_equivalent_margin"]
    result["yield_strength_margin_mpa"] = state["yield_strength_margin_mpa"]
    result["tensile_strength_margin_mpa"] = state["tensile_strength_margin_mpa"]
    result["traceability_match_count"] = state["traceability_match_count"]
    return result


def _register_rows(_variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("SUB-15-MAN-01", "Submittal manifest", "Rev C", "Issued for review"),
        ("CERT-15-MILL-01", "Mill certificates", "Rev B", "Issued for review"),
        ("TRACE-15-HEAT-01", "Heat traceability table", "Rev B", "Issued for review"),
        ("APP-15-SCH-01", "Product application schedule", "Rev B", "Issued for review"),
        ("DEV-15-LOG-01", "Deviation register", "Rev A", "Issued for review"),
        ("CRIT-SSC15-001", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _format_heat_row(heat_id: str, row: dict[str, float]) -> str:
    return (
        f"| {heat_id} | {row['c']:.3f} | {row['mn']:.2f} | {row['cr']:.2f} | {row['mo']:.2f} | "
        f"{row['v']:.2f} | {row['ni']:.2f} | {row['cu']:.2f} | {row['yield']:.0f} | "
        f"{row['tensile']:.0f} | CEV summary pass |"
    )


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
        "# Document Register - DOC-REG-SSC15-01\n\n"
        "Issue package: product submittal compliance review for SUB-15.\n\n" + "\n".join(register_lines) + "\n"
    )

    submittal_manifest = """# Submittal Manifest - SUB-15-MAN-01 (Rev C)

Submittal SUB-15 covers product PROD-15 for the APP-15 application schedule.

| Item | Value |
|---|---|
| Product | PROD-15 fabricated steel plate |
| Required grade | GRADE-15 |
| Certificate set | CERT-15-MILL-01 |
| Heat traceability table | TRACE-15-HEAT-01 |
| Application schedule | APP-15-SCH-01 |
| Deviation register | DEV-15-LOG-01 |
| Disposition basis | CRIT-SSC15-001 |
"""

    certificate_revision = "Rev A" if variant == "stale_certificate_revision" else "Rev B"
    stale_note = ""
    if variant == "stale_certificate_revision":
        stale_note = (
            "\nNote: this certificate file is Rev A. The document register lists "
            "CERT-15-MILL-01 Rev B as the current issue for review.\n"
        )

    heat_rows = [
        "| Heat | C | Mn | Cr | Mo | V | Ni | Cu | Yield MPa | Tensile MPa | Certificate summary |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for heat_id, row in s["heats"].items():
        heat_rows.append(_format_heat_row(heat_id, row))
    mill_certificates = f"""# Mill Certificates - CERT-15-MILL-01 ({certificate_revision})

Certificate package CERT-15-MILL-01 covers product PROD-15 and required grade GRADE-15.

{chr(10).join(heat_rows)}
{stale_note}
"""

    trace_heat_b = "HEAT-15-X" if variant == "heat_number_mismatch" else "HEAT-15-B"
    traceability = f"""# Heat Traceability Table - TRACE-15-HEAT-01 (Rev B)

Traceability table for submittal SUB-15 and product PROD-15.

| Application row | Product | Heat | Certificate |
|---|---|---|---|
| APP-15-A | PROD-15 | HEAT-15-A | CERT-15-MILL-01 |
| APP-15-B | PROD-15 | {trace_heat_b} | CERT-15-MILL-01 |
| APP-15-C | PROD-15 | HEAT-15-B | CERT-15-MILL-01 |
"""

    application_heat_b = "traceability pending" if variant == "missing_heat_number" else "HEAT-15-B"
    application_schedule = f"""# Product Application Schedule - APP-15-SCH-01 (Rev B)

Application schedule APP-15 assigns product PROD-15 to the GRADE-15 use case.

| Application row | Location | Product | Heat | Required grade |
|---|---|---|---|---|
| APP-15-A | West frame base plate | PROD-15 | HEAT-15-A | GRADE-15 |
| APP-15-B | East frame base plate | PROD-15 | {application_heat_b} | GRADE-15 |
| APP-15-C | Pump skid tie plate | PROD-15 | HEAT-15-B | GRADE-15 |
"""

    deviation_register = """# Deviation Register - DEV-15-LOG-01 (Rev A)

Deviation register for product submittal SUB-15.

| Deviation | Status | Owner | Agreed action |
|---|---|---|---|
| DEV-15-001 | Closed | Product reviewer | Weld prep note added to fabrication ITP |
"""

    comments = [
        ("C-01", "Materials", "Confirm the required product grade is recorded.", "Closed", "minor", "", ""),
        ("C-02", "QA", "Confirm the certificate revision is listed in the register.", "Closed", "minor", "", ""),
        ("C-03", "Design", "Confirm deviation DEV-15-001 is closed in the issue package.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Materials",
                "Resolve product certificate scope before issue.",
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
                "Add certificate page reference to the submittal cover sheet.",
                "Open",
                "minor",
                "Materials reviewer",
                "Add page reference at next issue (carried action)",
            )
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, disc, text, status, crit, owner, action in comments:
        comment_lines.append(f"| {cid} | {disc} | {text} | {status} | {crit} | {owner} | {action} |")

    standard_basis = "GRADE-15 application schedule"
    if variant == "scenario_copy_forward":
        standard_basis = "copied from SUB-14 anchor-plate schedule; GRADE-15 selection matrix pending"

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC15-001 (Rev A)

## Application criteria

| Item | Value |
|---|---|
| Product use case | APP-15 |
| Required product grade | GRADE-15 |
| Standard applicability basis | {standard_basis} |
| Carbon equivalent limit | {p["cev_limit"]:.3f} |
| Minimum yield strength | {p["required_yield_mpa"]:.0f} MPa |
| Minimum tensile strength | {p["required_tensile_mpa"]:.0f} MPa |

Carbon equivalent limit: {p["cev_limit"]:.3f}
Minimum yield strength: {p["required_yield_mpa"]:.0f} MPa
Minimum tensile strength: {p["required_tensile_mpa"]:.0f} MPa

## Assessment bases (source-owned methods)

- Carbon equivalent formula: CEV = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15.
- Carbon equivalent margin: carbon equivalent limit minus the maximum CEV across applied heats.
- Yield strength margin: minimum certified yield strength across applied heats minus the required yield strength.
- Tensile strength margin: minimum certified tensile strength across applied heats minus the required tensile strength.
- Certificate coverage count: unique applied heats with a row in CERT-15-MILL-01.
- Traceability match count: application rows with a named heat number that appears in the certificate set.

## Review comments

{chr(10).join(comment_lines)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/submittal-manifest.md": submittal_manifest,
        "sources/mill-certificates.md": mill_certificates,
        "sources/heat-traceability-table.md": traceability,
        "sources/product-application-schedule.md": application_schedule,
        "sources/deviation-register.md": deviation_register,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_certificate_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "CERT-15-MILL-01",
        "object_id": "CERT-15-MILL-01",
        "consequence": (
            "The mill certificate file is Rev A while the document register lists Rev B, so the certificate "
            "basis is not traceable to the current issue package."
        ),
        "action": "Reissue CERT-15-MILL-01 at Rev B or reconcile the register before issue.",
    },
    "heat_number_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "TRACE-15-HEAT-01",
        "object_id": "APP-15-B",
        "consequence": "The traceability table uses a heat number that does not exist in CERT-15-MILL-01.",
        "action": "Reconcile the APP-15-B heat number between the traceability table and certificate set.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "CRIT-SSC15-001",
        "object_id": "GRADE-15",
        "consequence": "The standard applicability basis is copied from another submittal without the GRADE-15 matrix.",
        "action": "Provide the GRADE-15 standard applicability matrix for SUB-15 before issue.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC15-001",
        "object_id": "C-04",
        "consequence": "Critical product certificate scope comment C-04 is open with no owner or agreed action.",
        "action": "Assign an owner and closure path for C-04 before issue.",
    },
    "carbon_equivalent_exceeds": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "CERT-15-MILL-01",
        "object_id": "HEAT-15-B",
        "consequence": (
            "Recomputed carbon equivalent for an applied heat exceeds the source-owned weldability limit, "
            "while the certificate summary claims pass."
        ),
        "action": "Reject the heat for this use case or obtain an accepted engineering deviation before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All six register documents are present with IDs and revisions in DOC-REG-SSC15-01.",
        "RLR-02": "SUB-15, PROD-15, GRADE-15, HEAT-15-A/B, CERT-15, APP-15, DEV-15, and CRIT-SSC15-001 reconcile.",
        "RLR-03": "Chemistry, mechanical properties, certificate scope, and source revisions are traceable.",
        "RLR-04": "CEV, yield, tensile, certificate coverage, and traceability clear the source criteria.",
        "RLR-05": (
            "The same GRADE-15 application basis is used across schedule, certificates, deviations, and criteria."
        ),
        "RLR-06": "Certificate coverage and heat traceability are source-backed for the issue package.",
        "RLR-07": "All review comments in CRIT-SSC15-001 are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_heat_number":
        evidence_notes["RLR-04"] = (
            "APP-15-SCH-01 marks an application heat number as traceability pending, so the applied "
            "heat cannot be assessed for CEV and properties."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "carbon_equivalent_max",
            "carbon_equivalent_margin",
            "yield_strength_margin_mpa",
            "tensile_strength_margin_mpa",
            "certificate_coverage_count",
            "traceability_match_count",
        )
        if key in ground_truth
    }

    findings = []
    actions = []
    if variant in _VARIANT_FINDINGS:
        finding = dict(_VARIANT_FINDINGS[variant])
        findings.append(finding)
        actions.append({"action": finding["action"], "owner": "Product reviewer", "linked_item": finding["item"]})

    information_requests = []
    if variant == "missing_heat_number":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "heat number for APP-15-B",
                "source_id": "APP-15-SCH-01",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: add certificate page reference to the submittal cover sheet.",
                "owner": "Materials reviewer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "submittal": "SUB-15",
            "product": "PROD-15",
            "grade": "GRADE-15",
            "heat_a": "HEAT-15-A",
            "heat_b": "HEAT-15-B",
            "certificates": "CERT-15-MILL-01",
            "application_schedule": "APP-15-SCH-01",
            "deviation_register": "DEV-15-LOG-01",
            "criteria_memo": "CRIT-SSC15-001",
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
        "## Issue-Readiness Review - product submittal SUB-15\n\n"
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
        "The product submittal package has been reviewed and is approved for issue. The product is fully "
        "compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
