# ABOUTME: Derives generation-level candidate and evaluation costs from immutable work receipts.
# ABOUTME: Deduplicates shared work while enforcing complete plane coverage and frozen budgets.

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.evaluation_outcome import NonNegativeFiniteFloat
from aec_bench.contracts.evaluation_plane import (
    EvaluationBudget,
    EvaluationBudgetPartition,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
)
from aec_bench.contracts.validators import NonEmptyStr


class EvaluationAccountingPlane(StrEnum):
    """Closed budget and reporting planes within one evaluation generation."""

    PROPOSAL = "proposal"
    CANDIDATE_EXECUTION = "candidate_execution"
    DEVELOPMENT = "development"
    ACCEPTANCE = "acceptance"
    RED_TEAM = "red_team"
    MONITOR = "monitor"
    HUMAN_AUDIT = "human_audit"


class EvaluationWorkReceipt(ContentAddressedModel):
    """One immutable unit of observed work that may serve more than one plane."""

    schema_version: Literal["aecbench.evaluation-work-receipt.v1"] = "aecbench.evaluation-work-receipt.v1"
    receipt_id: NonEmptyStr
    cases: NonNegativeInt
    attempts: NonNegativeInt
    turns: NonNegativeInt
    tokens: NonNegativeInt
    provider_cost_usd: NonNegativeFiniteFloat
    wall_time_seconds: NonNegativeFiniteFloat


class EvaluationPlaneReceiptBatch(FrozenStrictModel):
    """Explicit coverage declaration and observed receipts for one plane."""

    plane: EvaluationAccountingPlane
    receipts: tuple[EvaluationWorkReceipt, ...] = ()

    @field_validator("receipts")
    @classmethod
    def canonicalize_receipts(
        cls,
        value: tuple[EvaluationWorkReceipt, ...],
    ) -> tuple[EvaluationWorkReceipt, ...]:
        receipt_ids = tuple(receipt.receipt_id for receipt in value)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("duplicate receipt identity within one accounting plane")
        return tuple(sorted(value, key=lambda receipt: receipt.receipt_id))


class EvaluationUsageTotals(FrozenStrictModel):
    """Receipt-addressed cumulative work and spend for one reporting view."""

    receipt_ids: tuple[NonEmptyStr, ...]
    cases: NonNegativeInt
    attempts: NonNegativeInt
    turns: NonNegativeInt
    tokens: NonNegativeInt
    provider_cost_usd: NonNegativeFiniteFloat
    wall_time_seconds: NonNegativeFiniteFloat

    @field_validator("receipt_ids")
    @classmethod
    def canonicalize_receipt_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("usage totals receipt identities must be unique")
        return tuple(sorted(value))

    @property
    def receipt_count(self) -> int:
        """Return the number of unique work receipts in this view."""
        return len(self.receipt_ids)


class EvaluationPlaneAccounting(FrozenStrictModel):
    """Derived observed usage for one exact budget partition."""

    plane: EvaluationAccountingPlane
    totals: EvaluationUsageTotals


