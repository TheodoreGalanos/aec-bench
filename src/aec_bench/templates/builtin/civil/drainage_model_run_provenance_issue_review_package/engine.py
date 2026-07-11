# ABOUTME: Engine for the SSC-03 drainage model-run provenance review package.
# ABOUTME: Renders temporal source packets and derives transition-aware verifier gold state.

from __future__ import annotations

import json

STATUS_PASS = 0.0
STATUS_FAIL = 1.0
STATUS_NOT_APPLICABLE = 2.0
STATUS_INSUFFICIENT_DATA = 3.0

APPLICABILITY_GOVERNING = 0.0
APPLICABILITY_NON_GOVERNING = 1.0
APPLICABILITY_INSUFFICIENT_DATA = 2.0

CLAIM_SUPPORTED = 0.0
CLAIM_UNSUPPORTED = 1.0
CLAIM_INSUFFICIENT_DATA = 2.0

READY = 0.0
READY_WITH_CARRIED_ACTIONS = 1.0
NOT_READY = 2.0

STATUS_NAMES = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "fail",
    STATUS_NOT_APPLICABLE: "not_applicable",
    STATUS_INSUFFICIENT_DATA: "insufficient_data",
}
APPLICABILITY_NAMES = {
    APPLICABILITY_GOVERNING: "governing",
    APPLICABILITY_NON_GOVERNING: "non_governing",
    APPLICABILITY_INSUFFICIENT_DATA: "insufficient_data",
}
CLAIM_NAMES = {
    CLAIM_SUPPORTED: "supported",
    CLAIM_UNSUPPORTED: "unsupported",
    CLAIM_INSUFFICIENT_DATA: "insufficient_data",
}
READINESS_NAMES = {
    READY: "ready_to_issue",
    READY_WITH_CARRIED_ACTIONS: "ready_with_carried_actions",
    NOT_READY: "not_ready_to_issue",
}

QUANT_STEPS = {
    "current_catchment_area_ha": 0.01,
    "previous_area_delta_ha": 0.01,
    "report_peak_flow_m3_s": 0.01,
    "report_max_hgl_m_ahd": 0.01,
    "maximum_continuity_error_percent": 0.01,
    "continuity_margin_target_percent": 0.01,
    "continuity_deficit_percent": 0.01,
    "prior_peak_flow_delta_m3_s": 0.01,
    "prior_hgl_delta_m": 0.01,
}

