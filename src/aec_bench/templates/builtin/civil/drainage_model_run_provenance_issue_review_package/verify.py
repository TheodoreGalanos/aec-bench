# ABOUTME: Stage-gated verifier for the SSC-03 model-run provenance review package.
# ABOUTME: Grades revision tracing, state transitions, linkage, readiness, and claim boundaries.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

GATE_WEIGHTS = {
    "matrix": 0.25,
    "evidence": 0.15,
    "provenance": 0.20,
    "transition": 0.15,
    "linkage": 0.10,
    "readiness": 0.10,
    "identity_claims": 0.05,
}

STATUS_NAMES = {0.0: "pass", 1.0: "fail", 2.0: "not_applicable", 3.0: "insufficient_data"}
READINESS_NAMES = {0.0: "ready_to_issue", 1.0: "ready_with_carried_actions", 2.0: "not_ready_to_issue"}
APPLICABILITY_NAMES = {0.0: "governing", 1.0: "non_governing", 2.0: "insufficient_data"}
CLAIM_NAMES = {0.0: "supported", 1.0: "unsupported", 2.0: "insufficient_data"}

VALID_STATUSES = set(STATUS_NAMES.values())
VALID_READINESS = set(READINESS_NAMES.values())
PRV_ITEMS = [f"PRV-0{i}" for i in range(1, 10)]

ITEM_EVIDENCE = {
    "PRV-03": ["all_input_revisions_match_score"],
    "PRV-04": ["report_run_match_score", "continuity_error_percent", "continuity_margin_percent"],
    "PRV-05": ["scenario_match_score"],
    "PRV-06": [
        "report_peak_flow_m3_s",
        "memo_peak_flow_m3_s",
        "peak_flow_propagation_delta_m3_s",
        "report_max_hgl_m_ahd",
        "memo_max_hgl_m_ahd",
        "hgl_propagation_delta_m",
    ],
}

EVIDENCE_KEYS = [
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
]

REQUIRED_SOURCE_RECORDS = {
    "catch-03-basis-01": "rev d",
    "rain-03-basis-01": "rev c",
    "net-03-model-01": "rev f",
    "cfg-03-model-01": "rev b",
    "manifest-03-042": "rev a",
    "run-03-register-01": "rev e",
    "report-03-042": "rev a",
    "memo-03-design-01": "rev d",
    "crit-ssc03-001": "rev c",
}

REQUIRED_LEDGER_TOKENS = [
    "site-03",
    "catch-03-a",
    "catch-03-basis-01",
    "rain-03-basis-01",
    "storm-03-a",
    "net-03-model-01",
    "cfg-03-model-01",
    "manifest-03-042",
    "run-03-042",
    "report-03-042",
    "memo-03-design-01",
    "crit-ssc03-001",
]

VARIANT_REQUEST_TOKENS = {
    "missing_manifest_catchment_revision": ("catchment", "basis", "revision", "manifest-03-042"),
}


def extract_json_block(text: str) -> dict | None:
    """Return the final fenced JSON object in a response."""
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def value_close(expected: float, actual: object) -> bool:
    """Compare a numeric response to source reporting precision."""
    try:
        actual_float = float(actual)
    except (TypeError, ValueError):
        return False
    return math.isclose(actual_float, expected, rel_tol=0.02, abs_tol=0.01)


def item_gold_status(ground_truth: dict, item_id: str) -> str:
    """Map one numeric gold status to the response vocabulary."""
    return STATUS_NAMES[ground_truth[f"prv_0{item_id[-1]}_status"]]


def matching_requests(payload: dict, item_id: str, tokens: tuple[str, ...]) -> list[dict]:
    """Find complete information requests linked to one matrix item."""
    matches = []
    for request in payload.get("information_requests", []):
        if not isinstance(request, dict):
            continue
        if str(request.get("item", "")).strip().upper() != item_id:
            continue
        missing_field = str(request.get("missing_field", "")).strip()
        source_id = str(request.get("source_id", "")).strip()
        if not missing_field or not source_id:
            continue
        haystack = f"{missing_field} {source_id}".lower()
        if tokens and not all(token in haystack for token in tokens):
            continue
        matches.append(request)
    return matches


