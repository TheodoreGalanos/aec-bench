# ABOUTME: Defines typed references to final evidence produced by execution authorities.
# ABOUTME: Names the authority and protocol without copying authority-owned evidence into trials.

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

ACTOR_INVOCATION_EVIDENCE_PROTOCOL = "aec-bench/actor-invocation-evidence/1"


class AuthorityEvidenceKind(StrEnum):
    """Authority classes that can publish final retained evidence."""

    ACTOR_INVOCATION = "actor_invocation"
    WORLD = "world"
    LIFECYCLE = "lifecycle"
    PROVIDER = "provider"
    EVALUATION = "evaluation"


class AuthorityEvidenceRef(FrozenStrictModel):
    """One final artifact produced under one named authority protocol."""

    authority_kind: AuthorityEvidenceKind
    protocol: NonEmptyStr
    artifact: ArtifactRef

    @model_validator(mode="after")
    def validate_supported_protocol(self) -> Self:
        if (
            self.authority_kind is AuthorityEvidenceKind.ACTOR_INVOCATION
            and self.protocol != ACTOR_INVOCATION_EVIDENCE_PROTOCOL
        ):
            raise ValueError("actor invocation evidence protocol is not supported")
        return self


__all__ = ("ACTOR_INVOCATION_EVIDENCE_PROTOCOL", "AuthorityEvidenceKind", "AuthorityEvidenceRef")