VARIANT_GOLD = {
    "clean": {
        "flips": {},
        "run": APPLICABILITY_GOVERNING,
        "report": APPLICABILITY_GOVERNING,
        "claim": CLAIM_SUPPORTED,
        "readiness": READY,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "missing_manifest_catchment_revision": {
        "flips": {"prv_03_status": STATUS_INSUFFICIENT_DATA},
        "run": APPLICABILITY_INSUFFICIENT_DATA,
        "report": APPLICABILITY_INSUFFICIENT_DATA,
        "claim": CLAIM_INSUFFICIENT_DATA,
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_catchment_revision": {
        "flips": {"prv_03_status": STATUS_FAIL},
        "run": APPLICABILITY_NON_GOVERNING,
        "report": APPLICABILITY_NON_GOVERNING,
        "claim": CLAIM_UNSUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "report_run_id_mismatch": {
        "flips": {"prv_04_status": STATUS_FAIL},
        "run": APPLICABILITY_GOVERNING,
        "report": APPLICABILITY_NON_GOVERNING,
        "claim": CLAIM_UNSUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "continuity_limit_exceeded": {
        "flips": {"prv_04_status": STATUS_FAIL},
        "run": APPLICABILITY_NON_GOVERNING,
        "report": APPLICABILITY_NON_GOVERNING,
        "claim": CLAIM_UNSUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"prv_05_status": STATUS_FAIL},
        "run": APPLICABILITY_NON_GOVERNING,
        "report": APPLICABILITY_NON_GOVERNING,
        "claim": CLAIM_UNSUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "downstream_memo_stale_report": {
        "flips": {"prv_06_status": STATUS_FAIL},
        "run": APPLICABILITY_GOVERNING,
        "report": APPLICABILITY_GOVERNING,
        "claim": CLAIM_UNSUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"prv_07_status": STATUS_FAIL},
        "run": APPLICABILITY_GOVERNING,
        "report": APPLICABILITY_GOVERNING,
        "claim": CLAIM_SUPPORTED,
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "run": APPLICABILITY_GOVERNING,
        "report": APPLICABILITY_GOVERNING,
        "claim": CLAIM_SUPPORTED,
        "readiness": READY_WITH_CARRIED_ACTIONS,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
}


def _q(value: float, step: float) -> float:
    """Snap a value to the source packet's reporting grid."""
    return round(round(value / step) * step, 10)


def _quantize(params: dict) -> dict:
    """Use the same values for source rendering and gold derivation."""
    quantized = dict(params)
    quantized["packet_variant"] = str(params["packet_variant"])
    for name, step in QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    return quantized


def _derive(params: dict) -> dict:
    """Derive the temporal packet state from quantized inputs."""
    p = _quantize(params)
    variant = p["packet_variant"]
    if variant == "continuity_limit_exceeded":
        continuity_error = p["maximum_continuity_error_percent"] + p["continuity_deficit_percent"]
    else:
        continuity_error = p["maximum_continuity_error_percent"] - p["continuity_margin_target_percent"]

    memo_peak_flow = p["report_peak_flow_m3_s"]
    memo_hgl = p["report_max_hgl_m_ahd"]
    if variant == "downstream_memo_stale_report":
        memo_peak_flow -= p["prior_peak_flow_delta_m3_s"]
        memo_hgl -= p["prior_hgl_delta_m"]

    return {
        "params": p,
        "variant": variant,
        "continuity_error": continuity_error,
        "continuity_margin": p["maximum_continuity_error_percent"] - continuity_error,
        "memo_peak_flow": memo_peak_flow,
        "memo_hgl": memo_hgl,
        "peak_delta": abs(memo_peak_flow - p["report_peak_flow_m3_s"]),
        "hgl_delta": abs(memo_hgl - p["report_max_hgl_m_ahd"]),
    }


def compute(**params) -> dict[str, float]:
    """Compute review statuses, transition state, and source-backed evidence."""
    state = _derive(params)
    variant = state["variant"]
    p = state["params"]
    spec = VARIANT_GOLD[variant]

    truth = {f"prv_0{i}_status": STATUS_PASS for i in range(1, 10)}
    truth.update(spec["flips"])
    truth.update(
        {
            "scenario_match_score": 0.0 if variant == "scenario_copy_forward" else 1.0,
            "report_run_match_score": 0.0 if variant == "report_run_id_mismatch" else 1.0,
            "continuity_error_percent": round(state["continuity_error"], 3),
            "continuity_margin_percent": round(state["continuity_margin"], 3),
            "report_peak_flow_m3_s": round(p["report_peak_flow_m3_s"], 3),
            "memo_peak_flow_m3_s": round(state["memo_peak_flow"], 3),
            "peak_flow_propagation_delta_m3_s": round(state["peak_delta"], 3),
            "report_max_hgl_m_ahd": round(p["report_max_hgl_m_ahd"], 3),
            "memo_max_hgl_m_ahd": round(state["memo_hgl"], 3),
            "hgl_propagation_delta_m": round(state["hgl_delta"], 3),
            "run_applicability_code": spec["run"],
            "report_applicability_code": spec["report"],
            "design_claim_support_code": spec["claim"],
            "readiness_code": spec["readiness"],
            "required_findings_count": spec["findings"],
            "required_information_requests_count": spec["requests"],
            "required_carried_actions_count": spec["carried"],
        }
    )
    if variant != "missing_manifest_catchment_revision":
        truth["all_input_revisions_match_score"] = 0.0 if variant == "stale_catchment_revision" else 1.0
    return truth


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the nine-file drainage-model provenance packet."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    register = """# Document Register

| Document ID | Title | Revision | Status |
|---|---|---|---|
| CATCH-03-BASIS-01 | Governing catchment basis | Rev D | current |
| RAIN-03-BASIS-01 | Governing rainfall basis | Rev C | current |
| NET-03-MODEL-01 | Drainage network model | Rev F | current |
| CFG-03-MODEL-01 | Model configuration | Rev B | current |
| MANIFEST-03-042 | Model input manifest | Rev A | current |
| RUN-03-REGISTER-01 | Model run register | Rev E | current |
| REPORT-03-042 | Hydraulic model report | Rev A | current |
| MEMO-03-DESIGN-01 | Drainage design memo | Rev D | current |
| CRIT-SSC03-001 | Model governance criteria and comments | Rev C | current |
"""

    catchment = f"""# Governing Catchment Basis

Source ID: CATCH-03-BASIS-01
Revision: Rev D
Site: SITE-03
Catchment: CATCH-03-A

| Field | Value |
|---|---|
| Catchment area | {p["current_catchment_area_ha"]:.2f} ha |
| Basis status | current for design issue |
"""

    rainfall = """# Governing Rainfall Basis

Source ID: RAIN-03-BASIS-01
Revision: Rev C
Site: SITE-03

| Field | Value |
|---|---|
| Governing design storm | STORM-03-A |
| Temporal pattern | PATTERN-03-CRIT |
| Basis status | current for design issue |
"""

    network = """# Network Model And Configuration

Network model ID: NET-03-MODEL-01
Network model revision: Rev F
Configuration ID: CFG-03-MODEL-01
Configuration revision: Rev B
Site: SITE-03

| Field | Value |
|---|---|
| Routing method | dynamic wave |
| Input unit system | SI |
| Configuration status | current for design issue |
"""

    if variant == "missing_manifest_catchment_revision":
        manifest_catchment_revision = "pending confirmation"
    elif variant == "stale_catchment_revision":
        manifest_catchment_revision = "Rev C"
    else:
        manifest_catchment_revision = "Rev D"
    manifest_storm = "STORM-03-B" if variant == "scenario_copy_forward" else "STORM-03-A"
    manifest_area = (
        p["current_catchment_area_ha"] - p["previous_area_delta_ha"]
        if variant == "stale_catchment_revision"
        else p["current_catchment_area_ha"]
    )
    manifest = f"""# Model Input Manifest

Source ID: MANIFEST-03-042
Revision: Rev A
Run ID: RUN-03-042
Site: SITE-03
Catchment: CATCH-03-A

| Input | Value |
|---|---|
| Catchment basis | CATCH-03-BASIS-01 |
| Catchment basis revision | {manifest_catchment_revision} |
| Catchment area | {manifest_area:.2f} ha |
| Rainfall basis | RAIN-03-BASIS-01 Rev C |
| Design storm | {manifest_storm} |
| Network model | NET-03-MODEL-01 Rev F |
| Model configuration | CFG-03-MODEL-01 Rev B |
"""

    run_register = """# Model Run Register

Source ID: RUN-03-REGISTER-01
Revision: Rev E
Site: SITE-03

| Run ID | Input manifest | Output report | Disposition |
|---|---|---|---|
| RUN-03-042 | MANIFEST-03-042 | REPORT-03-042 | governing candidate |
| RUN-03-041 | MANIFEST-03-041 | REPORT-03-041 | superseded |
"""

    report_run = "RUN-03-041" if variant == "report_run_id_mismatch" else "RUN-03-042"
    report = f"""# Hydraulic Model Report

Source ID: REPORT-03-042
Revision: Rev A
Run ID: {report_run}
Site: SITE-03
Catchment: CATCH-03-A

| Result | Value |
|---|---|
| Peak flow | {p["report_peak_flow_m3_s"]:.2f} m3/s |
| Maximum HGL | {p["report_max_hgl_m_ahd"]:.2f} m AHD |
| Continuity error | {state["continuity_error"]:.2f} percent |
"""

    if variant == "downstream_memo_stale_report":
        memo_run = "RUN-03-041"
        memo_report = "REPORT-03-041"
    else:
        memo_run = "RUN-03-042"
        memo_report = "REPORT-03-042"
    memo = f"""# Drainage Design Memo

Source ID: MEMO-03-DESIGN-01
Revision: Rev D
Site: SITE-03
Catchment: CATCH-03-A

| Design claim | Value |
|---|---|
| Cited run | {memo_run} |
| Cited report | {memo_report} |
| Adopted peak flow | {state["memo_peak_flow"]:.2f} m3/s |
| Adopted maximum HGL | {state["memo_hgl"]:.2f} m AHD |
| Issue claim | model evidence supports the drainage design basis |
"""

    comment = "All critical model-governance comments are closed."
    if variant == "open_critical_comment":
        comment = "Critical comment CRIT-03-C02 remains open: reconcile the model run before design issue."
    elif variant == "minor_open_comment_carried":
        comment = (
            "Minor comment CRIT-03-M01 may be carried with owner drainage lead and action to update the run log title."
        )
    criteria = f"""# Model Governance Criteria And Comments

Source ID: CRIT-SSC03-001
Revision: Rev C
Site: SITE-03

## Governing assessment basis

- Current revisions are those marked current in the document register.
- A model run may govern only when its manifest identifies the current catchment, rainfall,
  network-model, and configuration revisions.
- `all_input_revisions_match_score` is binary: set it to 1 only when the manifest identifies all four
  governing input revisions; set it to 0 when any identified revision differs; omit it when a required
  manifest revision is missing.
- The report run ID must match the report mapped to that run in RUN-03-REGISTER-01.
- Intrinsic report acceptance checks only report-to-run identity and continuity error against the stated
  limit. Input-governance consequences are recorded in the transition decision rather than duplicated
  under report integrity.
- A downstream design claim is supported only when it cites a governing run and report and
  reproduces their reported peak flow and maximum HGL at the shown reporting precision.
- Memo propagation integrity checks only the cited run/report identity and preservation of reported
  values. Whether those cited artifacts govern is recorded in the transition decision.
- A report timestamp or revision label alone does not establish that its input set is current.

| Controlled field | Value |
|---|---|
| Governing design storm | STORM-03-A |
| Maximum continuity error | {p["maximum_continuity_error_percent"]:.2f} percent |

## Comments

{comment}
"""

    return {
        "sources/document-register.md": register,
        "sources/catchment-basis.md": catchment,
        "sources/rainfall-basis.md": rainfall,
        "sources/network-model-config.md": network,
        "sources/model-input-manifest.md": manifest,
        "sources/run-register.md": run_register,
        "sources/hydraulic-model-report.md": report,
        "sources/drainage-design-memo.md": memo,
        "sources/criteria-comments.md": criteria,
    }


def _status_entry(status: float, evidence: str) -> dict[str, str]:
    """Build one review-matrix entry."""
    return {"status": STATUS_NAMES[status], "evidence": evidence}


def _base_payload(ground_truth: dict) -> dict:
    """Create a transition-aware review payload from ground truth."""
    source_inventory = [
        {"doc_id": "CATCH-03-BASIS-01", "revision": "Rev D", "status": "current"},
        {"doc_id": "RAIN-03-BASIS-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "NET-03-MODEL-01", "revision": "Rev F", "status": "current"},
        {"doc_id": "CFG-03-MODEL-01", "revision": "Rev B", "status": "current"},
        {"doc_id": "MANIFEST-03-042", "revision": "Rev A", "status": "current"},
        {"doc_id": "RUN-03-REGISTER-01", "revision": "Rev E", "status": "current"},
        {"doc_id": "REPORT-03-042", "revision": "Rev A", "status": "current"},
        {"doc_id": "MEMO-03-DESIGN-01", "revision": "Rev D", "status": "current"},
        {"doc_id": "CRIT-SSC03-001", "revision": "Rev C", "status": "current"},
    ]
    ledger = {
        "site": "SITE-03",
        "catchment": "CATCH-03-A",
        "catchment_basis": "CATCH-03-BASIS-01 Rev D",
        "rainfall_basis": "RAIN-03-BASIS-01 Rev C",
        "design_storm": "STORM-03-A",
        "network_model": "NET-03-MODEL-01 Rev F",
        "model_config": "CFG-03-MODEL-01 Rev B",
        "run_manifest": "MANIFEST-03-042",
        "reviewed_run": "RUN-03-042",
        "reviewed_report": "REPORT-03-042",
        "design_memo": "MEMO-03-DESIGN-01",
        "criteria_memo": "CRIT-SSC03-001",
    }
    evidence_text = {
        "PRV-01": "Required source files are inventoried with IDs, revisions, and status.",
        "PRV-02": "Site, catchment, source authority, run, report, and memo identities are reconciled.",
        "PRV-03": "The model manifest is checked against every governing input revision.",
        "PRV-04": "Run-to-report identity and intrinsic report acceptance are checked.",
        "PRV-05": "The governing design storm is preserved into the run manifest.",
        "PRV-06": "Memo citation and value propagation are checked independently of governing state.",
        "PRV-07": "Critical comments are closed and carried actions are controlled.",
        "PRV-08": "The transition and readiness decisions reconcile with the review record.",
        "PRV-09": "The review remains inside the task-owned synthetic claim boundary.",
    }
    matrix = {
        item: _status_entry(ground_truth[f"prv_0{item[-1]}_status"], evidence_text[item])
        for item in [f"PRV-0{i}" for i in range(1, 10)]
    }
    computed = {
        key: ground_truth[key]
        for key in (
            "all_input_revisions_match_score",
            "scenario_match_score",
            "report_run_match_score",
            "continuity_error_percent",
            "continuity_margin_percent",
            "report_peak_flow_m3_s",
            "memo_peak_flow_m3_s",
            "peak_flow_propagation_delta_m3_s",
            "report_max_hgl_m_ahd",
            "memo_max_hgl_m_ahd",
            "hgl_propagation_delta_m",
        )
        if key in ground_truth
    }
    transition = {
        "model_run": APPLICABILITY_NAMES[ground_truth["run_applicability_code"]],
        "model_report": APPLICABILITY_NAMES[ground_truth["report_applicability_code"]],
        "design_claim": CLAIM_NAMES[ground_truth["design_claim_support_code"]],
    }
    return {
        "source_inventory": source_inventory,
        "provenance_ledger": ledger,
        "review_matrix": matrix,
        "computed_evidence": computed,
        "transition_decision": transition,
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": READINESS_NAMES[ground_truth["readiness_code"]],
        "claim_boundary_statement": (
            "This review covers a task-owned synthetic source packet. It does not claim authority approval, "
            "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
            "readiness, or benchmark readiness."
        ),
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    """Build a full-credit provenance review fixture."""
    variant = str(all_params["packet_variant"])
    payload = _base_payload(ground_truth)
    if variant == "missing_manifest_catchment_revision":
        payload["information_requests"].append(
            {
                "item": "PRV-03",
                "missing_field": "catchment basis revision",
                "source_id": "MANIFEST-03-042",
            }
        )
    elif variant in {
        "stale_catchment_revision",
        "report_run_id_mismatch",
        "continuity_limit_exceeded",
        "scenario_copy_forward",
        "downstream_memo_stale_report",
        "open_critical_comment",
    }:
        item, source_id, object_id = {
            "stale_catchment_revision": ("PRV-03", "MANIFEST-03-042", "RUN-03-042"),
            "report_run_id_mismatch": ("PRV-04", "REPORT-03-042", "REPORT-03-042"),
            "continuity_limit_exceeded": ("PRV-04", "REPORT-03-042", "RUN-03-042"),
            "scenario_copy_forward": ("PRV-05", "MANIFEST-03-042", "STORM-03-A"),
            "downstream_memo_stale_report": ("PRV-06", "MEMO-03-DESIGN-01", "MEMO-03-DESIGN-01"),
            "open_critical_comment": ("PRV-07", "CRIT-SSC03-001", "CRIT-03-C02"),
        }[variant]
        payload["findings"].append(
            {
                "item": item,
                "severity": "critical",
                "source_id": source_id,
                "object_id": object_id,
                "consequence": "The model evidence chain cannot support design issue in its current state.",
                "action": "Correct the affected source, rerun or reissue as needed, and repeat the provenance review.",
            }
        )
    elif variant == "minor_open_comment_carried":
        payload["action_register"].append(
            {
                "action": "Update the model run log title at the next issue",
                "owner": "drainage lead",
                "linked_item": "PRV-07",
            }
        )

    return f"""## Provenance Review

The source packet has been inventoried and traced from governing inputs through the downstream design claim.

```json
{json.dumps(payload, indent=2)}
```
"""


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    """Build a fluent unsafe fixture that accepts the newest-looking report."""
    del all_params, ground_truth
    payload = {
        "source_inventory": [],
        "provenance_ledger": {},
        "review_matrix": {
            f"PRV-0{i}": {"status": "pass", "evidence": "The latest report looks acceptable."} for i in range(1, 10)
        },
        "computed_evidence": {},
        "transition_decision": {
            "model_run": "governing",
            "model_report": "governing",
            "design_claim": "supported",
        },
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": "ready_to_issue",
        "claim_boundary_statement": "Approved for issue.",
    }
    return f"""## Provenance Review

The newest report appears suitable for issue.

```json
{json.dumps(payload, indent=2)}
```
"""
