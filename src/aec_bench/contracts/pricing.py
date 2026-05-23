# ABOUTME: Shared token-pricing helpers for cost estimation across contract consumers.
# ABOUTME: Centralizes model pricing so importers and reports agree on estimated USD cost.

from __future__ import annotations

# Prices in USD per million tokens.
# Each entry maps a model name pattern to input/output/cache pricing.
# Patterns are matched as substrings against the model name (case-insensitive),
# so "claude-sonnet-4" matches "au.anthropic.claude-sonnet-4-6" etc.
# More specific patterns must appear before less specific ones.
PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-sonnet-4": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-haiku": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
    # OpenAI — more specific patterns first to avoid prefix conflicts
    "gpt-4.1-nano": {
        "input": 0.10,
        "output": 0.40,
        "cache_read": 0.025,
    },
    "gpt-4.1-mini": {
        "input": 0.40,
        "output": 1.60,
        "cache_read": 0.10,
    },
    "gpt-4.1": {
        "input": 2.00,
        "output": 8.00,
        "cache_read": 0.50,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "cache_read": 0.075,
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
        "cache_read": 1.25,
    },
    "o3-mini": {
        "input": 1.10,
        "output": 4.40,
    },
    "o4-mini": {
        "input": 1.10,
        "output": 4.40,
    },
    "o3": {
        "input": 10.00,
        "output": 40.00,
    },
}


def match_pricing(model: str) -> dict[str, float] | None:
    """Match a model name against the pricing table.

    Uses case-insensitive substring matching so that Bedrock-prefixed
    names like ``au.anthropic.claude-sonnet-4-6`` match ``claude-sonnet-4``.
    """
    lower = model.lower()
    for pattern, prices in PRICING_PER_MTOK.items():
        if pattern in lower:
            return prices
    return None


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float | None:
    """Estimate USD cost for a single LLM call, accounting for cached tokens.

    Cached reads are cheaper than full input tokens.  The billable input
    is ``input_tokens - cache_read_tokens`` (clamped to zero).  Returns
    ``None`` for unknown models.
    """
    prices = match_pricing(model)
    if prices is None:
        return None

    billable_input = max(input_tokens - cache_read_tokens, 0)
    return (
        billable_input * prices["input"] / 1_000_000
        + output_tokens * prices["output"] / 1_000_000
        + cache_read_tokens * prices.get("cache_read", 0.0) / 1_000_000
        + cache_write_tokens * prices.get("cache_write", 0.0) / 1_000_000
    )
