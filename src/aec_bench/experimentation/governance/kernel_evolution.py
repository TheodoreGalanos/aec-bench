# ABOUTME: Captures content-addressed missing-primitive evidence without changing fixed kernel K.
# ABOUTME: Keeps deterministic, human-approved kernel-change proposals behind closed governance gates.

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityRef,
    KernelCapabilitySpec,
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.compilation import CompilationError
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry


class PromotionEvidenceSplit(StrEnum):
    """Dataset partitions recorded on missing-primitive observations."""

    OPTIMIZATION = "optimization"
    DEVELOPMENT = "development"
    SAME_TOPOLOGY_TEST = "same_topology_test"
    STRUCTURAL_HOLDOUT = "structural_holdout"


class MissingPrimitiveObservationBoundary(StrEnum):
    """Boundary that observed a requested primitive was unavailable."""

    COMPILER = "compiler"
    RUNTIME = "runtime"


class EvidenceSelectionBasis(StrEnum):
    """Reward-free selection rule permitted for kernel-evolution evidence."""

    CAPABILITY_RECURRENCE = "capability_recurrence"


class KernelVersionBump(StrEnum):
    """Immediate semantic-version transition requested for a kernel change."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class KernelChangeRejectionCode(StrEnum):
    """Stable reason codes returned by the deterministic governance gate."""

    SOURCE_KERNEL_MISMATCH = "source_kernel_mismatch"
    PRIMITIVE_ALREADY_INSTALLED = "primitive_already_installed"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_SET_NOT_EXACT = "evidence_set_not_exact"
    EVIDENCE_TAMPERED = "evidence_tampered"
    EVIDENCE_KERNEL_MISMATCH = "evidence_kernel_mismatch"
    REQUESTED_CAPABILITY_MISMATCH = "requested_capability_mismatch"
    SELECTION_SPLIT_NOT_ALLOWED = "selection_split_not_allowed"
    INSUFFICIENT_DISTINCT_TASK_FAMILIES = "insufficient_distinct_task_families"
    APPROVAL_MISSING = "approval_missing"
    APPROVAL_NOT_GRANTED = "approval_not_granted"
    APPROVAL_SCOPE_MISMATCH = "approval_scope_mismatch"
    REGRESSION_EVIDENCE_MISSING = "regression_evidence_missing"
    REGRESSION_TESTS_FAILED = "regression_tests_failed"
    REGRESSION_SCOPE_MISMATCH = "regression_scope_mismatch"
    INVALID_VERSION_PROGRESSION = "invalid_version_progression"


class MissingPrimitiveSource(FrozenStrictModel):
    """Complete task lineage for one missing-primitive observation."""

    task_family_id: NonEmptyStr
    task_id: NonEmptyStr
    bundle_id: NonEmptyStr
    world_id: NonEmptyStr
    split: PromotionEvidenceSplit


class MissingPrimitiveFailure(FrozenStrictModel):
    """Closed compiler or runtime failure captured as evidence."""

    boundary: MissingPrimitiveObservationBoundary
    owner: NonEmptyStr
    code: NonEmptyStr
    message: NonEmptyStr
    subject_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("subject_ids")
    @classmethod
    def validate_subject_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("failure subject ids must be sorted and unique")
        return value


class RuntimeMissingPrimitiveDiagnostic(FrozenStrictModel):
    """Typed runtime diagnostic accepted by missing-primitive capture."""

    code: NonEmptyStr
    message: NonEmptyStr
    subject_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("subject_ids")
    @classmethod
    def validate_subject_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("runtime diagnostic subject ids must be sorted and unique")
        return value


class MissingPrimitiveEvidenceRef(FrozenStrictModel):
    """Content-pinned reference to one immutable missing-primitive observation."""

    evidence_id: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)


class MissingPrimitiveEvidence(ContentAddressedModel):
    """One immutable observation that fixed K lacks a requested capability."""

    evidence_id: NonEmptyStr
    kernel_ref: KernelRef
    requested_capability: KernelCapabilitySpec
    source: MissingPrimitiveSource
    failure: MissingPrimitiveFailure

    @property
    def ref(self) -> MissingPrimitiveEvidenceRef:
        return MissingPrimitiveEvidenceRef(
            evidence_id=self.evidence_id,
            content_sha256=self.content_sha256,
        )


class MissingPrimitiveEvidenceSet(ContentAddressedModel):
    """Frozen reward-free selection of evidence used for one promotion decision."""

    evidence_set_id: NonEmptyStr
    source_kernel_ref: KernelRef
    requested_capability_ref: KernelCapabilityRef
    selection_basis: EvidenceSelectionBasis = EvidenceSelectionBasis.CAPABILITY_RECURRENCE
    minimum_distinct_task_families: int = Field(default=2, ge=2)
    evidence_refs: tuple[MissingPrimitiveEvidenceRef, ...]

    @field_validator("evidence_refs")
    @classmethod
    def canonicalize_evidence_refs(
        cls,
        value: tuple[MissingPrimitiveEvidenceRef, ...],
    ) -> tuple[MissingPrimitiveEvidenceRef, ...]:
        if not value:
            raise ValueError("evidence set must include at least one reference")
        evidence_ids = [reference.evidence_id for reference in value]
        content_hashes = [reference.content_sha256 for reference in value]
        if len(evidence_ids) != len(set(evidence_ids)) or len(content_hashes) != len(set(content_hashes)):
            raise ValueError("evidence references must be unique by id and content")
        return tuple(sorted(value, key=lambda reference: (reference.evidence_id, reference.content_sha256)))


class HumanApprovalArtifact(ContentAddressedModel):
    """Human decision bound to the exact source K, evidence set, capability, and target version."""

    approval_id: NonEmptyStr
    approved_by: NonEmptyStr
    approved: bool
    source_kernel_ref: KernelRef
    requested_capability_ref: KernelCapabilityRef
    evidence_set_sha256: str
    target_kernel_version: NonEmptyStr
    artifact_sha256: str

    @field_validator("evidence_set_sha256", "artifact_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class KernelRegressionEvidence(ContentAddressedModel):
    """Regression-suite result bound to one exact proposed kernel transition."""

    regression_id: NonEmptyStr
    suite_id: NonEmptyStr
    source_kernel_ref: KernelRef
    requested_capability_ref: KernelCapabilityRef
    evidence_set_sha256: str
    target_kernel_version: NonEmptyStr
    passed: bool
    artifact_sha256: str

    @field_validator("evidence_set_sha256", "artifact_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class KernelChangeRequest(ContentAddressedModel):
    """Closed request evaluated by the fixed-kernel governance gate."""

    request_id: NonEmptyStr
    source_kernel_ref: KernelRef
    requested_capability: KernelCapabilitySpec
    evidence_set: MissingPrimitiveEvidenceSet
    target_kernel_version: NonEmptyStr
    version_bump: KernelVersionBump
    approval: HumanApprovalArtifact | None = None
    regression_evidence: tuple[KernelRegressionEvidence, ...] = ()

    @field_validator("regression_evidence")
    @classmethod
    def canonicalize_regression_evidence(
        cls,
        value: tuple[KernelRegressionEvidence, ...],
    ) -> tuple[KernelRegressionEvidence, ...]:
        regression_ids = [evidence.regression_id for evidence in value]
        content_hashes = [evidence.content_sha256 for evidence in value]
        if len(regression_ids) != len(set(regression_ids)) or len(content_hashes) != len(set(content_hashes)):
            raise ValueError("regression evidence must be unique by id and content")
        return tuple(sorted(value, key=lambda evidence: (evidence.regression_id, evidence.content_sha256)))


class KernelChangeProposal(ContentAddressedModel):
    """Governed authorization to implement a new kernel version, never a registry mutation."""

    proposal_id: NonEmptyStr
    status: Literal["governed_for_implementation"] = "governed_for_implementation"
    source_kernel_ref: KernelRef
    requested_capability: KernelCapabilitySpec
    source_evidence_set: MissingPrimitiveEvidenceSet
    target_kernel_version: NonEmptyStr
    version_bump: KernelVersionBump
    approval: HumanApprovalArtifact
    regression_evidence: tuple[KernelRegressionEvidence, ...]


class KernelChangeDecision(ContentAddressedModel):
    """Deterministic output of evaluating one kernel-change request."""

    request_sha256: str
    eligible: bool
    rejection_codes: tuple[KernelChangeRejectionCode, ...]
    distinct_task_family_ids: tuple[NonEmptyStr, ...]
    proposal: KernelChangeProposal | None = None

    @field_validator("request_sha256")
    @classmethod
    def validate_request_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        expected_rejections = tuple(sorted(set(self.rejection_codes), key=lambda code: code.value))
        if self.rejection_codes != expected_rejections:
            raise ValueError("kernel change rejection codes must be sorted and unique")
        expected_families = tuple(sorted(set(self.distinct_task_family_ids)))
        if self.distinct_task_family_ids != expected_families:
            raise ValueError("task family ids must be sorted and unique")
        if self.eligible != (not self.rejection_codes):
            raise ValueError("eligible must be true exactly when there are no rejection codes")
        if self.eligible != (self.proposal is not None):
            raise ValueError("eligible decisions must include a proposal and rejected decisions must not")
        return self


def capture_compiler_missing_primitive(
    *,
    evidence_id: str,
    kernel_ref: KernelRef,
    requested_capability: KernelCapabilitySpec,
    source: MissingPrimitiveSource,
    error: CompilationError,
) -> MissingPrimitiveEvidence:
    """Capture a typed compiler failure without mutating or extending the installed kernel."""
    diagnostic = error.diagnostic
    return MissingPrimitiveEvidence(
        evidence_id=evidence_id,
        kernel_ref=kernel_ref,
        requested_capability=requested_capability,
        source=source,
        failure=MissingPrimitiveFailure(
            boundary=MissingPrimitiveObservationBoundary.COMPILER,
            owner=diagnostic.owner.value,
            code=diagnostic.code,
            message=diagnostic.message,
            subject_ids=diagnostic.subject_ids,
        ),
    )


def capture_runtime_missing_primitive(
    *,
    evidence_id: str,
    kernel_ref: KernelRef,
    requested_capability: KernelCapabilitySpec,
    source: MissingPrimitiveSource,
    diagnostic: RuntimeMissingPrimitiveDiagnostic,
) -> MissingPrimitiveEvidence:
    """Capture a typed runtime failure without creating an executable primitive."""
    return MissingPrimitiveEvidence(
        evidence_id=evidence_id,
        kernel_ref=kernel_ref,
        requested_capability=requested_capability,
        source=source,
        failure=MissingPrimitiveFailure(
            boundary=MissingPrimitiveObservationBoundary.RUNTIME,
            owner="runtime",
            code=diagnostic.code,
            message=diagnostic.message,
            subject_ids=diagnostic.subject_ids,
        ),
    )


def decide_kernel_change(
    request: KernelChangeRequest,
    *,
    evidence_records: Iterable[MissingPrimitiveEvidence],
    installed_registry: KernelRuntimeRegistry,
) -> KernelChangeDecision:
    """Evaluate an immutable request without changing the installed fixed-kernel registry."""
    records = tuple(evidence_records)
    rejection_codes: set[KernelChangeRejectionCode] = set()
    resolved_records: tuple[MissingPrimitiveEvidence, ...] = ()

    if request.source_kernel_ref != installed_registry.manifest.ref:
        rejection_codes.add(KernelChangeRejectionCode.SOURCE_KERNEL_MISMATCH)
    if request.evidence_set.source_kernel_ref != request.source_kernel_ref:
        rejection_codes.add(KernelChangeRejectionCode.SOURCE_KERNEL_MISMATCH)
    if any(
        capability.capability_id == request.requested_capability.capability_id
        for capability in installed_registry.manifest.capabilities
    ):
        rejection_codes.add(KernelChangeRejectionCode.PRIMITIVE_ALREADY_INSTALLED)
    if request.evidence_set.requested_capability_ref != request.requested_capability.ref:
        rejection_codes.add(KernelChangeRejectionCode.REQUESTED_CAPABILITY_MISMATCH)
    if not _is_valid_version_progression(
        source=request.source_kernel_ref.version,
        target=request.target_kernel_version,
        bump=request.version_bump,
    ):
        rejection_codes.add(KernelChangeRejectionCode.INVALID_VERSION_PROGRESSION)

    evidence_rejections, resolved_records = _resolve_evidence_set(request.evidence_set, records)
    rejection_codes.update(evidence_rejections)
    distinct_families: tuple[str, ...] = ()
    if not evidence_rejections:
        content_rejections, distinct_families = _validate_evidence_content(request, resolved_records)
        rejection_codes.update(content_rejections)

    rejection_codes.update(_validate_approval(request))
    rejection_codes.update(_validate_regression_evidence(request))

    sorted_rejections = tuple(sorted(rejection_codes, key=lambda code: code.value))
    proposal = None
    if not sorted_rejections:
        assert request.approval is not None
        proposal = KernelChangeProposal(
            proposal_id=f"proposal.{request.request_id}.{request.content_sha256[:12]}",
            source_kernel_ref=request.source_kernel_ref,
            requested_capability=request.requested_capability,
            source_evidence_set=request.evidence_set,
            target_kernel_version=request.target_kernel_version,
            version_bump=request.version_bump,
            approval=request.approval,
            regression_evidence=request.regression_evidence,
        )
    return KernelChangeDecision(
        request_sha256=request.content_sha256,
        eligible=not sorted_rejections,
        rejection_codes=sorted_rejections,
        distinct_task_family_ids=distinct_families,
        proposal=proposal,
    )


def _resolve_evidence_set(
    evidence_set: MissingPrimitiveEvidenceSet,
    records: tuple[MissingPrimitiveEvidence, ...],
) -> tuple[set[KernelChangeRejectionCode], tuple[MissingPrimitiveEvidence, ...]]:
    rejections: set[KernelChangeRejectionCode] = set()
    record_ids = [record.evidence_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        rejections.add(KernelChangeRejectionCode.DUPLICATE_EVIDENCE)
        return rejections, ()

    expected_by_id = {reference.evidence_id: reference for reference in evidence_set.evidence_refs}
    actual_by_id = {record.evidence_id: record for record in records}
    missing_ids = set(expected_by_id) - set(actual_by_id)
    extra_ids = set(actual_by_id) - set(expected_by_id)
    if missing_ids:
        rejections.add(KernelChangeRejectionCode.EVIDENCE_MISSING)
    if extra_ids:
        rejections.add(KernelChangeRejectionCode.EVIDENCE_SET_NOT_EXACT)
    if rejections:
        return rejections, ()

    resolved: list[MissingPrimitiveEvidence] = []
    for evidence_id in sorted(expected_by_id):
        record = actual_by_id[evidence_id]
        try:
            validated = MissingPrimitiveEvidence.model_validate(record.model_dump(mode="json"))
        except ValueError:
            rejections.add(KernelChangeRejectionCode.EVIDENCE_TAMPERED)
            continue
        if validated.ref != expected_by_id[evidence_id]:
            rejections.add(KernelChangeRejectionCode.EVIDENCE_TAMPERED)
            continue
        resolved.append(validated)
    if rejections:
        return rejections, ()
    return rejections, tuple(resolved)


def _validate_evidence_content(
    request: KernelChangeRequest,
    records: tuple[MissingPrimitiveEvidence, ...],
) -> tuple[set[KernelChangeRejectionCode], tuple[str, ...]]:
    rejections: set[KernelChangeRejectionCode] = set()
    if any(record.kernel_ref != request.source_kernel_ref for record in records):
        rejections.add(KernelChangeRejectionCode.EVIDENCE_KERNEL_MISMATCH)
    if any(record.requested_capability.ref != request.requested_capability.ref for record in records):
        rejections.add(KernelChangeRejectionCode.REQUESTED_CAPABILITY_MISMATCH)
    allowed_splits = {PromotionEvidenceSplit.OPTIMIZATION, PromotionEvidenceSplit.DEVELOPMENT}
    if any(record.source.split not in allowed_splits for record in records):
        rejections.add(KernelChangeRejectionCode.SELECTION_SPLIT_NOT_ALLOWED)
    distinct_families = tuple(sorted({record.source.task_family_id for record in records}))
    if len(distinct_families) < request.evidence_set.minimum_distinct_task_families:
        rejections.add(KernelChangeRejectionCode.INSUFFICIENT_DISTINCT_TASK_FAMILIES)
    return rejections, distinct_families


def _validate_approval(request: KernelChangeRequest) -> set[KernelChangeRejectionCode]:
    approval = request.approval
    if approval is None:
        return {KernelChangeRejectionCode.APPROVAL_MISSING}
    if not approval.approved:
        return {KernelChangeRejectionCode.APPROVAL_NOT_GRANTED}
    expected = (
        request.source_kernel_ref,
        request.requested_capability.ref,
        request.evidence_set.content_sha256,
        request.target_kernel_version,
    )
    actual = (
        approval.source_kernel_ref,
        approval.requested_capability_ref,
        approval.evidence_set_sha256,
        approval.target_kernel_version,
    )
    if actual != expected:
        return {KernelChangeRejectionCode.APPROVAL_SCOPE_MISMATCH}
    return set()


def _validate_regression_evidence(request: KernelChangeRequest) -> set[KernelChangeRejectionCode]:
    if not request.regression_evidence:
        return {KernelChangeRejectionCode.REGRESSION_EVIDENCE_MISSING}
    rejections: set[KernelChangeRejectionCode] = set()
    if any(not evidence.passed for evidence in request.regression_evidence):
        rejections.add(KernelChangeRejectionCode.REGRESSION_TESTS_FAILED)
    expected = (
        request.source_kernel_ref,
        request.requested_capability.ref,
        request.evidence_set.content_sha256,
        request.target_kernel_version,
    )
    if any(
        (
            evidence.source_kernel_ref,
            evidence.requested_capability_ref,
            evidence.evidence_set_sha256,
            evidence.target_kernel_version,
        )
        != expected
        for evidence in request.regression_evidence
    ):
        rejections.add(KernelChangeRejectionCode.REGRESSION_SCOPE_MISMATCH)
    return rejections


_SEMANTIC_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def _is_valid_version_progression(*, source: str, target: str, bump: KernelVersionBump) -> bool:
    source_match = _SEMANTIC_VERSION.fullmatch(source)
    target_match = _SEMANTIC_VERSION.fullmatch(target)
    if source_match is None or target_match is None:
        return False
    major, minor, patch = (int(part) for part in source_match.groups())
    if bump is KernelVersionBump.PATCH:
        expected = (major, minor, patch + 1)
    elif bump is KernelVersionBump.MINOR:
        expected = (major, minor + 1, 0)
    else:
        expected = (major + 1, 0, 0)
    return tuple(int(part) for part in target_match.groups()) == expected
