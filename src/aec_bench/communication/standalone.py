# ABOUTME: Standalone communication artefact builders for public and internal exports.
# ABOUTME: Keeps public and internal reporting visibility policy shared.

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from aec_bench.communication.job_report import (
    build_experiment_report,
    experiment_report_to_dict,
)
from aec_bench.communication.query import query_report_records
from aec_bench.communication.report_builder import build_leaderboard, leaderboard_to_dict

VisibilityScope = Literal["public", "internal"]


def build_public_leaderboard_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    return build_leaderboard_artifact(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        scope="public",
    )


def build_internal_leaderboard_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    return build_leaderboard_artifact(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        scope="internal",
    )


def build_public_experiment_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str,
) -> dict[str, Any]:
    return build_experiment_artifact(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        scope="public",
    )


def build_internal_experiment_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str,
) -> dict[str, Any]:
    return build_experiment_artifact(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        scope="internal",
    )


def build_leaderboard_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str | None = None,
    scope: VisibilityScope = "public",
) -> dict[str, Any]:
    records = query_report_records(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        include_holdout=scope == "internal",
    )
    leaderboard = build_leaderboard(records)
    return {
        "artifact_type": "leaderboard",
        "visibility_scope": scope,
        "experiment_id": experiment_id,
        "leaderboard": leaderboard_to_dict(leaderboard),
    }


def build_experiment_artifact(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str,
    scope: VisibilityScope = "public",
) -> dict[str, Any]:
    records = query_report_records(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        experiment_id=experiment_id,
        include_holdout=scope == "internal",
    )
    report = build_experiment_report(records)
    return {
        "artifact_type": "experiment_report",
        "visibility_scope": scope,
        "experiment_id": experiment_id,
        "report": experiment_report_to_dict(report),
    }
