# ABOUTME: Projects bounded public dam-seepage learning feedback and named outcome scores.
# ABOUTME: Keeps escalation-boundary semantics with the dam-world task owner and outside Learning Studies contracts.

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageAction,
    SeepageResponse,
)

DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID = "dam-escalation-boundary-public-feedback"

_DAM_TASK_PREFIX = f"world/{DAM_SEEPAGE_TASK_WORLD_ID}/"
_SELECTED_EVALUATION_FIELDS = (
    "response_correct",
    "evidence_complete",
    "all_scheduled_readings_reviewed",
    "measurement_system_checked",
    "latest_downstream_area_inspected",
)
_PUBLIC_VALIDITY_FIELDS = ("output_parseable", "schema_valid", "verifier_completed")
_MONITORING_DISCIPLINE_PRINCIPLES = (
    "Escalate only when currently released evidence supports it.",
    "Routine surveillance is the correct response when released evidence does not indicate an "
    "unreliable instrument or an alert condition.",
    "A prior episode's correct response does not by itself justify the same response in a new episode.",
    "Check the measurement system and inspect the downstream area before submitting a response "
    "whenever that evidence is not yet released.",
)
_TOP_LEVEL_FIELDS = {
    "feedback_view_id",
    "trial_id",
    "task_id",
    "execution_status",
    "terminal_outcome",
    "action_sequence",
    "selected_response",
    "evaluation_outcomes",
    "monitoring_discipline_principles",
}


def dam_escalation_boundary_feedback(record: TrialRecord) -> bytes:
    """Return the declared public escalation-boundary feedback view for one completed episode."""

    if not record.task_id.startswith(_DAM_TASK_PREFIX):
        raise ValueError(f"dam-feedback-source-mismatch: {record.task_id}")
    if record.execution_status is not ExecutionStatus.COMPLETED:
        raise ValueError("dam-feedback-projection-failed: dam-seepage execution is not complete")
    evaluation = _completed_evaluation(record, category="dam-feedback-projection-failed")
    reward = _bounded_number(evaluation.reward, category="dam-feedback-projection-failed", label="reward")
    breakdown = _breakdown(evaluation, category="dam-feedback-projection-failed")
    action_sequence = _action_sequence(record, category="dam-feedback-projection-failed")
    selected_response = breakdown.get("selected_response")
    payload = {
        "feedback_view_id": DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID,
        "trial_id": record.trial_id,
        "task_id": record.task_id,
        "execution_status": record.execution_status.value,
        "terminal_outcome": {
            "canonical_reward": reward,
            "validity": {
                "output_parseable": evaluation.validity.output_parseable,
                "schema_valid": evaluation.validity.schema_valid,
                "verifier_completed": evaluation.validity.verifier_completed,
            },
        },
        "action_sequence": list(action_sequence),
        "selected_response": None if selected_response is None else str(selected_response),
        "evaluation_outcomes": {
            field: _required_bool(breakdown, field, category="dam-feedback-projection-failed")
            for field in _SELECTED_EVALUATION_FIELDS
        },
        "monitoring_discipline_principles": list(_MONITORING_DISCIPLINE_PRINCIPLES),
    }
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    validate_dam_escalation_boundary_feedback(data)
    return data


