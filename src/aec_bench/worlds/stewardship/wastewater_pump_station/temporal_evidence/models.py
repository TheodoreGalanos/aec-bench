# ABOUTME: Defines strict task-owned contracts for temporal documentary evidence.
# ABOUTME: Separates corpus lineage, access policy, availability, and retrieval budgets.

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class TemporalEvidenceIntegrityError(RuntimeError):
    """Raised when temporal evidence does not match its declared authority."""


class TemporalEvidenceRightsClass(StrEnum):
    """Retention and redistribution class for one source."""

    REDISTRIBUTABLE = "redistributable"
    CITE_ONLY = "cite_only"
    EXCLUDED = "excluded"
    SEALED = "sealed"


class TemporalEvidenceSourceClass(StrEnum):
    """Declared origin of documentary evidence."""

    SYNTHETIC = "synthetic"
    INSTITUTIONAL = "institutional"
    PUBLIC = "public"
    EXTERNAL_UNVERIFIED = "external_unverified"


class TemporalEvidenceAuthorityClass(StrEnum):
    """Authority carried by a document without claiming physical truth."""

    DOCUMENTARY = "documentary"
    INSTITUTIONAL_ACCEPTED = "institutional_accepted"
    ADVISORY = "advisory"


class TemporalEvidenceEventKind(StrEnum):
    """Host-owned changes to documentary availability and status."""

    PUBLISHED = "published"
    INGESTED = "ingested"
    SEARCHABLE = "searchable"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SUPERSEDED = "superseded"
    POLICY_CHANGED = "policy_changed"


class TemporalEvidenceSource(ContentAddressedModel):
    """One source and its immutable rights declaration."""

    source_id: NonEmptyStr
    source_class: TemporalEvidenceSourceClass
    rights_class: TemporalEvidenceRightsClass
    redistribution_permitted: bool
    retention_permitted: bool
    citation: NonEmptyStr

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _safe_id(value, "source_id")

    @model_validator(mode="after")
    def validate_rights(self) -> Self:
        if self.rights_class is not TemporalEvidenceRightsClass.REDISTRIBUTABLE and self.redistribution_permitted:
            raise ValueError("non-redistributable source cannot permit redistribution")
        return self


class TemporalEvidenceLineage(ContentAddressedModel):
    """Rights, derivation, assumption, transformation, and treatment authority."""

    parent_profile_id: NonEmptyStr
    parent_generation_id: NonEmptyStr
    parent_package_content_id: NonEmptyStr
    parent_certification_id: NonEmptyStr
    sources: tuple[TemporalEvidenceSource, ...]
    derivation_ids: tuple[NonEmptyStr, ...]
    assumption_ids: tuple[NonEmptyStr, ...]
    transformation_ids: tuple[NonEmptyStr, ...]
    constructed_treatment_ids: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        _require_distinct((item.source_id for item in self.sources), "source ids")
        for label, values in (
            ("derivation ids", self.derivation_ids),
            ("assumption ids", self.assumption_ids),
            ("transformation ids", self.transformation_ids),
            ("constructed treatment ids", self.constructed_treatment_ids),
        ):
            _require_distinct(values, label)
        return self


