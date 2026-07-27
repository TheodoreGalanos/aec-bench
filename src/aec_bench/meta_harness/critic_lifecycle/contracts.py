# ABOUTME: Defines durable critic retirement, reveal, and audit-closure evidence contracts.
# ABOUTME: Keeps critic lifecycle records content-addressed, canonical, and independently reloadable.


from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import field_validator

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestReveal,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.authority_ledger import (
    StoredAuthorityEvent,
    StoredBasis,
)


class CriticGenerationRetirement(ContentAddressedModel):
    """Human-signable retirement proposal binding one critic to its complete history."""

    schema_version: Literal["aecbench.critic-generation-retirement.v1"] = "aecbench.critic-generation-retirement.v1"
    retirement_id: NonEmptyStr
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    critic_generation_sha256: str
    release_authority_event_sha256: str
    evaluation_outcome_sha256s: tuple[str, ...] = ()
    promotion_authority_event_sha256s: tuple[str, ...] = ()

    @field_validator(
        "critic_generation_sha256",
        "release_authority_event_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "evaluation_outcome_sha256s",
        "promotion_authority_event_sha256s",
    )
    @classmethod
    def canonicalize_history_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("critic retirement history identities must be unique")
        return tuple(sorted(value))


@dataclass(frozen=True)
class StoredCriticGenerationRetirement:
    """Retirement proposal, its durable evidence bytes, and exact authority event."""

    retirement: CriticGenerationRetirement
    evidence: StoredBasis
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class StoredAcceptanceManifestReveal:
    """Durable reveal evidence joined to its retirement and reveal authority."""

    reveal: AcceptanceManifestReveal
    evidence: StoredBasis
    retirement: CriticGenerationRetirement
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class AcceptanceAuditClosure:
    """Exact retirement and reveal pair proving one acceptance generation is auditable."""

    retirement: StoredCriticGenerationRetirement
    reveal: StoredAcceptanceManifestReveal
