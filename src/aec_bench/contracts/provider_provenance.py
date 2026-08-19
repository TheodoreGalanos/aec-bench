# ABOUTME: Defines provider package identity, resolved runtime identity, and qualification evidence.
# ABOUTME: Keeps source, runtime, and live qualification claims separate and content-addressed.

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


def _validate_full_git_sha(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("source_revision must be a lowercase 40-character Git commit")
    return value


FullGitSha = Annotated[str, AfterValidator(_validate_full_git_sha)]
QualificationEvidenceLevel = Literal["keyless", "live"]
QualificationStatus = Literal["unqualified", "partial", "qualified"]


class ProviderAdapterIdentity(FrozenStrictModel):
    """Identify one provider adapter package and the exact source used to build it."""

    adapter_id: NonEmptyStr
    package_version: NonEmptyStr
    source_revision: FullGitSha | None = None
    source_snapshot: ArtifactRef | None = None

    @model_validator(mode="after")
    def validate_source_identity(self) -> Self:
        if (self.source_revision is None) == (self.source_snapshot is None):
            raise ValueError("provider adapter identity requires exactly one source revision or source snapshot")
        return self


class ResolvedRuntimeIdentity(FrozenStrictModel):
    """Keep installed distribution identity separate from a runtime's own report."""

    distribution_name: NonEmptyStr
    distribution_version: NonEmptyStr
    reported_version: NonEmptyStr | None = None


class ProviderQualificationCell(FrozenStrictModel):
    """Record one feature claim for one exact provider and runtime version set."""

    provider_route: NonEmptyStr
    feature: NonEmptyStr
    adapter_identity: ProviderAdapterIdentity
    sdk: ResolvedRuntimeIdentity
    runtime: ResolvedRuntimeIdentity
    evidence_level: QualificationEvidenceLevel
    status: QualificationStatus
    evidence: tuple[ArtifactRef, ...] = ()
    qualified_at: datetime | None = None
    reason: NonEmptyStr | None = None

    @field_validator("qualified_at")
    @classmethod
    def validate_qualified_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("qualified_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_status_evidence(self) -> Self:
        if self.status == "qualified":
            if not self.evidence or self.qualified_at is None or self.reason is not None:
                raise ValueError("qualified provider evidence requires retained evidence and an event time")
            return self
        if self.qualified_at is not None:
            raise ValueError("only qualified provider evidence can have qualified_at")
        if self.reason is None:
            raise ValueError("partial or unqualified provider evidence requires a reason")
        if self.status == "unqualified" and self.evidence:
            raise ValueError("unqualified provider evidence cannot claim retained evidence")
        return self


__all__ = (
    "FullGitSha",
    "ProviderAdapterIdentity",
    "ProviderQualificationCell",
    "QualificationEvidenceLevel",
    "QualificationStatus",
    "ResolvedRuntimeIdentity",
)
