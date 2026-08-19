# ABOUTME: Tests phase-neutral evaluation-generation, cohort, budget, and batch contracts.
# ABOUTME: Proves supplied cardinality and budget data govern reusable generation schemas.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.evaluation_generation.cohort import EvaluationTaskIdentity
from aec_bench.contracts.evaluation_generation.spec import (
    CandidateKindRequirement,
    EvaluationExecutionProfileRef,
    EvaluationGenerationBudget,
    EvaluationGenerationSpec,
)
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_review_snapshot import TaskReviewSnapshot
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _execution_profile_ref() -> EvaluationExecutionProfileRef:
    return EvaluationExecutionProfileRef(
        profile_id="proposal-execution.sequential",
        version="1",
        content_sha256=_sha("proposal-execution-profile"),
    )


def _task_snapshot(task_id: str, label: str) -> ArtifactTaskSnapshotRef:
    digest = _sha(label)
    return ArtifactTaskSnapshotRef(
        task_id=task_id,
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest}",
            sha256=digest,
            size_bytes=len(label),
            media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
        ),
    )


def test_evaluation_task_uses_exact_snapshots_and_one_review_value() -> None:
    task_id = "civil/drainage/review"
    public = _task_snapshot(task_id, "public")
    identity = EvaluationTaskIdentity(
        task_id=task_id,
        public_snapshot=public,
        snapshot=_task_snapshot(task_id, "sealed"),
        review=TaskReviewSnapshot(
            task_id=task_id,
            profile_id="review.drainage",
            visibility=Visibility.HOLDOUT,
        ),
    )

    assert set(identity.model_dump(mode="json")) == {
        "schema_version",
        "task_id",
        "public_snapshot",
        "snapshot",
        "review",
        "content_sha256",
    }
    with pytest.raises(ValidationError, match="must be distinct"):
        EvaluationTaskIdentity(
            task_id=task_id,
            public_snapshot=public,
            snapshot=public,
            review=identity.review,
        )


def _custom_budget() -> EvaluationGenerationBudget:
    return EvaluationGenerationBudget(
        task_count=3,
        proposer_invocation_count=6,
        assignment_count=12,
        primary_execution_attempt_count=12,
        max_no_effect_retry_count=2,
        max_execution_attempt_count=14,
        planned_high_level_invocation_count=18,
        max_total_attempt_count=20,
        max_main_model_turns=90,
        max_auxiliary_compaction_calls=30,
        max_raw_provider_calls=120,
        max_observed_tokens=900_000,
        max_cost_usd=12.5,
        max_wall_time_seconds=7_200,
        max_concurrency=3,
    )


def test_generation_spec_treats_cardinality_and_budget_as_supplied_data() -> None:
    spec = EvaluationGenerationSpec(
        spec_id="evaluation-generation.custom",
        task_count=3,
        proposer_invocations_per_task=2,
        candidate_kind_requirements=(
            CandidateKindRequirement(
                kind=ProgramCandidateKind.INCUMBENT,
                count_per_task=1,
            ),
            CandidateKindRequirement(
                kind=ProgramCandidateKind.PROPOSAL,
                count_per_task=3,
            ),
        ),
        assignment_count_per_task=4,
        total_assignment_count=12,
        effect_budget=_custom_budget(),
        execution_profile=_execution_profile_ref(),
    )

    assert spec.task_count == 3
    assert spec.proposal_candidate_count_per_task == 3
    assert spec.total_assignment_count == 12

    mismatched = spec.model_dump(mode="python", exclude={"content_sha256"})
    mismatched["effect_budget"].pop("content_sha256")
    mismatched["effect_budget"]["task_count"] = 2
    with pytest.raises(ValidationError, match="budget task count"):
        EvaluationGenerationSpec.model_validate(mismatched)
