# ABOUTME: Projects bounded public learning feedback and scores from drainage lifecycle evidence.
# ABOUTME: Keeps drainage review semantics with the task owner and outside Learning Studies contracts.

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
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
DRAINAGE_MEMO_FINDING_ID = "F-PRV06-001"
DRAINAGE_MEMO_CLOSURE_REQUEST_ID = "CER-002"
DRAINAGE_MEMO_CLOSURE_FAILURE_TOKENS = frozenset(
    {
        f"closeout_review:{DRAINAGE_MEMO_FINDING_ID}:closure_evidence",
        f"closeout_review:{DRAINAGE_MEMO_CLOSURE_REQUEST_ID}:status",
        f"closeout_review:{DRAINAGE_MEMO_CLOSURE_REQUEST_ID}:response_refs",
    }
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
_DRAINAGE_SUBMISSION_FIELDS = {
    "checkpoint_id",
    "evidence_refs",
    "review_matrix",
    "transition_decision",
    "findings",
    "closure_evidence_requests",
    "accepted_decisions",
    "readiness_decision",
    "claim_boundary_statement",
}


class DrainagePhaseEvidence(StrictModel):
    phase_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...]
    phase_outcome: NonEmptyStr
    evidence_requested: int | None = Field(default=None, ge=0)
    evidence_released: int | None = Field(default=None, ge=0)
    submissions_accepted: int | None = Field(default=None, ge=0)
    submissions_rejected: int | None = Field(default=None, ge=0)
    constraints_satisfied: int | None = Field(default=None, ge=0)
    rework_events: int | None = Field(default=None, ge=0)
    revisited_decisions: int | None = Field(default=None, ge=0)
    recovery_actions: int | None = Field(default=None, ge=0)


class DrainageLearningEvidence(StrictModel):
    evidence_schema: str = "aec-bench/lifecycle/drainage/learning-evidence/1"
    lifecycle_template_id: NonEmptyStr
    variant_id: NonEmptyStr
    phase_records: tuple[DrainagePhaseEvidence, ...]


def extract_drainage_learning_evidence(record: TrialRecord) -> DrainageLearningEvidence | None:
    """Extract phase evidence from one completed drainage lifecycle record.

    The current drainage runtime does not record rejection, rework, or recovery
    events. Those fields therefore remain explicitly unavailable rather than
    being represented as fabricated zero counts.
    """

    try:
        if not record.task_id.startswith(_DRAINAGE_TASK_PREFIX):
            return None
        evaluation = _completed_evaluation(record, category="phase-evidence-extraction-failed")
        gates = _phase_evidence_gates(evaluation)
        submissions = _phase_evidence_submissions(record)
        variant_id = record.task_id.removeprefix(_DRAINAGE_TASK_PREFIX)
        if not variant_id:
            return None
        phase_records = (
            _drainage_phase(
                phase_id="evidence_assessment",
                checkpoint_ids=("initial_review",),
                submissions=submissions,
                gate_values=gates,
                gate_ids=("checkpoint_contract", "staged_disclosure"),
            ),
            _drainage_phase(
                phase_id="response_and_closeout",
                checkpoint_ids=("response_review", "closeout_review"),
                submissions=submissions,
                gate_values=gates,
                gate_ids=GATE_IDS,
            ),
        )
        return DrainageLearningEvidence(
            lifecycle_template_id=TEMPLATE_ID,
            variant_id=variant_id,
            phase_records=phase_records,
        )
    except (TypeError, ValueError, KeyError, ValidationError):
        return None


def _drainage_phase(
    *,
    phase_id: str,
    checkpoint_ids: tuple[str, ...],
    submissions: dict[str, dict[str, Any]],
    gate_values: dict[str, dict[str, Any]],
    gate_ids: tuple[str, ...],
) -> DrainagePhaseEvidence:
    selected = [submissions[checkpoint_id] for checkpoint_id in checkpoint_ids]
    review_matrices = [submission["review_matrix"] for submission in selected]
    if any(
        not isinstance(matrix, dict) or any(not isinstance(value, str) for value in matrix.values())
        for matrix in review_matrices
    ):
        raise ValueError("phase-evidence-extraction-failed: drainage review matrix is malformed")
    accepted_decisions = [
        decision
        for submission in selected
        for decision in submission["accepted_decisions"]
        if isinstance(decision, dict) and isinstance(decision.get("decision_id"), str)
    ]
    decision_ids = [decision["decision_id"] for decision in accepted_decisions]
    repeated_decisions = len(decision_ids) - len(set(decision_ids))
    gate_complete = all(gate_values[gate_id]["passed"] for gate_id in gate_ids)
    return DrainagePhaseEvidence(
        phase_id=phase_id,
        checkpoint_ids=checkpoint_ids,
        phase_outcome="complete" if gate_complete else "incomplete",
        evidence_requested=sum(len(submission["closure_evidence_requests"]) for submission in selected),
        # The current TrialRecord retains cited references, not release-event
        # counts, so this field remains explicitly unavailable.
        evidence_released=None,
        submissions_accepted=len(selected),
        submissions_rejected=None,
        constraints_satisfied=sum(sum(value == "pass" for value in matrix.values()) for matrix in review_matrices),
        rework_events=None,
        revisited_decisions=repeated_decisions,
        recovery_actions=None,
    )


