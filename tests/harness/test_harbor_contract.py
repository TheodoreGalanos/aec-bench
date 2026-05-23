# ABOUTME: Tests for the minimal Harbor artifact contract required by the Python importer.
# ABOUTME: Validates the real Harbor result shape and failure on missing required fields.

import json
from pathlib import Path

import pytest

from aec_bench.harness.harbor_contract import HarborArtifactContractError, read_harbor_trial_result

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_TRIAL_RESULT = REPO_ROOT / "jobs" / "2026-03-04__17-57-43" / "brisbane-8rm__BHVuXg2" / "result.json"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_TRIAL_RESULT.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_read_harbor_trial_result_accepts_real_trial_result() -> None:
    result = read_harbor_trial_result(HARBOR_TRIAL_RESULT)

    assert result.trial_name == "brisbane-8rm__BHVuXg2"
    assert result.config.task.path == "tasks/mechanical/heat-load/audit-office-building/brisbane-8rm"
    assert result.config.environment.type == "modal"
    assert result.agent_info.name == "tool-loop-anthropic"


@_skip_no_job_data
def test_read_harbor_trial_result_rejects_missing_task_path(tmp_path: Path) -> None:
    payload = json.loads(HARBOR_TRIAL_RESULT.read_text(encoding="utf-8"))
    del payload["config"]["task"]["path"]
    broken_path = tmp_path / "result.json"
    broken_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HarborArtifactContractError, match="config.task.path"):
        read_harbor_trial_result(broken_path)
