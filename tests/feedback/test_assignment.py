# ABOUTME: Tests reviewer assignment logic for the feedback domain in aec-bench.
# ABOUTME: Verifies holdout safety, duplicate avoidance, and discipline-aware prioritization.

from aec_bench.contracts.task_definition import Visibility
from aec_bench.feedback.assignment import build_reviewer_queue
from tests.support.feedback_factories import make_feedback_annotation, make_reviewer_profile
from tests.support.trial_record_factories import make_trial_record


def test_build_reviewer_queue_filters_holdout_and_prioritizes_matching_discipline() -> None:
    reviewer = make_reviewer_profile(reviewer_id="reviewer-public", discipline="mechanical")
    records = [
        make_trial_record(
            trial_id="trial-mech",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        ),
        make_trial_record(
            trial_id="trial-holdout",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
        make_trial_record(
            trial_id="trial-elec",
            task={"task_id": "electrical/voltage-drop/public-task", "task_revision": "git"},
        ),
    ]
    annotations = [
        make_feedback_annotation(
            annotation_id="annotation-existing",
            trial_id="trial-elec",
            task_id="electrical/voltage-drop/public-task",
            reviewer_id="reviewer-other",
            reviewer_discipline="electrical",
        ),
        make_feedback_annotation(
            annotation_id="annotation-self",
            trial_id="trial-holdout",
            task_id="mechanical/heat-load/holdout-task",
            task_visibility=Visibility.HOLDOUT,
            reviewer_id="reviewer-public",
        ),
    ]

    assignments = build_reviewer_queue(
        records=records,
        task_visibility_by_id={
            "mechanical/heat-load/public-task": Visibility.PUBLIC,
            "mechanical/heat-load/holdout-task": Visibility.HOLDOUT,
            "electrical/voltage-drop/public-task": Visibility.PUBLIC,
        },
        reviewer=reviewer,
        existing_annotations=annotations,
    )

    assert [assignment.trial_id for assignment in assignments] == ["trial-mech", "trial-elec"]
    assert assignments[0].assignment_reason == "discipline_match"
    assert assignments[1].assignment_reason == "cross_discipline_backup"
    assert all(assignment.task_visibility == Visibility.PUBLIC for assignment in assignments)
