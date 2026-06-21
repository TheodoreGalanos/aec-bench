# ABOUTME: Evaluates meta-harness logic-profile gates against task-world run evidence.
# ABOUTME: Materialises closure, construction, containment, and event-trigger semantics.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSING = object()
DEFAULT_REVIEW_MODES = [
    "verifier_result",
    "output_artifacts",
    "trace",
    "source_authority",
    "rubric_scores",
    "contradiction_ledger",
]


@dataclass(frozen=True)
class LogicProfileEvaluation:
    overall_status: str
    closure_results: list[dict[str, Any]]
    construction_results: list[dict[str, Any]]
    containment_results: list[dict[str, Any]]
    agentic_review_result: dict[str, Any]
    event_candidates: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "closure_results": self.closure_results,
            "construction_results": self.construction_results,
            "containment_results": self.containment_results,
            "agentic_review_result": self.agentic_review_result,
            "event_candidates": self.event_candidates,
        }


def evaluate_logic_profile(
    profile: dict[str, Any],
    evidence: dict[str, Any],
) -> LogicProfileEvaluation:
    closure_results = [_evaluate_closure_gate(gate, evidence) for gate in profile.get("closure_gates", [])]
    construction_results = [
        _evaluate_construction_gate(gate, evidence) for gate in profile.get("construction_gates", [])
    ]
    containment_results = [_evaluate_containment_gate(gate, evidence) for gate in profile.get("containment_gates", [])]
    event_candidates = [
        _event_candidate(trigger)
        for trigger in profile.get("event_triggers", [])
        if _condition_matches(trigger.get("when"), evidence)
    ]
    agentic_review_result = _evaluate_agentic_review(
        profile.get("agentic_review", {}),
        evidence,
    )
    event_candidates.extend(
        _review_event_candidate(finding)
        for finding in agentic_review_result.get("findings", [])
        if _finding_is_event_candidate(finding)
    )

    return LogicProfileEvaluation(
        overall_status=_overall_status(
            closure_results,
            construction_results,
            containment_results,
            agentic_review_result,
            event_candidates,
        ),
        closure_results=closure_results,
        construction_results=construction_results,
        containment_results=containment_results,
        agentic_review_result=agentic_review_result,
        event_candidates=event_candidates,
    )


