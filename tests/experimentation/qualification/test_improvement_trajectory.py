# ABOUTME: Exercises receipt-addressed generation accounting and cumulative cost views.
# ABOUTME: Proves shared work is deduplicated while plane coverage and budgets fail closed.

from __future__ import annotations

import pytest

from aec_bench.contracts.evaluation_plane import (
    EvaluationBudgetPartition,
    EvaluationBudgetPlan,
)
from aec_bench.experimentation.qualification.improvement_trajectory import (
    EvaluationAccountingPlane,
    EvaluationPlaneReceiptBatch,
    EvaluationWorkReceipt,
    GenerationEvaluationAccounting,
)


def _partition(**updates: int | float) -> EvaluationBudgetPartition:
    values: dict[str, int | float] = {
        "case_count": 10,
        "max_attempts": 10,
        "max_turns": 100,
        "max_tokens": 10_000,
        "max_cost_usd": 100.0,
        "max_wall_time_seconds": 1_000.0,
    }
    values.update(updates)
    return EvaluationBudgetPartition(**values)


def _budgets(
    *,
    execution: EvaluationBudgetPartition | None = None,
) -> EvaluationBudgetPlan:
    default = _partition()
    return EvaluationBudgetPlan(
        proposal=default,
        execution=execution or default,
        development=default,
        acceptance=default,
        red_team=default,
        monitor=default,
        audit=default,
    )


def _receipt(
    receipt_id: str,
    *,
    cases: int = 1,
    attempts: int = 1,
    turns: int = 1,
    tokens: int = 10,
    provider_cost_usd: float = 1.0,
    wall_time_seconds: float = 2.0,
) -> EvaluationWorkReceipt:
    return EvaluationWorkReceipt(
        receipt_id=receipt_id,
        cases=cases,
        attempts=attempts,
        turns=turns,
        tokens=tokens,
        provider_cost_usd=provider_cost_usd,
        wall_time_seconds=wall_time_seconds,
    )


def _complete_batches(
    *,
    candidate_receipts: tuple[EvaluationWorkReceipt, ...] = (),
) -> tuple[EvaluationPlaneReceiptBatch, ...]:
    return (
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.PROPOSAL,
            receipts=(),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.CANDIDATE_EXECUTION,
            receipts=candidate_receipts,
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.DEVELOPMENT,
            receipts=(),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.ACCEPTANCE,
            receipts=(),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.RED_TEAM,
            receipts=(),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.MONITOR,
            receipts=(),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.HUMAN_AUDIT,
            receipts=(),
        ),
    )