def matching_findings(payload: dict, item_id: str) -> list[dict]:
    """Find complete findings linked to one matrix item."""
    matches = []
    for finding in payload.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if str(finding.get("item", "")).strip().upper() != item_id:
            continue
        required = ("source_id", "object_id", "consequence", "action")
        if all(str(finding.get(field, "")).strip() for field in required):
            matches.append(finding)
    return matches


def score_matrix(payload: dict, ground_truth: dict, variant: str) -> tuple[float, dict]:
    """Grade matrix statuses with evidence-dependent credit."""
    matrix = payload.get("review_matrix", {})
    evidence = payload.get("computed_evidence", {})
    if not isinstance(matrix, dict):
        matrix = {}
    if not isinstance(evidence, dict):
        evidence = {}

    items: dict[str, float] = {}
    for item_id in PRV_ITEMS:
        entry = matrix.get(item_id)
        status = str(entry.get("status", "")).strip().lower() if isinstance(entry, dict) else ""
        gold_status = item_gold_status(ground_truth, item_id)
        item_score = 1.0 if status == gold_status else 0.0

        if item_score == 1.0 and item_id in ITEM_EVIDENCE:
            if gold_status == "insufficient_data":
                tokens = VARIANT_REQUEST_TOKENS.get(variant, ())
                if not matching_requests(payload, item_id, tokens):
                    item_score = 0.0
            else:
                for key in ITEM_EVIDENCE[item_id]:
                    if key not in ground_truth:
                        continue
                    if not value_close(ground_truth[key], evidence.get(key)):
                        item_score = 0.0
                        break
        items[item_id] = item_score

    score = sum(items.values()) / len(PRV_ITEMS)
    return score, {"score": round(score * GATE_WEIGHTS["matrix"], 4), "items": items}


