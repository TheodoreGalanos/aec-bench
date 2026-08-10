# ABOUTME: Tests shared Prime ACP usage aggregation and JSON evidence values.
# ABOUTME: Keeps composed journey and lifecycle accounting on one implementation path.

from decimal import Decimal

from aec_bench.prime_agent.session_evidence import PrimeAcpUsage, acp_usage_payload, aggregate_acp_usage


def test_aggregate_acp_usage_preserves_all_accounting_fields() -> None:
    usages = (
        PrimeAcpUsage(True, 2, 10, 4, 3, 1, 18, Decimal("0.25")),
        PrimeAcpUsage(True, 3, 20, 5, 6, 2, 33, Decimal("0.50")),
    )

    result = aggregate_acp_usage(usages)

    assert result == PrimeAcpUsage(True, 5, 30, 9, 9, 3, 51, Decimal("0.75"))
    assert acp_usage_payload(result) == {
        "complete": True,
        "model_calls": 5,
        "input_tokens": 30,
        "output_tokens": 9,
        "cache_read_tokens": 9,
        "cache_write_tokens": 3,
        "total_tokens": 51,
        "cost_usd": "0.75",
    }


def test_aggregate_acp_usage_requires_at_least_one_complete_item() -> None:
    assert aggregate_acp_usage(()).complete is False
    assert aggregate_acp_usage((PrimeAcpUsage(False, 0, 0, 0, 0, 0, 0, Decimal(0)),)).complete is False
