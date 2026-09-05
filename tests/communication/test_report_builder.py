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


def test_leaderboard_costs_distinguish_unknown_and_free_experiments() -> None:
    from aec_bench.communication.metrics import total_cost_usd

    records = [
        make_trial_record(trial_id="known", experiment_id="partial", cost={"estimated_cost_usd": 0.25}),
        make_trial_record(trial_id="unknown", experiment_id="partial", cost=None),
        make_trial_record(trial_id="free", experiment_id="free", cost={"estimated_cost_usd": 0.0}),
    ]
    entries = leaderboard_to_dict(build_leaderboard(records))["entries"]
    free, partial = entries
    assert free["total_cost_usd"] == 0.0
    assert free["n_uncosted"] == 0
    assert partial["total_cost_usd"] is None
    assert partial["known_cost_usd"] == 0.25
    assert partial["n_costed"] == 1
    assert partial["n_uncosted"] == 1
    assert total_cost_usd(records) is None
    assert total_cost_usd([]) == 0.0
