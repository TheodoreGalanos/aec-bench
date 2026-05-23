# ABOUTME: Tests ledger-backed trace summary exports derived from imported TrialRecords.
# ABOUTME: Verifies per-trial signal extraction and batch export over a real Harbor job.

from pathlib import Path

import pytest

from aec_bench.communication.trace_report import build_trace_summaries, trace_summary_from_record
from aec_bench.harness.harbor_import import import_harbor_job, import_harbor_trial

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"
HARBOR_TRIAL_DIR = HARBOR_JOB_DIR / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_trace_summary_from_record_preserves_legacy_summary_fields() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    summary = trace_summary_from_record(record)

    assert summary.trial_id == "brisbane-8rm__BHVuXg2"
    assert summary.model == "claude-sonnet-4-6"
    assert summary.task == "brisbane-8rm"
    assert summary.task_type == "audit-office-building"
    assert summary.reward == 1.0
    assert summary.turns_used == 8
    assert summary.max_turns == 20
    assert summary.tokens_in == 131093
    assert summary.tokens_out == 9283
    assert summary.duration_sec > 0.0
    assert summary.tool_calls > 0
    assert summary.tool_errors == 0
    assert summary.used_calc_tool is True
    assert summary.wrote_output is True
    assert summary.fields_correct == 2
    assert summary.fields_total == 8
    assert summary.first_error is None
    assert summary.trace_path.endswith("agent/conversation.jsonl")


@_skip_no_job_data
def test_build_trace_summaries_returns_real_job_results() -> None:
    records = import_harbor_job(job_dir=HARBOR_JOB_DIR, repo_root=REPO_ROOT)

    summaries = build_trace_summaries(records)

    assert len(summaries) == 60
    assert summaries[0].trial_id == "adelaide-15rm__EUcepGa"
    assert summaries[-1].trial_id == "townsville-8rm__WBreAVv"
