# ABOUTME: Defines the resolved provider-neutral execution limits for one run.
# ABOUTME: Keeps scheduler policy at the foundational contract boundary for persistence and inspection.

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.validators import FrozenStrictModel


class ExecutionPolicy(FrozenStrictModel):
    """Resolved local execution limits and fairness settings for one run."""

    schema_version: Literal[1] = 1
    max_concurrency: Annotated[int, Field(strict=True, gt=0)]
    lease_ttl_seconds: Annotated[int, Field(strict=True, gt=0)] = 300
    lease_heartbeat_seconds: Annotated[int, Field(strict=True, gt=0)] = 30
    priority_aging_seconds: Annotated[int, Field(strict=True, gt=0)] = 300
    run_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    backend_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    provider_route_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    model_route_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    resource_class_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    execution_family_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)

    @field_validator(
        "run_limits",
        "backend_limits",
        "provider_route_limits",
        "model_route_limits",
        "resource_class_limits",
        "execution_family_limits",
    )
    @classmethod
    def validate_limit_keys(cls, value: dict[str, int], info: object) -> dict[str, int]:
        for key in value:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("concurrency limit keys must not be blank")
        if getattr(info, "field_name", None) == "run_limits":
            for key in value:
                validate_uuidv7(key)
        return value

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.lease_heartbeat_seconds >= self.lease_ttl_seconds:
            raise ValueError("lease heartbeat interval must be shorter than lease ttl")
        if any(limit > self.max_concurrency for limits in self._limit_groups() for limit in limits.values()):
            raise ValueError("a concurrency limit must not exceed max_concurrency")
        return self

    def _limit_groups(self) -> tuple[Mapping[str, int], ...]:
        return (
            self.run_limits,
            self.backend_limits,
            self.provider_route_limits,
            self.model_route_limits,
            self.resource_class_limits,
            self.execution_family_limits,
        )


__all__ = ("ExecutionPolicy",)
