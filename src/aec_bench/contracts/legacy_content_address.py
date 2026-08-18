# ABOUTME: Reads compatibility-era self-addressed model JSON and validates its embedded digest.
# ABOUTME: Returns current plain models without carrying or re-emitting the legacy hash field.

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from pydantic import Field, TypeAdapter, model_validator

from aec_bench.contracts.commitments import canonical_json_sha256, validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel

ModelT = TypeVar("ModelT")


class LegacyContentAddressedModel(FrozenStrictModel):
    """Compatibility base for persisted records awaiting an owning-format migration."""

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


def read_legacy_content_addressed_model(
    payload: bytes | str | Mapping[str, Any],
    adapter: TypeAdapter[ModelT],
) -> ModelT:
    """Validate one historical self digest and return its current plain model."""

    raw = _object_payload(payload)
    observed = raw.pop("content_sha256", None)
    if not isinstance(observed, str):
        raise ValueError("legacy content-addressed model must include content_sha256")
    validate_sha256(observed)
    model = adapter.validate_python(raw)
    canonical = adapter.dump_python(model, mode="json")
    if canonical_json_sha256(canonical) != observed:
        raise ValueError("legacy content_sha256 does not match canonical model content")
    return model


def _object_payload(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    try:
        decoded = json.loads(payload)
    except (TypeError, ValueError) as error:
        raise ValueError("legacy content-addressed model must contain JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("legacy content-addressed model must contain a JSON object")
    return decoded


__all__ = ("LegacyContentAddressedModel", "read_legacy_content_addressed_model")
