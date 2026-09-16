# ABOUTME: Runs the pinned Harbor job SDK behind the existing subprocess boundary.
# ABOUTME: Sends bounded trial metadata on stdout while Harbor logs remain on stderr.

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from collections.abc import Callable
from pathlib import Path

import yaml
from harbor.job import Job  # type: ignore[import-untyped]
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]
from harbor.models.job.result import JobResult  # type: ignore[import-untyped]
from harbor.trial.hooks import TrialEvent, TrialHookEvent  # type: ignore[import-untyped]

from aec_bench.harness.progress_tracker import HarborTrialProgress, notify_observer


async def run_job(
    config: JobConfig,
    *,
    progress_callback: Callable[[HarborTrialProgress], None] | None = None,
) -> JobResult:
    """Let Harbor own scheduling and retries; callbacks observe individual attempts."""
    job = await Job.create(config)

    async def observe(event: TrialHookEvent) -> None:
        progress = HarborTrialProgress(
            event=event.event.value,
            timestamp=event.timestamp,
            harbor_trial_id=event.trial_id,
            trial_name=event.trial_name,
            task_name=event.task_name,
            agent_name=event.config.agent.name or event.result.agent_info.name,
            model_name=event.config.agent.model_name,
            trial_dir=(event.config.trials_dir / event.trial_name).resolve(),
            exception_type=event.result.exception_info.exception_type if event.result.exception_info else None,
        )
        notify_observer(progress_callback, progress, label="Harbor progress")

    for event in TrialEvent:
        job.add_hook(event, observe)
    return await job.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Harbor job with structured trial progress.")
    parser.add_argument("-c", "--config", type=Path, required=True)
    args = parser.parse_args()
    event_stream = sys.stdout

    def emit(event: HarborTrialProgress) -> None:
        print(event.model_dump_json(), file=event_stream, flush=True)

    # Keep native console output and untrusted provider logs out of the event stream.
    with contextlib.redirect_stdout(sys.stderr):
        config = JobConfig.model_validate(yaml.safe_load(args.config.read_text(encoding="utf-8")))
        asyncio.run(run_job(config, progress_callback=emit))


if __name__ == "__main__":
    main()
