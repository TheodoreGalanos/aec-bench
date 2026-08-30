# ABOUTME: Maps verifier execution receipts to authoritative evaluation outcomes.
# ABOUTME: Keeps reward acceptance and validity interpretation in the evaluation owner.

from dataclasses import dataclass
from math import isfinite

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt, VerifierOutputParseStatus
from aec_bench.contracts.trial_record import EvaluationStatus


@dataclass(frozen=True)
class VerifierEvaluationMapping:
    """The evaluation status and result derived from one verifier receipt."""

    status: EvaluationStatus
    evaluation: EvaluationResult


def map_verifier_execution(
    *,
    receipt: VerifierExecutionReceipt,
    evaluation: EvaluationResult,
    expected_verifier_key: str,
    expected_verifier_version: int,
) -> VerifierEvaluationMapping:
    """Map authoritative verifier process truth onto legacy evaluation fields."""

    errors = list(evaluation.validity.errors)
    reward = evaluation.reward
    completed = False
    status: EvaluationStatus
    reason: str | None = None
    if receipt.verifier_key != expected_verifier_key or receipt.verifier_version != expected_verifier_version:
        status = EvaluationStatus.INVALID
        reason = "verifier identity mismatch"
        reward = 0.0
    elif receipt.timed_out:
        status = EvaluationStatus.FAILED
        reason = receipt.failure_message or "verifier timed out"
        reward = 0.0
    elif receipt.cancelled:
        status = EvaluationStatus.FAILED
        reason = receipt.failure_message or "verifier was cancelled"
        reward = 0.0
    elif receipt.exit_code != 0:
        status = EvaluationStatus.FAILED
        reason = receipt.failure_message or "verifier exited unsuccessfully"
        reward = 0.0
    elif receipt.output_parse_status is VerifierOutputParseStatus.MALFORMED:
        status = EvaluationStatus.INVALID
        reason = receipt.failure_message or "verifier reward was malformed"
        reward = 0.0
    elif receipt.output_parse_status is VerifierOutputParseStatus.MISSING:
        status = EvaluationStatus.FAILED
        reason = receipt.failure_message or "verifier did not produce its reward artifact"
        reward = 0.0
    elif receipt.completed:
        status = EvaluationStatus.COMPLETED
        completed = True
    else:
        status = EvaluationStatus.FAILED
        reason = receipt.failure_message or "verifier did not complete successfully"
        reward = 0.0
    if reason is not None and reason not in errors:
        errors.append(reason)
    updated_validity = evaluation.validity.model_copy(update={"verifier_completed": completed, "errors": errors})
    updated = evaluation.model_dump(mode="python")
    updated["reward"] = reward if isfinite(reward) and 0.0 <= reward <= 1.0 else 0.0
    updated["validity"] = updated_validity.model_dump(mode="python")
    return VerifierEvaluationMapping(
        status=status,
        evaluation=EvaluationResult.model_validate(updated),
    )


__all__ = ["VerifierEvaluationMapping", "map_verifier_execution"]
