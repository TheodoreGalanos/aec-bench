# ABOUTME: Tests for soil archetypes and Australian site contexts.
# ABOUTME: Validates data integrity, frozen dataclass behaviour, and cross-references.

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.templates.archetypes import (
    SITE_CONTEXTS,
    SOIL_ARCHETYPES,
    SiteContext,
    SoilArchetype,
)


def test_all_archetypes_have_valid_ranges() -> None:
    """Every archetype's min values must be <= their corresponding max values."""
    for key, archetype in SOIL_ARCHETYPES.items():
        c_min, c_max = archetype.cohesion_kpa_min, archetype.cohesion_kpa_max
        assert c_min <= c_max, f"{key}: cohesion min ({c_min}) > max ({c_max})"

        f_min = archetype.friction_angle_deg_min
        f_max = archetype.friction_angle_deg_max
        assert f_min <= f_max, f"{key}: friction_angle min ({f_min}) > max ({f_max})"

        w_min = archetype.unit_weight_kn_m3_min
        w_max = archetype.unit_weight_kn_m3_max
        assert w_min <= w_max, f"{key}: unit_weight min ({w_min}) > max ({w_max})"


def test_all_site_contexts_reference_valid_archetypes() -> None:
    """Every archetype name referenced in a SiteContext must exist in SOIL_ARCHETYPES."""
    for site_key, context in SITE_CONTEXTS.items():
        for archetype_name in context.typical_archetypes:
            assert archetype_name in SOIL_ARCHETYPES, (
                f"Site context '{site_key}' references unknown archetype '{archetype_name}'"
            )


def test_minimum_archetype_count() -> None:
    """SOIL_ARCHETYPES must contain at least 8 entries."""
    assert len(SOIL_ARCHETYPES) >= 8, f"Expected at least 8 archetypes, got {len(SOIL_ARCHETYPES)}"


def test_minimum_site_context_count() -> None:
    """SITE_CONTEXTS must contain at least 8 entries."""
    assert len(SITE_CONTEXTS) >= 8, f"Expected at least 8 site contexts, got {len(SITE_CONTEXTS)}"


def test_archetype_is_frozen() -> None:
    """SoilArchetype instances must be immutable (frozen dataclass)."""
    archetype = list(SOIL_ARCHETYPES.values())[0]
    assert isinstance(archetype, SoilArchetype)
    with pytest.raises(FrozenInstanceError):
        archetype.cohesion_kpa_min = 999.0  # type: ignore[misc]


def test_site_context_is_frozen() -> None:
    """SiteContext instances must be immutable (frozen dataclass)."""
    context = list(SITE_CONTEXTS.values())[0]
    assert isinstance(context, SiteContext)
    with pytest.raises(FrozenInstanceError):
        context.location = "MUTATED"  # type: ignore[misc]