def validate_dam_escalation_boundary_feedback(data: bytes) -> dict[str, Any]:
    """Validate the exact dam-owned public escalation-boundary feedback projection."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("dam-feedback-projection-failed: feedback is not UTF-8 JSON") from error
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_FIELDS:
        raise ValueError("dam-feedback-forbidden-field-detected: feedback fields do not match the public view")
    if payload["feedback_view_id"] != DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID:
        raise ValueError("dam-feedback-projection-failed: feedback view identity does not match")
    if not isinstance(payload["task_id"], str) or not payload["task_id"].startswith(_DAM_TASK_PREFIX):
        raise ValueError(f"dam-feedback-source-mismatch: {payload.get('task_id')!r}")
    if payload["execution_status"] != ExecutionStatus.COMPLETED.value:
        raise ValueError("dam-feedback-projection-failed: feedback source is not complete")
    if not isinstance(payload["trial_id"], str) or not payload["trial_id"]:
        raise ValueError("dam-feedback-projection-failed: feedback trial identity is missing")

    terminal = payload["terminal_outcome"]
    if not isinstance(terminal, dict) or set(terminal) != {"canonical_reward", "validity"}:
        raise ValueError("dam-feedback-forbidden-field-detected: terminal outcome fields do not match")
    _bounded_number(terminal["canonical_reward"], category="dam-feedback-projection-failed", label="reward")
    validity = terminal["validity"]
    if (
        not isinstance(validity, dict)
        or set(validity) != set(_PUBLIC_VALIDITY_FIELDS)
        or any(not isinstance(validity[field], bool) for field in _PUBLIC_VALIDITY_FIELDS)
    ):
        raise ValueError("dam-feedback-forbidden-field-detected: public validity fields are invalid")

    action_sequence = payload["action_sequence"]
    if not isinstance(action_sequence, list) or not action_sequence:
        raise ValueError("dam-feedback-projection-failed: action sequence is missing")
    if any(action not in set(SeepageAction) for action in action_sequence):
        raise ValueError("dam-feedback-forbidden-field-detected: action sequence contains an unknown action")

    selected_response = payload["selected_response"]
    if selected_response is not None and not isinstance(selected_response, str):
        raise ValueError("dam-feedback-forbidden-field-detected: selected response must be a string or null")

    outcomes = payload["evaluation_outcomes"]
    if not isinstance(outcomes, dict) or set(outcomes) != set(_SELECTED_EVALUATION_FIELDS):
        raise ValueError("dam-feedback-forbidden-field-detected: evaluation outcome allowlist does not match")
    if any(not isinstance(outcomes[field], bool) for field in _SELECTED_EVALUATION_FIELDS):
        raise ValueError("dam-feedback-forbidden-field-detected: evaluation outcome values must be boolean")
    if payload["monitoring_discipline_principles"] != list(_MONITORING_DISCIPLINE_PRINCIPLES):
        raise ValueError("dam-feedback-forbidden-field-detected: declared monitoring principles do not match")
    return payload


def dam_response_correct(record: TrialRecord) -> float:
    """Read the dam-owned response-correctness outcome from authoritative evaluation evidence."""

    breakdown = _eligible_breakdown(record)
    value = _required_bool(breakdown, "response_correct", category="dam-projection-value-out-of-bounds")
    return 1.0 if value else 0.0


def dam_evidence_complete(record: TrialRecord) -> float:
    """Read whether the learner's own actions revealed evidence sufficient to justify its response."""

    breakdown = _eligible_breakdown(record)
    value = _required_bool(breakdown, "evidence_complete", category="dam-projection-value-out-of-bounds")
    return 1.0 if value else 0.0


def dam_inappropriate_escalation(record: TrialRecord) -> float:
    """Measure a familiar-but-inappropriate escalation, distinct from generic response incorrectness."""

    breakdown = _eligible_breakdown(record)
    selected = breakdown.get("selected_response")
    required = breakdown.get("required_response")
    is_inappropriate = (
        selected == SeepageResponse.ENGINEERING_REVIEW and required == SeepageResponse.ROUTINE_SURVEILLANCE
    )
    return 1.0 if is_inappropriate else 0.0


def _eligible_breakdown(record: TrialRecord) -> dict[str, Any]:
    evaluation = _completed_evaluation(record, category="dam-projection-ineligible")
    breakdown = _breakdown(evaluation, category="dam-projection-ineligible")
    if breakdown.get("assessment_submitted") is not True:
        raise ValueError("dam-projection-ineligible: no response was submitted")
    return breakdown


def _completed_evaluation(record: TrialRecord, *, category: str) -> EvaluationResult:
    if record.evaluation_status is not EvaluationStatus.COMPLETED or record.evaluation is None:
        raise ValueError(f"{category}: dam-seepage evaluation is unavailable")
    if not record.evaluation.validity.verifier_completed:
        raise ValueError(f"{category}: dam-seepage replay did not complete")
    return record.evaluation


def _breakdown(evaluation: EvaluationResult, *, category: str) -> dict[str, Any]:
    breakdown = evaluation.breakdown
    if not isinstance(breakdown, dict):
        raise ValueError(f"{category}: dam-seepage evaluation breakdown is unavailable")
    return breakdown


def _required_bool(breakdown: dict[str, Any], field: str, *, category: str) -> bool:
    value = breakdown.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{category}: dam-seepage evaluation field is invalid: {field}")
    return value


def _action_sequence(record: TrialRecord, *, category: str) -> tuple[str, ...]:
    output = record.output
    if output is None or output.agent_output is None:
        raise ValueError(f"{category}: dam world evidence is unavailable")
    evidence_path = Path(output.agent_output.output_path)
    if not evidence_path.is_file() or evidence_path.is_symlink():
        raise ValueError(f"{category}: dam world evidence file is unavailable")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{category}: dam world evidence is unreadable") from error
    actions = evidence.get("actions") if isinstance(evidence, dict) else None
    if not isinstance(actions, list) or not actions or any(not isinstance(item, str) for item in actions):
        raise ValueError(f"{category}: dam world evidence action sequence is missing or malformed")
    if any(action not in set(SeepageAction) for action in actions):
        raise ValueError(f"{category}: dam world evidence action sequence contains an unknown action")
    return tuple(actions)


def _bounded_number(value: object, *, category: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{category}: {label} must be finite")
    selected = float(value)
    if not 0.0 <= selected <= 1.0:
        raise ValueError(f"{category}: {label} must be within [0, 1]")
    return selected


__all__ = (
    "DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID",
    "dam_escalation_boundary_feedback",
    "dam_evidence_complete",
    "dam_inappropriate_escalation",
    "dam_response_correct",
    "validate_dam_escalation_boundary_feedback",
)
