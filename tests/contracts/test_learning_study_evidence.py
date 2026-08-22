# ABOUTME: Tests strict Learning Study evidence and assessment contract round trips.
# ABOUTME: Rejects inconsistent learner-state and transition commitment shapes.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study_assessment import (
    LearningComparisonValidity,
    LearningMeasurementResult,
    PairedMeasurementValue,
)
from aec_bench.contracts.learning_study_evidence import (
    LearnerStateRef,
    LearnerTransitionReceipt,
    StudyEvent,
    StudyEventKind,
)


def _artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifacts/sha256/aa/" + "a" * 64,
        sha256="a" * 64,
        size_bytes=10,
        media_type="application/x-tar",
    )


def test_evidence_contracts_round_trip() -> None:
    state = LearnerStateRef(
        state_id="run:cold:state:000",
        arm_run_id="run--cold--r01",
        treatment_id="reset",
        parent_state_id=None,
        created_after_step_id=None,
        artifact=_artifact(),
    )
    event = StudyEvent(
        sequence=0,
        study_run_id="run",
        kind=StudyEventKind.LEARNER_INITIALISED,
        arm_run_id=state.arm_run_id,
        reference="states/run:cold:state:000.json",
    )

    assert LearnerStateRef.model_validate_json(state.model_dump_json()) == state
    assert StudyEvent.model_validate_json(event.model_dump_json()) == event


def test_evidence_contracts_reject_inconsistent_state_and_discard() -> None:
    with pytest.raises(ValidationError, match="parent and creating step"):
        LearnerStateRef(
            state_id="state-1",
            arm_run_id="arm-1",
            treatment_id="memory",
            parent_state_id="state-0",
            created_after_step_id=None,
            artifact=_artifact(),
        )
    with pytest.raises(ValidationError, match="discarded transition must preserve"):
        LearnerTransitionReceipt(
            transition_id="transition-1",
            arm_run_id="arm-1",
            step_id="probe",
            operation_kind="probe_discard",
            state_before_id="state-0",
            candidate_state_id="state-1",
            committed_state_id="state-1",
            committed=False,
        )


def test_assessment_contract_retains_pair_values() -> None:
    result = LearningMeasurementResult(
        measurement_id="transfer",
        validity=LearningComparisonValidity.CONTROLLED,
        projection_id="canonical-reward",
        included_pairs=(
            PairedMeasurementValue(
                repetition=1,
                focal_trial_id="focal-1",
                comparator_trial_id="cold-1",
                focal_value=0.8,
                comparator_value=0.3,
                normalised_effect=0.5,
            ),
        ),
        excluded_repetitions=(),
        focal_mean=0.8,
        comparator_mean=0.3,
        mean_effect=0.5,
        diagnostics=(),
    )

    assert LearningMeasurementResult.model_validate_json(result.model_dump_json()) == result