class GenerationEvaluationAccounting(ContentAddressedModel):
    """Complete receipt-addressed accounting for one evaluation generation."""

    schema_version: Literal["aecbench.generation-evaluation-accounting.v1"] = (
        "aecbench.generation-evaluation-accounting.v1"
    )
    generation_id: NonEmptyStr
    budget: EvaluationBudget
    receipts: tuple[EvaluationWorkReceipt, ...]
    planes: tuple[EvaluationPlaneAccounting, ...]
    candidate_only_cumulative: EvaluationUsageTotals
    critic_plane_cumulative: EvaluationUsageTotals
    monitor_audit_cumulative: EvaluationUsageTotals
    all_in_cumulative: EvaluationUsageTotals

    @field_validator("receipts")
    @classmethod
    def canonicalize_receipt_registry(
        cls,
        value: tuple[EvaluationWorkReceipt, ...],
    ) -> tuple[EvaluationWorkReceipt, ...]:
        receipt_ids = tuple(receipt.receipt_id for receipt in value)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("generation receipt registry must contain unique receipt identities")
        return tuple(sorted(value, key=lambda receipt: receipt.receipt_id))

    @field_validator("planes")
    @classmethod
    def canonicalize_planes(
        cls,
        value: tuple[EvaluationPlaneAccounting, ...],
    ) -> tuple[EvaluationPlaneAccounting, ...]:
        plane_ids = tuple(plane.plane for plane in value)
        if len(plane_ids) != len(set(plane_ids)):
            raise ValueError("generation accounting must contain one record per plane")
        return tuple(sorted(value, key=lambda plane: plane.plane.value))

    @model_validator(mode="after")
    def validate_complete_accounting(self) -> Self:
        observed_planes = {plane.plane for plane in self.planes}
        required_planes = set(EvaluationAccountingPlane)
        if observed_planes != required_planes:
            missing = sorted(plane.value for plane in required_planes - observed_planes)
            unexpected = sorted(plane.value for plane in observed_planes - required_planes)
            raise ValueError(f"missing plane coverage; missing={missing!r}; unexpected={unexpected!r}")

        receipt_by_id = {receipt.receipt_id: receipt for receipt in self.receipts}
        plane_by_id = {plane.plane: plane for plane in self.planes}
        for plane in self.planes:
            unknown = sorted(set(plane.totals.receipt_ids) - set(receipt_by_id))
            if unknown:
                raise ValueError(f"{plane.plane.value} references unknown receipt identities")
            expected = _usage_totals(tuple(receipt_by_id[receipt_id] for receipt_id in plane.totals.receipt_ids))
            if plane.totals != expected:
                raise ValueError(f"{plane.plane.value} totals do not match its receipts")
            _assert_within_budget(
                plane=plane.plane,
                totals=plane.totals,
                budget=_budget_for_plane(self.budget, plane.plane),
            )

        expected_views = {
            "candidate_only_cumulative": _totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.PROPOSAL,
                    EvaluationAccountingPlane.CANDIDATE_EXECUTION,
                },
            ),
            "critic_plane_cumulative": _totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.DEVELOPMENT,
                    EvaluationAccountingPlane.ACCEPTANCE,
                    EvaluationAccountingPlane.RED_TEAM,
                    EvaluationAccountingPlane.MONITOR,
                    EvaluationAccountingPlane.HUMAN_AUDIT,
                },
            ),
            "monitor_audit_cumulative": _totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.MONITOR,
                    EvaluationAccountingPlane.HUMAN_AUDIT,
                },
            ),
            "all_in_cumulative": _usage_totals(self.receipts),
        }
        for field_name, expected in expected_views.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name.replace('_', ' ')} does not match unique receipts")
        return self

    @classmethod
    def create(
        cls,
        *,
        generation_id: str,
        budget: EvaluationBudget,
        plane_receipts: tuple[EvaluationPlaneReceiptBatch, ...],
    ) -> GenerationEvaluationAccounting:
        """Derive a complete report while deduplicating shared receipt work."""
        selected_budget = EvaluationBudget.model_validate(budget.model_dump(mode="python"))
        batches = tuple(
            EvaluationPlaneReceiptBatch.model_validate(batch.model_dump(mode="python")) for batch in plane_receipts
        )
        batch_planes = tuple(batch.plane for batch in batches)
        if len(batch_planes) != len(set(batch_planes)):
            raise ValueError("generation accounting must contain one batch per plane")
        observed_planes = set(batch_planes)
        if observed_planes != set(EvaluationAccountingPlane):
            missing = sorted(plane.value for plane in set(EvaluationAccountingPlane) - observed_planes)
            raise ValueError(f"missing plane coverage: {missing!r}")

        receipt_by_id: dict[str, EvaluationWorkReceipt] = {}
        for batch in batches:
            for receipt in batch.receipts:
                existing = receipt_by_id.get(receipt.receipt_id)
                if existing is not None and existing.content_sha256 != receipt.content_sha256:
                    raise ValueError("conflicting receipt identity across accounting planes")
                receipt_by_id[receipt.receipt_id] = receipt

        planes = tuple(
            EvaluationPlaneAccounting(
                plane=batch.plane,
                totals=_usage_totals(batch.receipts),
            )
            for batch in batches
        )
        plane_by_id = {plane.plane: plane for plane in planes}
        receipts = tuple(receipt_by_id.values())
        return cls(
            generation_id=generation_id,
            budget=selected_budget,
            receipts=receipts,
            planes=planes,
            candidate_only_cumulative=_totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.PROPOSAL,
                    EvaluationAccountingPlane.CANDIDATE_EXECUTION,
                },
            ),
            critic_plane_cumulative=_totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.DEVELOPMENT,
                    EvaluationAccountingPlane.ACCEPTANCE,
                    EvaluationAccountingPlane.RED_TEAM,
                    EvaluationAccountingPlane.MONITOR,
                    EvaluationAccountingPlane.HUMAN_AUDIT,
                },
            ),
            monitor_audit_cumulative=_totals_for_planes(
                plane_by_id,
                receipt_by_id,
                {
                    EvaluationAccountingPlane.MONITOR,
                    EvaluationAccountingPlane.HUMAN_AUDIT,
                },
            ),
            all_in_cumulative=_usage_totals(receipts),
        )


