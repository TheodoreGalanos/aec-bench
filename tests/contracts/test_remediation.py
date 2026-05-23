# ABOUTME: Tests remediation contracts — Patch, PatchProposal, HitlItem, RemediationResult.
# ABOUTME: Patches are surgical diffs with locator + replacement; HITL items are structured review queue entries.

import dataclasses

import pytest

from aec_bench.contracts.remediation import (
    HitlItem,
    Patch,
    PatchProposal,
    PatchStatus,
    RemediationIteration,
    RemediationResult,
)


def test_patch_is_frozen():
    patch = Patch(
        section_id="contractor_obligations",
        locator_phrase="shall not permit any person",
        replacement="shall not permit unauthorised personnel",
        occurrence=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        patch.replacement = "x"  # type: ignore[misc]


def test_patch_proposal_carries_patch_plus_metadata():
    prop = PatchProposal(
        patch=Patch(
            section_id="x",
            locator_phrase="a",
            replacement="b",
            occurrence=1,
        ),
        criterion="clear responsible party",
        evidence="Obligation lacks named party",
        rationale="Name the Site Access Coordinator",
        confidence="high",
        status=PatchStatus.APPLY,
    )
    assert prop.status == PatchStatus.APPLY
    assert prop.criterion == "clear responsible party"


def test_patch_status_values():
    assert PatchStatus.APPLY.value == "apply"
    assert PatchStatus.REVIEW.value == "review"
    assert PatchStatus.DEFER.value == "defer"


def test_hitl_item_captures_review_context():
    item = HitlItem(
        section_id="contractor_obligations",
        criterion="DCAC process steps",
        evidence="No DCAC process captured in sources",
        suggested_resolution="Clarify with project security lead",
        attempt_count=2,
    )
    assert item.attempt_count == 2


def test_remediation_iteration_tracks_reward_and_patches():
    it = RemediationIteration(
        iteration=1,
        patches_applied=3,
        patches_rejected=1,
        reward_before=0.69,
        reward_after=0.78,
    )
    assert it.reward_delta == pytest.approx(0.09)


def test_remediation_result_summary():
    result = RemediationResult(
        iterations=(
            RemediationIteration(
                iteration=1,
                patches_applied=3,
                patches_rejected=0,
                reward_before=0.70,
                reward_after=0.78,
            ),
            RemediationIteration(
                iteration=2,
                patches_applied=2,
                patches_rejected=1,
                reward_before=0.78,
                reward_after=0.82,
            ),
        ),
        hitl_items=(
            HitlItem(
                section_id="x",
                criterion="y",
                evidence="z",
                suggested_resolution="w",
                attempt_count=2,
            ),
        ),
        stop_reason="plateau",
        final_reward=0.82,
    )
    assert len(result.iterations) == 2
    assert result.total_patches_applied == 5
    assert result.stop_reason == "plateau"


def test_remediation_result_carries_final_output_text():
    result = RemediationResult(
        iterations=(),
        hitl_items=(),
        stop_reason="no_defects",
        final_reward=1.0,
        final_output_text="Patched content.",
    )
    assert result.final_output_text == "Patched content."
