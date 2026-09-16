# ABOUTME: Proves recorded artifact regrading through Harbor's native verifier lifecycle.
# ABOUTME: Checks unchanged source evidence, retained inputs, and failures before environment startup.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from aec_bench.harness.harbor_contract import HarborArtifactContractError, read_harbor_trial_result
from aec_bench.harness.harbor_regrade import plan_regrade, run_regrade
from tests.support.harbor_regrade import local_verifier_environment, recorded_trial


def _bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_regrade_runs_only_verifier_and_retains_exact_inputs(tmp_path: Path) -> None:
    source, task = recorded_trial(tmp_path)
    before = _bytes(source)
    revised = _bytes(task)
    output = tmp_path / "assessment"
    config = plan_regrade(
        source_trial=source, task_dir=task, output_dir=output, environment=local_verifier_environment()
    )
    assert not output.exists()
    result = asyncio.run(run_regrade(config))

    assert result.exception_info is None
    assert result.verifier_result.rewards == {"reward": 1.0}
    assert result.agent_execution is None
    assert result.agent_setup is None
    assert result.agent_info.name == "recorded-agent"
    assert result.agent_result.cost_usd == 0.5  # Retained source fact, never a new execution charge.
    assert _bytes(source) == before
    assert _bytes(output / "source") == before
    assert _bytes(task) == revised == _bytes(output / "task" / "example")
    assert json.loads((output / "inputs.json").read_text())["source_trial_id"] == str(config.source_trial.trial_id)
    operations = [
        json.loads(line) for line in (output / "verification" / "environment-operations.jsonl").read_text().splitlines()
    ]
    assert sum(event["event"] == "start" for event in operations) == 1
    assert sum(event["event"] == "stop" for event in operations) == 1
    assert (output / "verification" / "artifacts" / "agent" / "output.md").read_text() == "42\n"
    assert json.loads((output / "source" / "result.json").read_text())["verifier_result"]["rewards"] == {"reward": 0.0}
    with pytest.raises(HarborArtifactContractError, match="not a new execution"):
        read_harbor_trial_result(output / "verification" / "result.json")
    with pytest.raises(FileExistsError):
        asyncio.run(run_regrade(config))


@pytest.mark.parametrize("defect", ["missing_file", "failed_collection", "changed_destination", "new_input"])
def test_missing_verifier_input_fails_before_environment_start(tmp_path: Path, defect: str) -> None:
    source, task = recorded_trial(tmp_path)
    manifest_path = source / "artifacts" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if defect == "missing_file":
        (source / "artifacts" / "agent" / "output.md").unlink()
    elif defect == "failed_collection":
        manifest[1]["status"] = "failed"
    elif defect == "changed_destination":
        manifest[1]["destination"] = "different/output.md"
    else:
        task_config = task / "task.toml"
        task_config.write_text(task_config.read_text().replace("/workspace/output.md", "/workspace/missing.md"))
    manifest_path.write_text(json.dumps(manifest))
    output = tmp_path / "assessment"
    config = plan_regrade(
        source_trial=source, task_dir=task, output_dir=output, environment=local_verifier_environment()
    )
    result = asyncio.run(run_regrade(config))
    assert result.exception_info.exception_type == "RegradeError"
    assert result.verifier_result is None
    assert not (output / "verification" / "environment-operations.jsonl").exists()
    assert (output / "verification" / "result.json").is_file()


@pytest.mark.parametrize("defect", ["shared", "unfinished", "wrong_task", "private", "manifest", "symlink", "steps"])
def test_plan_rejects_unusable_sources_without_writes(tmp_path: Path, defect: str) -> None:
    source, task = recorded_trial(tmp_path)
    if defect in {"shared", "private"}:
        task_config = task / "task.toml"
        old, new = ("separate", "shared") if defect == "shared" else ("public", "holdout")
        task_config.write_text(task_config.read_text().replace(old, new))
    elif defect in {"unfinished", "wrong_task"}:
        result_path = source / "result.json"
        result = json.loads(result_path.read_text())
        result["finished_at" if defect == "unfinished" else "task_name"] = None if defect == "unfinished" else "other"
        result_path.write_text(json.dumps(result))
    elif defect == "manifest":
        (source / "artifacts" / "manifest.json").unlink()
    elif defect == "steps":
        (source / "steps").mkdir()
    else:
        (source / "artifacts" / "external").symlink_to(task / "instruction.md")
    output = tmp_path / "assessment"
    from harbor.trial.regrade import RegradeError  # type: ignore[import-untyped]

    with pytest.raises((ValueError, RegradeError)):
        plan_regrade(source_trial=source, task_dir=task, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("location", ["source", "task", "ancestor", "existing"])
def test_output_cannot_overlap_or_replace_inputs(tmp_path: Path, location: str) -> None:
    source, task = recorded_trial(tmp_path)
    output = {
        "source": source / "assessment",
        "task": task / "assessment",
        "ancestor": tmp_path,
        "existing": tmp_path / "existing",
    }[location]
    if location == "existing":
        output.mkdir()
    with pytest.raises((ValueError, FileExistsError)):
        plan_regrade(source_trial=source, task_dir=task, output_dir=output)
