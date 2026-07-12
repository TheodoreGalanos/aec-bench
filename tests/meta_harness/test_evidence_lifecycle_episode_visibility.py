# ABOUTME: Tests visibility-aware conditional-evidence binding at the lifecycle episode boundary.
# ABOUTME: Ensures fresh episode identity hashes every requested artifact the model can read.

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aec_bench.meta_harness.evidence_lifecycle import _build_episode_request
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeContext,
    LifecycleVisibilityPolicy,
)


@pytest.mark.parametrize(
    "visibility_policy",
    [
        LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
    ],
)
def test_cumulative_episode_visibility_binds_prior_and_active_requested_evidence(
    visibility_policy: LifecycleVisibilityPolicy,
) -> None:
    context = LifecycleEpisodeContext.from_runtime_context(
        _runtime_context(),
        visibility_policy=visibility_policy,
    )

    request = _build_episode_request(
        context,
        _environment(visibility_policy),
        attempt_id="response_review.attempt-001",
        session_id="response_review.session-001",
    )

    assert [artifact.workspace_path for artifact in request.released_evidence_artifacts] == [
        "inbox/initial_review/requests/survey_revision/survey-rev-b.txt",
        "inbox/response_review/requests/outlet_inspection/inspection.txt",
    ]


def test_current_release_only_episode_visibility_excludes_prior_requested_evidence() -> None:
    context = LifecycleEpisodeContext.from_runtime_context(
        _runtime_context(),
        visibility_policy=LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY,
    )

    request = _build_episode_request(
        context,
        _environment(LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY),
        attempt_id="response_review.attempt-001",
        session_id="response_review.session-001",
    )

    assert [artifact.workspace_path for artifact in request.released_evidence_artifacts] == [
        "inbox/response_review/requests/outlet_inspection/inspection.txt",
    ]


def _environment(visibility_policy: LifecycleVisibilityPolicy) -> SimpleNamespace:
    return SimpleNamespace(
        execution_mode="fresh_context",
        memory_visibility_policy=visibility_policy.value,
        requested_adapter="tool_loop",
        requested_model="test-model",
        max_turns_per_session=20,
    )


def _runtime_context() -> dict[str, object]:
    return {
        "lifecycle_id": "lifecycle.demo",
        "world_id": "world.demo",
        "lifecycle_spec_sha256": "1" * 64,
        "package_sha256": "2" * 64,
        "status": "awaiting_checkpoint_submission",
        "active_checkpoint_id": "response_review",
        "checkpoint_id": "response_review",
        "title": "Response review",
        "workspace": "/tmp/run/workspace",
        "run_dir": "/tmp/run",
        "instruction": "Review the response.",
        "instruction_path": "/tmp/run/workspace/checkpoints/response_review/instruction.md",
        "submission_path": "/tmp/run/workspace/submissions/response_review.json",
        "released_files": ("response.txt",),
        "evidence_request_catalog": None,
        "completed_checkpoints": (
            {
                "checkpoint_id": "initial_review",
                "submission_path": "submissions/initial_review.json",
                "submission_sha256": "3" * 64,
                "released_files": ("initial.txt",),
            },
        ),
        "checkpoint_runs": (
            _checkpoint_run(
                checkpoint_id="initial_review",
                status="submitted",
                action_id="evidence-request-000001",
                sequence=1,
                request_id="survey_revision",
                artifact_path=("evidence_requests/evidence-request-000001/artifacts/survey-rev-b.txt"),
                workspace_path=("inbox/initial_review/requests/survey_revision/survey-rev-b.txt"),
                artifact_sha256="4" * 64,
                submission_path="submissions/initial_review.json",
                submission_sha256="3" * 64,
            ),
            _checkpoint_run(
                checkpoint_id="response_review",
                status="active",
                action_id="evidence-request-000002",
                sequence=2,
                request_id="outlet_inspection",
                artifact_path=("evidence_requests/evidence-request-000002/artifacts/inspection.txt"),
                workspace_path=("inbox/response_review/requests/outlet_inspection/inspection.txt"),
                artifact_sha256="5" * 64,
            ),
        ),
    }


def _checkpoint_run(
    *,
    checkpoint_id: str,
    status: str,
    action_id: str,
    sequence: int,
    request_id: str,
    artifact_path: str,
    workspace_path: str,
    artifact_sha256: str,
    submission_path: str | None = None,
    submission_sha256: str | None = None,
) -> dict[str, object]:
    return {
        "checkpoint_id": checkpoint_id,
        "status": status,
        "released_files": [],
        "submission_path": submission_path,
        "submission_sha256": submission_sha256,
        "attempts": [],
        "evidence_request_budget": 1,
        "evidence_request_budget_remaining": 0,
        "evidence_request_actions": [
            {
                "action_id": action_id,
                "sequence": sequence,
                "checkpoint_id": checkpoint_id,
                "requested_checkpoint_id": checkpoint_id,
                "request_id": request_id,
                "reason": "Inspect the declared evidence.",
                "session_id": f"{checkpoint_id}.session-001",
                "attempt_id": f"{checkpoint_id}.attempt-001",
                "outcome": "released",
                "rejection": None,
                "pre_action_state_sha256": "6" * 64,
                "post_action_state_sha256": "7" * 64,
                "released_artifacts": [
                    {
                        "path": artifact_path,
                        "workspace_path": workspace_path,
                        "sha256": artifact_sha256,
                    }
                ],
                "budget_before": 1,
                "budget_consumed": 1,
                "budget_after": 0,
                "inherited_from_parent": False,
            }
        ],
        "inherited_from_parent": False,
    }
