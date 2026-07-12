# ABOUTME: Tests for importing Harbor trial artifacts into Python TrialRecord contracts.
# ABOUTME: Covers a real successful Harbor trial and missing-result failure handling.

import json
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import Completeness
from aec_bench.harness.harbor_import import (
    HarborImportError,
    import_harbor_job,
    import_harbor_trial,
    iter_harbor_trial_dirs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"
HARBOR_TRIAL_DIR = HARBOR_JOB_DIR / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_import_harbor_trial_maps_real_successful_trial() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    assert record.trial_id == "brisbane-8rm__BHVuXg2"
    assert record.experiment_id == "6834bc30-3801-4a45-a114-afb2d3764b7d"
    assert record.task.task_id == "mechanical/heat-load/audit-office-building/brisbane-8rm"
    assert record.task.task_revision == "b3b51915e026ccfe5393293338afb9360eefdd1d4d17c55760494334241403c5"
    assert record.task.visibility is Visibility.PUBLIC
    assert record.agent.adapter == "tool-loop-anthropic"
    assert record.agent.adapter_revision == "1.0.0"
    assert record.agent.model == "claude-sonnet-4-6"
    assert record.agent.configuration["max_turns"] == 20
    assert record.environment.compute_backend == "modal"
    assert record.environment.runtime_image.endswith(
        "tasks/mechanical/heat-load/audit-office-building/brisbane-8rm/environment/Dockerfile"
    )
    assert record.inputs.system_prompt is not None
    assert record.inputs.input_files is not None
    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.COMPLETED
    assert record.outputs.raw_output_path is not None
    assert record.outputs.conversation_path is not None
    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["usage_input_tokens"] == 65551
    assert record.outputs.agent_result["usage_output_tokens"] == 9283
    assert record.outputs.agent_result["usage_cache_tokens"] == 50835
    assert record.outputs.agent_result["usage_cache_write_tokens"] == 14707
    assert record.evaluation.reward == pytest.approx(1.0)
    assert record.evaluation.validity.verifier_completed is True
    assert record.evaluation.breakdown is not None
    assert record.evaluation.breakdown["detected"] == 3
    assert record.timing.total_seconds > 0
    assert record.timing.agent_seconds is not None
    assert record.timing.setup_seconds is not None
    assert record.timing.verification_seconds is not None
    assert record.cost is not None
    assert record.cost.tokens_in == 131093
    assert record.cost.tokens_out == 9283
    assert record.cost.estimated_cost_usd == pytest.approx(0.25379475)
    assert record.completeness is Completeness.PARTIAL


def test_import_harbor_trial_derives_morph_backend_from_import_path_environment(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "mechanical" / "heat-load" / "alpha"
    trial_dir = repo_root / "jobs" / "job-001" / "trial-morph"
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("answer\n", encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (trial_dir / "result.json").write_text(
        """
{
  "trial_name": "trial-morph",
  "task_checksum": "sha256-task",
  "config": {
    "task": {"path": "tasks/mechanical/heat-load/alpha"},
    "agent": {"name": "entrypoint", "model_name": "test-model", "kwargs": {"adapter": "tool_loop"}},
    "environment": {
      "type": null,
      "import_path": "aec_bench.providers.morph_harbor:MorphHarborEnvironment",
      "kwargs": {"compute_backend": "morph"}
    },
    "job_id": "experiment-001"
  },
  "agent_info": {"name": "entrypoint", "version": "1.0.0"},
  "agent_result": {},
  "started_at": "2026-06-05T00:00:00Z",
  "finished_at": "2026-06-05T00:00:01Z"
}
""".strip(),
        encoding="utf-8",
    )

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.environment.compute_backend == "morph"


def test_import_harbor_trial_includes_reviewer_summary_in_breakdown(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "mechanical" / "heat-load" / "alpha"
    trial_dir = repo_root / "jobs" / "job-001" / "trial-reviewed"
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (trial_dir / "reviewer").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("answer\n", encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (trial_dir / "reviewer" / "summary.json").write_text(
        json.dumps({"status": "complete", "event_candidates": ["verifier_language_gap"]}),
        encoding="utf-8",
    )
    (trial_dir / "result.json").write_text(
        """
{
  "trial_name": "trial-reviewed",
  "task_checksum": "sha256-task",
  "config": {
    "task": {"path": "tasks/mechanical/heat-load/alpha"},
    "agent": {"name": "entrypoint", "model_name": "test-model", "kwargs": {"adapter": "tool_loop"}},
    "environment": {"type": "modal", "kwargs": {}},
    "job_id": "experiment-001"
  },
  "agent_info": {"name": "entrypoint", "version": "1.0.0"},
  "agent_result": {},
  "started_at": "2026-06-05T00:00:00Z",
  "finished_at": "2026-06-05T00:00:01Z"
}
""".strip(),
        encoding="utf-8",
    )

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.evaluation.breakdown is not None
    assert record.evaluation.breakdown["llm_reviewer"]["status"] == "complete"


@_skip_no_job_data
def test_import_harbor_trial_rejects_missing_result_json(tmp_path: Path) -> None:
    with pytest.raises(HarborImportError, match="missing Harbor result artifact"):
        import_harbor_trial(trial_dir=tmp_path, repo_root=REPO_ROOT)


@_skip_no_job_data
def test_iter_harbor_trial_dirs_finds_only_trial_directories() -> None:
    trial_dirs = iter_harbor_trial_dirs(job_dir=HARBOR_JOB_DIR)

    assert len(trial_dirs) == 60
    assert trial_dirs[0].name == "adelaide-15rm__EUcepGa"
    assert trial_dirs[-1].name == "townsville-8rm__WBreAVv"


@_skip_no_job_data
def test_import_harbor_job_maps_real_job_directory() -> None:
    records = import_harbor_job(job_dir=HARBOR_JOB_DIR, repo_root=REPO_ROOT)

    assert len(records) == 60
    assert records[0].experiment_id == "6834bc30-3801-4a45-a114-afb2d3764b7d"
    assert records[0].task.task_id == "mechanical/heat-load/audit-mixed-use/adelaide-15rm"
    assert records[-1].task.task_id == "mechanical/heat-load/audit-office-building/townsville-8rm"
    assert all(record.environment.compute_backend == "modal" for record in records)
