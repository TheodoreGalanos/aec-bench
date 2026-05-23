# ABOUTME: Tests for the shared pricing module with cache-aware cost estimation.
# ABOUTME: Validates model matching, cache token handling, and fallback pricing.

from aec_bench.contracts.pricing import estimate_cost_usd, match_pricing


class TestMatchPricing:
    """Tests for model name matching against the pricing table."""

    def test_exact_match(self) -> None:
        prices = match_pricing("claude-sonnet-4-6")
        assert prices is not None
        assert prices["input"] == 3.00

    def test_prefix_match_bedrock(self) -> None:
        prices = match_pricing("au.anthropic.claude-sonnet-4-6-v1")
        assert prices is not None
        assert prices["input"] == 3.00

    def test_substring_match_bedrock_region(self) -> None:
        prices = match_pricing("us.anthropic.claude-sonnet-4-6")
        assert prices is not None

    def test_haiku_match(self) -> None:
        prices = match_pricing("claude-haiku-4-5-20251001")
        assert prices is not None
        assert prices["input"] == 1.00

    def test_opus_match(self) -> None:
        prices = match_pricing("claude-opus-4-6")
        assert prices is not None
        assert prices["input"] == 15.00

    def test_gpt_mini_match(self) -> None:
        prices = match_pricing("gpt-4.1-mini")
        assert prices is not None
        assert prices["input"] == 0.40

    def test_unknown_model_returns_none(self) -> None:
        prices = match_pricing("totally-unknown-model-xyz")
        assert prices is None

    def test_cache_prices_present_for_anthropic(self) -> None:
        prices = match_pricing("claude-sonnet-4-6")
        assert prices is not None
        assert "cache_read" in prices
        assert "cache_write" in prices


class TestEstimateCostUsd:
    """Tests for cache-aware cost estimation."""

    def test_sonnet_input_only(self) -> None:
        cost = estimate_cost_usd(
            "claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost is not None
        assert abs(cost - 3.0) < 0.01

    def test_sonnet_with_cache_read(self) -> None:
        """Cache reads should reduce billable input and add cache_read cost."""
        cost = estimate_cost_usd(
            "claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=800_000,
        )
        assert cost is not None
        # billable_input = 1M - 800K = 200K @ $3/M = $0.60
        # cache_read = 800K @ $0.30/M = $0.24
        # total = $0.84
        assert abs(cost - 0.84) < 0.01

    def test_sonnet_with_cache_write(self) -> None:
        cost = estimate_cost_usd(
            "claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_write_tokens=500_000,
        )
        assert cost is not None
        # billable_input = 1M @ $3/M = $3.00
        # cache_write = 500K @ $3.75/M = $1.875
        # total = $4.875
        assert abs(cost - 4.875) < 0.01

    def test_haiku_with_full_cache(self) -> None:
        cost = estimate_cost_usd(
            "claude-haiku-4-5-20251001",
            input_tokens=500_000,
            output_tokens=100_000,
            cache_read_tokens=400_000,
            cache_write_tokens=50_000,
        )
        assert cost is not None
        # billable_input = (500K - 400K) = 100K @ $1/M = $0.10
        # output = 100K @ $5/M = $0.50
        # cache_read = 400K @ $0.10/M = $0.04
        # cache_write = 50K @ $1.25/M = $0.0625
        expected = 0.10 + 0.50 + 0.04 + 0.0625
        assert abs(cost - expected) < 0.001

    def test_zero_tokens_is_free(self) -> None:
        cost = estimate_cost_usd(
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
        )
        assert cost is not None
        assert cost == 0.0

    def test_unknown_model_returns_none(self) -> None:
        cost = estimate_cost_usd(
            "totally-unknown-model",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost is None

    def test_bedrock_prefixed_sonnet(self) -> None:
        cost = estimate_cost_usd(
            "au.anthropic.claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=900_000,
        )
        assert cost is not None
        # billable = 100K @ $3/M = $0.30, cache_read = 900K @ $0.30/M = $0.27
        assert abs(cost - 0.57) < 0.01

    def test_opus_pricing(self) -> None:
        cost = estimate_cost_usd(
            "claude-opus-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost is not None
        assert abs(cost - 15.0) < 0.01

    def test_cache_read_cannot_exceed_input(self) -> None:
        """Billable input should be clamped to 0, not go negative."""
        cost = estimate_cost_usd(
            "claude-sonnet-4-6",
            input_tokens=100_000,
            output_tokens=0,
            cache_read_tokens=200_000,
        )
        assert cost is not None
        # billable_input = max(100K - 200K, 0) = 0
        # cache_read = 200K @ $0.30/M = $0.06
        assert abs(cost - 0.06) < 0.01