def _usage_totals(
    receipts: tuple[EvaluationWorkReceipt, ...],
) -> EvaluationUsageTotals:
    unique: dict[str, EvaluationWorkReceipt] = {}
    for receipt in receipts:
        existing = unique.get(receipt.receipt_id)
        if existing is not None and existing.content_sha256 != receipt.content_sha256:
            raise ValueError("conflicting receipt identity in cumulative cost view")
        unique[receipt.receipt_id] = receipt
    selected = tuple(sorted(unique.values(), key=lambda receipt: receipt.receipt_id))
    return EvaluationUsageTotals(
        receipt_ids=tuple(receipt.receipt_id for receipt in selected),
        cases=sum(receipt.cases for receipt in selected),
        attempts=sum(receipt.attempts for receipt in selected),
        turns=sum(receipt.turns for receipt in selected),
        tokens=sum(receipt.tokens for receipt in selected),
        provider_cost_usd=sum(receipt.provider_cost_usd for receipt in selected),
        wall_time_seconds=sum(receipt.wall_time_seconds for receipt in selected),
    )


def _totals_for_planes(
    planes: dict[EvaluationAccountingPlane, EvaluationPlaneAccounting],
    receipts: dict[str, EvaluationWorkReceipt],
    selected_planes: set[EvaluationAccountingPlane],
) -> EvaluationUsageTotals:
    receipt_ids = {receipt_id for plane in selected_planes for receipt_id in planes[plane].totals.receipt_ids}
    return _usage_totals(tuple(receipts[receipt_id] for receipt_id in receipt_ids))


def _budget_for_plane(
    plan: EvaluationBudget,
    plane: EvaluationAccountingPlane,
) -> EvaluationBudgetPartition:
    budget_by_plane: dict[
        EvaluationAccountingPlane,
        EvaluationBudgetPartition,
    ] = {
        EvaluationAccountingPlane.PROPOSAL: plan.proposal,
        EvaluationAccountingPlane.CANDIDATE_EXECUTION: plan.execution,
        EvaluationAccountingPlane.DEVELOPMENT: plan.development,
        EvaluationAccountingPlane.ACCEPTANCE: plan.acceptance,
        EvaluationAccountingPlane.RED_TEAM: plan.red_team,
        EvaluationAccountingPlane.MONITOR: plan.monitor,
        EvaluationAccountingPlane.HUMAN_AUDIT: plan.audit,
    }
    return budget_by_plane[plane]


def _assert_within_budget(
    *,
    plane: EvaluationAccountingPlane,
    totals: EvaluationUsageTotals,
    budget: EvaluationBudgetPartition,
) -> None:
    integer_dimensions = (
        ("cases", totals.cases, budget.case_count),
        ("attempts", totals.attempts, budget.max_attempts),
        ("turns", totals.turns, budget.max_turns),
        ("tokens", totals.tokens, budget.max_tokens),
    )
    for integer_label, integer_observed, integer_limit in integer_dimensions:
        if integer_observed > integer_limit:
            raise ValueError(f"{plane.value} {integer_label} budget exceeded: {integer_observed} > {integer_limit}")

    finite_dimensions = (
        ("provider cost", totals.provider_cost_usd, budget.max_cost_usd),
        (
            "wall time",
            totals.wall_time_seconds,
            budget.max_wall_time_seconds,
        ),
    )
    for finite_label, finite_observed, finite_limit in finite_dimensions:
        if finite_observed > finite_limit and not math.isclose(
            finite_observed,
            finite_limit,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{plane.value} {finite_label} budget exceeded: {finite_observed} > {finite_limit}")
