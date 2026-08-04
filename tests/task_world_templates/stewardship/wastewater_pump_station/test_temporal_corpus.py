# ABOUTME: Tests immutable temporal corpus publication, lineage, and source-right controls.
# ABOUTME: Uses the certified pump-station package and real filesystem storage without mocks.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceIntegrityError,
    TemporalEvidenceRepository,
    TemporalEvidenceRightsClass,
    build_reference_temporal_evidence_bundle,
)


def test_temporal_corpus_publishes_and_reloads_exact_certified_lineage(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")

    repository.initialize(bundle, package=package)
    reloaded = repository.load_bundle(package=package)

    assert reloaded == bundle
    assert reloaded.capability.corpus_snapshot_id == bundle.corpus_manifest.content_sha256
    assert reloaded.corpus_manifest.parent_package_content_id == package.package_content_id
    assert reloaded.corpus_manifest.parent_generation_id == package.generation_id
    assert reloaded.versions
    assert all(item.content_text for item in reloaded.versions)
    assert all(
        source.rights_class is TemporalEvidenceRightsClass.REDISTRIBUTABLE for source in reloaded.lineage.sources
    )


def test_temporal_corpus_rejects_drifted_parent_and_prohibited_source_bytes(
    tmp_path: Path,
) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")

    drifted_manifest = bundle.corpus_manifest.model_copy(
        update={"parent_package_content_id": "0" * 64},
    )
    with pytest.raises(TemporalEvidenceIntegrityError, match="parent package"):
        repository.initialize(
            bundle.model_copy(update={"corpus_manifest": drifted_manifest}),
            package=package,
        )

    cite_only_source = bundle.lineage.sources[0].model_copy(
        update={
            "rights_class": TemporalEvidenceRightsClass.CITE_ONLY,
            "redistribution_permitted": False,
        },
    )
    cite_only_lineage = bundle.lineage.model_copy(
        update={
            "sources": (cite_only_source, *bundle.lineage.sources[1:]),
        },
    )
    with pytest.raises(TemporalEvidenceIntegrityError, match="prohibited source bytes"):
        repository.initialize(
            bundle.model_copy(update={"lineage": cite_only_lineage}),
            package=package,
        )


def test_temporal_corpus_detects_persisted_artifact_drift(tmp_path: Path) -> None:
    package = load_reference_package()
    bundle = build_reference_temporal_evidence_bundle(
        package,
        world_branch_id="branch-temporal",
    )
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")
    repository.initialize(bundle, package=package)
    manifest_path = repository.root / "corpus" / "manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(TemporalEvidenceIntegrityError, match="corpus manifest"):
        repository.load_bundle(package=package)
