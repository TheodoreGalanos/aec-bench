# ABOUTME: Runs the complete provider-free stewardship fixture and reload journey.
# ABOUTME: Proves analysis readiness without provider calls, study outcomes, or reward changes.

from __future__ import annotations

from pathlib import Path

from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    publish_provider_free_fixture_study,
    reload_and_verify_study_report,
)


def test_provider_free_study_freeze_e2e(tmp_path: Path) -> None:
    root = tmp_path / "asw-4a"
    result = publish_provider_free_fixture_study(root)
    replayed = reload_and_verify_study_report(
        root=root,
        report_content_sha256=result.report.content_sha256,
    )

    assert replayed == result.report
    assert replayed.conclusion is ContinuityConclusion.ANALYSIS_FIXTURE
    assert replayed.fixture_rule_result is ContinuityConclusion.SUPPORTED
    assert replayed.coverage.exact
    assert replayed.coverage.analyzable_block_count == 32
    assert replayed.provider_call_count == 0
    assert replayed.input_token_count == 0
    assert replayed.output_token_count == 0
    assert replayed.spend_currency is None
    assert replayed.spend_microunits == 0
    assert replayed.study_outcome_count == 0
    assert replayed.fixture_observation_count == 64
    assert replayed.task_reward_mutation_count == 0
    assert not result.manifest.study_outcomes_allowed
    assert result.manifest.provider_calls_allowed == 0
