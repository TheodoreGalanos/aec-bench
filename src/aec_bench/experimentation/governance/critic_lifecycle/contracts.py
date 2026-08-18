# ABOUTME: Defines durable critic retirement, reveal, and audit-closure evidence contracts.
# ABOUTME: Keeps governed critic lifecycle records canonical and reloadable under named commitments.

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import field_validator

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestReveal,
)
from aec_bench.contracts.evaluation_refs import CriticRef
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import (
    StoredAuthorityEvent,
    StoredBasis,
)


class CriticRetirement(FrozenStrictModel):
    """Human-signable retirement proposal binding one critic to its complete history."""

    schema_version: Literal["aecbench.critic-retirement.v2"] = "aecbench.critic-retirement.v2"
    retirement_id: NonEmptyStr
    critic: CriticRef
    release_authority_event_sha256: str
    evaluation_outcome_sha256s: tuple[str, ...] = ()
    promotion_authority_event_sha256s: tuple[str, ...] = ()

    @field_validator(
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


def critic_retirement_commitment(retirement: CriticRetirement) -> str:
    """Return the named commitment used by retirement authority."""

    return canonical_json_sha256(retirement.model_dump(mode="json"))


@dataclass(frozen=True)
class StoredCriticRetirement:
    """Retirement proposal, its durable evidence bytes, and exact authority event."""

    retirement: CriticRetirement
    evidence: StoredBasis
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class StoredAcceptanceManifestReveal:
    """Durable reveal evidence joined to its retirement and reveal authority."""

    reveal: AcceptanceManifestReveal
    evidence: StoredBasis
    retirement: CriticRetirement
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class AcceptanceAuditClosure:
    """Exact retirement and reveal pair proving one acceptance critic is auditable."""

    retirement: StoredCriticRetirement
    reveal: StoredAcceptanceManifestReveal
