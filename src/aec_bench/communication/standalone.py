# ABOUTME: Standalone communication artefact builders for public and internal exports.
# ABOUTME: Keeps visibility policy and adaptation-family reporting shared.
# ABOUTME: The same builders support CLI exports now and web routes later.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from aec_bench.communication.job_report import (
    build_experiment_report,
    experiment_report_to_dict,
)
from aec_bench.communication.query import query_report_records
from aec_bench.communication.report_builder import build_leaderboard, leaderboard_to_dict
from aec_bench.evaluation.adaptation import (
    AcceptanceThresholds,
    build_adaptation_artifact_bundle,
)
from aec_bench.ledger.api import query_ledger

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


def build_adaptation_family_artifact(
    *,
    ledger_root: Path,
    family_id: str,
    experiment_id: str | None = None,
    thresholds: AcceptanceThresholds | None = None,
) -> dict[str, Any]:
    records = query_ledger(ledger_root, experiment_id=experiment_id)
    family_records = [
        record for record in records if record.adaptation is not None and record.adaptation.family_id == family_id
    ]
    bundle = build_adaptation_artifact_bundle(family_records, thresholds=thresholds)
    return {
        "artifact_type": "adaptation_family",
        "family_id": family_id,
        "experiment_id": experiment_id,
        "bundle": bundle.to_dict(),
    }


def export_standalone_artifact_json(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


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
