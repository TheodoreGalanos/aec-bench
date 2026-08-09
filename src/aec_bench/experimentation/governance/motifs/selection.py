# ABOUTME: Owns frozen-archive motif selection requests, decisions, and deterministic resolution.
# ABOUTME: Selects structurally applicable motifs without exposing reward-bearing evidence.

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import field_validator, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.experimentation.governance.motifs.contracts import (
    EvidenceSplit,
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifStatus,
    MotifTemplate,
    _canonical_sha256,
    _validate_bound_hash,
    _validate_sha256,
)
from aec_bench.experimentation.governance.motifs.store import MotifLibrary


class MotifSelectionOutcome(StrEnum):
    """Whether an auditable archive lookup selected a reusable motif."""

    SELECTED = "selected"
    NO_SELECTION = "no_selection"


class MotifSelectionReason(StrEnum):
    """Closed set of deterministic reasons why motif selection did not occur."""

    ARCHIVE_IDENTITY_MISMATCH = "archive_identity_mismatch"
    ARCHIVE_NOT_FROZEN = "archive_not_frozen"
    HOLDOUT_SELECTION_FORBIDDEN = "holdout_selection_forbidden"
    KERNEL_ABI_MISMATCH = "kernel_abi_mismatch"
    NO_ELIGIBLE_MOTIF_MATCH = "no_eligible_motif_match"
    TARGET_REVIEW_LINEAGE_ALREADY_SEEN = "target_review_lineage_already_seen"


