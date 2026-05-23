# ABOUTME: Tests the shared review service used by both the web and terminal review flows.
# ABOUTME: Verifies queue loading, holdout enforcement, and annotation persistence.

from pathlib import Path

import pytest

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.contracts.task_definition import Visibility
from aec_bench.feedback.annotation_consumer import write_reviewer_profile
from aec_bench.feedback.models import CalibrationReference, CalibrationStatus
from aec_bench.feedback.review_service import (
    ReviewAccessError,
    adjudicate_review_trial,
    load_review_bundle,
    load_review_queue,
    score_review_calibration,
    submit_review_annotation,
)
from aec_bench.ledger.writer import write_trial_record
from tests.support.feedback_factories import make_reviewer_profile
from tests.support.trial_record_factories import make_trial_record


def test_review_service_loads_queue_and_persists_annotation(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-public",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        ),
    )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-public"),
    )

    queue = load_review_queue(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-public",
    )

    assert [assignment.trial_id for assignment in queue.assignments] == ["trial-public"]

    annotation = submit_review_annotation(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-public",
        trial_id="trial-public",
        judgment=Judgment.PASS,
        categories=["verifier.output"],
        notes="Looks correct.",
    )
    bundle = load_review_bundle(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-public",
        trial_id="trial-public",
    )

    assert annotation.trial_id == "trial-public"
    assert len(bundle.annotations) == 1
    assert bundle.handoff.confidence.annotator_count == 1


def test_review_service_blocks_non_holdout_reviewer_from_holdout_trial(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-holdout",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-public", can_review_holdout=False),
    )

    with pytest.raises(ReviewAccessError, match="holdout"):
        load_review_bundle(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            feedback_root=feedback_root,
            reviewer_id="reviewer-public",
            trial_id="trial-holdout",
        )


def test_review_service_scores_calibration_and_updates_reviewer(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    for trial_id in ["trial-cal-1", "trial-cal-2"]:
        write_trial_record(
            ledger_root=tmp_path / "ledger",
            record=make_trial_record(
                trial_id=trial_id,
                task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
            ),
        )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-cal"),
    )

    submit_review_annotation(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-cal",
        trial_id="trial-cal-1",
        judgment=Judgment.PASS,
        categories=["verifier.output"],
        notes="Calibration case 1.",
        is_calibration=True,
        calibration_version="v1",
    )
    submit_review_annotation(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-cal",
        trial_id="trial-cal-2",
        judgment=Judgment.FAIL,
        categories=["instruction.clarity"],
        notes="Calibration case 2.",
        is_calibration=True,
        calibration_version="v1",
    )

    result, reviewer = score_review_calibration(
        feedback_root=feedback_root,
        reviewer_id="reviewer-cal",
        calibration_version="v1",
        references={
            "trial-cal-1": CalibrationReference(
                trial_id="trial-cal-1",
                reference_judgment=Judgment.PASS,
                reference_categories=["verifier.output"],
                calibration_version="v1",
            ),
            "trial-cal-2": CalibrationReference(
                trial_id="trial-cal-2",
                reference_judgment=Judgment.FAIL,
                reference_categories=["instruction.clarity"],
                calibration_version="v1",
            ),
        },
    )

    assert result.agreement_rate == 1.0
    assert reviewer.calibration_status == CalibrationStatus.CALIBRATED
    assert reviewer.calibration_version == "v1"


def test_review_service_adjudicates_disagreement_and_generates_feedback_items(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-public",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        ),
    )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-a", can_review_holdout=True),
    )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-b", can_review_holdout=True),
    )

    submit_review_annotation(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-a",
        trial_id="trial-public",
        judgment=Judgment.PASS,
        categories=["instruction.clarity"],
        notes="Pass.",
    )
    submit_review_annotation(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="reviewer-b",
        trial_id="trial-public",
        judgment=Judgment.FAIL,
        categories=["verifier.output"],
        notes="Fail.",
    )

    adjudication, items = adjudicate_review_trial(
        feedback_root=feedback_root,
        reviewer_id="reviewer-a",
        trial_id="trial-public",
        decision_id="decision-1",
        final_judgment=Judgment.FAIL,
        rationale="Failure is better supported.",
    )

    assert adjudication.status.value == "adjudicated"
    assert adjudication.final_judgment == Judgment.FAIL
    assert adjudication.decided_by == "reviewer-a"
    assert len(items) >= 1
    assert items[0].trial_id == "trial-public"


def _write_task_instance(*, tasks_root: Path, relative_path: str, visibility: Visibility) -> None:
    instance_dir = tasks_root / relative_path
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )
