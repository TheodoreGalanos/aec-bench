# ABOUTME: Defines phase-bound authority for one pump-station review agent run.
# ABOUTME: Calculates exact token-based spend without storing provider credentials.

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aec_bench.adapters.base import AdapterRequest
from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
)

PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class PumpStationReviewAgentAuthority(ContentAddressedModel):
    """Exact approval boundary for one ASW-6A-R model-agent run."""

    schema_version: str = "pump-station.review-agent-authority.v1"
    authorization_id: NonEmptyStr
    approved_by: NonEmptyStr
    approved_on: NonEmptyStr
    provider_id: NonEmptyStr
    provider_route: NonEmptyStr
    model_id: NonEmptyStr
    adapter_id: Literal["tool_loop"]
    execution_path: Literal["direct_host_session"]
    maximum_provider_calls: PositiveInt
    maximum_model_turns: PositiveInt
    maximum_tool_calls: PositiveInt
    maximum_output_tokens_per_call: PositiveInt
    maximum_total_tokens: PositiveInt | None
    maximum_estimated_spend_microusd: PositiveInt
    input_price_microusd_per_million_tokens: NonNegativeInt
    output_price_microusd_per_million_tokens: NonNegativeInt
    cache_read_price_microusd_per_million_tokens: NonNegativeInt
    cache_write_price_microusd_per_million_tokens: NonNegativeInt
    spend_currency: Literal["USD"]
    cache_enabled: Literal[False]
    bash_enabled: Literal[False]
    advisor_enabled: Literal[False]
    count_tokens_before_request: Literal[False]

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        if self.schema_version != "pump-station.review-agent-authority.v1":
            raise ValueError("unsupported review agent authority version")
        if self.maximum_total_tokens is not None and self.maximum_total_tokens < self.maximum_output_tokens_per_call:
            raise ValueError("maximum total tokens cannot be below one output limit")
        return self


def build_pump_station_review_adapter_request(
    authority: PumpStationReviewAgentAuthority,
    *,
    tool_specs: tuple[ToolSpec, ...],
    output_path: str,
) -> AdapterRequest:
    """Build the exact closed-tool request for one approved review run."""
    if tuple(tool.name for tool in tool_specs) != (PUMP_STATION_REVIEW_TOOL_NAMES):
        raise ValueError("review agent tool catalogue differs")
    configuration: dict[str, int | bool] = {
        "max_turns": authority.maximum_model_turns,
        "max_tool_calls": authority.maximum_tool_calls,
        "max_output_tokens_per_call": (authority.maximum_output_tokens_per_call),
        "count_tokens_before_request": (authority.count_tokens_before_request),
    }
    if authority.maximum_total_tokens is not None:
        configuration["max_total_tokens"] = authority.maximum_total_tokens
    return AdapterRequest(
        instruction=(
            "Review the named maintenance closeout pack. Reconcile each record "
            "with its component, cited evidence, work scope, operating duties, "
            "restrictions, and follow-up. Identify any material evidence "
            "association or closeout problem. Submit one complete source-bound "
            "review through the review tool, then give a short factual summary."
        ),
        system_prompt=(
            "You are the asset engineer for this closeout review. Use only the "
            "declared review tools and only identifiers in the visible pack. "
            "First call observe_closeout_pack. Check the records against one "
            "another. Do not infer hidden state or ask for private controls. "
            "Before you finish, call submit_closeout_review with the finding, "
            "affected records, unaffected duties, missing evidence, disposition, "
            "required follow-up, and source references. Do not invent an identifier."
        ),
        tools=list(tool_specs),
        configuration=configuration,
        output_path=output_path,
        output_format="markdown",
    )


def calculate_pump_station_review_spend_microusd(
    authority: PumpStationReviewAgentAuthority,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> int:
    """Calculate rounded micro-USD spend from one approved price basis."""
    token_values = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in token_values.values()):
        raise ValueError("review agent token counts must be non-negative integers")
    if cache_read_tokens + cache_write_tokens > input_tokens:
        raise ValueError("review agent cache tokens cannot exceed input tokens")
    uncached_input_tokens = input_tokens - cache_read_tokens - cache_write_tokens
    cost_numerator = (
        Decimal(uncached_input_tokens) * authority.input_price_microusd_per_million_tokens
        + Decimal(output_tokens) * authority.output_price_microusd_per_million_tokens
        + Decimal(cache_read_tokens) * authority.cache_read_price_microusd_per_million_tokens
        + Decimal(cache_write_tokens) * authority.cache_write_price_microusd_per_million_tokens
    )
    return int(
        (cost_numerator / Decimal(1_000_000)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


__all__ = (
    "PumpStationReviewAgentAuthority",
    "build_pump_station_review_adapter_request",
    "calculate_pump_station_review_spend_microusd",
)