class TemporalEvidenceVersion(ContentAddressedModel):
    """One immutable documentary version with distinct temporal meanings."""

    logical_document_id: NonEmptyStr
    version_id: NonEmptyStr
    title: NonEmptyStr
    media_type: Literal["text/plain", "text/markdown"] = "text/plain"
    content_text: str | None
    citation: NonEmptyStr
    event_start_seconds: int
    event_end_seconds: int | None = None
    created_at_seconds: int
    ingested_at_seconds: int
    available_at_seconds: int
    effective_from_seconds: int
    effective_to_seconds: int | None = None
    superseded_at_seconds: int | None = None
    superseding_version_id: str | None = None
    source_id: NonEmptyStr
    source_class: TemporalEvidenceSourceClass
    rights_class: TemporalEvidenceRightsClass
    derivation_ids: tuple[NonEmptyStr, ...]
    assumption_ids: tuple[NonEmptyStr, ...]
    transformation_ids: tuple[NonEmptyStr, ...]
    constructed_treatment_id: NonEmptyStr | None = None
    parent_profile_id: NonEmptyStr
    parent_generation_id: NonEmptyStr
    parent_package_content_id: NonEmptyStr
    authority_class: TemporalEvidenceAuthorityClass
    access_roles: tuple[NonEmptyStr, ...]
    scope_labels: tuple[NonEmptyStr, ...]
    branch_namespace: NonEmptyStr
    inherited_from_branch_id: str | None = None
    applicable_asset_ids: tuple[NonEmptyStr, ...]
    applicable_component_ids: tuple[NonEmptyStr, ...]
    applicable_mechanism_ids: tuple[NonEmptyStr, ...]
    applicable_operating_regime_ids: tuple[NonEmptyStr, ...]
    snippet_policy_id: NonEmptyStr

    @field_validator("logical_document_id", "version_id", "source_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _safe_id(value, "evidence id")

    @model_validator(mode="after")
    def validate_version(self) -> Self:
        times = (
            self.event_start_seconds,
            self.created_at_seconds,
            self.ingested_at_seconds,
            self.available_at_seconds,
            self.effective_from_seconds,
        )
        if any(value < 0 for value in times):
            raise ValueError("temporal evidence times must be non-negative")
        if self.event_end_seconds is not None and self.event_end_seconds < self.event_start_seconds:
            raise ValueError("evidence event interval is inverted")
        if self.effective_to_seconds is not None and self.effective_to_seconds < self.effective_from_seconds:
            raise ValueError("evidence applicability interval is inverted")
        if (self.superseded_at_seconds is None) != (self.superseding_version_id is None):
            raise ValueError("supersession time and version must appear together")
        for label, values in (
            ("access roles", self.access_roles),
            ("scope labels", self.scope_labels),
            ("asset ids", self.applicable_asset_ids),
            ("component ids", self.applicable_component_ids),
            ("mechanism ids", self.applicable_mechanism_ids),
            ("operating regime ids", self.applicable_operating_regime_ids),
        ):
            _require_distinct(values, label)
        if self.rights_class is not TemporalEvidenceRightsClass.REDISTRIBUTABLE and self.content_text is not None:
            raise ValueError("prohibited source bytes cannot enter corpus content")
        if self.rights_class is TemporalEvidenceRightsClass.REDISTRIBUTABLE and not self.content_text:
            raise ValueError("redistributable evidence requires retained content")
        return self


class TemporalEvidenceVersionRef(FrozenStrictModel):
    """Stable authored version identity bound to immutable canonical content."""

    version_id: NonEmptyStr
    content_sha256: NonEmptyStr


class TemporalEvidenceAvailabilityEvent(ContentAddressedModel):
    """One scheduled documentary event that never creates an agent turn itself."""

    event_id: NonEmptyStr
    kind: TemporalEvidenceEventKind
    scheduled_seconds: int
    evidence_version_id: NonEmptyStr | None = None
    actor_roles: tuple[NonEmptyStr, ...] = ()
    policy_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.scheduled_seconds < 0:
            raise ValueError("availability event time must be non-negative")
        if self.kind is TemporalEvidenceEventKind.POLICY_CHANGED:
            if self.policy_id is None or self.evidence_version_id is not None:
                raise ValueError("policy event requires only a policy identity")
        elif self.evidence_version_id is None:
            raise ValueError("evidence event requires an evidence version")
        return self


class TemporalEvidenceAvailabilitySchedule(ContentAddressedModel):
    """Content-pinned chronological epistemic event schedule."""

    schedule_id: NonEmptyStr
    events: tuple[TemporalEvidenceAvailabilityEvent, ...]

    @model_validator(mode="after")
    def validate_events(self) -> Self:
        _require_distinct((item.event_id for item in self.events), "availability event ids")
        ordering = tuple((item.scheduled_seconds, item.event_id) for item in self.events)
        if ordering != tuple(sorted(ordering)):
            raise ValueError("availability events must use canonical time and id order")
        return self


class TemporalRetrievalPolicy(ContentAddressedModel):
    """Pinned normalization, ranking, tie-break, snippet, and limit policy."""

    policy_id: NonEmptyStr
    normalization: Literal["unicode_nfkc_lower_whitespace"]
    index: Literal["token_index"]
    ranking: Literal["token_frequency"]
    tie_break: Literal["version_id_ascending"]
    snippet: Literal["matched_window"]
    maximum_query_characters: int
    maximum_results: int
    maximum_snippet_characters: int

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if (
            min(
                self.maximum_query_characters,
                self.maximum_results,
                self.maximum_snippet_characters,
            )
            <= 0
        ):
            raise ValueError("retrieval policy limits must be positive")
        return self


class TemporalAccessPolicy(ContentAddressedModel):
    """Pinned role and bounded actor-selected scope policy."""

    policy_id: NonEmptyStr
    actor_roles: tuple[NonEmptyStr, ...]
    allowed_scopes: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        _require_distinct(self.actor_roles, "actor roles")
        _require_distinct(self.allowed_scopes, "allowed scopes")
        return self


class TemporalBranchPolicy(ContentAddressedModel):
    """Pinned branch namespace and pre-fork inheritance policy."""

    policy_id: NonEmptyStr
    shared_namespace: NonEmptyStr
    initial_branch_id: NonEmptyStr


class TemporalCostPolicy(ContentAddressedModel):
    """Pinned retrieval cost and invocation/completion ordering."""

    policy_id: NonEmptyStr
    simulated_duration_seconds: int = 0
    provider_spend_microusd: int = 0
    result_time_basis: Literal["invocation"] = "invocation"

    @model_validator(mode="after")
    def validate_cost(self) -> Self:
        if self.simulated_duration_seconds < 0 or self.provider_spend_microusd < 0:
            raise ValueError("temporal evidence cost must be non-negative")
        return self


class RetrievalBudgetVector(FrozenStrictModel):
    """Exact multi-dimensional retrieval allowance or consumption."""

    calls: int
    returned_references: int
    visible_bytes: int
    visible_tokens: int
    turns: int
    simulated_duration_seconds: int
    provider_spend_microusd: int

    @model_validator(mode="after")
    def validate_non_negative(self) -> Self:
        if any(value < 0 for value in self.model_dump(mode="python").values()):
            raise ValueError("retrieval budget values must be non-negative")
        return self


class TemporalCorpusManifest(ContentAddressedModel):
    """Complete immutable snapshot and its parent-world and lineage bindings."""

    evidence_corpus_id: NonEmptyStr
    parent_profile_id: NonEmptyStr
    parent_generation_id: NonEmptyStr
    parent_package_content_id: NonEmptyStr
    parent_certification_id: NonEmptyStr
    lineage_manifest_id: NonEmptyStr
    availability_schedule_id: NonEmptyStr
    versions: tuple[TemporalEvidenceVersionRef, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if not self.versions:
            raise ValueError("temporal corpus must contain evidence")
        _require_distinct((item.version_id for item in self.versions), "corpus version ids")
        if tuple(item.version_id for item in self.versions) != tuple(sorted(item.version_id for item in self.versions)):
            raise ValueError("corpus versions must be sorted")
        return self


class TemporalEvidenceCapability(ContentAddressedModel):
    """Present-only declaration for one deterministic temporal corpus."""

    profile: Literal["deterministic_snapshot"] = "deterministic_snapshot"
    evidence_corpus_id: NonEmptyStr
    corpus_snapshot_id: NonEmptyStr
    retrieval_policy_id: NonEmptyStr
    access_policy_id: NonEmptyStr
    availability_schedule_id: NonEmptyStr
    branch_namespace_policy_id: NonEmptyStr
    simulated_cost_policy_id: NonEmptyStr
    initial_budget: RetrievalBudgetVector


class TemporalEvidenceBundle(ContentAddressedModel):
    """Complete enabled local corpus and every policy needed to replay it."""

    capability: TemporalEvidenceCapability
    corpus_manifest: TemporalCorpusManifest
    lineage: TemporalEvidenceLineage
    availability: TemporalEvidenceAvailabilitySchedule
    retrieval_policy: TemporalRetrievalPolicy
    access_policy: TemporalAccessPolicy
    branch_policy: TemporalBranchPolicy
    cost_policy: TemporalCostPolicy
    versions: tuple[TemporalEvidenceVersion, ...]

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        manifest_refs = tuple((item.version_id, item.content_sha256) for item in self.corpus_manifest.versions)
        version_refs = tuple(
            (item.version_id, item.content_sha256) for item in sorted(self.versions, key=lambda item: item.version_id)
        )
        if manifest_refs != version_refs:
            raise ValueError("corpus manifest and evidence versions differ")
        if self.capability.corpus_snapshot_id != self.corpus_manifest.content_sha256:
            raise ValueError("capability corpus snapshot differs from manifest")
        identities = (
            (self.capability.evidence_corpus_id, self.corpus_manifest.evidence_corpus_id),
            (self.capability.retrieval_policy_id, self.retrieval_policy.content_sha256),
            (self.capability.access_policy_id, self.access_policy.content_sha256),
            (self.capability.availability_schedule_id, self.availability.content_sha256),
            (self.capability.branch_namespace_policy_id, self.branch_policy.content_sha256),
            (self.capability.simulated_cost_policy_id, self.cost_policy.content_sha256),
            (self.corpus_manifest.lineage_manifest_id, self.lineage.content_sha256),
            (self.corpus_manifest.availability_schedule_id, self.availability.content_sha256),
        )
        if any(left != right for left, right in identities):
            raise ValueError("temporal evidence policy or lineage identity differs")
        return self


def _safe_id(value: str, label: str) -> str:
    if _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must use safe identifier characters")
    return value


def _require_distinct(values: Iterable[str], label: str) -> None:
    selected: tuple[str, ...] = tuple(values)
    if not selected:
        raise ValueError(f"{label} must not be empty")
    if len(selected) != len(set(selected)):
        raise ValueError(f"{label} must be distinct")
