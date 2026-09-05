# ABOUTME: Tests reproducible hydraulic lineages, selective revision, and verifier challenge controls.
# ABOUTME: Exercises the real lifecycle and solver rather than substituting expected rewards.

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.engineering_decisions.definitions import (
    CHALLENGES,
    HydraulicChallenge,
    HydraulicExperiment,
)
from aec_bench.experimentation.engineering_decisions.hydraulic_counterfactual import (
    run_hydraulic_counterfactual,
)
from aec_bench.experimentation.engineering_decisions.records import diagnostics
from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage


def test_lineages_are_reproducible_distinct_and_split_before_revision() -> None:
    lineages = [HydraulicLineage(seed=i) for i in range(20)]
    assert len({x.source().model_dump_json() for x in lineages}) == 20
    assert {p.split for p in HydraulicExperiment().partitions} == {"train", "development", "acceptance"}
    lineage = lineages[2]
    assert lineage.source() == HydraulicLineage(seed=2).source()
    assert lineage.source() == lineage.source("administrative_no_op")
    baseline = lineage.source().payload
    changed = lineage.source("major_idf_revision").payload
    assert baseline.catchments == changed.catchments
    assert baseline.basin == changed.basin
    assert baseline.scenarios[0] == changed.scenarios[0]
    assert baseline.scenarios[1].rainfall_intensity_mm_h != changed.scenarios[1].rainfall_intensity_mm_h


@pytest.mark.parametrize("seed", [-1, True, 2.5])
def test_invalid_generation_seed_fails(seed: object) -> None:
    with pytest.raises(ValidationError):
        HydraulicLineage.model_validate({"seed": seed})


@pytest.mark.parametrize(
    ("revision", "retained"),
    [
        ("administrative_no_op", 6),
        ("major_idf_revision", 3),
        ("outlet_geometry_revision", 2),
        ("tailwater_revision", 2),
    ],
)
def test_generated_siblings_complete_real_lifecycles(tmp_path: Path, revision: str, retained: int) -> None:
    report = diagnostics(run_hydraulic_counterfactual(tmp_path, seed=2, revision_id=revision))
    assert report["verification"]["passed"], report["verification"]
    assert len(report["preserved_operations"]) == retained
    assert len(report["recomputed_operations"]) == 6 - retained
    if revision == "major_idf_revision":
        assert report["baseline_readiness"] != report["revision_readiness"]


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_verifier_accepts_valid_alternatives_and_rejects_false_claims(
    tmp_path: Path, challenge: HydraulicChallenge
) -> None:
    report = diagnostics(
        run_hydraulic_counterfactual(tmp_path, seed=2, revision_id="major_idf_revision", challenge=challenge)
    )
    assert report["expectation_met"], report["verification"]


def test_lineage_metadata_cannot_relabel_other_source_bytes(tmp_path: Path) -> None:
    from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
        materialize_hydraulic_review_lifecycle,
        validated_hydraulic_review_variant,
    )

    package = materialize_hydraulic_review_lifecycle(tmp_path, lineage=HydraulicLineage(seed=2))
    (package / "hidden" / "lineage.json").write_text('{"seed": 8}')
    with pytest.raises(ValueError, match="identity does not match"):
        validated_hydraulic_review_variant(package)
