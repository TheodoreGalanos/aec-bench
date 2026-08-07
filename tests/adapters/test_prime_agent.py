# ABOUTME: Tests the thin Prime Agent adapter mapping into existing AEC-Bench adapter contracts.
# ABOUTME: Ensures process, protocol, timeout, and output evidence remain explicit without invented usage.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest
from aec_bench.adapters.prime_agent import PrimeAgentAdapter
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.prime_agent.batch import PrimeRun, prime_paths
from aec_bench.prime_agent.events import PrimeEvents, parse_prime_events


def _events(*, text: str = "Fallback", include_usage: bool = True) -> PrimeEvents:
    usage = ',"usage":{"input":8,"output":3,"cacheRead":2,"cacheWrite":1}' if include_usage else ""
    payload = (
        '{"type":"session","version":3,"id":"adapter-session"}\n'
        '{"type":"turn_start"}\n'
        f'{{"type":"message_end","message":{{"role":"assistant","content":[{{"type":"text","text":"{text}"}}],'
        f'"provider":"anthropic","model":"anthropic/requested","responseModel":"anthropic/resolved",'
        f'"responseId":"response-1","stopReason":"stop","timestamp":1786064524000{usage}}}}}\n'
        '{"type":"turn_end","message":{},"toolResults":[]}\n'
        '{"type":"agent_end","messages":[]}\n'
    )
    return parse_prime_events(payload.encode())


def _prime_run(
    workspace: Path,
    *,
    completion: str = "completed",
    events: PrimeEvents | None = None,
    error: str | None = None,
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> PrimeRun:
    now = datetime.now(UTC)
    return PrimeRun(
        command=("/fake/prime-agent", "--mode", "json"),
        prime_version="0.7.0",
        paths=prime_paths(workspace),
        started_at=now,
        finished_at=now,
        elapsed_seconds=0.1,
        exit_code=exit_code,
        timed_out=timed_out,
        events=events,
        completion=completion,
        error=error,
    )


def test_maps_success_and_final_text_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    parsed = _events()
    monkeypatch.setattr(
        "aec_bench.adapters.prime_agent.run_prime_agent",
        lambda **_kwargs: _prime_run(tmp_path, events=parsed),
    )
    adapter = PrimeAgentAdapter(model_name="anthropic/requested", workspace=tmp_path)

    result = adapter.execute(AdapterRequest(instruction="Do the task", configuration={"timeout_seconds": 12}))

    assert result.adapter_name == "prime-agent"
    assert result.resolved_model == "anthropic/resolved"
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.raw_output_text == "Fallback"
    assert result.failure_kind is None
    assert result.turns_used == 1
    assert result.usage_model_calls == 1
    assert result.usage_input_tokens == 8
    assert result.configuration_record == {
        "model": "anthropic/resolved",
        "prime_version": "0.7.0",
        "event_stream_version": 3,
        "session_id": "adapter-session",
        "state_isolated": True,
        "ambient_resources_disabled": True,
    }


def test_direct_workspace_output_wins_over_final_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "output.md").write_text("Direct output\n", encoding="utf-8")
    monkeypatch.setattr(
        "aec_bench.adapters.prime_agent.run_prime_agent",
        lambda **_kwargs: _prime_run(tmp_path, events=_events(text="Do not copy me")),
    )

    result = PrimeAgentAdapter(model_name="anthropic/requested", workspace=tmp_path).execute(
        AdapterRequest(instruction="Do the task")
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.raw_output_text is None
    assert (tmp_path / "output.md").read_text(encoding="utf-8") == "Direct output\n"


@pytest.mark.parametrize(
    ("completion", "failure_kind", "timed_out"),
    [
        ("timed_out", AdapterFailureKind.TIMEOUT, True),
        ("process_failed", AdapterFailureKind.PROVIDER_ERROR, False),
        ("protocol_failed", AdapterFailureKind.PROVIDER_ERROR, False),
        ("missing_output", AdapterFailureKind.MISSING_OUTPUT, False),
    ],
)
def test_maps_failures_without_exposing_stderr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    completion: str,
    failure_kind: AdapterFailureKind,
    timed_out: bool,
) -> None:
    monkeypatch.setattr(
        "aec_bench.adapters.prime_agent.run_prime_agent",
        lambda **_kwargs: _prime_run(
            tmp_path,
            completion=completion,
            events=_events(),
            error=f"safe {completion} summary",
            exit_code=None if timed_out else 1,
            timed_out=timed_out,
        ),
    )

    result = PrimeAgentAdapter(model_name="anthropic/requested", workspace=tmp_path).execute(
        AdapterRequest(instruction="Do the task")
    )

    assert result.agent_output.status in {AgentOutputStatus.FAILED, AgentOutputStatus.EMPTY}
    assert result.failure_kind is failure_kind
    assert result.provider_error == f"safe {completion} summary"


def test_does_not_invent_usage_when_prime_does_not_report_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "aec_bench.adapters.prime_agent.run_prime_agent",
        lambda **_kwargs: _prime_run(tmp_path, events=_events(include_usage=False)),
    )

    result = PrimeAgentAdapter(model_name="anthropic/requested", workspace=tmp_path).execute(
        AdapterRequest(instruction="Do the task")
    )

    assert result.usage_model_calls is None
    assert result.usage_input_tokens is None
    assert result.usage_output_tokens is None
    assert result.usage_cache_read_tokens is None
    assert result.usage_cache_write_tokens is None