def _phase_evidence_gates(evaluation: EvaluationResult) -> dict[str, dict[str, Any]]:
    breakdown = evaluation.breakdown
    if not isinstance(breakdown, dict) or not isinstance(breakdown.get("lifecycle_gates"), dict):
        raise ValueError("phase-evidence-extraction-failed: lifecycle gates are unavailable")
    gates = breakdown["lifecycle_gates"]
    selected: dict[str, dict[str, Any]] = {}
    for gate_id in GATE_IDS:
        gate = gates.get(gate_id)
        if not isinstance(gate, dict) or not isinstance(gate.get("passed"), bool):
            raise ValueError("phase-evidence-extraction-failed: lifecycle gate is malformed")
        _bounded_number(gate.get("score"), category="phase-evidence-extraction-failed", label=gate_id)
        selected[gate_id] = gate
    return selected


def _phase_evidence_submissions(record: TrialRecord) -> dict[str, dict[str, Any]]:
    output = record.output
    agent_output = None if output is None else output.agent_output
    if agent_output is None:
        raise ValueError("phase-evidence-extraction-failed: lifecycle run is unavailable")
    run_dir = Path(agent_output.output_path)
    if not run_dir.is_absolute() or not run_dir.is_dir() or run_dir.is_symlink():
        raise ValueError("phase-evidence-extraction-failed: lifecycle run is unavailable")
    run_dir = run_dir.resolve(strict=True)
    submissions: dict[str, dict[str, Any]] = {}
    for checkpoint_id in CHECKPOINT_IDS:
        path = run_dir / "episodes" / checkpoint_id / "submission.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError("phase-evidence-extraction-failed: checkpoint submission is unavailable")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("checkpoint_id") != checkpoint_id
            or not _DRAINAGE_SUBMISSION_FIELDS.issubset(payload)
            or not isinstance(payload.get("evidence_refs"), list)
            or any(not isinstance(item, str) for item in payload["evidence_refs"])
            or not isinstance(payload.get("closure_evidence_requests"), list)
            or not isinstance(payload.get("accepted_decisions"), list)
        ):
            raise ValueError("phase-evidence-extraction-failed: checkpoint submission is malformed")
        submissions[checkpoint_id] = payload
    return submissions


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


def drainage_inappropriate_memo_closure(record: TrialRecord) -> float:
    """Measure an unsupported closeout assertion separately from generic failure."""

    _require_drainage_task(record, category="projection-task-mismatch")
    _completed_evaluation(record, category="projection-evaluation-missing")
    evaluation = record.evaluation
    if evaluation is None or not isinstance(evaluation.breakdown, dict):
        raise ValueError("projection-ineligible: lifecycle evaluation breakdown is unavailable")
    gates = evaluation.breakdown.get("lifecycle_gates")
    if not isinstance(gates, dict):
        raise ValueError("projection-ineligible: lifecycle gates are unavailable")
    closure_gate = gates.get("closure_evidence")
    if not isinstance(closure_gate, dict):
        raise ValueError("projection-ineligible: closure evidence gate is unavailable")
    if not isinstance(closure_gate.get("passed"), bool):
        raise ValueError("projection-ineligible: closure evidence gate status is invalid")
    _bounded_number(closure_gate.get("score"), category="projection-ineligible", label="closure evidence gate")
    failures = closure_gate.get("failures")
    if not isinstance(failures, list) or any(not isinstance(item, str) for item in failures):
        raise ValueError("projection-ineligible: closure evidence gate failures are malformed")

    submissions = _archived_submissions(record)
    closeout = submissions.get("closeout_review")
    if not isinstance(closeout, dict):
        raise ValueError("projection-ineligible: closeout submission is malformed")
    finding = _identified_record(closeout.get("findings"), DRAINAGE_MEMO_FINDING_ID, "finding", "finding_id")
    request = _identified_record(
        closeout.get("closure_evidence_requests"),
        DRAINAGE_MEMO_CLOSURE_REQUEST_ID,
        "closure request",
        "request_id",
    )
    if finding.get("status") not in {"open", "closed"} or request.get("status") not in {"open", "closed"}:
        raise ValueError("projection-ineligible: memo closure status is malformed")
    _string_list(finding.get("closure_evidence"), "finding closure evidence")
    _string_list(request.get("response_refs"), "closure response references")

    identified_attempt = (
        closure_gate["passed"] is False
        and finding["status"] == "closed"
        and request["status"] == "closed"
        and DRAINAGE_MEMO_CLOSURE_FAILURE_TOKENS.issubset(set(failures))
    )
    return 1.0 if identified_attempt else 0.0


def _identified_record(value: Any, record_id: str, label: str, identity_key: str) -> dict[str, Any]:
    if not isinstance(value, list):
        raise ValueError(f"projection-ineligible: {label} records are malformed")
    if any(
        not isinstance(item, dict) or not isinstance(item.get(identity_key), str) or not item[identity_key]
        for item in value
    ):
        raise ValueError(f"projection-ineligible: {label} records are malformed")
    identities = [item[identity_key] for item in value]
    if len(set(identities)) != len(identities):
        raise ValueError(f"projection-ineligible: {label} identities are ambiguous")
    matches = [item for item in value if isinstance(item, dict) and item.get(identity_key) == record_id]
    if len(matches) != 1:
        raise ValueError(f"projection-ineligible: {label} identity is missing or ambiguous")
    return matches[0]


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"projection-ineligible: {label} is malformed")
    return value


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
    "DRAINAGE_MEMO_CLOSURE_FAILURE_TOKENS",
    "DRAINAGE_MEMO_CLOSURE_REQUEST_ID",
    "DRAINAGE_MEMO_FINDING_ID",
    "DRAINAGE_PROBE_TASK_ID",
    "DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID",
    "drainage_gate_score",
    "drainage_inappropriate_memo_closure",
    "drainage_staged_review_feedback",
    "validate_drainage_staged_review_feedback",
)
