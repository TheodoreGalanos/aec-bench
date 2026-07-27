# ABOUTME: Defines immutable, provider-bounded policy for reusable program proposal generation.
# ABOUTME: Keeps proposer instructions, grammar, checkpoint, and effect ceilings phase-neutral.

from __future__ import annotations

import hashlib
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class FrozenProgramProposerPolicy(ContentAddressedModel):
    """Exact zero-shot proposer bytes, identities, and provider budget."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )

    schema_version: Literal["aecbench.frozen-proposer-policy.v1"] = "aecbench.frozen-proposer-policy.v1"
    policy_id: NonEmptyStr
    version: NonEmptyStr
    instruction_bytes: bytes = Field(min_length=1)
    instruction_sha256: str
    model_id: NonEmptyStr
    policy_checkpoint_sha256: str
    grammar_sha256: str
    max_turns: Literal[4] = 4
    max_observed_tokens: Literal[100_000] = 100_000
    max_cost_usd: float = Field(default=1.0, ge=1.0, le=1.0)
    max_wall_time_seconds: Literal[600] = 600
    expected_plan_count: Literal[2] = 2

    @field_validator(
        "instruction_sha256",
        "policy_checkpoint_sha256",
        "grammar_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_instruction_identity(self) -> Self:
        expected = hashlib.sha256(self.instruction_bytes).hexdigest()
        if self.instruction_sha256 != expected:
            raise ValueError(
                "proposer instruction identity must match the exact instruction bytes",
            )
        return self


__all__ = ["FrozenProgramProposerPolicy"]
