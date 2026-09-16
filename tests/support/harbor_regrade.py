# ABOUTME: Creates a synthetic recorded Harbor artifact trial and a revised public verifier.
# ABOUTME: Uses a deliberately unavailable original agent to detect accidental agent execution.

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from harbor.models.trial.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.result import TrialResult  # type: ignore[import-untyped]


def local_verifier_environment() -> EnvironmentConfig:
    return EnvironmentConfig(
        import_path="tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
        delete=False,
    )


def recorded_trial(root: Path) -> tuple[Path, Path]:
    source = root / "recorded"
    task = root / "revised" / "example"
    (source / "artifacts" / "agent").mkdir(parents=True)
    (source / "agent").mkdir()
    (source / "artifacts" / "agent" / "output.md").write_text("42\n")
    (source / "agent" / "trajectory.jsonl").write_text('{"message":"recorded answer"}\n')
    (source / "artifacts" / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "source": "/logs/artifacts",
                    "destination": "artifacts/logs/artifacts",
                    "type": "directory",
                    "status": "empty",
                },
                {
                    "source": "/workspace/output.md",
                    "destination": "artifacts/agent/output.md",
                    "type": "file",
                    "status": "ok",
                },
                {
                    "source": "/workspace/optional.json",
                    "destination": "artifacts/agent/optional.json",
                    "type": "file",
                    "status": "failed",
                },
            ]
        )
    )
    (task / "environment").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "instruction.md").write_text("Write the answer to /workspace/output.md.\n")
    (task / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n")
    (task / "tests" / "Dockerfile").write_text("FROM python:3.13-slim\nCOPY . /tests\n")
    (task / "task.toml").write_text("""
artifacts = [{source = "/workspace/output.md", destination = "agent/output.md"}]
[metadata]
visibility = "public"
[verifier]
environment_mode = "separate"
""")
    # Harbor invokes test.sh from /tests. Relative paths also let the test-only
    # local filesystem environment run this script without a host /logs mount.
    (task / "tests" / "test.sh").write_text("""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
answer=$(cat ../workspace/output.md)
test "$answer" = 42
mkdir -p ../logs/verifier
echo '{"reward": 1.0}' > ../logs/verifier/reward.json
""")
    result = TrialResult.model_validate(
        {
            "id": str(uuid4()),
            "task_name": "example",
            "trial_name": "recorded",
            "trial_uri": source.as_uri(),
            "task_id": {"path": str(task)},
            "task_checksum": "original-task-checksum",
            "config": {
                "task": {"path": str(task)},
                "agent": {"import_path": "unavailable_original_agent:Agent", "model_name": "recorded-model"},
                "artifacts": [{"source": "/workspace/optional.json", "destination": "agent/optional.json"}],
                "job_id": str(uuid4()),
            },
            "agent_info": {"name": "recorded-agent", "version": "1"},
            "agent_result": {"n_input_tokens": 100, "n_output_tokens": 20, "cost_usd": 0.5},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "started_at": "2026-09-15T00:00:00Z",
            "finished_at": "2026-09-15T00:01:00Z",
        }
    )
    (source / "result.json").write_text(result.model_dump_json(indent=2))
    return source, task
