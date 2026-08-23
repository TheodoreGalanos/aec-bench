# ABOUTME: Authors and validates dam-seepage profile variants for the dam learning family.
# ABOUTME: Cross-checks each variant's declared expected response against the world's own derivation logic.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.task_definition import Difficulty
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageResponse,
    SeepageScenario,
    requires_engineering_review,
)

_SCENARIO_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class DamSeepageProfileVariant:
    """One authored dam-seepage profile variant, checked in as its own scenario file."""

    profile_id: str
    scenario_path: Path
    title: str
    summary: str
    difficulty: Difficulty
    tags: tuple[str, ...]
    expected_required_response: SeepageResponse
    rationale: str


def dam_seepage_profile_variants() -> tuple[DamSeepageProfileVariant, ...]:
    """Return the small, matched set of additional dam-seepage profiles W01 needs."""

    return (
        DamSeepageProfileVariant(
            profile_id="unreliable-instrument-escalation",
            scenario_path=_SCENARIO_DIR / "unreliable-instrument-escalation.json",
            title="Unreliable instrument escalation",
            summary="An otherwise unremarkable seepage event where the measurement instrument is unreliable.",
            difficulty=Difficulty.MEDIUM,
            tags=("dam", "monitoring", "seepage", "synthetic", "acquisition"),
            expected_required_response=SeepageResponse.ENGINEERING_REVIEW,
            rationale=(
                "instrument_condition is unreliable while every reading otherwise stays within routine "
                "flow and visual limits, so escalation is justified solely by instrument distrust."
            ),
        ),
        DamSeepageProfileVariant(
            profile_id="reliable-routine-surveillance",
            scenario_path=_SCENARIO_DIR / "reliable-routine-surveillance.json",
            title="Reliable routine surveillance",
            summary=(
                "A superficially familiar seepage event where the instrument is serviceable "
                "and escalation is not warranted."
            ),
            difficulty=Difficulty.MEDIUM,
            tags=("dam", "monitoring", "seepage", "synthetic", "probe"),
            expected_required_response=SeepageResponse.ROUTINE_SURVEILLANCE,
            rationale=(
                "instrument_condition is serviceable and no reading trips the visual or flow alert "
                "conditions, so continued routine surveillance is the only correct response."
            ),
        ),
    )


def validate_dam_seepage_profile_variant(variant: DamSeepageProfileVariant) -> SeepageScenario:
    """Load, validate, and cross-check one authored variant against the world's own logic."""

    scenario = SeepageScenario.model_validate_json(variant.scenario_path.read_bytes())
    if scenario.profile_id != variant.profile_id:
        raise ValueError(
            f"dam-variant-invalid: scenario profile_id {scenario.profile_id!r} "
            f"does not match declared variant {variant.profile_id!r}"
        )
    if scenario.task_world_id != DAM_SEEPAGE_TASK_WORLD_ID:
        raise ValueError(f"dam-variant-invalid: scenario world id does not match {DAM_SEEPAGE_TASK_WORLD_ID!r}")
    derived_requires_review = requires_engineering_review(scenario)
    expected_requires_review = variant.expected_required_response is SeepageResponse.ENGINEERING_REVIEW
    if derived_requires_review != expected_requires_review:
        raise ValueError(
            f"dam-variant-expectation-mismatch: {variant.profile_id!r} declares "
            f"{variant.expected_required_response.value!r} but the world derives "
            f"{'engineering-review' if derived_requires_review else 'routine-surveillance'!r}"
        )
    return scenario


__all__ = (
    "DamSeepageProfileVariant",
    "dam_seepage_profile_variants",
    "validate_dam_seepage_profile_variant",
)
