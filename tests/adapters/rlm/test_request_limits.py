# ABOUTME: Tests request-owned RLM limits against the adapter's configured ceilings.
# ABOUTME: Proves proposal-node budgets can tighten execution but cannot loosen H0 guardrails.

from __future__ import annotations

import pytest

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterStopReason,
)
from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
)
from aec_bench.adapters.rlm.config import ExecutionConfig, GuardrailConfig
from aec_bench.contracts.agent_output import AgentOutputStatus


def _responses(
    *,
    input_tokens: int,
    output_tokens: int,
) -> list[RlmCompletionResponse]:
    return [
        RlmCompletionResponse(
            output_text="```repl\nx = 1\n```",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        RlmCompletionResponse(
            output_text="FINAL\n42",
            input_tokens=1,
            output_tokens=1,
            done=True,
        ),
    ]


def test_request_token_budget_tightens_and_is_enforced() -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=_responses(
                input_tokens=80,
                output_tokens=30,
            ),
        ),
        guardrails=GuardrailConfig(
            token_budget=1_000,
            max_iterations=10,
        ),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Stay within the node reservation.",
            configuration={"token_budget": 100},
        ),
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TOKEN_BUDGET_REACHED
    assert result.stop_reason is AdapterStopReason.TOKEN_BUDGET
    assert result.turns_used == 1
    assert result.configuration_record["token_budget"] == 100
    assert result.agent_output.error_message == "Token budget exceeded (110/100)"


def test_request_cost_budget_tightens_and_is_enforced() -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="gpt-4o",
        client=ReplayRlmClient(
            responses=_responses(
                input_tokens=10_000,
                output_tokens=5_000,
            ),
        ),
        guardrails=GuardrailConfig(
            token_budget=100_000,
            max_iterations=10,
            max_budget_usd=1.0,
        ),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Stay within the node reservation.",
            configuration={"max_cost_usd": 0.05},
        ),
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.COST_BUDGET_REACHED
    assert result.stop_reason is AdapterStopReason.COST_BUDGET
    assert result.turns_used == 1
    assert result.configuration_record["max_cost_usd"] == 0.05
    assert result.agent_output.error_message == "USD budget exceeded ($0.0750/$0.05)"


def test_request_context_budget_tightens_and_is_enforced() -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=_responses(
                input_tokens=960,
                output_tokens=10,
            ),
        ),
        guardrails=GuardrailConfig(
            token_budget=10_000,
            max_iterations=10,
        ),
        execution=ExecutionConfig(
            context_limit=10_000,
            compaction_threshold_pct=0.99,
            hard_ceiling_pct=0.95,
        ),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Stay within the node reservation.",
            configuration={"context_budget_tokens": 1_000},
        ),
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.CONTEXT_LIMIT_REACHED
    assert result.stop_reason is AdapterStopReason.CONTEXT_LIMIT
    assert result.turns_used == 1
    assert result.configuration_record["context_budget_tokens"] == 1_000


def test_request_limits_cannot_loosen_configured_rlm_limits() -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="gpt-4o",
        client=ReplayRlmClient(
            responses=_responses(
                input_tokens=80,
                output_tokens=30,
            ),
        ),
        guardrails=GuardrailConfig(
            token_budget=100,
            max_iterations=1,
            max_budget_usd=0.0005,
        ),
        execution=ExecutionConfig(
            context_limit=1_000,
            compaction_threshold_pct=0.99,
            hard_ceiling_pct=0.95,
        ),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Do not loosen H0.",
            configuration={
                "max_turns": 10,
                "token_budget": 1_000,
                "max_cost_usd": 0.01,
                "context_budget_tokens": 10_000,
            },
        ),
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TOKEN_BUDGET_REACHED
    assert result.stop_reason is AdapterStopReason.TOKEN_BUDGET
    assert result.max_turns == 1
    assert result.configuration_record["max_turns"] == 1
    assert result.configuration_record["token_budget"] == 100
    assert result.configuration_record["max_cost_usd"] == 0.0005
    assert result.configuration_record["context_budget_tokens"] == 1_000


@pytest.mark.parametrize(
    "value",
    [
        True,
        0,
        -1,
        float("nan"),
        float("inf"),
        "not-a-number",
    ],
)
def test_request_cost_budget_must_be_positive_and_finite(value: object) -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(responses=[]),
    )

    with pytest.raises(ValueError, match="max_cost_usd must be a positive finite number"):
        adapter.execute(
            AdapterRequest(
                instruction="Reject before execution.",
                configuration={"max_cost_usd": value},
            ),
        )
