# ABOUTME: Tests binding meta-harness task-run resolvers to AEC-Bench Harbor APIs.
# ABOUTME: Exercises real workflow/import contracts while using a local executor fixture.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.meta_harness.aecbench import (
    AecBenchWorkflowConfig,
    build_aecbench_harbor_task_run_resolver,
    import_aecbench_harbor_trial_to_task_run,
)


def test_trial_importer_converts_harbor_trial_to_task_run_evidence(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    trial_dir = _write_aecbench_repo_with_trial(repo_root)

    task_run = import_aecbench_harbor_trial_to_task_run(
        trial_dir=trial_dir,
        repo_root=repo_root,
        runtime_result={"process_id": "process.demo"},
    )

    assert task_run["run_id"] == "process.demo.trial-alpha"
    assert task_run["evidence"]["score"]["reward"] == 1.0
    assert task_run["evidence"]["aecbench"]["trial_id"] == "trial-alpha"
    assert task_run["evidence"]["trial_records"][0]["task"]["task_id"] == "civil/calculation/alpha"


def test_workflow_resolver_runs_aecbench_workflow_and_imports_trials(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_aecbench_task(repo_root)
    executor = _WritingHarborExecutor(repo_root)
    resolver = build_aecbench_harbor_task_run_resolver(
        manifest={
            "experiment_id": "experiment-alpha",
            "name": "Meta-harness workflow binding",
            "tasks": {"domains": ["civil"]},
            "agents": [{"name": "entrypoint", "adapter": "entrypoint", "model": "test-model"}],
            "compute": {"backend": "docker"},
        },
        workflow_config=AecBenchWorkflowConfig(project_root=repo_root),
        executor=executor,
    )

    task_run = resolver(
        {
            "process_id": "process.workflow",
            "autonomy_request": {"batch_size": 1, "run_directives": []},
        }
    )

    assert task_run["run_id"] == "process.workflow.experiment-alpha"
    assert task_run["evidence"]["score"]["reward"] == 1.0
    assert task_run["evidence"]["aecbench"]["workflow"] == "SynchronousHarborWorkflow"
    assert task_run["evidence"]["aecbench"]["imported_trials"] == 1
    assert len(task_run["evidence"]["trial_records"]) == 1
    assert executor.called


class _WritingHarborExecutor:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.called = False

    def execute(self, *, command: list[str], cwd: Path) -> int:
        self.called = True
        self.command = command
        self.cwd = cwd
        _write_harbor_trial(self.repo_root / "jobs" / "job-alpha" / "trial-alpha")
        return 0


def _write_aecbench_repo_with_trial(repo_root: Path) -> Path:
    _write_aecbench_task(repo_root)
    trial_dir = repo_root / "jobs" / "job-alpha" / "trial-alpha"
    _write_harbor_trial(trial_dir)
    return trial_dir


def _write_aecbench_task(repo_root: Path) -> Path:
    task_dir = repo_root / "tasks" / "civil" / "calculation" / "alpha"
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        """
[metadata]
visibility = "public"
difficulty = "easy"
lifecycle = "active"

[agent]
timeout_sec = 60
""".strip(),
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return task_dir


def _write_harbor_trial(trial_dir: Path) -> None:
    (trial_dir / "artifacts" / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("42\n", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
        json.dumps({"status": "completed", "input_tokens": 10, "output_tokens": 2}),
        encoding="utf-8",
    )
    (trial_dir / "verifier" / "reward.json").write_text(json.dumps({"reward": 1.0}), encoding="utf-8")
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-alpha",
                "task_checksum": "sha256-task",
                "config": {
                    "task": {"path": "tasks/civil/calculation/alpha"},
                    "agent": {
                        "name": "entrypoint",
                        "model_name": "test-model",
                        "kwargs": {"adapter": "entrypoint"},
                    },
                    "environment": {"type": "docker", "kwargs": {}},
                    "job_id": "experiment-alpha",
                },
                "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                "agent_result": {},
                "started_at": "2026-06-05T00:00:00Z",
                "finished_at": "2026-06-05T00:00:01Z",
            }
        ),
        encoding="utf-8",
    )