def score_evidence(payload: dict, ground_truth: dict) -> tuple[float, dict]:
    """Grade every evidence key that is knowable in the packet."""
    evidence = payload.get("computed_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    keys = [key for key in EVIDENCE_KEYS if key in ground_truth]
    per_key = {key: 1.0 if value_close(ground_truth[key], evidence.get(key)) else 0.0 for key in keys}
    score = sum(per_key.values()) / len(keys) if keys else 0.0
    return score, {"score": round(score * GATE_WEIGHTS["evidence"], 4), "keys": per_key}


def score_provenance(payload: dict) -> tuple[float, dict]:
    """Grade registered sources and the complete model-evidence chain."""
    inventory = payload.get("source_inventory", [])
    inventory_text = json.dumps(inventory).lower() if isinstance(inventory, list) else ""
    inventory_checks = {
        doc_id: 1.0 if doc_id in inventory_text and revision in inventory_text else 0.0
        for doc_id, revision in REQUIRED_SOURCE_RECORDS.items()
    }
    inventory_score = sum(inventory_checks.values()) / len(inventory_checks)

    ledger = payload.get("provenance_ledger", {})
    ledger_text = json.dumps(ledger).lower() if isinstance(ledger, dict) else ""
    ledger_checks = {token: 1.0 if token in ledger_text else 0.0 for token in REQUIRED_LEDGER_TOKENS}
    ledger_score = sum(ledger_checks.values()) / len(ledger_checks)

    score = (inventory_score + ledger_score) / 2.0
    return score, {
        "score": round(score * GATE_WEIGHTS["provenance"], 4),
        "inventory": inventory_checks,
        "ledger": ledger_checks,
    }


def score_transition(payload: dict, ground_truth: dict) -> tuple[float, dict]:
    """Grade the propagated state of run, report, and design claim."""
    transition = payload.get("transition_decision", {})
    if not isinstance(transition, dict):
        transition = {}
    expected = {
        "model_run": APPLICABILITY_NAMES[ground_truth["run_applicability_code"]],
        "model_report": APPLICABILITY_NAMES[ground_truth["report_applicability_code"]],
        "design_claim": CLAIM_NAMES[ground_truth["design_claim_support_code"]],
    }
    states = {
        key: 1.0 if str(transition.get(key, "")).strip().lower() == value else 0.0 for key, value in expected.items()
    }
    score = sum(states.values()) / len(states)
    return score, {"score": round(score * GATE_WEIGHTS["transition"], 4), "states": states}


def score_linkage(payload: dict, ground_truth: dict, variant: str) -> tuple[float, dict]:
    """Grade matrix coverage and register linkage."""
    matrix = payload.get("review_matrix", {})
    if not isinstance(matrix, dict):
        matrix = {}
    statuses = {
        item: str(entry.get("status", "")).strip().lower() if isinstance(entry, dict) else ""
        for item, entry in matrix.items()
    }
    coverage_ok = set(matrix) == set(PRV_ITEMS) and all(status in VALID_STATUSES for status in statuses.values())

    findings = payload.get("findings", [])
    complete_findings = (
        [
            finding
            for finding in findings
            if isinstance(finding, dict)
            and all(
                str(finding.get(field, "")).strip()
                for field in ("item", "source_id", "object_id", "consequence", "action")
            )
        ]
        if isinstance(findings, list)
        else []
    )
    fail_linkage_ok = all(
        matching_findings(payload, item) for item, status in statuses.items() if status == "fail"
    ) and all(statuses.get(str(finding["item"]).strip().upper()) == "fail" for finding in complete_findings)

    missing_linkage_ok = True
    for item, status in statuses.items():
        if status == "insufficient_data" and not matching_requests(payload, item, ()):
            missing_linkage_ok = False
        if status == "not_applicable":
            entry = matrix.get(item, {})
            reason = str(entry.get("evidence", "")).strip() if isinstance(entry, dict) else ""
            if not reason:
                missing_linkage_ok = False

    requests = payload.get("information_requests", [])
    complete_requests = (
        [
            request
            for request in requests
            if isinstance(request, dict)
            and all(str(request.get(field, "")).strip() for field in ("item", "missing_field", "source_id"))
        ]
        if isinstance(requests, list)
        else []
    )
    if not all(
        statuses.get(str(request["item"]).strip().upper()) == "insufficient_data" for request in complete_requests
    ):
        missing_linkage_ok = False

    required_findings = int(ground_truth.get("required_findings_count", 0.0))
    required_requests = int(ground_truth.get("required_information_requests_count", 0.0))
    required_carried = int(ground_truth.get("required_carried_actions_count", 0.0))
    gold_registers_ok = True

    gold_fail_items = [item for item in PRV_ITEMS if item_gold_status(ground_truth, item) == "fail"]
    if required_findings != len(gold_fail_items) or len(complete_findings) != required_findings:
        gold_registers_ok = False
    for item in gold_fail_items:
        if not matching_findings(payload, item):
            gold_registers_ok = False

    gold_missing_items = [item for item in PRV_ITEMS if item_gold_status(ground_truth, item) == "insufficient_data"]
    request_tokens = VARIANT_REQUEST_TOKENS.get(variant, ())
    if required_requests != len(gold_missing_items) or len(complete_requests) != required_requests:
        gold_registers_ok = False
    for item in gold_missing_items:
        if not matching_requests(payload, item, request_tokens):
            gold_registers_ok = False

    actions = payload.get("action_register", [])
    complete_actions = (
        [
            action
            for action in actions
            if isinstance(action, dict)
            and str(action.get("action", "")).strip()
            and str(action.get("owner", "")).strip()
            and str(action.get("linked_item", "")).strip().upper() in PRV_ITEMS
        ]
        if isinstance(actions, list)
        else []
    )
    if len(complete_actions) != required_carried:
        gold_registers_ok = False

    checks = {
        "matrix_coverage": 1.0 if coverage_ok else 0.0,
        "fail_findings_linked": 1.0 if fail_linkage_ok else 0.0,
        "missing_and_na_linked": 1.0 if missing_linkage_ok else 0.0,
        "gold_required_registers": 1.0 if gold_registers_ok else 0.0,
    }
    score = sum(checks.values()) / len(checks)
    return score, {"score": round(score * GATE_WEIGHTS["linkage"], 4), "checks": checks}


def score_readiness(payload: dict, ground_truth: dict, evidence_score: float) -> tuple[float, dict]:
    """Grade readiness against matrix, transitions, actions, and evidence."""
    decision = str(payload.get("readiness_decision", "")).strip().lower()
    expected = READINESS_NAMES[ground_truth["readiness_code"]]
    reasons: list[str] = []
    if decision not in VALID_READINESS:
        reasons.append("readiness decision missing or outside the controlled vocabulary")
    elif decision != expected:
        reasons.append("readiness decision does not match the packet state")

    matrix = payload.get("review_matrix", {})
    statuses = []
    if isinstance(matrix, dict):
        statuses = [
            str(entry.get("status", "")).strip().lower() for entry in matrix.values() if isinstance(entry, dict)
        ]
    if any(status in {"fail", "insufficient_data"} for status in statuses) and decision != "not_ready_to_issue":
        reasons.append("decision claims readiness while the matrix has blockers")

    transition = payload.get("transition_decision", {})
    transition_values = set(transition.values()) if isinstance(transition, dict) else set()
    has_unsupported_transition = bool(
        transition_values.intersection({"non_governing", "unsupported", "insufficient_data"})
    )
    if has_unsupported_transition and decision != "not_ready_to_issue":
        reasons.append("decision claims readiness while the transition contains unsupported evidence")

    actions = payload.get("action_register", [])
    if isinstance(actions, list) and actions and decision == "ready_to_issue":
        reasons.append("decision ignores carried actions")
    if decision in {"ready_to_issue", "ready_with_carried_actions"} and evidence_score < 0.8:
        reasons.append("ready decision lacks source-backed evidence")

    score = 1.0 if not reasons else 0.0
    return score, {"score": round(score * GATE_WEIGHTS["readiness"], 4), "reasons": reasons}


def _claim_boundary_supported(statement: str) -> bool:
    """Accept equivalent wording for every prohibited claim category."""
    text = re.sub(r"[^a-z0-9]+", " ", statement.lower()).strip()
    concept_groups = (
        ("authority approval", "regulatory approval", "authority acceptance", "ahj approval", "authority ahj approval"),
        (
            "accepted project evidence",
            "acceptance as project evidence",
            "acceptance of project evidence",
            "acceptance of any project evidence",
            "project of record evidence",
        ),
        (
            "full standards compliance",
            "standards compliance",
            "compliance with any standard",
            "compliance with any named standard",
            "compliance with drainage engineering standards",
            "compliance certification",
            "certification of standards compliance",
            "regulatory or standards compliance",
        ),
        (
            "source pack hardening",
            "hardening of the source pack",
            "hardening of the source packet",
            "hardening or certification of the source packet",
            "validation or hardening of the source packet",
            "harden or validate source",
            "source pack is hardened",
        ),
        (
            "executable verifier readiness",
            "executable verification readiness",
            "readiness for use in an executable verifier",
            "readiness of any executable verifier",
            "readiness for executable verification",
            "ready for executable verification",
            "verified as executable",
        ),
        (
            "benchmark readiness",
            "benchmark certification",
            "benchmark compliance",
            "benchmark testing",
            "benchmark standard",
        ),
    )
    return (
        bool(text)
        and "task owned synthetic" in text
        and any(phrase in text for phrase in ("does not", "do not", "not constitute", "not represent"))
        and all(any(term in text for term in group) for group in concept_groups)
    )


def score_identity_claims(payload: dict) -> tuple[float, dict]:
    """Grade stable packet identity and conservative claim boundaries."""
    ledger = payload.get("provenance_ledger", payload.get("identity_ledger", {}))
    ledger_text = json.dumps(ledger).lower() if isinstance(ledger, dict) else ""
    ledger_hits = sum(1.0 for token in REQUIRED_LEDGER_TOKENS if token in ledger_text)
    ledger_score = ledger_hits / len(REQUIRED_LEDGER_TOKENS)
    statement = str(payload.get("claim_boundary_statement", "")).strip()
    claims_ok = _claim_boundary_supported(statement)
    checks = {"identity_ledger": ledger_score, "claim_boundary": 1.0 if claims_ok else 0.0}
    score = sum(checks.values()) / len(checks)
    return score, {"score": round(score * GATE_WEIGHTS["identity_claims"], 4), "checks": checks}


def zero_details() -> dict:
    """Return localized zero scores for an unparseable response."""
    return {
        "gates": {
            "matrix": {"score": 0.0, "items": {item: 0.0 for item in PRV_ITEMS}},
            "evidence": {"score": 0.0, "keys": {}},
            "provenance": {"score": 0.0, "inventory": {}, "ledger": {}},
            "transition": {"score": 0.0, "states": {}},
            "linkage": {"score": 0.0, "checks": {}},
            "readiness": {"score": 0.0, "reasons": ["no parseable structured answer"]},
            "identity_claims": {"score": 0.0, "checks": {}},
        },
        "variant": None,
    }


def score_payload(payload: dict, instance: dict) -> tuple[float, dict]:
    """Score one structured response against the generated instance."""
    ground_truth = instance["ground_truth"]
    variant = str(instance["all_params"]["packet_variant"])
    matrix_score, matrix_details = score_matrix(payload, ground_truth, variant)
    evidence_score, evidence_details = score_evidence(payload, ground_truth)
    provenance_score, provenance_details = score_provenance(payload)
    transition_score, transition_details = score_transition(payload, ground_truth)
    linkage_score, linkage_details = score_linkage(payload, ground_truth, variant)
    readiness_score, readiness_details = score_readiness(payload, ground_truth, evidence_score)
    identity_score, identity_details = score_identity_claims(payload)

    component_scores = {
        "matrix": matrix_score,
        "evidence": evidence_score,
        "provenance": provenance_score,
        "transition": transition_score,
        "linkage": linkage_score,
        "readiness": readiness_score,
        "identity_claims": identity_score,
    }
    reward = sum(component_scores[name] * GATE_WEIGHTS[name] for name in GATE_WEIGHTS)
    details = {
        "gates": {
            "matrix": matrix_details,
            "evidence": evidence_details,
            "provenance": provenance_details,
            "transition": transition_details,
            "linkage": linkage_details,
            "readiness": readiness_details,
            "identity_claims": identity_details,
        },
        "variant": variant,
    }
    return round(reward, 2), details


def write_result(reward: float, details: dict, path: Path) -> None:
    """Write reward and localized details beside it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": reward}))
    (path.parent / "details.json").write_text(json.dumps(details, indent=2))


def main() -> None:
    """Verify the generated task response."""
    parser = argparse.ArgumentParser(description="Verify a drainage model-run provenance review response")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()
    try:
        instance = json.loads((Path(__file__).resolve().parent / "instance.json").read_text())
        if not args.input.exists() or args.input.stat().st_size == 0:
            write_result(0.0, zero_details(), args.output)
            return
        payload = extract_json_block(args.input.read_text())
        if payload is None:
            write_result(0.0, zero_details(), args.output)
            return
        reward, details = score_payload(payload, instance)
        write_result(reward, details, args.output)
    except Exception:
        write_result(0.0, zero_details(), args.output)


if __name__ == "__main__":
    main()
