# ABOUTME: Tests the frozen retrieval-state continuity study contracts and plan.
# ABOUTME: Proves exact pairing, budgets, treatment isolation, and provider-free authority.

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from aec_bench.experiments.retrieval_state_continuity import (
    StudyPhase,
    StudyPlan,
    Treatment,
    build_provider_free_manifest,
    build_study_plan,
)


def test_manifest_freezes_temporal_question_budget_and_analysis() -> None:
    manifest = build_provider_free_manifest()

    assert manifest.phase is StudyPhase.ANALYSIS_FIXTURE
    assert manifest.profile_id == "AU-NSW-LH-SYN-SPS-v1"
    assert manifest.study_id == "retrieval-state-continuity-under-delayed-evidence.v1"
    assert manifest.material_evidence_version_id == "pump-a-delayed-condition-report.v1"
    assert manifest.pre_handover_world_time_seconds == 7_200_000
    assert manifest.evidence_available_at_seconds == 7_203_600
    assert manifest.decision_deadline_seconds == 7_207_200
    assert manifest.treatments == tuple(Treatment)
    assert manifest.budget.maximum_search_calls == 2
    assert manifest.budget.maximum_fetch_calls == 1
    assert manifest.budget.maximum_references_per_result == 5
    assert manifest.budget.maximum_visible_bytes == 8_000
    assert manifest.budget.maximum_visible_tokens == 2_000
    assert manifest.budget.maximum_agent_turns == 12
    assert manifest.budget.simulated_retrieval_duration_seconds == 0
    assert manifest.budget.external_retrieval_provider_spend_microusd == 0
    assert manifest.analysis.independent_world_history_count == 8
    assert manifest.analysis.model_sampling_replicates_per_history == 4
    assert manifest.analysis.minimum_meaningful_effect == 0.25
    assert manifest.analysis.bootstrap_replicates == 20_000
    assert manifest.analysis.bootstrap_seed == 20_260_802
    assert manifest.analysis.minimum_eligible_world_histories == 7
    assert manifest.analysis.minimum_eligible_pairs == 28
    assert manifest.provider_calls_allowed == 0
    assert not manifest.study_outcomes_allowed
    assert not manifest.promotion_permitted


def test_plan_has_exact_clustered_pairs_and_hidden_balanced_order() -> None:
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)

    assert plan.manifest_content_sha256 == manifest.content_sha256
    assert len(plan.blocks) == 32
    assert len(plan.trials) == 64
    assert len({trial.trial_id for trial in plan.trials}) == 64
    assert tuple(trial for block in plan.blocks for trial in block.trials) == plan.trials
    assert Counter(block.world_history_seed for block in plan.blocks) == {
        seed: 4 for seed in manifest.world_history_seeds
    }
    for seed in manifest.world_history_seeds:
        blocks = [block for block in plan.blocks if block.world_history_seed == seed]
        assert Counter(block.trials[0].treatment for block in blocks) == {
            Treatment.RETRIEVAL_STATE_ABSENT: 2,
            Treatment.RETRIEVAL_STATE_PRESERVED: 2,
        }
    assert all(block.trials[0].execution_position + 1 == block.trials[1].execution_position for block in plan.blocks)
    assert all("absent" not in trial.trial_id and "preserved" not in trial.trial_id for trial in plan.trials)
    assert build_study_plan(manifest) == plan


def test_plan_rejects_incomplete_coverage() -> None:
    plan = build_study_plan(build_provider_free_manifest())
    payload = plan.model_dump(mode="json")
    payload["content_sha256"] = ""
    payload["trials"] = payload["trials"][:-1]

    with pytest.raises(ValidationError, match="ordered block trials"):
        StudyPlan.model_validate(payload)
