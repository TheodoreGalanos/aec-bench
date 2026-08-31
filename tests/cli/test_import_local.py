# ABOUTME: Tests for the import-local CLI command.
# ABOUTME: Validates TrialRecord construction and artifact copying from local run directories.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.trial_record import EvidenceStatus, ExecutionStatus
from aec_bench.harness.local_import import (
    build_trial_record,
    copy_artifacts,
    find_tasks_root,
)
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record_at


def _create_task_dir(tmp_path: Path) -> Path:
    """Create a minimal task directory that load_task_definition can parse."""
    task_dir = tmp_path / "tasks" / "test-domain" / "test-task"
    task_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Calculate the thing and write to /workspace/output.md")
    (task_dir / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "test-domain/test-task"\nversion = 1\n\n'
        '[metadata]\ndifficulty = "easy"\nlifecycle = "active"\nvisibility = "public"\n\n'
        "[agent]\ntimeout_sec = 600\n"
    )
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text('print("ok")')
    return task_dir


def _create_run_dir(
    tmp_path: Path,
    *,
    status: str = "ok",
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 100_000,
    output_tokens: int = 5_000,
    cache_read_tokens: int = 80_000,
    cache_write_tokens: int = 10_000,
) -> Path:
    """Create a minimal local run directory with agent_result.json and artifacts."""
    run_dir = tmp_path / "_local_runs" / "20260327-120000"
    run_dir.mkdir(parents=True)
    (run_dir / "agent_result.json").write_text(
        json.dumps(
            {
                "status": status,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_write_tokens": cache_write_tokens,
                "turns_used": 30,
                "max_turns": 100,
                "output_source": "direct_write",
                "compaction_count": 2,
            }
        )
    )
    (run_dir / "output.md").write_text("# Test Output\n\nSome results here.")
    (run_dir / "trajectory.jsonl").write_text("")
    (run_dir / "conversation.jsonl").write_text(json.dumps({"role": "user", "content": "hello"}) + "\n")
    return run_dir


# ---------------------------------------------------------------------------
# find_tasks_root
# ---------------------------------------------------------------------------


