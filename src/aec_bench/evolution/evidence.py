# ABOUTME: Shared accessors for evidence required by functional evolution projections.
# ABOUTME: Fails clearly when a trial cannot provide the evaluation result that evolution needs.

from __future__ import annotations

from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import TrialRecord


def require_evaluation(record: TrialRecord) -> EvaluationResult:
    """Return the evaluation evidence required by evolution projections."""
    if record.evaluation is None:
        raise ValueError(f"trial {record.trial_id} has no EvaluationResult evidence")
    return record.evaluation
