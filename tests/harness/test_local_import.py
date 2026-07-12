# ABOUTME: Tests for local run import logic in the harness package.
# ABOUTME: Covers task root discovery, artifact copying, and trial record construction.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import Completeness, TimingRecord, TrialRecord
from aec_bench.harness.local_import import (
    ARTIFACT_FILENAMES,
    build_trial_record,
    build_trial_record_from_workspace,
    copy_artifacts,
    find_tasks_root,
)


def test_find_tasks_root_walks_up_to_tasks_ancestor(tmp_path: Path) -> None:
    """find_tasks_root returns the nearest 'tasks/' ancestor directory."""
    tasks_dir = tmp_path / "repo" / "tasks"
    task_dir = tasks_dir / "electrical" / "voltage-drop" / "instance-01"
    task_dir.mkdir(parents=True)

    result = find_tasks_root(task_dir)
    assert result == tasks_dir


def test_find_tasks_root_falls_back_to_parent(tmp_path: Path) -> None:
    """When no 'tasks/' ancestor exists, fall back to the parent directory."""
    task_dir = tmp_path / "standalone" / "my-task"
    task_dir.mkdir(parents=True)

    result = find_tasks_root(task_dir)
    assert result == task_dir.parent


def test_copy_artifacts_copies_known_files(tmp_path: Path) -> None:
    """copy_artifacts copies recognised files from run_path to artifact_dir."""
    run_path = tmp_path / "run"
    run_path.mkdir()
    artifact_dir = tmp_path / "artifacts"

    # Create two recognised files
    (run_path / "agent_result.json").write_text("{}")
    (run_path / "trajectory.jsonl").write_text("")

    copied = copy_artifacts(run_path, artifact_dir)

    assert sorted(copied) == ["agent_result.json", "trajectory.jsonl"]
    assert (artifact_dir / "agent_result.json").exists()
    assert (artifact_dir / "trajectory.jsonl").exists()


def test_copy_artifacts_skips_missing_files(tmp_path: Path) -> None:
    """copy_artifacts silently skips files that don't exist in run_path."""
    run_path = tmp_path / "run"
    run_path.mkdir()
    artifact_dir = tmp_path / "artifacts"

    # Create only one file — the rest should be silently skipped
    (run_path / "output.md").write_text("# Output")

    copied = copy_artifacts(run_path, artifact_dir)

    assert copied == ["output.md"]
    # None of the other artifact files should appear in the target
    for fname in ARTIFACT_FILENAMES:
        if fname != "output.md":
            assert not (artifact_dir / fname).exists()


def _scaffold_task_dir(tasks_dir: Path, task_slug: str) -> Path:
    """Create a minimal valid task directory under a tasks/ root."""
    task_dir = tasks_dir / task_slug
    task_dir.mkdir(parents=True)

    task_toml = """\
[metadata]
task_id = "electrical/voltage-drop/test-instance"
domain = "electrical"
category = "reasoning"
difficulty = "easy"
lifecycle = "proposed"
visibility = "public"
timeout_seconds = 300

[agent]
timeout_sec = 300
"""
    (task_dir / "task.toml").write_text(task_toml)
    (task_dir / "instruction.md").write_text("Calculate the voltage drop.\n")

    # Verifier script required by loader
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text("# stub verifier\n")

    return task_dir


def test_build_trial_record_constructs_valid_record(tmp_path: Path) -> None:
    """build_trial_record returns a TrialRecord with correct fields from a mock run."""
    # Set up a tasks/ root with a minimal task
    tasks_dir = tmp_path / "repo" / "tasks"
    task_dir = _scaffold_task_dir(tasks_dir, "electrical/voltage-drop/test-instance")

    # Set up a run directory with agent_result.json
    run_path = tmp_path / "run"
    run_path.mkdir()
    agent_result = {
        "status": "ok",
        "model": "test-model",
        "input_tokens": 100,
        "output_tokens": 50,
    }
    (run_path / "agent_result.json").write_text(json.dumps(agent_result))

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    record = build_trial_record(
        run_path=run_path,
        task_dir=task_dir,
        experiment_id="exp-001",
        trial_id="trial-001",
        artifact_dir=artifact_dir,
        repo_root=tmp_path / "repo",
    )

    assert isinstance(record, TrialRecord)
    assert record.trial_id == "trial-001"
    assert record.experiment_id == "exp-001"
    assert record.task.visibility is Visibility.PUBLIC
    assert record.agent.model == "test-model"
    assert record.outputs.agent_output.status == AgentOutputStatus.COMPLETED
    assert record.cost is not None
    assert record.cost.tokens_in == 100
    assert record.cost.tokens_out == 50
    assert record.completeness == Completeness.PARTIAL


# ---------------------------------------------------------------------------
# build_trial_record_from_workspace
# ---------------------------------------------------------------------------