class TestFindTasksRoot:
    """Validate tasks root discovery by walking upward."""

    def test_finds_tasks_ancestor(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop"
        task_dir.mkdir(parents=True)
        assert find_tasks_root(task_dir) == tmp_path / "tasks"

    def test_finds_nested_tasks_ancestor(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "project" / "tasks" / "civil" / "drainage"
        task_dir.mkdir(parents=True)
        assert find_tasks_root(task_dir) == tmp_path / "project" / "tasks"

    def test_fallback_to_parent(self, tmp_path: Path) -> None:
        """When no 'tasks' ancestor exists, fall back to the parent directory."""
        task_dir = tmp_path / "some-dir" / "my-task"
        task_dir.mkdir(parents=True)
        assert find_tasks_root(task_dir) == tmp_path / "some-dir"


# ---------------------------------------------------------------------------
# copy_artifacts
# ---------------------------------------------------------------------------


class TestCopyArtifacts:
    """Validate artifact file copying from run directory."""

    def test_copies_existing_files(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "output.md").write_text("hello")
        (run_dir / "trajectory.jsonl").write_text("{}")

        dest = tmp_path / "artifacts"
        copied = copy_artifacts(run_dir, dest)

        assert "output.md" in copied
        assert "trajectory.jsonl" in copied
        assert (dest / "output.md").read_text() == "hello"

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "output.md").write_text("hello")

        dest = tmp_path / "artifacts"
        copied = copy_artifacts(run_dir, dest)

        assert "output.md" in copied
        assert "trajectory.jsonl" not in copied

    def test_creates_destination_directory(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "agent_result.json").write_text("{}")

        dest = tmp_path / "nested" / "deep" / "artifacts"
        copy_artifacts(run_dir, dest)

        assert dest.is_dir()
        assert (dest / "agent_result.json").exists()


# ---------------------------------------------------------------------------
# build_trial_record
# ---------------------------------------------------------------------------


class TestBuildTrialRecord:
    """Validate TrialRecord construction from local run artifacts."""

    def test_basic_record_fields(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="test-exp",
            trial_id="test-trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.trial_id == "test-trial"
        assert record.experiment_id == "test-exp"
        assert record.dataset_id is None
        assert record.execution_status is ExecutionStatus.COMPLETED
        assert record.evidence_status is EvidenceStatus.NOT_REQUIRED

    def test_agent_reference(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path, model="claude-sonnet-4-6")
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.agent.adapter == "rlm"
        assert record.agent.model == "claude-sonnet-4-6"
        assert record.agent.configuration["source"] == "import-local"
        assert record.agent.configuration["compaction_count"] == 2

    def test_task_reference(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.task.task_id == "test-domain/test-task"
        assert record.task.task_revision == "local"

    def test_cost_record(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(
            tmp_path,
            model="claude-sonnet-4-6",
            input_tokens=100_000,
            output_tokens=5_000,
            cache_read_tokens=80_000,
            cache_write_tokens=10_000,
        )
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.cost is not None
        assert record.cost.tokens_in == 100_000
        assert record.cost.tokens_out == 5_000
        assert record.cost.estimated_cost_usd is not None
        assert record.cost.estimated_cost_usd > 0

    def test_evaluation_not_verified(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.evaluation.reward == 0.0
        assert record.evaluation.validity.verifier_completed is False
        assert "not verified" in record.evaluation.validity.errors[0]

    def test_completed_agent_status(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path, status="ok")
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.outputs.agent_output is not None
        assert record.outputs.agent_output.status == AgentOutputStatus.COMPLETED
        assert record.outputs.agent_output.error_message is None

    def test_failed_agent_status(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path, status="error")
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.outputs.agent_output is not None
        assert record.outputs.agent_output.status == AgentOutputStatus.FAILED
        assert record.outputs.agent_output.error_message == "error"

    def test_output_paths_relative_to_repo_root(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        # Paths should be POSIX and relative to repo root
        assert record.outputs.trajectory_path is not None
        assert Path(record.outputs.trajectory_path).is_relative_to(artifact_dir)
        assert record.outputs.raw_output_path is not None
        assert Path(record.outputs.raw_output_path).is_relative_to(artifact_dir)

    def test_agent_result_metadata(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        ar = record.outputs.agent_result
        assert ar is not None
        assert "usage_input_tokens" not in ar
        assert ar["turns_used"] == 30
        assert ar["max_turns"] == 100
        assert ar["output_source"] == "direct_write"
        assert ar["compaction_count"] == 2
        assert record.cost is not None
        assert record.cost.tokens_in == 100_000
        assert record.cost.tokens_out == 5_000

    def test_unknown_model_cost_is_none(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path, model="some-obscure-model")
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.cost is not None
        assert record.cost.estimated_cost_usd is None

    def test_environment_snapshot(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        assert record.environment.runtime_image == "local"
        assert record.environment.compute_backend == "local"

    def test_adapter_read_from_agent_result(self, tmp_path: Path) -> None:
        """When agent_result.json has an 'adapter' key, use it."""
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        ar_path = run_dir / "agent_result.json"
        data = json.loads(ar_path.read_text())
        data["adapter"] = "lambda-rlm"
        ar_path.write_text(json.dumps(data))

        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )
        assert record.agent.adapter == "lambda-rlm"

    def test_adapter_defaults_to_rlm_when_missing(self, tmp_path: Path) -> None:
        """When agent_result.json has no 'adapter' key, default to 'rlm'."""
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)

        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )
        assert record.agent.adapter == "rlm"


# ---------------------------------------------------------------------------
# Serialization roundtrip
# ---------------------------------------------------------------------------


class TestSerializationRoundtrip:
    """Verify the record can be serialised and read back as valid JSON."""

    def test_record_serializes_to_valid_json(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        json_str = record.model_dump_json(indent=2)
        roundtripped = json.loads(json_str)
        assert roundtripped["trial_id"] == "trial"
        assert "experiment_id" not in roundtripped

    def test_record_validates_after_roundtrip(self, tmp_path: Path) -> None:
        task_dir = _create_task_dir(tmp_path)
        run_dir = _create_run_dir(tmp_path)
        artifact_dir = tmp_path / "artifacts"
        copy_artifacts(run_dir, artifact_dir)

        record = build_trial_record(
            run_path=run_dir,
            task_dir=task_dir,
            experiment_id="exp",
            trial_id="trial",
            artifact_dir=artifact_dir,
            repo_root=tmp_path,
        )

        record_path = write_trial_record_at(path=tmp_path / "trial.json", record=record)
        restored = read_trial_record(record_path)
        assert restored.trial_id == record.trial_id
        assert restored.agent.model == record.agent.model
