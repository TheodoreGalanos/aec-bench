# ABOUTME: Projects bounded public learning feedback and scores from drainage lifecycle evidence.
# ABOUTME: Keeps drainage review semantics with the task owner and outside Learning Studies contracts.

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.lifecycles.runtime.lifecycle import load_validated_lifecycle_submissions
from aec_bench.lifecycles.stormwater_design.drainage_model import CHECKPOINT_IDS, GATE_IDS, TEMPLATE_ID

DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID = "drainage-staged-review-public-feedback"
DRAINAGE_ACQUISITION_TASK_ID = f"lifecycle/{TEMPLATE_ID}/staged_full_correction"
DRAINAGE_PROBE_TASK_ID = f"lifecycle/{TEMPLATE_ID}/semantic_no_op_release"

_DRAINAGE_TASK_PREFIX = f"lifecycle/{TEMPLATE_ID}/"
_SELECTED_FEEDBACK_GATE_IDS = (
    "checkpoint_contract",
    "staged_disclosure",
    "finding_continuity",
    "closure_evidence",
    "accepted_decision_preservation",
    "final_readiness",
    "claim_boundary",
)
_PUBLIC_VALIDITY_FIELDS = ("output_parseable", "schema_valid", "verifier_completed")
_REVIEW_PRINCIPLES = (
    "Current registered evidence controls finding, closure, and readiness status transitions.",
    "Non-governing administrative material does not justify correction or closure.",
    "Preserve stable finding and accepted-decision identities unless current evidence supports a transition.",
    "Closure and readiness require the relevant current evidence chain.",
)
_TOP_LEVEL_FIELDS = {
    "feedback_view_id",
    "trial_id",
    "task_id",
    "execution_status",
    "terminal_outcome",
    "review_gates",
    "checkpoint_submissions",
    "review_principles",
}


def drainage_staged_review_feedback(record: TrialRecord) -> bytes:
    """Return the declared public feedback view for one completed acquisition."""

    if record.task_id != DRAINAGE_ACQUISITION_TASK_ID:
        raise ValueError(f"feedback-source-task-mismatch: {record.task_id}")
    if record.execution_status is not ExecutionStatus.COMPLETED:
        raise ValueError("feedback-source-trial-missing: lifecycle execution is not complete")
    evaluation = _completed_evaluation(record, category="feedback-source-evaluation-missing")
    reward = _bounded_number(evaluation.reward, category="feedback-projection-failed", label="reward")
    validity = evaluation.validity
    gates = {
        gate_id: _public_gate(record, gate_id, category="feedback-projection-failed")
        for gate_id in _SELECTED_FEEDBACK_GATE_IDS
    }
    submissions = _archived_submissions(record)
    payload = {
        "feedback_view_id": DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
        "trial_id": record.trial_id,
        "task_id": record.task_id,
        "execution_status": record.execution_status.value,
        "terminal_outcome": {
            "canonical_reward": reward,
            "validity": {
                "output_parseable": validity.output_parseable,
                "schema_valid": validity.schema_valid,
                "verifier_completed": validity.verifier_completed,
            },
        },
        "review_gates": gates,
        "checkpoint_submissions": submissions,
        "review_principles": list(_REVIEW_PRINCIPLES),
    }
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    validate_drainage_staged_review_feedback(data)
    return data


