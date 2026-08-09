# ABOUTME: Defines the stable identity of one generated benchmark task instance.
# ABOUTME: Keeps generated-task provenance independent from research workflows.

from __future__ import annotations

from typing import Literal

from pydantic import NonNegativeInt, field_validator

from aec_bench.contracts.harness_kernel import FrozenStrictModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr


class TaskGenerationIdentity(FrozenStrictModel):
    """Stable generated-instance identity excluding mutable paths and timestamps."""

    task_id: NonEmptyStr
    origin: Literal["generated"] = "generated"
    template: NonEmptyStr
    template_source_sha256: str
    seed: int
    instance_index: NonNegativeInt

    @field_validator("template_source_sha256")
    @classmethod
    def validate_template_source_sha256(cls, value: str) -> str:
        return validate_sha256(value)
