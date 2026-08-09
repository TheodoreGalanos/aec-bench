# ABOUTME: Defines the four public stormwater hydraulic-review variants.
# ABOUTME: Binds each lifecycle variant to one registered physical or administrative revision.

from __future__ import annotations

import re
from typing import Literal

from pydantic import field_validator, model_validator

from aec_bench.contracts.adaptation import AdaptationCandidate, DerivationStep
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.stormwater_design.hydraulics.revisions import get_hydraulic_revision

FAMILY_ID = "hydraulic-interaction-review"
TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
DEFAULT_VARIANT_ID = "major_idf_revision"
HydraulicInteractionVariantId = Literal[
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
]


class HydraulicReviewVariantSpec(StrictModel):
    variant_id: HydraulicInteractionVariantId
    revision_id: HydraulicInteractionVariantId
    summary: NonEmptyStr
    visibility: Literal["public"] = "public"
    adaptation: AdaptationCandidate

    @field_validator("variant_id", "revision_id")
    @classmethod
    def validate_safe_id(cls, value: str) -> str:
        if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", value) is None:
            raise ValueError("variant identity must use lowercase words separated by underscores")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> HydraulicReviewVariantSpec:
        if self.variant_id != self.revision_id:
            raise ValueError("variant and revision identities must match")
        get_hydraulic_revision(self.revision_id)
        if self.adaptation.family_id != FAMILY_ID or self.adaptation.seed_task_id != TEMPLATE_ID:
            raise ValueError("adaptation identity must match the hydraulic interaction family")
        if self.adaptation.variation != {"change_topology": self.variant_id}:
            raise ValueError("adaptation variation must identify the hydraulic revision topology")
        return self


def _variant(variant_id: HydraulicInteractionVariantId) -> HydraulicReviewVariantSpec:
    revision = get_hydraulic_revision(variant_id)
    lineage = (
        ()
        if variant_id == DEFAULT_VARIANT_ID
        else (
            DerivationStep(
                axis="change_topology",
                parent_value=DEFAULT_VARIANT_ID,
                value=variant_id,
            ),
        )
    )
    return HydraulicReviewVariantSpec(
        variant_id=variant_id,
        revision_id=variant_id,
        summary=revision.description,
        adaptation=AdaptationCandidate(
            family_id=FAMILY_ID,
            seed_task_id=TEMPLATE_ID,
            variation_key=f"change_topology={variant_id}",
            variation={"change_topology": variant_id},
            derivation_lineage=list(lineage),
        ),
    )


_VARIANT_IDS: tuple[HydraulicInteractionVariantId, ...] = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)
_VARIANTS: dict[str, HydraulicReviewVariantSpec] = {variant_id: _variant(variant_id) for variant_id in _VARIANT_IDS}


def list_hydraulic_review_variant_ids() -> tuple[str, ...]:
    """Return stable public hydraulic interaction variant IDs."""
    return tuple(sorted(_VARIANTS))


def get_hydraulic_review_variant(variant_id: str) -> HydraulicReviewVariantSpec:
    """Return a defensive copy of one registered interaction variant."""
    try:
        return _VARIANTS[variant_id].model_copy(deep=True)
    except KeyError as exc:
        known = ", ".join(list_hydraulic_review_variant_ids())
        raise KeyError(f"unknown hydraulic interaction variant {variant_id!r}; expected one of: {known}") from exc
