# ABOUTME: Generates reproducible synthetic hydraulic project lineages and their revision siblings.
# ABOUTME: Applies the same correlated physical variation to each sibling without assigning dataset policy.

from __future__ import annotations

import hashlib
import random

from pydantic import Field

from aec_bench.contracts.validators import StrictModel
from aec_bench.lifecycles.stormwater_design.hydraulics.models import (
    HydraulicSourcePayload,
    HydraulicSourceState,
    build_source_state_contract,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.lifecycles.stormwater_design.hydraulics.source import build_source_state


class HydraulicLineage(StrictModel):
    """Generation inputs shared by every revision sibling in one project."""

    seed: int = Field(ge=0, strict=True)

    @property
    def lineage_id(self) -> str:
        return hashlib.sha256(f"hydraulic-lineage:{self.seed}".encode()).hexdigest()

    def source(self, revision_id: str | None = None) -> HydraulicSourceState:
        """Apply the same correlated project variation before or after a declared revision.

        The narrow ranges are synthetic screening inputs, not calibrated project distributions.
        Revision magnitudes retain the existing authored intervention definitions.
        """
        source = build_source_state() if revision_id is None else build_hydraulic_revision_source_state(revision_id)
        rng = random.Random(self.seed)
        area_factor = rng.uniform(0.96, 1.04)
        rainfall_factor = rng.uniform(0.98, 1.02)
        payload = source.payload.model_dump(mode="json")
        for catchment in payload["catchments"]:
            catchment["area_ha"] = round(catchment["area_ha"] * area_factor, 8)
        # Correlate detention storage with catchment scale rather than sampling them independently.
        for field in ("bottom_area_m2", "top_area_m2"):
            payload["basin"][field] = round(payload["basin"][field] * area_factor, 8)
        for scenario in payload["scenarios"]:
            scenario["rainfall_intensity_mm_h"] = round(scenario["rainfall_intensity_mm_h"] * rainfall_factor, 8)
        return build_source_state_contract(
            source_id=source.source_id,
            title=source.title,
            description=source.description,
            claim_boundary=source.claim_boundary,
            reference=source.reference,
            payload=HydraulicSourcePayload.model_validate(payload),
            section_revisions={s.section_name: (s.source_id, s.revision) for s in source.sections},
        )
