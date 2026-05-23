# ABOUTME: Tests leaderboard-oriented communication report building over filtered TrialRecords.
# ABOUTME: Verifies grouped metrics are derived from canonical evaluation outputs only.

from aec_bench.communication.report_builder import build_leaderboard, leaderboard_to_dict
from tests.support.trial_record_factories import make_trial_record


def test_build_leaderboard_groups_trials_by_experiment() -> None:
    records = [
        make_trial_record(experiment_id="experiment-a"),
        make_trial_record(
            trial_id="trial-002",
            experiment_id="experiment-a",
            evaluation={
                "reward": 0.0,
                "validity": {
                    "output_parseable": False,
                    "schema_valid": False,
                    "verifier_completed": True,
                    "errors": ["schema"],
                },
            },
        ),
        make_trial_record(
            trial_id="trial-003",
            experiment_id="experiment-b",
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                    "errors": [],
                },
            },
        ),
    ]

    leaderboard = build_leaderboard(records)
    payload = leaderboard_to_dict(leaderboard)

    assert [entry["experiment_id"] for entry in payload["entries"]] == [
        "experiment-a",
        "experiment-b",
    ]
    assert payload["entries"][0]["n_trials"] == 2
    assert payload["entries"][0]["mean_reward"] == 0.5
    assert payload["entries"][0]["perfect_trial_rate"] == 0.5
    assert payload["entries"][1]["mean_reward"] == 0.5
