# ABOUTME: Verifies native Harbor concurrency and attempt hooks without provider credentials.
# ABOUTME: Exercises the actual subprocess protocol and isolates observer failures from results.

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from aec_bench.harness.harbor_dispatch import SubprocessHarborExecutor
from aec_bench.harness.harbor_job import run_job
from aec_bench.harness.progress_tracker import HarborTrialProgress
from tests.support.harbor_job import job_config


@pytest.mark.parametrize("shared", [False, True])
def test_native_agent_concurrency_limits_execution_phases(tmp_path: Path, shared: bool) -> None:
    config = job_config(tmp_path)
    agent = config.agents[0]
    agent.concurrency_group = "shared" if shared else None
    config.agents.append(agent.model_copy(update={"name": "another-condition"}))
    active: dict[str, int] = {}
    maxima: dict[str, int] = {}
    events: list[HarborTrialProgress] = []

    def observe(event: HarborTrialProgress) -> None:
        events.append(event)
        key = "shared" if shared else event.agent_name
        if event.event == "agent-start":
            active[key] = active.get(key, 0) + 1
            maxima[key] = max(maxima.get(key, 0), active[key])
        elif event.event == "agent-end":
            active[key] -= 1

    result = asyncio.run(run_job(config, progress_callback=observe))
    assert result.stats.n_errored_trials == 0
    assert result.stats.n_completed_trials == 4
    assert maxima == ({"shared": 1} if shared else {"probe-agent": 1, "another-condition": 1})
    assert all(value == 0 for value in active.values())
    assert len([event for event in events if event.event == "end"]) == 4
    assert "verification-start" in {event.event for event in events}


def test_retry_attempt_events_are_distinct_from_the_final_result(tmp_path: Path) -> None:
    config = job_config(tmp_path, n_attempts=1, fail_once=True)
    events: list[HarborTrialProgress] = []
    result = asyncio.run(run_job(config, progress_callback=events.append))
    endings = [event for event in events if event.event == "end"]
    assert len(endings) == 2
    assert endings[0].exception_type == "RuntimeError"
    assert endings[1].exception_type is None
    assert endings[0].trial_name == endings[1].trial_name
    assert endings[0].harbor_trial_id != endings[1].harbor_trial_id
    assert result.stats.n_completed_trials == 1
    assert result.stats.n_errored_trials == 0
    final = json.loads((endings[-1].trial_dir / "result.json").read_text())
    assert final["exception_info"] is None


def test_sdk_observer_failure_does_not_change_trial_results(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    config = job_config(tmp_path, n_attempts=1)

    def broken_observer(event: HarborTrialProgress) -> None:
        raise RuntimeError("observer-only failure")

    result = asyncio.run(run_job(config, progress_callback=broken_observer))
    assert result.stats.n_errored_trials == 0
    assert result.stats.n_completed_trials == 1
    assert "Harbor progress callback failed" in caplog.text


def test_subprocess_streams_events_even_when_consumer_fails(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    config = job_config(tmp_path, n_attempts=1)
    path = tmp_path / "job.json"
    path.write_text(config.model_dump_json())
    events: list[HarborTrialProgress] = []
    result_exists_at_start: list[bool] = []

    def observe(event: HarborTrialProgress) -> None:
        events.append(event)
        if event.event == "start":
            result_exists_at_start.append((event.trial_dir / "result.json").exists())
            raise ValueError("consumer failure")

    code = SubprocessHarborExecutor(progress_callback=observe).execute(
        command=[sys.executable, "-m", "aec_bench.harness.harbor_job", "-c", str(path)],
        cwd=Path(__file__).resolve().parents[2],
    )
    assert code == 0
    assert result_exists_at_start == [False]
    assert events[0].event == "start"
    assert events[-1].event == "end"
    assert events[-1].exception_type is None
    assert "Harbor progress callback failed" in caplog.text
    assert "Ignored invalid Harbor progress event" not in caplog.text
    assert "kwargs" not in events[0].model_dump()


def test_subprocess_reports_bad_frames_and_preserves_failure_exit_code(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    script = "print('not an event', flush=True); raise SystemExit(7)"
    code = SubprocessHarborExecutor().execute(command=[sys.executable, "-c", script], cwd=tmp_path)
    assert code == 7
    assert "Ignored invalid Harbor progress event" in caplog.text