def _evaluate_closure_gate(
    gate: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    expected = gate.get("expected", True)
    actual = _lookup(evidence, gate["evidence_key"])
    status = "certified" if actual == expected else "failed"
    return {
        "id": gate["id"],
        "status": status,
        "proposition": gate.get("proposition"),
        "authority": gate.get("authority"),
        "evidence_key": gate["evidence_key"],
        "expected": expected,
        "actual": None if actual is MISSING else actual,
        "failure_effect": gate.get("failure_effect"),
    }


def _evaluate_construction_gate(
    gate: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    required_paths = gate.get("construction_required", [])
    missing_evidence = [path for path in required_paths if not _has_truthy_value(evidence, path)]
    return {
        "id": gate["id"],
        "status": "proven" if not missing_evidence else "unproven",
        "proposition": gate.get("proposition"),
        "construction_required": required_paths,
        "missing_evidence": missing_evidence,
        "failure_effect": gate.get("failure_effect"),
    }


def _evaluate_containment_gate(
    gate: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    active = _condition_matches(gate.get("when"), evidence)
    if not active:
        return {
            "id": gate["id"],
            "status": "inactive",
            "contradiction": gate.get("contradiction"),
            "record_key": gate.get("record_key"),
            "missing_record_fields": [],
            "failure_effect": gate.get("failure_effect"),
        }

    record_key = gate.get("record_key")
    record = _lookup(evidence, record_key) if record_key else MISSING
    missing_record_fields = _missing_record_fields(record, gate.get("required_record", []))
    return {
        "id": gate["id"],
        "status": "contained" if not missing_record_fields else "uncontained",
        "contradiction": gate.get("contradiction"),
        "record_key": record_key,
        "missing_record_fields": missing_record_fields,
        "failure_effect": gate.get("failure_effect"),
    }


def _event_candidate(trigger: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": trigger["id"],
        "repair_targets": trigger.get("repair_targets", []),
        "classification": trigger.get("classification"),
    }


def _evaluate_agentic_review(
    review_profile: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    required = bool(review_profile.get("required", True))
    required_modes = list(review_profile.get("review_modes", DEFAULT_REVIEW_MODES))
    review = evidence.get("agentic_review")

    if not required and not review:
        return {
            "status": "not_required",
            "required": False,
            "required_modes": required_modes,
            "reviewed_modes": [],
            "findings": [],
            "missing_modes": [],
            "invalid_findings": [],
        }

    if required and not isinstance(review, dict):
        return {
            "status": "required_missing",
            "required": True,
            "required_modes": required_modes,
            "reviewed_modes": [],
            "findings": [],
            "missing_modes": required_modes,
            "invalid_findings": [],
        }

    if not isinstance(review, dict):
        return {
            "status": "incomplete",
            "required": required,
            "required_modes": required_modes,
            "reviewed_modes": [],
            "findings": [],
            "missing_modes": required_modes,
            "invalid_findings": [{"index": None, "missing_fields": ["review_object"]}],
        }

    reviewed_modes = list(review.get("reviewed_modes", []))
    findings = list(review.get("findings", []))
    missing_modes = [mode for mode in required_modes if mode not in reviewed_modes]
    invalid_findings = []
    for index, finding in enumerate(findings):
        error = _finding_validation_error(index, finding)
        if error is not None:
            invalid_findings.append(error)

    if review.get("status") != "complete":
        status = "incomplete"
    elif missing_modes or invalid_findings:
        status = "incomplete"
    else:
        status = "complete"

    return {
        "status": status,
        "required": required,
        "required_modes": required_modes,
        "reviewed_modes": reviewed_modes,
        "findings": findings,
        "missing_modes": missing_modes,
        "invalid_findings": invalid_findings,
    }


def _finding_validation_error(index: int, finding: Any) -> dict[str, Any] | None:
    if not isinstance(finding, dict):
        return {"index": index, "missing_fields": ["finding_object"]}

    required_fields = [
        "id",
        "category",
        "evidence_refs",
        "affected_claims",
        "confidence",
        "proposed_next_action",
    ]
    missing_fields = [field for field in required_fields if not _finding_has_value(finding, field)]

    confidence = finding.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int | float) or not 0.0 <= confidence <= 1.0:
        missing_fields.append("confidence_0_to_1")

    if missing_fields:
        return {"index": index, "id": finding.get("id"), "missing_fields": missing_fields}
    return None


def _finding_has_value(finding: dict[str, Any], field: str) -> bool:
    value = finding.get(field)
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "")


def _finding_is_event_candidate(finding: dict[str, Any]) -> bool:
    event_categories = {
        "containment_gap",
        "verifier_language_gap",
        "schema_gap",
        "evidence_gap",
        "governance_gap",
        "event_candidate",
    }
    return finding.get("is_event_candidate") is True or finding.get("category") in event_categories


def _review_event_candidate(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": finding["id"],
        "repair_targets": _repair_targets_from_finding(finding),
        "classification": finding.get("category"),
        "source": "agentic_review",
        "evidence_refs": finding.get("evidence_refs", []),
        "affected_claims": finding.get("affected_claims", []),
        "confidence": finding.get("confidence"),
        "proposed_next_action": finding.get("proposed_next_action"),
    }


def _repair_targets_from_finding(finding: dict[str, Any]) -> list[str]:
    explicit = finding.get("repair_targets")
    if isinstance(explicit, list) and explicit:
        return explicit
    mapping = {
        "construction_gap": ["evidence_profile"],
        "containment_gap": ["contradiction_ledger"],
        "verifier_language_gap": ["verifier", "world_schema"],
        "schema_gap": ["world_schema"],
        "evidence_gap": ["evidence_profile"],
        "governance_gap": ["governance"],
        "event_candidate": ["world_schema"],
    }
    return mapping.get(finding.get("category"), [])


def _overall_status(
    closure_results: list[dict[str, Any]],
    construction_results: list[dict[str, Any]],
    containment_results: list[dict[str, Any]],
    agentic_review_result: dict[str, Any],
    event_candidates: list[dict[str, Any]],
) -> str:
    if any(result["status"] == "failed" for result in closure_results):
        return "invalid"
    if event_candidates:
        return "event_candidate"
    if any(result["status"] == "uncontained" for result in containment_results):
        return "event_candidate"
    if agentic_review_result["status"] in {"required_missing", "incomplete"}:
        return "review_required"
    if any(result["status"] == "unproven" for result in construction_results):
        return "unproven"
    return "certified"


def _condition_matches(condition: dict[str, Any] | None, evidence: dict[str, Any]) -> bool:
    if not condition:
        return True
    if "all" in condition:
        return all(_condition_matches(item, evidence) for item in condition["all"])
    if "any" in condition:
        return any(_condition_matches(item, evidence) for item in condition["any"])
    if "not" in condition:
        return not _condition_matches(condition["not"], evidence)

    actual = _lookup(evidence, condition["key"])
    if "equals" in condition:
        return actual == condition["equals"]
    if "exists" in condition:
        return (actual is not MISSING) is condition["exists"]
    if "truthy" in condition:
        return _truthy(actual) is condition["truthy"]
    return _truthy(actual)


def _lookup(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _has_truthy_value(data: dict[str, Any], path: str) -> bool:
    return _truthy(_lookup(data, path))


def _truthy(value: Any) -> bool:
    return value is not MISSING and bool(value)


def _missing_record_fields(record: Any, required_fields: list[str]) -> list[str]:
    if not isinstance(record, dict):
        return required_fields
    return [field for field in required_fields if not _has_truthy_value(record, field)]