def validate_drainage_staged_review_feedback(data: bytes) -> dict[str, Any]:
    """Validate the exact drainage-owned public feedback projection."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("feedback-projection-invalid-json: drainage feedback is not UTF-8 JSON") from error
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_FIELDS:
        raise ValueError("feedback-projection-unsafe: drainage feedback fields do not match the public view")
    if payload["feedback_view_id"] != DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID:
        raise ValueError("feedback-projection-unsafe: drainage feedback view identity does not match")
    if payload["task_id"] != DRAINAGE_ACQUISITION_TASK_ID:
        raise ValueError("feedback-source-task-mismatch: drainage feedback source is not the acquisition task")
    if payload["execution_status"] != ExecutionStatus.COMPLETED.value:
        raise ValueError("feedback-source-trial-missing: drainage feedback source is not complete")
    if not isinstance(payload["trial_id"], str) or not payload["trial_id"]:
        raise ValueError("feedback-projection-unsafe: drainage feedback trial identity is missing")

    terminal = payload["terminal_outcome"]
    if not isinstance(terminal, dict) or set(terminal) != {"canonical_reward", "validity"}:
        raise ValueError("feedback-projection-unsafe: terminal outcome fields do not match the public view")
    _bounded_number(terminal["canonical_reward"], category="feedback-projection-unsafe", label="reward")
    validity = terminal["validity"]
    if (
        not isinstance(validity, dict)
        or set(validity) != set(_PUBLIC_VALIDITY_FIELDS)
        or any(not isinstance(validity[field], bool) for field in _PUBLIC_VALIDITY_FIELDS)
    ):
        raise ValueError("feedback-projection-unsafe: public validity fields are invalid")

    gates = payload["review_gates"]
    if not isinstance(gates, dict) or tuple(gates) != tuple(sorted(_SELECTED_FEEDBACK_GATE_IDS)):
        raise ValueError("feedback-projection-unsafe: drainage feedback gate allowlist does not match")
    for gate_id, gate in gates.items():
        if not isinstance(gate, dict) or set(gate) != {"passed", "score"} or not isinstance(gate["passed"], bool):
            raise ValueError(f"feedback-projection-unsafe: public gate shape is invalid: {gate_id}")
        _bounded_number(gate["score"], category="feedback-projection-unsafe", label=f"gate {gate_id}")

    submissions = payload["checkpoint_submissions"]
    if not isinstance(submissions, dict) or tuple(submissions) != tuple(sorted(CHECKPOINT_IDS)):
        raise ValueError("feedback-projection-unsafe: drainage feedback checkpoint allowlist does not match")
    if any(not isinstance(submissions[checkpoint_id], dict) for checkpoint_id in CHECKPOINT_IDS):
        raise ValueError("feedback-submission-invalid: archived checkpoint submissions must be objects")
    if payload["review_principles"] != list(_REVIEW_PRINCIPLES):
        raise ValueError("feedback-projection-unsafe: declared review principles do not match")
    return payload


def drainage_gate_score(record: TrialRecord, gate_id: str) -> float:
    """Read one bounded public gate score from authoritative drainage evidence."""

    _require_drainage_task(record, category="projection-task-mismatch")
    if gate_id not in GATE_IDS:
        raise ValueError(f"projection-unsupported: drainage gate is not declared: {gate_id}")
    _completed_evaluation(record, category="projection-evaluation-missing")
    return float(_public_gate(record, gate_id, category="projection")["score"])


def _completed_evaluation(record: TrialRecord, *, category: str) -> EvaluationResult:
    if record.evaluation_status is not EvaluationStatus.COMPLETED or record.evaluation is None:
        raise ValueError(f"{category}: lifecycle evaluation is unavailable")
    if not record.evaluation.validity.verifier_completed:
        raise ValueError(f"{category}: lifecycle verifier did not complete")
    return record.evaluation


def _public_gate(record: TrialRecord, gate_id: str, *, category: str) -> dict[str, Any]:
    evaluation = record.evaluation
    if evaluation is None:
        raise ValueError(f"{category}-evaluation-missing: lifecycle evaluation is unavailable")
    breakdown = evaluation.breakdown
    if not isinstance(breakdown, dict):
        raise ValueError(f"{category}-breakdown-missing: lifecycle evaluation breakdown is unavailable")
    gates = breakdown.get("lifecycle_gates")
    if not isinstance(gates, dict):
        raise ValueError(f"{category}-breakdown-missing: lifecycle gates are unavailable")
    gate = gates.get(gate_id)
    if not isinstance(gate, dict):
        raise ValueError(f"{category}-gate-missing: lifecycle gate is unavailable: {gate_id}")
    passed = gate.get("passed")
    if not isinstance(passed, bool):
        raise ValueError(f"{category}-value-invalid: lifecycle gate passed value is invalid: {gate_id}")
    score = _bounded_number(gate.get("score"), category=f"{category}-value", label=f"gate {gate_id}")
    return {"passed": passed, "score": score}


def _archived_submissions(record: TrialRecord) -> dict[str, dict[str, Any]]:
    output = record.output
    agent_output = None if output is None else output.agent_output
    if agent_output is None:
        raise ValueError("feedback-submission-missing: lifecycle run location is unavailable")
    run_candidate = Path(agent_output.output_path)
    if not run_candidate.is_absolute() or not run_candidate.is_dir() or run_candidate.is_symlink():
        raise ValueError("feedback-submission-missing: lifecycle run is unavailable")
    run_dir = run_candidate.resolve(strict=True)
    package_candidate = run_dir.parent / "package"
    if not package_candidate.is_dir() or package_candidate.is_symlink():
        raise ValueError("feedback-submission-missing: lifecycle package is unavailable")
    package_dir = package_candidate.resolve(strict=True)
    episodes_root = run_dir / "episodes"
    for checkpoint_id in CHECKPOINT_IDS:
        expected = episodes_root / checkpoint_id / "submission.json"
        matches = tuple(
            path.resolve(strict=True)
            for path in episodes_root.rglob("submission.json")
            if path.parent.name == checkpoint_id and path.is_file() and not path.is_symlink()
        )
        if len(matches) != 1 or matches[0] != expected.resolve(strict=False):
            raise ValueError(f"feedback-submission-missing: expected one archived submission: {checkpoint_id}")
    try:
        submissions = load_validated_lifecycle_submissions(package_dir, run_dir)
    except Exception as error:
        raise ValueError(f"feedback-submission-invalid: {error}") from error
    if set(submissions) != set(CHECKPOINT_IDS):
        raise ValueError("feedback-submission-invalid: archived checkpoint identities do not match")
    selected: dict[str, dict[str, Any]] = {}
    for checkpoint_id in CHECKPOINT_IDS:
        submission = submissions.get(checkpoint_id)
        if not isinstance(submission, dict):
            raise ValueError(f"feedback-submission-invalid: archived submission is not an object: {checkpoint_id}")
        selected[checkpoint_id] = submission
    return selected


def _require_drainage_task(record: TrialRecord, *, category: str) -> None:
    if not record.task_id.startswith(_DRAINAGE_TASK_PREFIX):
        raise ValueError(f"{category}: {record.task_id}")


def _bounded_number(value: object, *, category: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{category}-invalid: {label} must be finite")
    selected = float(value)
    if not 0.0 <= selected <= 1.0:
        raise ValueError(f"{category}-out-of-bounds: {label} must be within [0, 1]")
    return selected


__all__ = (
    "DRAINAGE_ACQUISITION_TASK_ID",
    "DRAINAGE_PROBE_TASK_ID",
    "DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID",
    "drainage_gate_score",
    "drainage_staged_review_feedback",
    "validate_drainage_staged_review_feedback",
)
