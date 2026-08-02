# ABOUTME: Runs the complete provider-free retrieval-state study specification path.
# ABOUTME: Proves immutable publication and independent reload without model calls.

from __future__ import annotations

from pathlib import Path

from aec_bench.experiments.retrieval_state_continuity import (
    StudyConclusion,
    publish_provider_free_study,
    reload_and_verify_study_report,
)


def test_provider_free_study_specification_e2e(tmp_path: Path) -> None:
    root = tmp_path / "retrieval-state-study"
    published = publish_provider_free_study(root)
    reloaded = reload_and_verify_study_report(
        root=root,
        report_content_sha256=published.report.content_sha256,
    )

    assert reloaded == published.report
    assert reloaded.conclusion is StudyConclusion.ANALYSIS_FIXTURE
    assert reloaded.fixture_rule_result is StudyConclusion.SUPPORTED
    assert reloaded.coverage.exact
    assert reloaded.provider_call_count == 0
    assert reloaded.study_outcome_count == 0
    assert not reloaded.promotion_permitted
    assert published.manifest.provider_calls_allowed == 0
    assert not published.manifest.study_outcomes_allowed
