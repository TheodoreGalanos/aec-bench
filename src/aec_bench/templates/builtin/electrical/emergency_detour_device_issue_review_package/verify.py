# ABOUTME: Stage-gated verifier for the emergency detour device issue review package.
# ABOUTME: Grades matrix statuses, recomputed evidence, linkage, readiness, and claim boundaries.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

GATE_WEIGHTS = {
    "matrix": 0.30,
    "evidence": 0.20,
    "linkage": 0.20,
    "readiness": 0.20,
    "identity_claims": 0.10,
}

STATUS_NAMES = {0.0: "pass", 1.0: "fail", 2.0: "not_applicable", 3.0: "insufficient_data"}
READINESS_NAMES = {0.0: "ready_to_issue", 1.0: "ready_with_carried_actions", 2.0: "not_ready_to_issue"}
VALID_STATUSES = set(STATUS_NAMES.values())
VALID_READINESS = set(READINESS_NAMES.values())

RLR_ITEMS = [f"RLR-0{i}" for i in range(1, 10)]

ITEM_EVIDENCE = {
    "RLR-03": [
        "vms_reading_time_s",
        "vms_message_margin_chars",
    ],
    "RLR-04": [
        "battery_runtime_h",
        "battery_margin_h",
    ],
    "RLR-06": [
        "required_network_mbps",
        "network_headroom_mbps",
        "rf_received_power_dbm",
        "rf_link_margin_db",
        "feeder_voltage_drop_percent",
        "voltage_drop_margin_percent",
    ],
}

EVIDENCE_KEYS = [
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
]

VARIANT_REQUEST_TOKENS = {
    "missing_closure_duration": ("closure", "duration", "ops-ssc01-004", "detour"),
}

REQUIRED_LEDGER_TOKENS = [
    "ops-ssc01-004",
    "detour-ssc01-004",
    "tmp-ssc01-004",
    "vms-ssc01-004",
    "cctv-ssc01-004",
    "rf-ssc01-004",
    "net-ssc01-004",
    "pwr-ssc01-004",
    "msg-ssc01-004",
]


def extract_json_block(text: str) -> dict | None:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def value_close(expected: float, actual: object) -> bool:
    try:
        actual_float = float(actual)
    except (TypeError, ValueError):
        return False
    return math.isclose(actual_float, expected, rel_tol=0.02, abs_tol=0.01)


def item_gold_status(ground_truth: dict, item_id: str) -> str:
    code = ground_truth[f"rlr_0{item_id[-1]}_status"]
    return STATUS_NAMES[code]


def matching_requests(payload: dict, item_id: str, tokens: tuple[str, ...]) -> list[dict]:
    found = []
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
        found.append(request)
    return found


def matching_findings(payload: dict, item_id: str) -> list[dict]:
    found = []
    for finding in payload.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if str(finding.get("item", "")).strip().upper() != item_id:
            continue
        required_fields = ("source_id", "object_id", "consequence", "action")
        if all(str(finding.get(field, "")).strip() for field in required_fields):
            found.append(finding)
    return found


