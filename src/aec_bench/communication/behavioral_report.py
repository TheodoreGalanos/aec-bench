# ABOUTME: Dedicated behavioral export helpers for ledger-backed downstream analysis.
# ABOUTME: Flattens per-trial behavioral summaries while preserving aggregate confidence context.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.aggregation import BehavioralTraceClassifier, summarize_behavioral_records


@dataclass(frozen=True)
class BehavioralExport:
    summary: dict[str, Any]
    trials: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "trials": self.trials,
        }


def build_behavioral_export(
    records: list[TrialRecord],
    *,
    classifier: BehavioralTraceClassifier,
) -> BehavioralExport:
    summary = summarize_behavioral_records(records, classifier=classifier)
    raw_trials = cast(list[object], summary.get("trials", []))
    trials = [item for item in raw_trials if isinstance(item, dict)]
    return BehavioralExport(summary=summary, trials=trials)


def export_behavioral_report_json(export_payload: BehavioralExport, output_path: Path) -> Path:
    output_path.write_text(
        json.dumps(export_payload.to_dict(), indent=2),
        encoding="utf-8",
    )
    return output_path
