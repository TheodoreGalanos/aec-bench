# ABOUTME: Tests persisted adaptation artefact bundles built from accepted trial outputs.
# ABOUTME: Verifies family scoping, acceptance filtering, and JSON export payload shape.

import json
from pathlib import Path

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    DerivationStepRecord,
)
from aec_bench.evaluation.adaptation import (
    AcceptanceThresholds,
    build_adaptation_artifact_bundle,
    export_adaptation_artifact_bundle_json,
)
from tests.support.trial_record_factories import make_trial_record


def test_build_adaptation_artifact_bundle_preserves_only_accepted_trials(tmp_path: Path) -> None:
    records = [
        make_trial_record(
            trial_id="trial-benchmark",
            adaptation=_adaptation(
                variation_key="jurisdiction=us",
                variation={"jurisdiction": "us"},
            ),
            evaluation=EvaluationResult(
                reward=0.99,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.COMPLETE,
        ),
        make_trial_record(
            trial_id="trial-training",
            adaptation=_adaptation(
                variation_key="jurisdiction=ca",
                variation={"jurisdiction": "ca"},
            ),
            evaluation=EvaluationResult(
                reward=0.70,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.PARTIAL,
        ),
        make_trial_record(
            trial_id="trial-analysis",
            adaptation=_adaptation(
                variation_key="jurisdiction=mx",
                variation={"jurisdiction": "mx"},
            ),
            evaluation=EvaluationResult(
                reward=0.10,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
        ),
    ]

    bundle = build_adaptation_artifact_bundle(
        records,
        thresholds=AcceptanceThresholds(),
    )
    output_path = export_adaptation_artifact_bundle_json(bundle, tmp_path / "bundle.json")
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written["family_id"] == "heat-load-family"
    assert written["seed_task_id"] == "mechanical/heat-load/au-office"
    assert written["source_trial_count"] == 3
    assert written["preserved_trial_count"] == 2
    assert written["band_counts"] == {
        "benchmark_grade": 1,
        "training_grade": 1,
        "analysis_grade": 1,
        "verifier_test_grade": 0,
    }
    assert [item["trial_id"] for item in written["artefacts"]] == [
        "trial-benchmark",
        "trial-training",
    ]
    assert written["artefacts"][0]["acceptance_band"] == "benchmark_grade"
    assert written["artefacts"][1]["acceptance_band"] == "training_grade"


def test_build_adaptation_artifact_bundle_rejects_mixed_families() -> None:
    records = [
        make_trial_record(adaptation=_adaptation(family_id="family-a")),
        make_trial_record(
            trial_id="trial-002",
            adaptation=_adaptation(family_id="family-b"),
        ),
    ]

    try:
        build_adaptation_artifact_bundle(records)
    except ValueError as exc:
        assert "same adaptation family" in str(exc)
    else:
        raise AssertionError("expected mixed families to fail")


def _adaptation(
    *,
    family_id: str = "heat-load-family",
    variation_key: str = "jurisdiction=us",
    variation: dict[str, str] | None = None,
) -> AdaptationProvenance:
    return AdaptationProvenance(
        family_id=family_id,
        seed_task_id="mechanical/heat-load/au-office",
        variation_key=variation_key,
        variation=variation or {"jurisdiction": "us"},
        derivation_lineage=[
            DerivationStepRecord(
                axis="jurisdiction",
                parent_value="au",
                value=(variation or {"jurisdiction": "us"})["jurisdiction"],
            )
        ],
    )