def score_matrix(payload: dict, ground_truth: dict, variant: str) -> tuple[float, dict]:
    matrix = payload.get("review_matrix", {})
    if not isinstance(matrix, dict):
        matrix = {}
    evidence = payload.get("computed_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}

    items: dict[str, float] = {}
    for item_id in RLR_ITEMS:
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

    score = sum(items.values()) / len(RLR_ITEMS)
    return score, {"score": round(score * GATE_WEIGHTS["matrix"], 4), "items": items}


def score_evidence(payload: dict, ground_truth: dict) -> tuple[float, dict]:
    evidence = payload.get("computed_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}

    keys = [key for key in EVIDENCE_KEYS if key in ground_truth]
    per_key: dict[str, float] = {}
    for key in keys:
        per_key[key] = 1.0 if value_close(ground_truth[key], evidence.get(key)) else 0.0

    score = sum(per_key.values()) / len(keys) if keys else 0.0
    return score, {"score": round(score * GATE_WEIGHTS["evidence"], 4), "keys": per_key}


def score_linkage(payload: dict, ground_truth: dict, variant: str) -> tuple[float, dict]:
    matrix = payload.get("review_matrix", {})
    if not isinstance(matrix, dict):
        matrix = {}

    statuses: dict[str, str] = {}
    for item_id in RLR_ITEMS:
        entry = matrix.get(item_id)
        statuses[item_id] = str(entry.get("status", "")).strip().lower() if isinstance(entry, dict) else ""

    coverage_ok = set(matrix) == set(RLR_ITEMS) and all(status in VALID_STATUSES for status in statuses.values())
    fail_linkage_ok = all(
        matching_findings(payload, item_id) for item_id, status in statuses.items() if status == "fail"
    )

    id_na_ok = True
    for item_id, status in statuses.items():
        if status == "insufficient_data" and not matching_requests(payload, item_id, ()):
            id_na_ok = False
        if status == "not_applicable":
            entry = matrix.get(item_id, {})
            reason = str(entry.get("reason", entry.get("evidence", ""))).strip() if isinstance(entry, dict) else ""
            if not reason:
                id_na_ok = False

    required_findings = int(ground_truth.get("required_findings_count", 0.0))
    required_requests = int(ground_truth.get("required_information_requests_count", 0.0))
    required_carried = int(ground_truth.get("required_carried_actions_count", 0.0))

    gold_ok = True
    gold_fail_items = [item for item in RLR_ITEMS if item_gold_status(ground_truth, item) == "fail"]
    for item_id in gold_fail_items:
        if len(matching_findings(payload, item_id)) < 1:
            gold_ok = False
    if required_findings > 0 and not gold_fail_items:
        gold_ok = False

    gold_id_items = [item for item in RLR_ITEMS if item_gold_status(ground_truth, item) == "insufficient_data"]
    tokens = VARIANT_REQUEST_TOKENS.get(variant, ())
    for item_id in gold_id_items:
        if len(matching_requests(payload, item_id, tokens)) < required_requests:
            gold_ok = False

    if required_carried > 0:
        register = payload.get("action_register", [])
        carried = [
            action
            for action in register
            if isinstance(action, dict)
            and str(action.get("owner", "")).strip()
            and str(action.get("action", "")).strip()
        ]
        if len(carried) < required_carried:
            gold_ok = False

    checks = {
        "matrix_coverage": 1.0 if coverage_ok else 0.0,
        "fail_findings_linked": 1.0 if fail_linkage_ok else 0.0,
        "insufficient_data_and_na_linked": 1.0 if id_na_ok else 0.0,
        "gold_required_registers": 1.0 if gold_ok else 0.0,
    }
    score = sum(checks.values()) / len(checks)
    return score, {"score": round(score * GATE_WEIGHTS["linkage"], 4), "checks": checks}


def score_readiness(payload: dict, ground_truth: dict, evidence_score: float) -> tuple[float, dict]:
    decision = str(payload.get("readiness_decision", "")).strip().lower()
    gold_decision = READINESS_NAMES[ground_truth["readiness_code"]]
    reasons: list[str] = []

    if decision not in VALID_READINESS:
        reasons.append("readiness decision missing or outside the controlled vocabulary")
    elif decision != gold_decision:
        reasons.append("readiness decision does not match the packet state")

    matrix = payload.get("review_matrix", {})
    statuses = []
    if isinstance(matrix, dict):
        for entry in matrix.values():
            if isinstance(entry, dict):
                statuses.append(str(entry.get("status", "")).strip().lower())

    register = payload.get("action_register", [])
    has_blockers = any(status in {"fail", "insufficient_data"} for status in statuses)
    if has_blockers and decision != "not_ready_to_issue":
        reasons.append("decision claims readiness while the matrix has unresolved failures or missing data")
    if not has_blockers and isinstance(register, list) and register and decision == "ready_to_issue":
        reasons.append("decision ignores carried actions in the action register")

    if evidence_score < 0.5:
        reasons.append("readiness decision is not supported by recomputed evidence")

    score = 1.0 if not reasons else 0.0
    return score, {"score": round(score * GATE_WEIGHTS["readiness"], 4), "reasons": reasons}


def _claim_boundary_supported(statement: str) -> bool:
    text = re.sub(r"[^a-z0-9]+", " ", statement.lower()).strip()
    concept_groups = (
        (
            "authority approval",
            "regulatory approval",
            "authority acceptance",
            "ahj approval",
            "authority ahj approval",
        ),
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
            "compliance with any named standard",
            "compliance certification",
            "certification of standards compliance",
            "regulatory or standards compliance",
        ),
        (
            "source pack hardening",
            "hardening of the source pack",
            "hardening of the source packet",
            "validation or hardening of the source packet",
            "harden or validate source",
        ),
        (
            "executable verifier readiness",
            "executable verification readiness",
            "readiness for use in an executable verifier",
            "readiness for executable verification",
            "ready for executable verification",
        ),
        ("benchmark readiness", "benchmark certification", "benchmark compliance", "benchmark testing"),
    )
    return (
        bool(text)
        and "task owned synthetic" in text
        and any(phrase in text for phrase in ("does not", "do not", "not constitute", "not represent"))
        and all(any(term in text for term in group) for group in concept_groups)
    )


def score_identity_claims(payload: dict) -> tuple[float, dict]:
    ledger = payload.get("identity_ledger", {})
    ledger_text = json.dumps(ledger).lower() if isinstance(ledger, dict) else ""
    ledger_hits = sum(1.0 for token in REQUIRED_LEDGER_TOKENS if token in ledger_text)
    ledger_score = ledger_hits / len(REQUIRED_LEDGER_TOKENS) if REQUIRED_LEDGER_TOKENS else 0.0

    statement = str(payload.get("claim_boundary_statement", "")).strip().lower()
    claims_ok = _claim_boundary_supported(statement)

    checks = {"identity_ledger": ledger_score, "claim_boundary": 1.0 if claims_ok else 0.0}
    score = sum(checks.values()) / len(checks)
    return score, {"score": round(score * GATE_WEIGHTS["identity_claims"], 4), "checks": checks}


def zero_details() -> dict:
    return {
        "gates": {
            "matrix": {"score": 0.0, "items": {item: 0.0 for item in RLR_ITEMS}},
            "evidence": {"score": 0.0, "keys": {}},
            "linkage": {"score": 0.0, "checks": {}},
            "readiness": {"score": 0.0, "reasons": ["no parseable structured answer"]},
            "identity_claims": {"score": 0.0, "checks": {}},
        },
        "variant": None,
    }


def score_payload(payload: dict, instance: dict) -> tuple[float, dict]:
    ground_truth = instance["ground_truth"]
    variant = str(instance["all_params"]["packet_variant"])

    matrix_score, matrix_details = score_matrix(payload, ground_truth, variant)
    evidence_score, evidence_details = score_evidence(payload, ground_truth)
    linkage_score, linkage_details = score_linkage(payload, ground_truth, variant)
    readiness_score, readiness_details = score_readiness(payload, ground_truth, evidence_score)
    identity_score, identity_details = score_identity_claims(payload)

    reward = (
        matrix_score * GATE_WEIGHTS["matrix"]
        + evidence_score * GATE_WEIGHTS["evidence"]
        + linkage_score * GATE_WEIGHTS["linkage"]
        + readiness_score * GATE_WEIGHTS["readiness"]
        + identity_score * GATE_WEIGHTS["identity_claims"]
    )
    details = {
        "gates": {
            "matrix": matrix_details,
            "evidence": evidence_details,
            "linkage": linkage_details,
            "readiness": readiness_details,
            "identity_claims": identity_details,
        },
        "variant": variant,
    }
    return round(reward, 2), details


def write_result(reward: float, details: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": reward}))
    (path.parent / "details.json").write_text(json.dumps(details, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an emergency detour device issue review response")
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
