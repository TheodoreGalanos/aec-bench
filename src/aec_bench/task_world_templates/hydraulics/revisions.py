# ABOUTME: Defines the four public source revisions for SSC-03 hydraulic interaction calibration.
# ABOUTME: Keeps physical source changes deterministic and separate from expected invalidation answers.

from __future__ import annotations

import re
from typing import Literal

from pydantic import field_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicSourcePayload,
    HydraulicSourceState,
    SectionName,
    build_source_state_contract,
)
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state

HydraulicRevisionId = Literal[
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
]


class HydraulicRevisionSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    revision_id: HydraulicRevisionId
    title: NonEmptyStr
    description: NonEmptyStr
    visibility: Literal["public"] = "public"
    physical_section: SectionName | None

    @field_validator("revision_id")
    @classmethod
    def validate_revision_id(cls, value: str) -> str:
        if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", value) is None:
            raise ValueError("revision_id must use lowercase words separated by underscores")
        return value


_REVISIONS: dict[HydraulicRevisionId, HydraulicRevisionSpec] = {
    "administrative_no_op": HydraulicRevisionSpec(
        revision_id="administrative_no_op",
        title="Administrative document-control notice",
        description=(
            "Release a document-control notice that changes no hydraulic source bytes or physical calculation input."
        ),
        physical_section=None,
    ),
    "major_idf_revision": HydraulicRevisionSpec(
        revision_id="major_idf_revision",
        title="Major-event IDF revision",
        description="Revise the declared major-event rainfall intensity from 105 to 120 mm/h.",
        physical_section="scenarios",
    ),
    "outlet_geometry_revision": HydraulicRevisionSpec(
        revision_id="outlet_geometry_revision",
        title="Controlled-outlet geometry revision",
        description="Revise the declared orifice diameter from 0.42 to 0.52 m.",
        physical_section="outlet",
    ),
    "tailwater_revision": HydraulicRevisionSpec(
        revision_id="tailwater_revision",
        title="Downstream tailwater revision",
        description="Revise the declared downstream tailwater elevation from 40.6 to 41.0 m.",
        physical_section="network",
    ),
}


def list_hydraulic_revision_ids() -> tuple[str, ...]:
    """Return the stable public revision IDs in lexical order."""
    return tuple(sorted(_REVISIONS))


def get_hydraulic_revision(revision_id: str) -> HydraulicRevisionSpec:
    """Return a defensive copy of one registered public revision."""
    try:
        return _REVISIONS[revision_id].model_copy(deep=True)  # type: ignore[index]
    except KeyError as exc:
        known = ", ".join(list_hydraulic_revision_ids())
        raise KeyError(f"unknown hydraulic revision {revision_id!r}; expected one of: {known}") from exc


def build_hydraulic_revision_source_state(revision_id: str) -> HydraulicSourceState:
    """Build the exact physical source state activated by one public revision."""
    spec = get_hydraulic_revision(revision_id)
    baseline = build_source_state()
    if spec.revision_id == "administrative_no_op":
        return baseline

    payload_data = baseline.payload.model_dump(mode="json")
    if spec.revision_id == "major_idf_revision":
        scenarios = list(baseline.payload.scenarios)
        major_index = next(index for index, scenario in enumerate(scenarios) if scenario.scenario_id == "major-100yr")
        scenarios[major_index] = scenarios[major_index].model_copy(update={"rainfall_intensity_mm_h": 120.0})
        payload_data["scenarios"] = [scenario.model_dump(mode="json") for scenario in scenarios]
    elif spec.revision_id == "tailwater_revision":
        payload_data["network"] = baseline.payload.network.model_copy(
            update={"tailwater_elevation_m": 41.0}
        ).model_dump(mode="json")
    elif spec.revision_id == "outlet_geometry_revision":
        orifice = baseline.payload.outlet.orifice.model_copy(update={"diameter_m": 0.52})
        payload_data["outlet"] = baseline.payload.outlet.model_copy(update={"orifice": orifice}).model_dump(mode="json")
    else:  # pragma: no cover - the typed registry makes this unreachable
        raise AssertionError(f"unhandled hydraulic revision: {spec.revision_id}")

    payload = HydraulicSourcePayload.model_validate(payload_data)
    section_revisions = {
        section.section_name: (
            section.source_id,
            "Rev B" if section.section_name == spec.physical_section else section.revision,
        )
        for section in baseline.sections
    }
    return build_source_state_contract(
        world_id=baseline.world_id,
        title=baseline.title,
        description=baseline.description,
        claim_boundary=baseline.claim_boundary,
        reference=baseline.reference,
        payload=payload,
        section_revisions=section_revisions,
    )
