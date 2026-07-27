# ABOUTME: Defines provider-broker policy and receipt evidence for isolated agent execution.
# ABOUTME: Binds exact model and resource authority without carrying provider credentials.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class ProviderBrokerStatus(StrEnum):
    """Terminal state of one isolated provider broker."""

    COMPLETED = "completed"
    FAILED = "failed"
    EFFECT_UNKNOWN = "effect_unknown"


class ProviderBrokerCallPlane(StrEnum):
    """Closed metering planes exposed by one provider broker."""

    MAIN = "main"
    AUXILIARY = "auxiliary"


class ProviderBrokerPolicy(ContentAddressedModel):
    """Closed provider authority delegated to one uncredentialed agent process."""

    schema_version: Literal["aecbench.provider-broker-policy.v1"] = "aecbench.provider-broker-policy.v1"
    broker_id: NonEmptyStr
    execution_request_sha256: str
    adapter_kind: Literal["rlm"]
    model: NonEmptyStr
    call_budget_basis: Literal["rlm-main-plus-auxiliary.v1"] = "rlm-main-plus-auxiliary.v1"
    max_main_calls: int = Field(gt=0)
    max_auxiliary_calls: int = Field(ge=0)
    max_calls: int = Field(gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    max_cost_usd: float | None = Field(default=None, gt=0)
    timeout_seconds: int = Field(gt=0)

    @field_validator("execution_request_sha256")
    @classmethod
    def validate_execution_request_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_call_budget(self) -> Self:
        if self.max_calls != self.max_main_calls + self.max_auxiliary_calls:
            raise ValueError(
                "provider broker max_calls must equal its main and auxiliary call reservations",
            )
        return self


class ProviderBrokerCallReceipt(ContentAddressedModel):
    """One broker-observed provider call and its metered response."""

    schema_version: Literal["aecbench.provider-broker-call-receipt.v1"] = "aecbench.provider-broker-call-receipt.v1"
    call_index: int = Field(gt=0)
    call_plane: ProviderBrokerCallPlane
    method: Literal["generate", "generate_with_tools"]
    model: NonEmptyStr
    request_sha256: str
    response_sha256: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(ge=0)
    cache_write_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    started_at: datetime
    finished_at: datetime

    @field_validator("request_sha256", "response_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider broker timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("provider broker call cannot finish before it starts")
        return self


class ProviderBrokerEffectUnknownCallReceipt(ContentAddressedModel):
    """Admitted provider effect whose terminal usage evidence is unavailable."""

    schema_version: Literal["aecbench.provider-broker-effect-unknown-call-receipt.v1"] = (
        "aecbench.provider-broker-effect-unknown-call-receipt.v1"
    )
    call_index: int = Field(gt=0)
    call_plane: ProviderBrokerCallPlane
    method: Literal["generate", "generate_with_tools"]
    model: NonEmptyStr
    request_sha256: str
    failure_code: Literal["provider_effect_outcome_unknown"]
    started_at: datetime
    recorded_at: datetime

    @field_validator("request_sha256")
    @classmethod
    def validate_request_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("started_at", "recorded_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider broker timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.recorded_at < self.started_at:
            raise ValueError(
                "provider broker unknown effect cannot be recorded before it starts",
            )
        return self


class ProviderBrokerReceipt(ContentAddressedModel):
    """Terminal metering receipt for one content-pinned broker policy."""

    schema_version: Literal["aecbench.provider-broker-receipt.v1"] = "aecbench.provider-broker-receipt.v1"
    broker_id: NonEmptyStr
    policy_sha256: str
    status: ProviderBrokerStatus
    calls: tuple[ProviderBrokerCallReceipt, ...] = ()
    effect_unknown_calls: tuple[ProviderBrokerEffectUnknownCallReceipt, ...] = Field(
        default=(),
        max_length=1,
    )
    denied_calls: int = Field(ge=0)
    total_calls: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_cache_read_tokens: int = Field(ge=0)
    total_cache_write_tokens: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    failure_reason: NonEmptyStr | None = None

    @field_validator("policy_sha256")
    @classmethod
    def validate_policy_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider broker timestamps must be timezone-aware")
        return value

    @model_serializer(mode="wrap")
    def serialize_receipt(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("provider broker receipt serialization must produce an object")
        if not self.effect_unknown_calls:
            payload.pop("effect_unknown_calls", None)
        return payload

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        _validate_receipt_time_and_indices(self)
        _validate_receipt_aggregates(self)
        _validate_receipt_status(self)
        return self


def _validate_receipt_time_and_indices(
    receipt: ProviderBrokerReceipt,
) -> None:
    if receipt.finished_at < receipt.started_at:
        raise ValueError("provider broker cannot finish before it starts")
    if tuple(call.call_index for call in receipt.calls) != tuple(
        range(1, len(receipt.calls) + 1),
    ):
        raise ValueError("provider broker call indices must be contiguous")
    if tuple(call.call_index for call in receipt.effect_unknown_calls) != tuple(
        range(
            len(receipt.calls) + 1,
            len(receipt.calls) + len(receipt.effect_unknown_calls) + 1,
        ),
    ):
        raise ValueError(
            "provider broker unknown-effect call indices must follow observed calls",
        )


def _validate_receipt_aggregates(
    receipt: ProviderBrokerReceipt,
) -> None:
    expected = {
        "total_calls": len(receipt.calls) + len(receipt.effect_unknown_calls),
        "total_input_tokens": sum(call.input_tokens for call in receipt.calls),
        "total_output_tokens": sum(call.output_tokens for call in receipt.calls),
        "total_cache_read_tokens": sum(call.cache_read_tokens for call in receipt.calls),
        "total_cache_write_tokens": sum(call.cache_write_tokens for call in receipt.calls),
    }
    for field_name, value in expected.items():
        if getattr(receipt, field_name) != value:
            raise ValueError(
                f"provider broker {field_name} must equal observed calls",
            )
    expected_cost = sum(call.cost_usd for call in receipt.calls)
    if abs(receipt.total_cost_usd - expected_cost) > 1e-9:
        raise ValueError(
            "provider broker total_cost_usd must equal observed calls",
        )


def _validate_receipt_status(
    receipt: ProviderBrokerReceipt,
) -> None:
    if receipt.status is ProviderBrokerStatus.COMPLETED:
        if receipt.failure_reason is not None:
            raise ValueError(
                "completed provider broker cannot carry a failure reason",
            )
        if receipt.effect_unknown_calls:
            raise ValueError(
                "completed provider broker cannot carry unknown-effect calls",
            )
        return
    if receipt.status is ProviderBrokerStatus.EFFECT_UNKNOWN:
        if receipt.failure_reason is None or len(receipt.effect_unknown_calls) != 1:
            raise ValueError(
                "effect-unknown provider broker requires one unknown-effect call and a failure reason",
            )
        return
    if receipt.failure_reason is None:
        raise ValueError("failed provider broker requires a failure reason")
    if receipt.effect_unknown_calls:
        raise ValueError(
            "failed provider broker cannot carry unknown-effect calls",
        )
