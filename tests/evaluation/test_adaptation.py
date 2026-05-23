# ABOUTME: Covers the first Phase 6A adaptation metadata and variation expansion slice.
# ABOUTME: Verifies deterministic candidate expansion and lineage without changing harness flow.

from pytest import raises

from aec_bench.evaluation.adaptation import (
    AdaptationSpec,
    VariationAxis,
    expand_adaptation_spec,
)


def test_expand_adaptation_spec_builds_deterministic_candidates() -> None:
    spec = AdaptationSpec(
        family_id="heat-load-audit",
        seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
        seed_variation={
            "city": "sydney",
            "building_type": "office",
        },
        axes=[
            VariationAxis(axis="city", values=["sydney", "perth"]),
            VariationAxis(axis="building_type", values=["office", "mixed-use"]),
        ],
    )

    candidates = expand_adaptation_spec(spec)

    assert [candidate.variation_key for candidate in candidates] == [
        "city=sydney__building_type=mixed-use",
        "city=perth__building_type=office",
        "city=perth__building_type=mixed-use",
    ]
    assert candidates[0].derivation_lineage[0].axis == "building_type"
    assert candidates[0].derivation_lineage[0].parent_value == "office"
    assert candidates[0].derivation_lineage[0].value == "mixed-use"
    assert candidates[2].derivation_lineage[0].axis == "city"
    assert candidates[2].derivation_lineage[1].axis == "building_type"


def test_expand_adaptation_spec_can_include_seed_without_lineage() -> None:
    spec = AdaptationSpec(
        family_id="heat-load-audit",
        seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
        seed_variation={"city": "sydney"},
        axes=[VariationAxis(axis="city", values=["sydney", "perth"])],
        include_seed=True,
    )

    candidates = expand_adaptation_spec(spec)

    assert [candidate.variation_key for candidate in candidates] == [
        "city=sydney",
        "city=perth",
    ]
    assert candidates[0].derivation_lineage == []
    assert candidates[1].derivation_lineage[0].axis == "city"
    assert candidates[1].derivation_lineage[0].parent_value == "sydney"
    assert candidates[1].derivation_lineage[0].value == "perth"


def test_adaptation_spec_rejects_seed_values_outside_axis_domain() -> None:
    with raises(ValueError, match="seed_variation value must exist in axis values"):
        AdaptationSpec(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            seed_variation={"city": "darwin"},
            axes=[VariationAxis(axis="city", values=["sydney", "perth"])],
        )


def test_variation_axis_rejects_duplicate_values() -> None:
    with raises(ValueError, match="values must be unique"):
        VariationAxis(axis="jurisdiction", values=["au", "au"])
