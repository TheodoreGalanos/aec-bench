# ABOUTME: Tests immutable stewardship-study publication and independent report reload.
# ABOUTME: Rejects report tampering and evidence drift through the real artifact store.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    publish_provider_free_fixture_study,
    reload_and_verify_study_report,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    ImmutableArtifactIntegrityError,
)


def test_publishes_and_independently_reloads_complete_fixture_evidence(
    tmp_path: Path,
) -> None:
    published = publish_provider_free_fixture_study(tmp_path / "study-evidence")

    assert published.report.conclusion is ContinuityConclusion.ANALYSIS_FIXTURE
    assert published.report.provider_call_count == 0
    assert published.report.study_outcome_count == 0
    assert published.report.task_reward_mutation_count == 0
    assert published.report_reference.path.is_file()
    assert published.report_reference.path.parent.name == published.report.content_sha256
    assert len(published.delivery_references) == 64
    assert len(published.observation_references) == 64

    reloaded = reload_and_verify_study_report(
        root=tmp_path / "study-evidence",
        report_content_sha256=published.report.content_sha256,
    )
    assert reloaded == published.report


def test_republishing_the_same_fixture_keeps_all_artifact_identities(
    tmp_path: Path,
) -> None:
    root = tmp_path / "study-evidence"

    first = publish_provider_free_fixture_study(root)
    second = publish_provider_free_fixture_study(root)

    assert second.manifest == first.manifest
    assert second.plan == first.plan
    assert second.report == first.report
    assert second.manifest_reference == first.manifest_reference
    assert second.plan_reference == first.plan_reference
    assert second.delivery_references == first.delivery_references
    assert second.observation_references == first.observation_references
    assert second.report_reference == first.report_reference


def test_reload_rejects_tampered_report_bytes(tmp_path: Path) -> None:
    published = publish_provider_free_fixture_study(tmp_path / "study-evidence")
    payload = json.loads(published.report_reference.path.read_text(encoding="utf-8"))
    payload["provider_call_count"] = 1
    published.report_reference.path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ImmutableArtifactIntegrityError, match="identity|invalid"):
        reload_and_verify_study_report(
            root=tmp_path / "study-evidence",
            report_content_sha256=published.report.content_sha256,
        )