def test_generation_accounting_deduplicates_shared_receipts_and_exposes_cost_views() -> None:
    proposal = _receipt(
        "receipt.proposal",
        tokens=10,
        provider_cost_usd=1.0,
        wall_time_seconds=2.0,
    )
    candidate = _receipt(
        "receipt.candidate",
        cases=2,
        attempts=2,
        turns=4,
        tokens=20,
        provider_cost_usd=2.0,
        wall_time_seconds=3.0,
    )
    shared_critic = _receipt(
        "receipt.shared-critic",
        cases=2,
        attempts=2,
        turns=2,
        tokens=30,
        provider_cost_usd=3.0,
        wall_time_seconds=4.0,
    )
    red_team = _receipt(
        "receipt.red-team",
        tokens=40,
        provider_cost_usd=4.0,
        wall_time_seconds=5.0,
    )
    monitor = _receipt(
        "receipt.monitor",
        turns=0,
        tokens=0,
        provider_cost_usd=0.5,
        wall_time_seconds=1.0,
    )
    audit = _receipt(
        "receipt.audit",
        turns=0,
        tokens=0,
        provider_cost_usd=1.5,
        wall_time_seconds=2.0,
    )
    batches = (
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.PROPOSAL,
            receipts=(proposal,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.CANDIDATE_EXECUTION,
            receipts=(candidate,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.DEVELOPMENT,
            receipts=(shared_critic,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.ACCEPTANCE,
            receipts=(shared_critic,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.RED_TEAM,
            receipts=(red_team,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.MONITOR,
            receipts=(monitor,),
        ),
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.HUMAN_AUDIT,
            receipts=(audit,),
        ),
    )

    report = GenerationEvaluationAccounting.create(
        generation_id="evaluation-generation-1",
        budget_plan=_budgets(),
        plane_receipt_batches=batches,
    )

    assert tuple(receipt.receipt_id for receipt in report.receipts) == (
        "receipt.audit",
        "receipt.candidate",
        "receipt.monitor",
        "receipt.proposal",
        "receipt.red-team",
        "receipt.shared-critic",
    )
    assert report.candidate_only_cumulative.receipt_count == 2
    assert report.candidate_only_cumulative.tokens == 30
    assert report.candidate_only_cumulative.provider_cost_usd == 3.0
    assert report.critic_plane_cumulative.receipt_count == 4
    assert report.critic_plane_cumulative.provider_cost_usd == 9.0
    assert report.monitor_audit_cumulative.receipt_count == 2
    assert report.monitor_audit_cumulative.provider_cost_usd == 2.0
    assert report.all_in_cumulative.receipt_count == 6
    assert report.all_in_cumulative.tokens == 100
    assert report.all_in_cumulative.provider_cost_usd == 12.0
    assert report.all_in_cumulative.provider_cost_usd < (
        report.candidate_only_cumulative.provider_cost_usd
        + sum(
            plane.totals.provider_cost_usd
            for plane in report.planes
            if plane.plane
            in {
                EvaluationAccountingPlane.DEVELOPMENT,
                EvaluationAccountingPlane.ACCEPTANCE,
                EvaluationAccountingPlane.RED_TEAM,
                EvaluationAccountingPlane.MONITOR,
                EvaluationAccountingPlane.HUMAN_AUDIT,
            }
        )
    )

    reordered = GenerationEvaluationAccounting.create(
        generation_id="evaluation-generation-1",
        budget_plan=_budgets(),
        plane_receipt_batches=tuple(reversed(batches)),
    )
    assert reordered.content_sha256 == report.content_sha256


def test_generation_accounting_rejects_duplicate_and_conflicting_receipt_identity() -> None:
    receipt = _receipt("receipt.duplicate")
    with pytest.raises(ValueError, match="duplicate receipt identity"):
        EvaluationPlaneReceiptBatch(
            plane=EvaluationAccountingPlane.PROPOSAL,
            receipts=(receipt, receipt),
        )

    batches = list(_complete_batches())
    batches[2] = EvaluationPlaneReceiptBatch(
        plane=EvaluationAccountingPlane.DEVELOPMENT,
        receipts=(receipt,),
    )
    batches[3] = EvaluationPlaneReceiptBatch(
        plane=EvaluationAccountingPlane.ACCEPTANCE,
        receipts=(
            _receipt(
                "receipt.duplicate",
                provider_cost_usd=2.0,
            ),
        ),
    )
    with pytest.raises(ValueError, match="conflicting receipt identity"):
        GenerationEvaluationAccounting.create(
            generation_id="evaluation-generation-1",
            budget_plan=_budgets(),
            plane_receipt_batches=tuple(batches),
        )


def test_generation_accounting_requires_explicit_coverage_for_every_plane() -> None:
    incomplete = tuple(
        batch for batch in _complete_batches() if batch.plane is not EvaluationAccountingPlane.HUMAN_AUDIT
    )

    with pytest.raises(ValueError, match="missing plane coverage"):
        GenerationEvaluationAccounting.create(
            generation_id="evaluation-generation-1",
            budget_plan=_budgets(),
            plane_receipt_batches=incomplete,
        )


@pytest.mark.parametrize(
    ("receipt_updates", "budget_updates", "expected_metric"),
    (
        ({"cases": 2}, {"case_count": 1}, "cases"),
        ({"attempts": 2}, {"max_attempts": 1}, "attempts"),
        ({"turns": 2}, {"max_turns": 1}, "turns"),
        ({"tokens": 2}, {"max_tokens": 1}, "tokens"),
        ({"provider_cost_usd": 2.0}, {"max_cost_usd": 1.0}, "provider cost"),
        (
            {"wall_time_seconds": 2.0},
            {"max_wall_time_seconds": 1.0},
            "wall time",
        ),
    ),
)
def test_generation_accounting_rejects_every_budget_dimension_overrun(
    receipt_updates: dict[str, int | float],
    budget_updates: dict[str, int | float],
    expected_metric: str,
) -> None:
    candidate = _receipt("receipt.candidate", **receipt_updates)

    with pytest.raises(
        ValueError,
        match=rf"candidate_execution {expected_metric} budget exceeded",
    ):
        GenerationEvaluationAccounting.create(
            generation_id="evaluation-generation-1",
            budget_plan=_budgets(execution=_partition(**budget_updates)),
            plane_receipt_batches=_complete_batches(candidate_receipts=(candidate,)),
        )
