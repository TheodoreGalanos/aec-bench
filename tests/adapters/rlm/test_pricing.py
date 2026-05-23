# ABOUTME: Tests that the RLM adapter uses contracts.pricing for cost estimation.
# ABOUTME: Validates the adapter import path and basic cache-aware pricing.

from aec_bench.contracts.pricing import estimate_cost_usd


def test_sonnet_pricing() -> None:
    cost = estimate_cost_usd(
        "us.anthropic.claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost is not None
    assert abs(cost - 3.0) < 0.01


def test_haiku_pricing() -> None:
    cost = estimate_cost_usd(
        "anthropic.claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost is not None
    assert abs(cost - 1.0) < 0.01


def test_opus_pricing() -> None:
    cost = estimate_cost_usd(
        "claude-opus-4-6",
        input_tokens=0,
        output_tokens=1_000_000,
    )
    assert cost is not None
    assert abs(cost - 75.0) < 0.01


def test_gpt4_mini_pricing() -> None:
    cost = estimate_cost_usd(
        "gpt-4.1-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost is not None
    assert abs(cost - 2.0) < 0.01  # 0.40 + 1.60


def test_unknown_model_returns_none() -> None:
    cost = estimate_cost_usd(
        "some-unknown-model",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost is None


def test_combined_input_output_cost() -> None:
    cost = estimate_cost_usd(
        "claude-sonnet-4-6",
        input_tokens=100_000,
        output_tokens=10_000,
    )
    assert cost is not None
    # 100k * $3/M + 10k * $15/M = $0.30 + $0.15 = $0.45
    assert abs(cost - 0.45) < 0.01


def test_zero_tokens_is_free() -> None:
    cost = estimate_cost_usd("claude-opus-4-6", input_tokens=0, output_tokens=0)
    assert cost is not None
    assert cost == 0.0


def test_cache_read_reduces_cost() -> None:
    """With caching, cost should be lower than without."""
    full_cost = estimate_cost_usd(
        "claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=100_000,
    )
    cached_cost = estimate_cost_usd(
        "claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=800_000,
    )
    assert full_cost is not None
    assert cached_cost is not None
    assert cached_cost < full_cost