def test_build_trial_record_from_workspace_with_verifier(tmp_path: Path) -> None:
    """With verifier results, reward is read and verifier_completed is True."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # agent_result.json
    agent_result = {
        "status": "ok",
        "model": "claude-sonnet-4-6",
        "adapter": "rlm",
        "input_tokens": 200,
        "output_tokens": 80,
        "cache_read_tokens": 10,
        "cache_write_tokens": 5,
        "output_source": "scratchpad",
        "compaction_count": 2,
    }
    (workspace / "agent_result.json").write_text(json.dumps(agent_result))

    # output.md
    (workspace / "output.md").write_text("# Result\nSome output here.\n")

    # verifier reward and details
    verifier_dir = workspace / "logs" / "verifier"
    verifier_dir.mkdir(parents=True)
    (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.85}))
    (verifier_dir / "details.json").write_text(json.dumps({"voltage_drop": 1.0, "cable_size": 0.7}))

    # optional artifacts
    (workspace / "trajectory.jsonl").write_text("")
    (workspace / "conversation.jsonl").write_text("")

    timing = TimingRecord(total_seconds=42.5, agent_seconds=38.0)

    record = build_trial_record_from_workspace(
        workspace_dir=workspace,
        trial_id="t-001",
        experiment_id="e-001",
        task_id="electrical/voltage-drop/inst-01",
        model="claude-sonnet-4-6",
        adapter="rlm",
        instruction="Calculate the voltage drop.",
        timing=timing,
    )

    assert isinstance(record, TrialRecord)
    assert record.trial_id == "t-001"
    assert record.experiment_id == "e-001"
    assert record.task.task_id == "electrical/voltage-drop/inst-01"
    assert record.agent.model == "claude-sonnet-4-6"
    assert record.agent.adapter == "rlm"
    assert record.agent.configuration["source"] == "run-local"

    # Evaluation
    assert record.evaluation.reward == 0.85
    assert record.evaluation.validity.verifier_completed is True
    assert record.evaluation.breakdown == {"voltage_drop": 1.0, "cable_size": 0.7}

    # Timing
    assert record.timing.total_seconds == 42.5
    assert record.timing.agent_seconds == 38.0

    # Cost
    assert record.cost is not None
    assert record.cost.tokens_in == 200
    assert record.cost.tokens_out == 80

    # Completeness — PARTIAL because we lack adapter_revision etc.
    assert record.completeness == Completeness.PARTIAL

    # Artifacts
    assert record.outputs.conversation_path is not None
    assert record.outputs.trajectory_path is not None


def test_build_trial_record_from_workspace_accepts_completed_status(tmp_path: Path) -> None:
    """Library-adapter runs write status='completed' (enum value); import must accept it.

    Regression: run_local.py writes AgentOutputStatus.COMPLETED.value == 'completed',
    while legacy rlm_script.py writes 'ok'. Both must classify as COMPLETED so that
    output_parseable=True and non-zero rewards pass the EvaluationResult validator.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    agent_result = {
        "status": "completed",
        "model": "au.anthropic.claude-sonnet-4-6",
        "adapter": "lambda-rlm",
        "input_tokens": 126113,
        "output_tokens": 33200,
        "output_source": "direct_write",
    }
    (workspace / "agent_result.json").write_text(json.dumps(agent_result))
    (workspace / "output.md").write_text("# Report\n")

    verifier_dir = workspace / "logs" / "verifier"
    verifier_dir.mkdir(parents=True)
    (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.61}))

    timing = TimingRecord(total_seconds=520.0, agent_seconds=518.0)

    record = build_trial_record_from_workspace(
        workspace_dir=workspace,
        trial_id="t-completed",
        experiment_id="e-completed",
        task_id="reports/lambda-rlm-demo",
        model="au.anthropic.claude-sonnet-4-6",
        adapter="lambda-rlm",
        instruction="Write the proposal.",
        timing=timing,
    )

    assert record.outputs.agent_output.status == AgentOutputStatus.COMPLETED
    assert record.evaluation.validity.output_parseable is True
    assert record.evaluation.reward == 0.61


def test_build_trial_record_from_workspace_without_verifier(tmp_path: Path) -> None:
    """Without verifier outputs, reward is 0.0 and verifier_completed is False."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # agent_result.json only — no verifier outputs
    agent_result = {
        "status": "ok",
        "model": "gpt-4.1-mini",
        "input_tokens": 50,
        "output_tokens": 30,
    }
    (workspace / "agent_result.json").write_text(json.dumps(agent_result))

    record = build_trial_record_from_workspace(
        workspace_dir=workspace,
        trial_id="t-002",
        experiment_id="e-002",
        task_id="civil/drainage/inst-01",
        model="gpt-4.1-mini",
        adapter="lambda-rlm",
        instruction="Design the drainage system.",
    )

    assert isinstance(record, TrialRecord)
    assert record.trial_id == "t-002"
    assert record.agent.adapter == "lambda-rlm"

    # No verifier
    assert record.evaluation.reward == 0.0
    assert record.evaluation.validity.verifier_completed is False
    assert record.evaluation.breakdown is None

    # Default timing
    assert record.timing.total_seconds == 0.0

    # Completeness
    assert record.completeness == Completeness.PARTIAL

    # No optional artifacts
    assert record.outputs.conversation_path is None
    assert record.outputs.trajectory_path is None
