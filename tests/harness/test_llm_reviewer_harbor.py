# ABOUTME: Tests the Harbor post-run hook for LLM reviewer artifacts.
# ABOUTME: Verifies reviewer summaries are produced before ledger import consumes trials.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.evaluation.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    run_harbor_job_reviewer,
)


def test_run_harbor_job_reviewer_writes_trial_reviewer_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "mechanical" / "heat-load" / "alpha"
    trial_dir = repo_root / "jobs" / "job-001" / "trial-001"
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Write the answer.", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("answer", encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 0.0}', encoding="utf-8")
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "config": {
                    "task": {"path": "tasks/mechanical/heat-load/alpha"},
                    "job_id": "job-001",
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_harbor_job_reviewer(
        job_dir=repo_root / "jobs" / "job-001",
        repo_root=repo_root,
        config=ReviewerRunConfig(
            enabled=True,
            models=[
                ReviewerEndpointConfig(
                    name="missing-compatible-endpoint",
                    model="reviewer",
                    provider="openai_compatible",
                )
            ],
        ),
    )

    summary_path = trial_dir / "reviewer" / "summary.json"

    assert result.trial_count == 1
    assert result.error_count == 1
    assert summary_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["status"] == "error"