class MotifSelectionRequest(FrozenStrictModel):
    """Content-addressed structural lookup against one explicitly frozen motif archive."""

    schema_version: Literal["3"] = "3"
    request_sha256: NonEmptyStr
    archive_sha256: NonEmptyStr
    archive_frozen: bool
    kernel_abi_sha256: NonEmptyStr
    applicability: MotifApplicabilityDescriptor
    target_review_lineage_ids: tuple[NonEmptyStr, ...] = ()
    eligible_statuses: tuple[MotifStatus, ...] = (
        MotifStatus.REUSABLE,
        MotifStatus.TRANSFER_VALIDATED,
    )
    selection_split: EvidenceSplit

    @field_validator("request_sha256", "archive_sha256", "kernel_abi_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("eligible_statuses")
    @classmethod
    def canonicalize_eligible_statuses(
        cls,
        value: tuple[MotifStatus, ...],
    ) -> tuple[MotifStatus, ...]:
        if not value:
            raise ValueError("motif selection requires at least one eligible status")
        return tuple(sorted(set(value), key=lambda status: status.value))

    @field_validator("target_review_lineage_ids")
    @classmethod
    def canonicalize_target_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("motif selection target review lineages must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_identity(self) -> MotifSelectionRequest:
        _validate_bound_hash(self, "request_sha256")
        return self

    @classmethod
    def create(
        cls,
        *,
        archive_sha256: str,
        archive_frozen: bool,
        kernel_abi_sha256: str,
        applicability: MotifApplicabilityDescriptor,
        selection_split: str,
        target_review_lineage_ids: tuple[str, ...] = (),
        eligible_statuses: tuple[MotifStatus | str, ...] | None = None,
    ) -> MotifSelectionRequest:
        resolved_statuses = tuple(
            sorted(
                {
                    MotifStatus(status)
                    for status in (
                        eligible_statuses
                        if eligible_statuses is not None
                        else (MotifStatus.REUSABLE, MotifStatus.TRANSFER_VALIDATED)
                    )
                },
                key=lambda status: status.value,
            )
        )
        payload: dict[str, Any] = {
            "schema_version": "3",
            "archive_sha256": archive_sha256,
            "archive_frozen": archive_frozen,
            "kernel_abi_sha256": kernel_abi_sha256,
            "applicability": applicability.model_dump(mode="json"),
            "target_review_lineage_ids": tuple(sorted(set(target_review_lineage_ids))),
            "eligible_statuses": [status.value for status in resolved_statuses],
            "selection_split": selection_split,
        }
        return cls(request_sha256=_canonical_sha256(payload), **payload)


class MotifSelectionDecision(FrozenStrictModel):
    """Content-addressed result that binds an archive lookup and any selected Hx/px templates."""

    schema_version: Literal["3"] = "3"
    decision_sha256: NonEmptyStr
    request_sha256: NonEmptyStr
    archive_sha256: NonEmptyStr
    archive_frozen: bool
    kernel_abi_sha256: NonEmptyStr
    applicability: MotifApplicabilityDescriptor
    target_review_lineage_ids: tuple[NonEmptyStr, ...]
    eligible_statuses: tuple[MotifStatus, ...]
    selection_split: EvidenceSplit
    outcome: MotifSelectionOutcome
    selected_motif_sha256: str | None
    selected_hx_template: MotifTemplate | None
    selected_px_template: MotifTemplate | None
    reasons: tuple[MotifSelectionReason, ...]

    @field_validator(
        "decision_sha256",
        "request_sha256",
        "archive_sha256",
        "kernel_abi_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("selected_motif_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256(value)

    @field_validator("eligible_statuses")
    @classmethod
    def canonicalize_eligible_statuses(
        cls,
        value: tuple[MotifStatus, ...],
    ) -> tuple[MotifStatus, ...]:
        if not value:
            raise ValueError("motif selection decision requires at least one eligible status")
        return tuple(sorted(set(value), key=lambda status: status.value))

    @field_validator("target_review_lineage_ids")
    @classmethod
    def canonicalize_target_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("motif selection decision target review lineages must be unique")
        return tuple(sorted(value))

    @field_validator("reasons")
    @classmethod
    def canonicalize_reasons(
        cls,
        value: tuple[MotifSelectionReason, ...],
    ) -> tuple[MotifSelectionReason, ...]:
        return _canonical_selection_reasons(value)

    @model_validator(mode="after")
    def validate_decision(self) -> MotifSelectionDecision:
        _validate_bound_hash(self, "decision_sha256")
        selected_fields = (
            self.selected_motif_sha256,
            self.selected_hx_template,
            self.selected_px_template,
        )
        if self.outcome is MotifSelectionOutcome.SELECTED:
            if any(field is None for field in selected_fields) or self.reasons:
                raise ValueError("selected motif decisions require a motif, Hx/px templates, and no reasons")
            if self.selected_hx_template is not None and self.selected_hx_template.kind != "hx":
                raise ValueError("selected_hx_template must contain an Hx template")
            if self.selected_px_template is not None and self.selected_px_template.kind != "px":
                raise ValueError("selected_px_template must contain a px template")
        elif any(field is not None for field in selected_fields) or not self.reasons:
            raise ValueError("no-selection decisions require no selected motif or templates and at least one reason")
        return self

    @classmethod
    def create(
        cls,
        *,
        request: MotifSelectionRequest,
        selected_motif: HarnessProgramMotif | None = None,
        reasons: tuple[MotifSelectionReason | str, ...] = (),
    ) -> MotifSelectionDecision:
        resolved_reasons = _canonical_selection_reasons(reasons)
        outcome = MotifSelectionOutcome.SELECTED if selected_motif is not None else MotifSelectionOutcome.NO_SELECTION
        payload: dict[str, Any] = {
            "schema_version": "3",
            "request_sha256": request.request_sha256,
            "archive_sha256": request.archive_sha256,
            "archive_frozen": request.archive_frozen,
            "kernel_abi_sha256": request.kernel_abi_sha256,
            "applicability": request.applicability.model_dump(mode="json"),
            "target_review_lineage_ids": request.target_review_lineage_ids,
            "eligible_statuses": [status.value for status in request.eligible_statuses],
            "selection_split": request.selection_split,
            "outcome": outcome.value,
            "selected_motif_sha256": None if selected_motif is None else selected_motif.motif_sha256,
            "selected_hx_template": (
                None if selected_motif is None else selected_motif.hx_template.model_dump(mode="json")
            ),
            "selected_px_template": (
                None if selected_motif is None else selected_motif.px_template.model_dump(mode="json")
            ),
            "reasons": [reason.value for reason in resolved_reasons],
        }
        return cls(decision_sha256=_canonical_sha256(payload), **payload)


def select_motif(
    library: MotifLibrary,
    request: MotifSelectionRequest,
) -> MotifSelectionDecision:
    """Select one structurally matching motif without consulting reward-bearing evidence."""

    rejection_reasons: list[MotifSelectionReason] = []
    if request.archive_sha256 != library.archive_sha256:
        rejection_reasons.append(MotifSelectionReason.ARCHIVE_IDENTITY_MISMATCH)
    if not request.archive_frozen:
        rejection_reasons.append(MotifSelectionReason.ARCHIVE_NOT_FROZEN)
    if request.selection_split == "holdout":
        rejection_reasons.append(MotifSelectionReason.HOLDOUT_SELECTION_FORBIDDEN)
    if rejection_reasons:
        return MotifSelectionDecision.create(request=request, reasons=tuple(rejection_reasons))

    kernel_matches = tuple(motif for motif in library.motifs if motif.kernel_abi_sha256 == request.kernel_abi_sha256)
    if library.motifs and not kernel_matches:
        return MotifSelectionDecision.create(
            request=request,
            reasons=(MotifSelectionReason.KERNEL_ABI_MISMATCH,),
        )

    applicable_candidates = tuple(
        motif
        for motif in kernel_matches
        if motif.status in request.eligible_statuses and motif.applicability == request.applicability
    )
    if not applicable_candidates:
        return MotifSelectionDecision.create(
            request=request,
            reasons=(MotifSelectionReason.NO_ELIGIBLE_MOTIF_MATCH,),
        )
    target_lineages = set(request.target_review_lineage_ids)
    candidates = tuple(
        motif
        for motif in applicable_candidates
        if not target_lineages.intersection(motif.supporting_review_lineage_ids)
    )
    if not candidates:
        return MotifSelectionDecision.create(
            request=request,
            reasons=(MotifSelectionReason.TARGET_REVIEW_LINEAGE_ALREADY_SEEN,),
        )

    selected = min(candidates, key=_motif_selection_key)
    return MotifSelectionDecision.create(request=request, selected_motif=selected)


def resolve_motif_selection(
    library: MotifLibrary,
    request: MotifSelectionRequest,
    decision: MotifSelectionDecision,
) -> HarnessProgramMotif | None:
    """Recompute and resolve a selection decision so forged decisions cannot bypass the selector."""

    expected = select_motif(library, request)
    if decision != expected:
        raise ValueError("motif selection decision does not match deterministic motif selection")
    if decision.outcome is MotifSelectionOutcome.NO_SELECTION:
        return None
    return next(motif for motif in library.motifs if motif.motif_sha256 == decision.selected_motif_sha256)


def _canonical_selection_reasons(
    value: tuple[MotifSelectionReason | str, ...],
) -> tuple[MotifSelectionReason, ...]:
    resolved = tuple(MotifSelectionReason(reason) for reason in value)
    if len(resolved) != len(set(resolved)):
        raise ValueError("motif selection reasons must be unique")
    order = {reason: index for index, reason in enumerate(MotifSelectionReason)}
    return tuple(sorted(resolved, key=lambda reason: order[reason]))


def _motif_selection_key(
    motif: HarnessProgramMotif,
) -> tuple[int, float, float, float, str, str, str]:
    status_rank = {
        MotifStatus.TRANSFER_VALIDATED: 0,
        MotifStatus.REUSABLE: 1,
        MotifStatus.PROVISIONAL: 2,
        MotifStatus.CANDIDATE: 3,
        MotifStatus.RETIRED: 4,
    }
    objective = motif.objective_reward
    validity = motif.validity_rate
    return (
        status_rank[motif.status],
        math.inf if objective is None else -objective,
        math.inf if validity is None else -validity,
        motif.estimated_cost_usd,
        motif.hx_template.template_sha256,
        motif.px_template.template_sha256,
        motif.motif_sha256,
    )
