# ABOUTME: Verifies phase-neutral completed-batch evidence against its frozen generation plan.
# ABOUTME: Keeps provider-specific terminal decoding outside the evaluation-generation store.

from __future__ import annotations

from aec_bench.contracts.evaluation_generation import (
    EvaluationBatchPlan,
    EvaluationGenerationEvidenceRef,
    GovernedBatchExecutionClosure,
    GovernedBatchTerminalEvidence,
)


class EvaluationGenerationEvidenceError(ValueError):
    """Completed-batch evidence does not form one exact generation join."""


def verify_completed_governed_batch_evidence(
    *,
    batch: EvaluationBatchPlan,
    closure: GovernedBatchExecutionClosure,
    evidence: GovernedBatchTerminalEvidence,
) -> None:
    """Verify execution evidence against one frozen batch."""

    if (
        evidence.execution_id != closure.execution_id
        or evidence.batch_plan_sha256 != batch.content_sha256
        or evidence.source_terminal != closure.source_terminal
    ):
        raise EvaluationGenerationEvidenceError(
            "evaluation-generation source terminal differs from its evidence reference",
        )
    _verify_evidence_reference(
        observed=closure.execution_evidence,
        expected=evidence.execution_evidence,
        label="governed batch execution",
    )
    expected_joins = tuple(
        zip(
            batch.ordered_assignment_sha256s,
            closure.ordered_assignment_terminal_sha256s,
            strict=True,
        ),
    )
    execution_joins = tuple((item.assignment_sha256, item.terminal_sha256) for item in evidence.execution_assignments)
    if execution_joins != expected_joins:
        raise EvaluationGenerationEvidenceError(
            "governed batch assignment terminal evidence differs from its batch",
        )


def _verify_evidence_reference(
    *,
    observed: EvaluationGenerationEvidenceRef,
    expected: EvaluationGenerationEvidenceRef,
    label: str,
) -> None:
    if (
        observed.artifact_id == expected.artifact_id
        and observed.content_sha256 == expected.content_sha256
        and observed.schema_version != expected.schema_version
    ):
        raise EvaluationGenerationEvidenceError(
            "completed governed batch closure uses an unsupported evidence schema",
        )
    if observed != expected:
        raise EvaluationGenerationEvidenceError(
            f"{label} evidence differs from its closure",
        )
