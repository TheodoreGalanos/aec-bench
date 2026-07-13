# ABOUTME: Defines bounded public source interventions for the SSC-03 design-response lifecycle.
# ABOUTME: Builds deterministic option sources from the issued major-rainfall problem state.

from __future__ import annotations

from typing import Literal

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicSourcePayload,
    HydraulicSourceState,
    SectionName,
    build_source_state_contract,
)
from aec_bench.task_world_templates.hydraulics.revisions import build_hydraulic_revision_source_state

HydraulicInterventionId = Literal[
    "controlled_orifice_resize",
    "emergency_weir_enlargement",
]


class HydraulicInterventionSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    intervention_id: HydraulicInterventionId
    title: NonEmptyStr
    description: NonEmptyStr
    visibility: Literal["public"] = "public"
    delivery_class: Literal["controlled_outlet_works", "emergency_outlet_works"]
    changed_sections: tuple[SectionName, ...]


_INTERVENTIONS: dict[HydraulicInterventionId, HydraulicInterventionSpec] = {
    "controlled_orifice_resize": HydraulicInterventionSpec(
        intervention_id="controlled_orifice_resize",
        title="Resize the controlled outlet",
        description=(
            "Increase the declared orifice diameter from 0.42 m to 0.48 m while retaining the emergency weir."
        ),
        delivery_class="controlled_outlet_works",
        changed_sections=("outlet",),
    ),
    "emergency_weir_enlargement": HydraulicInterventionSpec(
        intervention_id="emergency_weir_enlargement",
        title="Enlarge the emergency weir",
        description=(
            "Increase the declared emergency-weir length from 4.2 m to 5.5 m while retaining the controlled outlet."
        ),
        delivery_class="emergency_outlet_works",
        changed_sections=("outlet",),
    ),
}


def list_hydraulic_intervention_ids() -> tuple[str, ...]:
    """Return the stable public intervention IDs in lexical order."""
    return tuple(sorted(_INTERVENTIONS))


def get_hydraulic_intervention(intervention_id: str) -> HydraulicInterventionSpec:
    """Return a defensive copy of one declared public intervention."""
    try:
        return _INTERVENTIONS[intervention_id].model_copy(deep=True)  # type: ignore[index]
    except KeyError as exc:
        known = ", ".join(list_hydraulic_intervention_ids())
        raise KeyError(f"unknown hydraulic intervention {intervention_id!r}; expected one of: {known}") from exc


def build_hydraulic_problem_source_state() -> HydraulicSourceState:
    """Return the issued major-rainfall source that requires a design response."""
    return build_hydraulic_revision_source_state("major_idf_revision")


def build_hydraulic_intervention_source_state(intervention_id: str) -> HydraulicSourceState:
    """Build the exact physical source activated by one bounded intervention."""
    intervention = get_hydraulic_intervention(intervention_id)
    problem = build_hydraulic_problem_source_state()
    payload_data = problem.payload.model_dump(mode="json")

    if intervention.intervention_id == "controlled_orifice_resize":
        orifice = problem.payload.outlet.orifice.model_copy(update={"diameter_m": 0.48})
        outlet = problem.payload.outlet.model_copy(update={"orifice": orifice})
    elif intervention.intervention_id == "emergency_weir_enlargement":
        emergency_weir = problem.payload.outlet.emergency_weir.model_copy(update={"length_m": 5.5})
        outlet = problem.payload.outlet.model_copy(update={"emergency_weir": emergency_weir})
    else:  # pragma: no cover - the typed registry makes this unreachable
        raise AssertionError(f"unhandled hydraulic intervention: {intervention.intervention_id}")
    payload_data["outlet"] = outlet.model_dump(mode="json")
    payload = HydraulicSourcePayload.model_validate(payload_data)

    section_revisions = {
        section.section_name: (
            section.source_id,
            "Rev C" if section.section_name in intervention.changed_sections else section.revision,
        )
        for section in problem.sections
    }
    return build_source_state_contract(
        world_id=problem.world_id,
        title=problem.title,
        description=problem.description,
        claim_boundary=problem.claim_boundary,
        reference=problem.reference,
        payload=payload,
        section_revisions=section_revisions,
    )
