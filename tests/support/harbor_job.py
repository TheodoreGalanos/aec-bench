# ABOUTME: Supplies a keyless agent and local tasks for native Harbor scheduling tests.
# ABOUTME: Exercises real job concurrency, retry events, and verifier execution at test boundaries.

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from harbor.agents.nop import NopAgent  # type: ignore[import-untyped]
from harbor.environments.base import BaseEnvironment  # type: ignore[import-untyped]
from harbor.models.agent.context import AgentContext  # type: ignore[import-untyped]
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]


class ProbeAgent(NopAgent):  # type: ignore[misc]
    attempts: dict[Path, int] = {}

    def __init__(self, *, logs_dir: Path, fail_once: bool = False, **kwargs: Any) -> None:
        super().__init__(logs_dir=logs_dir, **kwargs)
        self._probe_logs = logs_dir
        self._fail_once = fail_once

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        del instruction, environment
        attempt = self.attempts.get(self._probe_logs, 0)
        self.attempts[self._probe_logs] = attempt + 1
        await asyncio.sleep(0.1)
        if self._fail_once and attempt == 0:
            raise RuntimeError("retry probe")
        context.metadata = {"probe": "completed"}


def job_config(root: Path, *, n_attempts: int = 2, fail_once: bool = False) -> JobConfig:
    task = root / "task"
    (task / "environment").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "task.toml").write_text('[metadata]\nvisibility = "public"\n')
    (task / "instruction.md").write_text("Complete the keyless probe.\n")
    (task / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n")
    (task / "tests" / "test.sh").write_text("""#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
mkdir -p ../logs/verifier
echo '{"reward": 1}' > ../logs/verifier/reward.json
""")
    return JobConfig.model_validate(
        {
            "job_name": "probe",
            "jobs_dir": str(root / "jobs"),
            "n_attempts": n_attempts,
            "n_concurrent_trials": 4,
            "tasks": [{"path": str(task)}],
            "agents": [
                {
                    "name": "probe-agent",
                    "import_path": "tests.support.harbor_job:ProbeAgent",
                    "model_name": "test-model",
                    "n_concurrent": 1,
                    "kwargs": {"fail_once": fail_once},
                }
            ],
            "environment": {
                "import_path": "tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
                "delete": False,
            },
            "retry": {"max_retries": 1 if fail_once else 0, "min_wait_sec": 0, "max_wait_sec": 0},
        }
    )
