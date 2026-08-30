# ABOUTME: Defines the current immutable model base for explicit content references.
# ABOUTME: Computes and validates canonical model digests without providing a legacy reader.

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from aec_bench.contracts.commitments import canonical_json_sha256, validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel


class ContentAddressedModel(FrozenStrictModel):
    """Immutable model with a digest when content identity is an explicit contract field."""

    content_sha256: str = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_content_address(self) -> Self:
        payload = self.model_dump(mode="json", exclude={"content_sha256"})
        expected = canonical_json_sha256(payload)
        if self.content_sha256:
            validate_sha256(self.content_sha256)
            if self.content_sha256 != expected:
                raise ValueError("content_sha256 does not match canonical model content")
        object.__setattr__(self, "content_sha256", expected)
        return self


__all__ = ("ContentAddressedModel",)
