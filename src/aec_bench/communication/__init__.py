# ABOUTME: Communication package for metrics, reports, exports, and dashboards in aec-bench.
# ABOUTME: Communication artefacts compile from canonical evaluation and trial data only.

from aec_bench.communication.metrics import mean_reward, perfect_trial_rate, total_cost_usd
from aec_bench.communication.query import query_report_records
from aec_bench.communication.report_builder import (
    LeaderboardEntry,
    LeaderboardReport,
    build_leaderboard,
    leaderboard_to_dict,
)
from aec_bench.communication.standalone import (
    build_adaptation_family_artifact,
    build_internal_experiment_artifact,
    build_internal_leaderboard_artifact,
    build_public_experiment_artifact,
    build_public_leaderboard_artifact,
    export_standalone_artifact_json,
)

__all__ = [
    "LeaderboardEntry",
    "LeaderboardReport",
    "build_adaptation_family_artifact",
    "build_internal_experiment_artifact",
    "build_internal_leaderboard_artifact",
    "build_leaderboard",
    "build_public_experiment_artifact",
    "build_public_leaderboard_artifact",
    "export_standalone_artifact_json",
    "leaderboard_to_dict",
    "mean_reward",
    "perfect_trial_rate",
    "query_report_records",
    "total_cost_usd",
]
