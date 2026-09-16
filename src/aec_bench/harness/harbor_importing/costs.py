# ABOUTME: Normalizes Harbor aggregate and per-model accounting into CostRecord.
# ABOUTME: Keeps reported costs, estimates, and missing usage distinct at import.

from typing import Any

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trial_record import CostRecord, ModelUsageRecord
from aec_bench.harness.harbor_contract import HarborAgentResult, HarborModelUsage


def import_cost_record(
    *,
    harbor: HarborAgentResult,
    execution_result: AdapterResult | None,
    payload: dict[str, Any],
    resolved_model: str,
) -> CostRecord:
    def usage(attribute: str, *keys: str) -> int | None:
        value = getattr(execution_result, attribute) if execution_result is not None else None
        if value is not None:
            return int(value)
        for key in (attribute, *keys):
            if payload.get(key) is not None:
                return int(payload[key])
        return None

    tokens_in = usage("usage_input_tokens")
    if tokens_in is None and payload.get("input_tokens") is not None:
        # Historical agent artifacts separate uncached input from cached input.
        tokens_in = sum(
            int(payload.get(key) or 0)
            for key in (
                "input_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        )
    if tokens_in is None:
        tokens_in = harbor.n_input_tokens
    tokens_out = usage("usage_output_tokens", "output_tokens")
    if tokens_out is None:
        tokens_out = harbor.n_output_tokens
    cache_read = usage("usage_cache_read_tokens", "cache_read_input_tokens")
    if cache_read is None:
        cache_read = harbor.n_cache_tokens
    cache_write = usage("usage_cache_write_tokens", "cache_creation_input_tokens")

    model_usage = (
        {model: _model_usage(model, item) for model, item in harbor.model_usage.items()}
        if harbor.model_usage is not None
        else None
    )
    cost_usd = harbor.cost_usd
    if model_usage:
        model_input = _sum_usage(model_usage, "tokens_in")
        model_output = _sum_usage(model_usage, "tokens_out")
        model_cache = _sum_usage(model_usage, "cache_read_tokens")
        # Harbor can backfill only the ATIF steps with metrics and model names.
        # A known mismatch means the breakdown cannot supply a full trial cost.
        matches_totals = all(
            total is None or total == attributed
            for total, attributed in (
                (tokens_in, model_input),
                (tokens_out, model_output),
                (cache_read, model_cache),
            )
        )
        if tokens_in is None:
            tokens_in = model_input
        if tokens_out is None:
            tokens_out = model_output
        if cache_read is None:
            cache_read = model_cache
        costs = [item.cost_usd for item in model_usage.values()]
        if cost_usd is None and matches_totals and all(value is not None for value in costs):
            cost_usd = sum(value for value in costs if value is not None)
    elif model_usage is None and cost_usd is None and tokens_in is not None and tokens_out is not None:
        cost_usd = estimate_cost_usd(
            resolved_model,
            input_tokens=max(tokens_in - (cache_write or 0), 0),
            output_tokens=tokens_out,
            cache_read_tokens=cache_read or 0,
            cache_write_tokens=cache_write or 0,
        )

    return CostRecord(
        model_calls=usage("usage_model_calls"),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        estimated_cost_usd=cost_usd,
        model_usage=model_usage,
        advisor_calls=usage("usage_advisor_calls"),
        advisor_input_tokens=usage("usage_advisor_input_tokens"),
        advisor_output_tokens=usage("usage_advisor_output_tokens"),
    )


def _model_usage(model: str, usage: HarborModelUsage) -> ModelUsageRecord:
    estimate = None
    if (
        usage.cost_usd is None
        and usage.n_input_tokens is not None
        and usage.n_output_tokens is not None
        and usage.n_cache_tokens is not None
    ):
        estimate = estimate_cost_usd(
            model,
            input_tokens=usage.n_input_tokens,
            output_tokens=usage.n_output_tokens,
            cache_read_tokens=usage.n_cache_tokens,
        )
    return ModelUsageRecord(
        tokens_in=usage.n_input_tokens,
        tokens_out=usage.n_output_tokens,
        cache_read_tokens=usage.n_cache_tokens,
        reported_cost_usd=usage.cost_usd,
        estimated_cost_usd=estimate,
    )


def _sum_usage(model_usage: dict[str, ModelUsageRecord], attribute: str) -> int | None:
    values: list[int | None] = [getattr(item, attribute) for item in model_usage.values()]
    return None if any(value is None for value in values) else sum(value for value in values if value is not None)
