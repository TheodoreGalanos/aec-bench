# ABOUTME: Well-known calculation payload contract for numerical engineering tasks.
# ABOUTME: Defines the minimal structured result shape for task outputs that report computed values.

from typing import Any

from pydantic import field_validator

from aec_bench.contracts.validators import StrictModel, ensure_non_empty_string


class CalculationResult(StrictModel):
    parameter: str
    value: float
    unit: str
    method: str | None = None
    inputs: dict[str, Any] | None = None

    @field_validator("parameter", "unit")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        return ensure_non_empty_string(value)
