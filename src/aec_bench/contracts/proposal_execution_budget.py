# ABOUTME: Defines deterministic per-node reservations beneath one shared proposal candidate budget.
# ABOUTME: Keeps budget partition arithmetic separate from graph, compilation, and session evidence.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.proposal_execution_types import ProposalExecutionSemantics
from aec_bench.contracts.validators import NonEmptyStr


class NodeBudgetReservation(LegacyContentAddressedModel):
    """Maximum candidate capacity reserved for one model-bearing node."""

    schema_version: Literal["aecbench.node-budget-reservation.v1"] = "aecbench.node-budget-reservation.v1"
    node_id: NonEmptyStr
    max_attempts: Literal[1]
    max_agent_turns: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_context_tokens: int = Field(ge=1)
    max_runtime_seconds: int = Field(ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, gt=0.0)


class CandidateBudgetPlan(LegacyContentAddressedModel):
    """Deterministic reservation partition beneath one unchanged harness budget."""

    schema_version: Literal["aecbench.candidate-budget-plan.v1"] = "aecbench.candidate-budget-plan.v1"
    candidate_id: NonEmptyStr
    proposal_graph_sha256: str
    proposal_freeze_sha256: str
    fixed_harness_ref: HarnessInstanceRef
    allocation_policy_sha256: str
    aggregate_budget: HarnessBudget
    execution_semantics: ProposalExecutionSemantics = ProposalExecutionSemantics.SEQUENTIAL_DATAFLOW
    session_overhead_seconds: int = Field(ge=0)
    reservations: tuple[NodeBudgetReservation, ...] = Field(min_length=1)

    @field_validator(
        "proposal_graph_sha256",
        "proposal_freeze_sha256",
        "allocation_policy_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("reservations")
    @classmethod
    def canonicalize_reservations(
        cls,
        value: tuple[NodeBudgetReservation, ...],
    ) -> tuple[NodeBudgetReservation, ...]:
        return _canonical_unique_models(
            value,
            identity="node_id",
            label="node budget reservations",
        )

    @model_validator(mode="after")
    def validate_reservation_sums(self) -> Self:
        budget = self.aggregate_budget
        if sum(item.max_attempts for item in self.reservations) > budget.max_total_attempts:
            raise ValueError("candidate attempt reservations exceed aggregate budget")
        if sum(item.max_agent_turns for item in self.reservations) > budget.max_agent_turns:
            raise ValueError("candidate agent-turn reservations exceed aggregate budget")
        if sum(item.max_tool_calls for item in self.reservations) > budget.max_tool_calls:
            raise ValueError("candidate tool-call reservations exceed aggregate budget")
        if sum(item.max_context_tokens for item in self.reservations) > budget.max_context_tokens:
            raise ValueError("candidate context reservations exceed aggregate budget")
        runtime = self.session_overhead_seconds + sum(item.max_runtime_seconds for item in self.reservations)
        if runtime > budget.max_runtime_seconds:
            raise ValueError("candidate runtime reservations exceed aggregate budget")
        _validate_optional_reservation_sum(
            values=tuple(item.max_tokens for item in self.reservations),
            aggregate=budget.max_tokens,
            label="token",
        )
        _validate_optional_reservation_sum(
            values=tuple(item.max_cost_usd for item in self.reservations),
            aggregate=budget.max_cost_usd,
            label="cost",
        )
        return self

    @property
    def reservation_node_ids(self) -> tuple[str, ...]:
        """Return the exact canonical node reservation set."""
        return tuple(item.node_id for item in self.reservations)


def _validate_optional_reservation_sum(
    *,
    values: tuple[int | float | None, ...],
    aggregate: int | float | None,
    label: str,
) -> None:
    if aggregate is None:
        if any(value is not None for value in values):
            raise ValueError(f"{label} reservations require an aggregate {label} budget")
        return
    if any(value is None for value in values):
        raise ValueError(f"aggregate {label} budget requires every node reservation")
    total = sum(value for value in values if value is not None)
    if total > aggregate:
        raise ValueError(f"candidate {label} reservations exceed aggregate budget")


def _canonical_unique_models(
    value: tuple[NodeBudgetReservation, ...],
    *,
    identity: str,
    label: str,
) -> tuple[NodeBudgetReservation, ...]:
    identities = [getattr(item, identity) for item in value]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} must be unique by {identity}")
    return tuple(sorted(value, key=lambda item: getattr(item, identity)))
